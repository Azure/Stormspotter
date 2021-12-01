import asyncio
import logging
import re
from pathlib import Path
from typing import List
from uuid import UUID

import aiosqlite
import msgpack
from aiocypher.aioneo4j import Driver
from rich import print

from .db import Neo4jDriver
from .models import get_available_models

MODELS = get_available_models()
print(MODELS)
log = logging.getLogger("rich")


def is_uuid(value: str) -> bool:
    try:
        UUID(value)
        return True
    except:
        return False


async def process_file(file: Path) -> None:

    # Process everything but sqlite files for subscriptions here
    if model := MODELS.get(file.stem):
        async with aiosqlite.connect(file) as db:
            async with db.execute("SELECT result from results") as cursor:
                async for result in cursor:
                    obj_json = msgpack.loads(result[0])
                    try:
                        model(**obj_json)
                    except Exception as e:
                        log.error(e)
                        print(obj_json)
    # Process UUID file names (subscriptions)
    elif is_uuid(file.stem):
        async with aiosqlite.connect(file) as db:
            async with db.execute("SELECT result from results") as cursor:
                async for result in cursor:
                    obj_json = msgpack.loads(result[0])
                    if model := MODELS.get(obj_json["type"].lower()):
                        try:
                            m = model(**obj_json)
                            print(m.node())
                        except Exception as e:
                            log.error(e)
                            print(obj_json)


async def start_parsing(files: List[Path], driver: Driver):
    neo4j = await Neo4jDriver(driver)
    await neo4j.close()

    for future in asyncio.as_completed(map(process_file, files)):
        result = await future
