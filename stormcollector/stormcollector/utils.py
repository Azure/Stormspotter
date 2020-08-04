from pathlib import Path
import aiosqlite


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
        await db.execute_insert("INSERT INTO results (result) VALUES (?)", (str(res),))
        await db.commit()
