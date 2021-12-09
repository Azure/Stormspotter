import asyncio
import functools
import logging
from pathlib import Path
from typing import List
from uuid import UUID

import aiosqlite
import msgpack
from aiocypher.aioneo4j import Driver
from rich import print
from rich.status import Status

from .db import Neo4jDriver
from .models import (
    AVAILABLE_MODELS,
    AADObject,
    ARMResource,
    DynamicObject,
    Relationship,
)

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
    if model := AVAILABLE_MODELS.get(file.stem) or file.stem == "rbac":
        async with aiosqlite.connect(file) as db:
            log.info(f"Reading {file.absolute()}")
            async with db.execute("SELECT result from results") as cursor:
                async for result in cursor:
                    obj_json = msgpack.loads(result[0])
                    try:
                        # If we're not processing RBAC we can just pass the object
                        # But RBAC needs to have its fields match the Relationship base
                        if not file.stem == "rbac":
                            await neo4j.insert(model(**obj_json))
                        else:
                            obj = DynamicObject.from_dict(obj_json)
                            await neo4j.insert(
                                Relationship(
                                    source=obj.principal_id,
                                    source_label=AADObject._labels()[0],
                                    target=obj.scope,
                                    target_label=ARMResource._labels()[0],
                                    relation=obj.roleName,
                                    properties={
                                        "name": obj.name,
                                        "roleName": obj.roleName,
                                        "roleType": obj.roleType,
                                        "description": obj.roleDescription,
                                    }
                                    | obj.permissions[0].__dict__,
                                )
                            )
                    except Exception as e:
                        log.error(e, exc_info=True)
                        log.error(obj_json)

    # Process UUID file names (subscriptions)
    elif is_uuid(file.stem):
        async with aiosqlite.connect(file) as db:
            log.info(f"Reading {file.absolute()}")
            async with db.execute("SELECT result from results") as cursor:
                async for result in cursor:
                    obj_json = msgpack.loads(result[0])
                    if model := AVAILABLE_MODELS.get(obj_json["type"].lower()):
                        try:
                            await neo4j.insert(model(**obj_json))
                        except Exception as e:
                            log.error(e, exc_info=True)
                            log.error(obj_json)
                    else:
                        log.warning(
                            f"No model available for {obj_json['type'].lower()}"
                        )
                        if logging.DEBUG >= log.level:
                            print(obj_json)
    log.info(f"Finished reading {file.absolute()}")


async def start_parsing(files: List[Path], driver: Driver):
    neo4j = await Neo4jDriver(driver)

    process_partial = functools.partial(process_file, neo4j)
    for future in asyncio.as_completed(map(process_partial, files)):
        await future

    with Status(f"Waiting for input queue to finish.", spinner="aesthetic"):
        await neo4j.close()
