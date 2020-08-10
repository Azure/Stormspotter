import asyncio
from pathlib import Path
from loguru import logger

import aiofiles
import aiosqlite
import orjson
import json


async def sqlite_writer(output, res):
    if not Path(output).exists():
        async with aiosqlite.connect(output) as db:
            await db.execute(
                """CREATE TABLE IF NOT EXISTS results 
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                result json)"""
            )
            await db.commit()

    async with aiosqlite.connect(output) as db:
        await db.execute_insert(
            "INSERT INTO results (result) VALUES (?)", (orjson.dumps(res),)
        )
        await db.commit()


async def _do_json_convert(file: Path):
    logger.info(f"Converting {file.name}")
    async with aiosqlite.connect(file) as db:
        async with db.execute("Select result from results") as cursor:
            rows = await cursor.fetchall()
            merged = [orjson.loads(row[0]) for row in rows]

            async with aiofiles.open(
                str(file).replace("sqlite", "json"), "wb"
            ) as output:
                await output.write(orjson.dumps(merged))
    logger.info(f"Finished converting {file.name}")
    Path.unlink(file)


async def json_convert(folder: Path):
    sqlites = folder.glob("*.sqlite")
    await asyncio.gather(*[_do_json_convert(file) for file in sqlites])
