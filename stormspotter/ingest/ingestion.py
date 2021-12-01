import asyncio
import msgpack
from pathlib import Path
from rich import print
from typing import List

import aiosqlite
from aiocypher.aioneo4j import Driver

from .db import Neo4jDriver
from .models import get_available_models

MODELS = get_available_models()


async def process_file(file: Path) -> None:
    if model := MODELS.get(file.stem):
        async with aiosqlite.connect(file) as db:
            async with db.execute("SELECT result from results") as cursor:
                async for result in cursor:
                    obj_json = msgpack.loads(result[0])

                    try:
                        print(model(**obj_json))
                    except Exception as e:
                        print(e)
                        print(obj_json)


async def start_parsing(files: List[Path], driver: Driver):
    neo4j = await Neo4jDriver(driver)
    print(await neo4j.stats())
    await neo4j.close()

    for future in asyncio.as_completed(map(process_file, files)):
        result = await future
