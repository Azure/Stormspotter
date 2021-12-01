from aiocypher.aioneo4j.driver import Driver
from neo4j.exceptions import AuthError

from .cypher import *


class Neo4jDriver:
    def __init__(self, driver: Driver) -> None:
        self.driver = driver

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
        await self.driver.close()

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
