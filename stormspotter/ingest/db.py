import asyncio
import logging

from aiocypher.aioneo4j.driver import Driver
from neo4j.exceptions import AuthError, ServiceUnavailable
from rich import inspect, print
from asyncio import Queue
from stormspotter.ingest.models import Node, Relationship
from contextlib import suppress
from .models import AVAILABLE_MODEL_LABELS

log = logging.getLogger("rich")

CREATE_INDEX_CYPHER_LIST = [
    f"CREATE INDEX IF NOT EXISTS FOR (n:{label}) ON (n.id)"
    for label in AVAILABLE_MODEL_LABELS
]

BASE_IMPORT_CYPHER = """MERGE (obj:{label}{{id:'{id}'}}) {set_statement}"""


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
                        for create_index in CREATE_INDEX_CYPHER_LIST:
                            async with session.begin_transaction() as tx:
                                await tx.run(create_index)
            except AuthError as e:
                raise e

            return self

        return await_().__await__()

    async def close(self):
        logging.info("Waiting for input queue to finish")
        await self.queue.join()
        await self.driver.close()

    async def _process_queue(self):
        while True:
            async with self.driver.session(database="neo4j") as session:
                statement = await self.queue.get()
                log.debug(statement)

                async with session.begin_transaction() as tx:
                    await tx.run(statement)

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
            return (
                f"'{self.sanitize_string(x)}'" if (isinstance(x, str) or not x) else x
            )

        if isinstance(item, Node):
            set_statements_parts = [
                f"obj.{key} = {check_type(value)}"
                for key, value in item.to_neo().items()
                if key not in ["_relationships", "id"]
            ]
            set_statements_parts.extend([f"obj:{secondary_label}"])
        else:
            set_statements_parts = [
                f"obj.{key} = {check_type(value)}"
                for key, value in item.properties.items()
                if key != "_relationships"
            ]

        return f"SET {','.join(set_statements_parts)}"

    async def insert(self, item: Node | Relationship):
        """Adds Node or Relationship to Neo4j"""

        insert_statement = ""

        if isinstance(item, Node):
            primary_label, secondary_label = item._labels()
            set_statement = self.generate_set_statement(item, secondary_label)
            insert_statement = BASE_IMPORT_CYPHER.format(
                label=primary_label, id=item.id, set_statement=set_statement
            )
            log.debug(insert_statement + "\n")

        await self.queue.put(insert_statement)

        # try:
        #     self.query(statement)
        # except ConnectionResetError as e:
        #     logger.error("exception: ", e)
        #     logger.warning("trying to reconnect to bolt server")
        #     self.get_graph_driver(self.server, self.user, self.password)

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
