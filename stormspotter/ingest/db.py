import asyncio
from enum import Enum
import logging
from asyncio import Queue

from aiocypher.aioneo4j.driver import Driver
import neo4j
from neo4j.exceptions import AuthError, CypherSyntaxError
from rich import inspect, print

from stormspotter.ingest.models import Node, Relationship

from .models import AVAILABLE_MODEL_LABELS, DynamicObject

log = logging.getLogger("rich")


CREATE_CONSTRAINTS_CYPHER_LIST = [
    f"CREATE CONSTRAINT IF NOT EXISTS ON (n:{label}) ASSERT n.id IS UNIQUE"
    for label in AVAILABLE_MODEL_LABELS
]

BASE_MERGE_CYPHER = """MERGE (obj:{label}{{id:'{id}'}}) {set_statement}"""

BASE_REL_CYPHER = """MERGE (to:{target_label}{{id:'{target}'}}) 
MERGE (from:{source_label}{{id:'{source}'}})  
MERGE (from)-[obj:{relation}]->(to) 
{set_statement}"""


class Neo4jDriver:
    def __init__(self, driver: Driver) -> None:
        self.driver = driver
        self.queue = Queue()
        self.queue_task = asyncio.create_task(self._process_queue())

    def __await__(self):
        """Method defined to allow for async class creation"""

        async def await_():

            # Try to create the indexes.
            # This also counts as user/password validation
            try:
                async with self.driver:
                    async with self.driver.session(database="neo4j") as session:
                        for create_constraint in CREATE_CONSTRAINTS_CYPHER_LIST:
                            async with session.begin_transaction() as tx:
                                await tx.run(create_constraint)
            except AuthError as e:
                raise e

            return self

        return await_().__await__()

    async def close(self):
        await self.queue.join()
        await self.driver.close()

    async def _process_queue(self):
        while True:
            async with self.driver.session(database="neo4j") as session:
                statement = await self.queue.get()
                log.debug(statement)

                try:
                    async with session.begin_transaction() as tx:
                        await tx.run(statement)
                except CypherSyntaxError as e:
                    log.error(e)

                self.queue.task_done()

    def sanitize_string(self, value: str):
        """Sanitize string values"""
        return value.replace("\\", "\\\\").replace("'", "") if value else value

    def generate_set_statement(
        self, item: Node | Relationship, secondary_label: str = None
    ):
        """Generates set statement for item"""

        def check_type(x):
            """Check type to determine if value needs to be sanitized"""
            if isinstance(x, str) or not x:
                return f"'{self.sanitize_string(x)}'"
            elif isinstance(x, DynamicObject):

                # Flatten the list with magic
                d = x.__dict__
                return [item for k in d for item in (k, d[k])]
            return x

        set_statements_parts = []

        if isinstance(item, Node):
            set_statements_parts = [
                f"obj.{key} = {check_type(value)}"
                for key, value in item.toNeo().items()
                if key not in ["_relationships", "id"]
            ]
            set_statements_parts.extend([f"obj:{secondary_label}"])
        elif isinstance(item, Relationship):
            if item.properties:
                set_statements_parts = [
                    f"obj.{key} = {check_type(value)}"
                    for key, value in item.properties.items()
                ]

        return f"SET {','.join(set_statements_parts)}" if set_statements_parts else ""

    async def insert_relationship(self, relationship: Relationship) -> str:
        set_statement = self.generate_set_statement(relationship)
        log.debug(set_statement)

        # Relation can be passed as either str or Enum so need to get the correct value
        relation = (
            relationship.relation.value
            if isinstance(relationship.relation, Enum)
            else relationship.relation
        )

        insert_statement = BASE_REL_CYPHER.format(
            target_label=relationship.target_label,
            target=relationship.target,
            source_label=relationship.source_label,
            source=relationship.source,
            relation=relation,
            set_statement=set_statement,
        )
        log.debug(insert_statement + "\n")
        await self.queue.put(insert_statement)

    async def insert(self, item: Node | Relationship):
        """Adds Node or Relationship to Neo4j"""

        insert_statement = ""
        if isinstance(item, Node):
            primary_label, secondary_label = item._labels()
            set_statement = self.generate_set_statement(item, secondary_label)
            insert_statement = BASE_MERGE_CYPHER.format(
                label=primary_label, id=item.id, set_statement=set_statement
            )
            log.debug(insert_statement + "\n")
            await self.queue.put(insert_statement)

            # Add relationships and Nodes associated in relationships
            for relationship in item._relationships:
                await self.insert(relationship)
        elif isinstance(item, Relationship):
            await self.insert_relationship(item)

    async def query(self, query: str):
        """Runs a query asynchronously"""
        async with self.driver.session(database="neo4j") as session:
            async with session.begin_transaction() as tx:
                return await tx.run(query).data()

    async def stats(self):
        """Returns the number of nodes in the database"""
        return await self.query(
            "MATCH (n) RETURN count(labels(n)) AS count, labels(n) AS labels"
        )
