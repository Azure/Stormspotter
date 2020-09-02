""" Sets up neo4j database and appropriate cypher query commands """
import inspect
import sys
import threading

import loguru
import neo4j
from loguru import logger
from neo4j import GraphDatabase
from neo4j.exceptions import AuthError, ClientError

from . import resources as labels


class Neo4j:
    """
    Instantiates the graph database and sets up base statements and cypher queries
    """

    server = None
    user = None
    password = None
    driver = None
    base_import_cypher = """MERGE (obj:{label}{{id:'{id}'}}) SET {set_statement}"""
    base_merge_cypher = """
    {to_merge_type} (to:{to_label}{{id:'{to_id}'}}) 
    MERGE (from:{from_label}{{id:'{from_id}'}})  
    MERGE (from)-[obj:{relationship_type}{unique_rel_clause}]->(to) {set_statement}"""

    def __init__(self, server, user=None, password=None):
        self.server = server
        logger.info(f"Connecting to {self.server}")
        self.user = user
        self.password = password
        self.get_graph_driver(self.server, self.user, self.password)
        self.create_indexes()
        self.updateKeys()
        self.updateLabels()

    def updateLabels(self):
        result = self.query("MATCH (n) RETURN DISTINCT labels(n) as labels", True)
        self.labels = sorted(set(lbl for lbls in result.value() for lbl in lbls))

    def updateKeys(self):
        result = self.query(
            """MATCH (n) 
                            WITH labels(n) AS labels, KEYS(n) AS keys
                            UNWIND labels as label
                            UNWIND keys as key
                            RETURN DISTINCT label, COLLECT(distinct key) AS props""",
            True,
        )
        self.keys = result.data()

    def get_graph_driver(self, url, username, password) -> GraphDatabase:
        """ sets up graph client """
        try:
            auth = None
            if username and password:
                auth = (username, password)
            self.driver = GraphDatabase.driver(url, auth=auth, encrypted=False)
        except AuthError:
            logger.error("Could not authenticate to Neo4j database server")
        except Exception:
            logger.error("[=] Failed to create graph client")
            raise

    def sanitize_string(self, input_str):
        """ clean objects that come in as type string """
        if input_str:
            return input_str.replace("\\", "\\\\").replace("'", "")
        return input_str

    def generate_set_statement(self, asset, extra_labels=None):
        """ parses resource for type and creates appropriate index via id"""

        def f(x):
            return (
                f"'{self.sanitize_string(x)}'" if (isinstance(x, str) or not x) else x
            )

        set_statements_parts = [
            f"obj.{key} = {f(value)}" for key, value in asset.items() if not key == "id"
        ]
        if extra_labels:
            set_statements_parts.extend([f"obj :{value}" for value in extra_labels])
        return ", ".join(set_statements_parts)

    def insert_asset(self, asset, label, asset_id, extra_labels=None):
        """ inserts asset into graph """
        set_statement = self.generate_set_statement(asset, extra_labels)
        statement = self.base_import_cypher.format(
            label=label, id=asset_id.lower(), set_statement=set_statement
        )
        try:
            self.query(statement)
        except ConnectionResetError as e:
            logger.error("exception: ", e)
            logger.warning("trying to reconnect to bolt server")
            self.get_graph_driver(self.server, self.user, self.password)

    def create_indexes(self):
        """ create indexes for faster lookup """
        for label, value in inspect.getmembers(labels):
            if "NODE_LABEL" in label:
                statement = "CREATE INDEX ON : " + value + "(id)"
                try:
                    self.query(statement)
                except ClientError:
                    pass

    def create_relationship(
        self,
        from_id,
        from_label,
        to_id,
        to_label,
        relationship_type,
        relationship_properties=None,
        relationship_unique_property=None,
        relationship_unique_value=None,
        to_find_type="MERGE",
    ):
        """ create base cypher statement for creating relationships in graph """
        set_statement = ""
        if relationship_properties:
            set_statement = "SET {}".format(
                self.generate_set_statement(relationship_properties)
            )
        unique_rel_clause = ""
        if relationship_unique_property and relationship_unique_value:
            unique_rel_clause = (
                "{"
                + f"{relationship_unique_property}:'{str(relationship_unique_value)}'"
                + "}"
            )

        statement = self.base_merge_cypher.format(
            from_label=from_label,
            from_id=from_id.lower(),
            to_merge_type=to_find_type,
            to_label=to_label,
            to_id=to_id.lower(),
            relationship_type=relationship_type,
            unique_rel_clause=unique_rel_clause,
            set_statement=set_statement,
        )
        self.query(statement)

    write_lock = threading.Lock()

    def dbSummary(self):
        countQuery = self.query(
            "MATCH (n) RETURN count(labels(n)) AS count, labels(n) AS labels", True
        )
        return countQuery

    def deleteDB(self):
        self.query("MATCH (n) DETACH DELETE n")

    def query(self, statement, requested=False):
        """ execute a query into the graph """
        self.write_lock.acquire()
        result = ""
        try:
            with self.driver.session() as session:
                result = session.run(statement)
        except ClientError as e:
            if str(e.message).startswith("An equivalent index"):
                raise
            logger.error(e)
            logger.error("[=] Failed to insert new document. Trying again.")
            self.get_graph_driver(self.server, self.user, self.password)
            self.session.run(statement)

        finally:
            self.write_lock.release()
            if result and requested:
                return result

    def __del__(self):
        self.shutdown()

    def shutdown(self):
        """ close session """
        if self.driver:
            logger.info("Closing the neo4j session")
            self.driver.close()
