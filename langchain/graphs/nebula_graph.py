from typing import Any, Dict, List
from string import Template
import logging

from nebula3.Exception import IOErrorException

rel_query = Template(
    """
MATCH ()-[e:`$edge_type`]->()
  WITH e limit 1
MATCH (m)-[:`$edge_type`]->(n) WHERE id(m) == src(e) AND id(n) == dst(e)
RETURN "(:" + tags(m)[0] + ")-[:`$edge_type`]->(:" + tags(n)[0] + ")" AS rels
"""
)

RETRY_TIMES = 3


class NebulaGraph:
    """NebulaGraph wrapper for graph operations
    NebulaGraph inherits methods from Neo4jGraph to bring ease to the user space.
    """

    def __init__(
        self,
        space,
        username: str = "root",
        password: str = "nebula",
        address: str = "127.0.0.1",
        port: int = 9669,
        session_pool_size: int = 30,
    ) -> None:
        """Create a new NebulaGraph wrapper instance."""
        try:
            import nebula3
        except ImportError:
            raise ValueError(
                "Please install NebulaGraph Python client first: "
                "`pip install nebula3-python`"
            )

        self.username = username
        self.password = password
        self.address = address
        self.port = port
        self.space = space
        self.session_pool_size = session_pool_size

        self.session_pool = self._get_session_pool()
        self.schema = ""
        # Set schema
        try:
            self.refresh_schema()
        except Exception as e:
            raise ValueError(f"Could not refresh schema. " f"Error: {e}")

    def _get_session_pool(self):
        assert all(
            [self.username, self.password, self.address, self.port, self.space]
        ), (
            "Please provide all of the following parameters: "
            "username, password, address, port, space"
        )

        from nebula3.gclient.net.SessionPool import SessionPool
        from nebula3.Config import SessionPoolConfig
        from nebula3.Exception import AuthFailedException, InValidHostname

        config = SessionPoolConfig()
        config.max_size = self.session_pool_size

        try:
            session_pool = SessionPool(
                self.username,
                self.password,
                self.space,
                [(self.address, self.port)],
            )
        except InValidHostname:
            raise ValueError(
                "Could not connect to NebulaGraph database. "
                "Please ensure that the address and port are correct"
            )

        try:
            session_pool.init(config)
        except AuthFailedException:
            raise ValueError(
                "Could not connect to NebulaGraph database. "
                "Please ensure that the username and password are correct"
            )
        except RuntimeError as e:
            raise ValueError("Error initializing session pool. " f"Error: {e}")

        return session_pool

    def __del__(self):
        try:
            self.session_pool.close()
        except Exception as e:
            logging.warning(f"Could not close session pool. Error: {e}")

    @property
    def get_schema(self) -> str:
        """Returns the schema of the NebulaGraph database"""
        return self.schema

    def query(self, query: str, params: dict = {}, retry: int = 0) -> Any:
        """Query NebulaGraph database."""
        from nebula3.Exception import NoValidSessionException
        from nebula3.fbthrift.transport.TTransport import TTransportException
        try:
            return self.session_pool.execute_parameter(query, params)
        except NoValidSessionException:
            logging.warning(
                f"No valid session found in session pool. "
                f"Please consider increasing the session pool size. "
                f"Current size: {self.session_pool_size}"
            )
            raise ValueError(
                f"No valid session found in session pool. "
                f"Please consider increasing the session pool size. "
                f"Current size: {self.session_pool_size}"
            )

        except RuntimeError as e:
            if retry < RETRY_TIMES:
                retry += 1
                logging.warning(
                    f"Error executing query to NebulaGraph. "
                    f"Retrying ({retry}/{RETRY_TIMES})...\n"
                    f"query: {query} \n"
                    f"Error: {e}"
                )
                return self.query(query, params, retry)
            else:
                raise ValueError(
                    f"Error executing query to NebulaGraph. " f"Error: {e}"
                )

        except (TTransportException, IOErrorException) as e:
            # connection issue, try to recreate session pool
            if retry < RETRY_TIMES:
                retry += 1
                logging.warning(
                    f"Connection issue with NebulaGraph. "
                    f"Retrying ({retry}/{RETRY_TIMES})...\n to recreate session pool"
                )
                self.session_pool = self._get_session_pool()
                return self.query(query, params, retry)

    def refresh_schema(self) -> None:
        """
        Refreshes the NebulaGraph schema information.
        """
        tags_schema, edge_types_schema, relationships = [], [], []
        for tag in self.query("SHOW TAGS").column_values("Name"):
            tag_name = tag.cast()
            tag_schema = {"tag": tag_name, "properties": []}
            r = self.query(f"DESCRIBE TAG `{tag_name}`")
            props, types = r.column_values("Field"), r.column_values("Type")
            for i in range(r.row_size()):
                tag_schema["properties"].append(
                    {"name": props[i].cast(), "type": types[i].cast()}
                )
            tags_schema.append(tag_schema)
        for edge_type in self.query("SHOW EDGES").column_values("Name"):
            edge_type_name = edge_type.cast()
            edge_schema = {"edge": edge_type_name, "properties": []}
            r = self.query(f"DESCRIBE EDGE `{edge_type_name}`")
            props, types = r.column_values("Field"), r.column_values("Type")
            for i in range(r.row_size()):
                edge_schema["properties"].append(
                    {"name": props[i].cast(), "type": types[i].cast()}
                )
            edge_types_schema.append(edge_schema)

            # build relationships types
            r = self.query(
                rel_query.substitute(edge_type=edge_type_name)
            ).column_values("rels")
            if len(r) > 0:
                relationships.append(r[0].cast())

        self.schema = (
            f"Node properties: {tags_schema}\n"
            f"Edge properties: {edge_types_schema}\n"
            f"Relationships: {relationships}\n"
        )
