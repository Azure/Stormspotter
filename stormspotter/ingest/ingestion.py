import asyncio
import functools
import logging
import re
from pathlib import Path
from sys import exc_info
from typing import List
from uuid import UUID

import aiosqlite
import msgpack
from aiocypher.aioneo4j import Driver
from rich import print

from .db import Neo4jDriver
from .models import AVAILABLE_MODELS

log = logging.getLogger("rich")
log.debug(AVAILABLE_MODELS)


def is_uuid(value: str) -> bool:
    try:
        UUID(value)
        return True
    except:
        return False


async def process_file(neo4j: Neo4jDriver, file: Path) -> None:

    # Process everything but sqlite files for subscriptions here
    if model := AVAILABLE_MODELS.get(file.stem):
        async with aiosqlite.connect(file) as db:
            log.info(f"Parsing {file.absolute()}")
            async with db.execute("SELECT result from results") as cursor:
                async for result in cursor:
                    obj_json = msgpack.loads(result[0])
                    try:
                        await neo4j.insert(model(**obj_json))
                    except Exception as e:
                        log.error(e, exc_info=True)
                        print(obj_json)
    # Process UUID file names (subscriptions)
    elif is_uuid(file.stem):
        async with aiosqlite.connect(file) as db:
            log.info(f"Parsing {file.absolute()}")
            async with db.execute("SELECT result from results") as cursor:
                async for result in cursor:
                    obj_json = msgpack.loads(result[0])
                    if model := AVAILABLE_MODELS.get(obj_json["type"].lower()):
                        try:
                            await neo4j.insert(model(**obj_json))
                        except Exception as e:
                            log.error(e, exc_info=True)
                            print(obj_json)
    log.info(f"Finished parsing {file.absolute()}")


async def start_parsing(files: List[Path], driver: Driver):
    neo4j = await Neo4jDriver(driver)

    process_partial = functools.partial(process_file, neo4j)
    for future in asyncio.as_completed(map(process_partial, files)):
        await future

    await neo4j.close()
