from __future__ import annotations

import csv
import json
import logging
import random
import time
import uuid
import warnings
from io import StringIO
from typing import (
    Any,
    Iterable,
    List,
    Optional,
    Tuple,
    Type,
)

from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore

from langchain_community.docstore.document import Document

logger = logging.getLogger(__name__)


class Yellowbrick(VectorStore):
    """Yellowbrick as a vector database.
    Example:
        .. code-block:: python
            from langchain_community.vectorstores import Yellowbrick
            from langchain_community.embeddings.openai import OpenAIEmbeddings
            ...
    """

    LSH_INDEX_TABLE: str = "_lsh_index"
    LSH_HYPERPLANE_TABLE: str = "_lsh_hyperplane"
    CONTENT_TABLE: str = "_content"

    def __init__(
        self,
        embedding: Embeddings,
        connection_string: str,
        table: str,
        use_lsh: Optional[bool] = False,
        idle_threshold_seconds: Optional[int] = 300,
        seed: Optional[float] = 0.42,
        drop: Optional[bool] = False,
    ) -> None:
        """Initialize with yellowbrick client.
        Args:
            embedding: Embedding operator
            connection_string: Format 'postgres://username:password@host:port/database'
            table: Table used to store / retrieve embeddings from
        """

        import psycopg2
        from psycopg2 import extras

        extras.register_uuid()

        if not isinstance(embedding, Embeddings):
            warnings.warn("embeddings input must be Embeddings object.")

        self.connection_string = connection_string
        self._table = table
        self._embedding = embedding
        self._max_embedding_len = None
        self.idle_threshold_seconds = idle_threshold_seconds
        self._connection = psycopg2.connect(self.connection_string)
        self.last_used_time = time.time()
        self._check_database_utf8()

        if drop:
            self._drop_table(self._table)
            self._drop_table(self._table + self.CONTENT_TABLE)
            self._drop_lsh_index_tables()

        self._create_table()

        self._use_lsh = use_lsh
        self._hamming_distance = 0

        if seed is not None:
            random.seed(seed)
        self._seed = seed

    def __del__(self) -> None:
        if self._connection:
            self._connection.close()

    @property
    def use_lsh(self) -> bool:
        return self._use_lsh

    @use_lsh.setter
    def use_lsh(self, use_lsh: bool) -> None:
        self._use_lsh = use_lsh
        if self._use_lsh:
            self._create_lsh_index_tables()

    @property
    def hamming_distance(self) -> bool:
        return self._hamming_distance

    @hamming_distance.setter
    def hamming_distance(self, hamming_distance: int) -> None:
        self._hamming_distance = hamming_distance

    def _get_connection(self):
        import psycopg2
        from psycopg2 import Error, OperationalError

        current_time = time.time()
        if self._connection.closed:
            self._connection = psycopg2.connect(self.connection_string)
            self.last_used_time = current_time
        elif (current_time - self.last_used_time) > self.idle_threshold_seconds:
            try:
                with self._connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
            except (OperationalError, Error):
                self._connection = psycopg2.connect(self.connection_string)
            self.last_used_time = current_time

        return self._connection

    def _create_table(self) -> None:
        """
        Helper function: create table if not exists
        """
        from psycopg2 import sql

        cursor = self._get_connection().cursor()
        cursor.execute(
            sql.SQL(
                """
                CREATE TABLE IF NOT EXISTS {t} (
                doc_id UUID NOT NULL,
                text VARCHAR(60000) NOT NULL,
                metadata VARCHAR(1024) NOT NULL,
                CONSTRAINT {c} PRIMARY KEY (doc_id))
                DISTRIBUTE ON (doc_id) SORT ON (doc_id)
            """
            ).format(
                t=sql.Identifier(self._table + self.CONTENT_TABLE),
                c=sql.Identifier(self._table + self.CONTENT_TABLE + "_pk_doc_id"),
            )
        )
        cursor.execute(
            sql.SQL(
                """
                CREATE TABLE IF NOT EXISTS {t1} (
                doc_id UUID NOT NULL,
                embedding_id SMALLINT NOT NULL,
                embedding FLOAT NOT NULL,
                CONSTRAINT {c1} PRIMARY KEY (doc_id, embedding_id),
                CONSTRAINT {c2} FOREIGN KEY (doc_id) REFERENCES {t2}(doc_id))
                DISTRIBUTE ON (doc_id) SORT ON (doc_id)
            """
            ).format(
                t1=sql.Identifier(self._table),
                t2=sql.Identifier(self._table + self.CONTENT_TABLE),
                c1=sql.Identifier(
                    self._table + self.CONTENT_TABLE + "_pk_doc_id_embedding_id"
                ),
                c2=sql.Identifier(self._table + self.CONTENT_TABLE + "_fk_doc_id"),
            )
        )
        self._get_connection().commit()
        cursor.close()

    def _drop_table(self, table: str) -> None:
        """
        Helper function: Drop data
        """
        from psycopg2 import sql

        cursor = self._get_connection().cursor()
        cursor.execute(
            sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(sql.Identifier(table))
        )
        self._get_connection().commit()
        cursor.close()

    def _check_database_utf8(self) -> bool:
        """
        Helper function: Test the database is UTF-8 encoded
        """
        cursor = self._get_connection().cursor()
        query = """
            SELECT pg_encoding_to_char(encoding)
            FROM pg_database
            WHERE datname = current_database();
        """
        cursor.execute(query)
        encoding = cursor.fetchone()[0]
        cursor.close()
        if encoding.lower() == "utf8" or encoding.lower() == "utf-8":
            return True
        else:
            raise Exception(
                f"Database \
           '{self.connection_string.split('/')[-1]}' encoding is not UTF-8"
            )

    def add_texts(
        self,
        texts: Iterable[str],
        metadatas: Optional[List[dict]] = None,
        **kwargs: Any,
    ) -> List[str]:
        batch_size = 10000

        texts = list(texts)
        embeddings = self._embedding.embed_documents(list(texts))
        results = []
        if not metadatas:
            metadatas = [{} for _ in texts]

        conn = self._get_connection()
        cursor = conn.cursor()

        content_io = StringIO()
        embeddings_io = StringIO()
        content_writer = csv.writer(
            content_io, delimiter="\t", quotechar='"', quoting=csv.QUOTE_MINIMAL
        )
        embeddings_writer = csv.writer(
            embeddings_io, delimiter="\t", quotechar='"', quoting=csv.QUOTE_MINIMAL
        )
        current_batch_size = 0

        for i, text in enumerate(texts):
            doc_uuid = str(uuid.uuid4())
            results.append(doc_uuid)

            content_writer.writerow([doc_uuid, text, json.dumps(metadatas[i])])

            for embedding_id, embedding in enumerate(embeddings[i]):
                embeddings_writer.writerow([doc_uuid, embedding_id, embedding])

            current_batch_size += 1

            if current_batch_size >= batch_size:
                self._copy_to_db(cursor, content_io, embeddings_io, self._table)

                content_io.seek(0)
                content_io.truncate(0)
                embeddings_io.seek(0)
                embeddings_io.truncate(0)
                current_batch_size = 0

        if current_batch_size > 0:
            self._copy_to_db(cursor, content_io, embeddings_io, self._table)

        conn.commit()
        cursor.close()

        if self.use_lsh:
            self.update_lsh_index(doc_uuid)

    def _copy_to_db(self, cursor, content_io, embeddings_io, table_name):
        content_io.seek(0)
        embeddings_io.seek(0)
        cursor.copy_expert(
            f"COPY {table_name + self.CONTENT_TABLE} (doc_id, text, metadata) \
                FROM STDIN WITH (FORMAT CSV, DELIMITER E'\\t', QUOTE '\"')",
            content_io,
        )
        cursor.copy_expert(
            f"COPY {table_name} (doc_id, embedding_id, embedding) \
                FROM STDIN WITH (FORMAT CSV, DELIMITER E'\\t', QUOTE '\"')",
            embeddings_io,
        )

    @classmethod
    def from_texts(
        cls: Type[Yellowbrick],
        texts: List[str],
        embedding: Embeddings,
        metadatas: Optional[List[dict]] = None,
        connection_string: str = "",
        table: str = "langchain",
        use_lsh: Optional[bool] = False,
        drop: Optional[bool] = False,
        **kwargs: Any,
    ) -> Yellowbrick:
        """Add texts to the vectorstore index.
        Args:
            texts: Iterable of strings to add to the vectorstore.
            metadatas: Optional list of metadatas associated with the texts.
            connection_string: URI to Yellowbrick instance
            embedding: Embedding function
            table: table to store embeddings
            kwargs: vectorstore specific parameters
        """
        if connection_string is None:
            raise ValueError("connection_string must be provided")
        vss = cls(
            embedding=embedding,
            connection_string=connection_string,
            table=table,
            use_lsh=use_lsh,
            drop=drop,
        )
        vss.add_texts(texts=texts, metadatas=metadatas)
        return vss

    def _generate_vector_uuid(self, vector: List[float]) -> uuid:
        import hashlib

        vector_str = ",".join(map(str, vector))
        hash_object = hashlib.sha1(vector_str.encode())
        hash_digest = hash_object.digest()
        vector_uuid = uuid.UUID(bytes=hash_digest[:16])
        return vector_uuid

    def similarity_search_with_score_by_vector(
        self, embedding: List[float], k: int = 4, **kwargs: Any
    ) -> List[Tuple[Document, float]]:
        """Perform a similarity search with Yellowbrick with vector

        Args:
            embedding (List[float]): query embedding
            k (int, optional): Top K neighbors to retrieve. Defaults to 4.

            NOTE: Please do not let end-user fill this and always be aware
                  of SQL injection.

        Returns:
            List[Document, float]: List of Documents and scores
        """
        from psycopg2 import sql
        from psycopg2.extras import execute_values

        cursor = self._get_connection().cursor()

        tmp_embeddings_table = "tmp_" + self._table
        tmp_doc_id = self._generate_vector_uuid(embedding)
        create_table_query = sql.SQL(
            """ 
            CREATE TEMPORARY TABLE {} (
            doc_id UUID,
            embedding_id SMALLINT,
            embedding FLOAT)
            DISTRIBUTE REPLICATE
        """
        ).format(sql.Identifier(tmp_embeddings_table))
        cursor.execute(create_table_query)

        data_input = [
            (str(tmp_doc_id), embedding_id, embedding_value)
            for embedding_id, embedding_value in enumerate(embedding)
        ]

        insert_query = sql.SQL(
            "INSERT INTO {table} (doc_id, embedding_id, embedding) VALUES %s"
        ).format(table=sql.Identifier(tmp_embeddings_table))
        execute_values(cursor, insert_query, data_input)
        self._get_connection().commit()

        if self._use_lsh:
            input_hash_table = self._table + "_tmp_hash"
            self._generate_lsh_hashes(
                embedding_table=tmp_embeddings_table, target_hash_table=input_hash_table
            )
            sql_query = sql.SQL(
                """
                WITH index_docs AS (
                SELECT
                    t1.doc_id,
                    SUM(ABS(t1.hash-t2.hash)) as hamming_distance
                FROM
                    {lsh_index} t1
                INNER JOIN
                    {input_hash_table} t2
                ON t1.hash_index = t2.hash_index
                GROUP BY t1.doc_id
                HAVING hamming_distance <= {hamming_distance}
                )
                SELECT
                    text,
                    metadata,
                    SUM(v1.embedding * v2.embedding) /
                    (SQRT(SUM(v1.embedding * v1.embedding)) *
                    SQRT(SUM(v2.embedding * v2.embedding))) AS score
                FROM
                    {v1} v1
                INNER JOIN
                    {v2} v2
                ON v1.embedding_id = v2.embedding_id
                INNER JOIN
                    {v3} v3
                ON v2.doc_id = v3.doc_id
                INNER JOIN
                    index_docs v4
                ON v2.doc_id = v4.doc_id
                GROUP BY v3.doc_id, v3.text, v3.metadata
                ORDER BY score DESC
                LIMIT %s
            """
            ).format(
                v1=sql.Identifier(tmp_embeddings_table),
                v2=sql.Identifier(self._table),
                v3=sql.Identifier(self._table + self.CONTENT_TABLE),
                lsh_index=sql.Identifier(self._table + self.LSH_INDEX_TABLE),
                input_hash_table=sql.Identifier(input_hash_table),
                hamming_distance=sql.Literal(self._hamming_distance),
            )
            cursor.execute(
                sql_query,
                (k,),
            )
            self._drop_table(input_hash_table)
        else:
            sql_query = sql.SQL(
                """
                SELECT 
                    text,
                    metadata,
                    score
                FROM
                    (SELECT
                        v2.doc_id doc_id,
                        SUM(v1.embedding * v2.embedding) /
                        (SQRT(SUM(v1.embedding * v1.embedding)) *
                        SQRT(SUM(v2.embedding * v2.embedding))) AS score
                    FROM
                        {v1} v1
                    INNER JOIN
                        {v2} v2
                    ON v1.embedding_id = v2.embedding_id
                    GROUP BY v2.doc_id
                    ORDER BY score DESC LIMIT %s
                    ) v4
                INNER JOIN
                    {v3} v3
                ON v4.doc_id = v3.doc_id
                ORDER BY score DESC
            """
            ).format(
                v1=sql.Identifier(tmp_embeddings_table),
                v2=sql.Identifier(self._table),
                v3=sql.Identifier(self._table + self.CONTENT_TABLE),
            )
            cursor.execute(sql_query, (k,))

        self._drop_table(tmp_embeddings_table)

        results = cursor.fetchall()

        documents: List[Tuple[Document, float]] = []
        for result in results:
            metadata = json.loads(result[1]) or {}
            doc = Document(page_content=result[0], metadata=metadata)
            documents.append((doc, result[2]))

        cursor.close()
        return documents

    def similarity_search(
        self, query: str, k: int = 4, **kwargs: Any
    ) -> List[Document]:
        """Perform a similarity search with Yellowbrick

        Args:
            query (str): query string
            k (int, optional): Top K neighbors to retrieve. Defaults to 4.

            NOTE: Please do not let end-user fill this and always be aware
                  of SQL injection.

        Returns:
            List[Document]: List of Documents
        """
        embedding = self._embedding.embed_query(query)
        documents = self.similarity_search_with_score_by_vector(
            embedding=embedding, k=k
        )
        return [doc for doc, _ in documents]

    def similarity_search_with_score(
        self, query: str, k: int = 4, **kwargs: Any
    ) -> List[Tuple[Document, float]]:
        """Perform a similarity search with Yellowbrick

        Args:
            query (str): query string
            k (int, optional): Top K neighbors to retrieve. Defaults to 4.

            NOTE: Please do not let end-user fill this and always be aware
                  of SQL injection.

        Returns:
            List[Document]: List of (Document, similarity)
        """
        embedding = self._embedding.embed_query(query)
        documents = self.similarity_search_with_score_by_vector(
            embedding=embedding, k=k
        )
        return documents

    def similarity_search_by_vector(
        self, embedding: List[float], k: int = 4, **kwargs: Any
    ) -> List[Document]:
        """Perform a similarity search with Yellowbrick by vectors

        Args:
            embedding (List[float]): query embedding
            k (int, optional): Top K neighbors to retrieve. Defaults to 4.

            NOTE: Please do not let end-user fill this and always be aware
                  of SQL injection.

        Returns:
            List[Document]: List of documents
        """
        documents = self.similarity_search_with_score_by_vector(
            embedding=embedding, k=k
        )
        return [doc for doc, _ in documents]

    def _generate_lsh_hashes(
        self,
        embedding_table: str,
        target_hash_table: Optional[str] = None,
        doc_id: Optional[uuid] = None,
    ) -> None:
        """Generate hashes for vectors"""
        from psycopg2 import sql

        if doc_id:
            condition = sql.SQL("WHERE e.doc_id = {doc_id}").format(
                doc_id=sql.Literal(str(doc_id))
            )
            group_by = sql.SQL("GROUP BY 1, 2")
        else:
            condition = sql.SQL("")
            group_by = (
                sql.SQL("GROUP BY 1") if target_hash_table else sql.SQL("GROUP BY 1, 2")
            )

        if target_hash_table:
            table_name = sql.Identifier(target_hash_table)
            query_prefix = sql.SQL("CREATE TEMPORARY TABLE {table_name} AS").format(
                table_name=table_name
            )
        else:
            table_name = sql.Identifier(self._table + self.LSH_INDEX_TABLE)
            query_prefix = sql.SQL("INSERT INTO {table_name}").format(
                table_name=table_name
            )

        input_query = query_prefix + sql.SQL(
            """
            SELECT
                {select_columns}
                h.id as hash_index,
                CASE WHEN
                    SUM(e.embedding * h.hyperplane) > 0
                THEN
                    1
                ELSE
                    0
                END as hash
            FROM {embedding_table} e
            INNER JOIN {hyperplanes} h ON e.embedding_id = h.hyperplane_id
            {condition}
            {group_by}
            """
        ).format(
            select_columns=sql.SQL("e.doc_id,")
            if not target_hash_table or doc_id
            else sql.SQL(""),
            embedding_table=sql.Identifier(embedding_table),
            hyperplanes=sql.Identifier(self._table + self.LSH_HYPERPLANE_TABLE),
            condition=condition,
            group_by=group_by,
        )

        cursor = self._get_connection().cursor()
        cursor.execute(input_query)
        self._get_connection().commit()
        cursor.close()

    def _populate_hyperplanes(self, num_hyperplanes: int) -> None:
        """Generate random hyperplanes and store in Yellowbrick"""
        from psycopg2 import sql

        cursor = self._get_connection().cursor()

        cursor.execute(
            sql.SQL("SELECT COUNT(*) FROM {};").format(
                sql.Identifier(self._table + self.LSH_HYPERPLANE_TABLE)
            )
        )
        if cursor.fetchone()[0] > 0:
            cursor.close()
            return

        cursor.execute(
            sql.SQL("SELECT MAX(embedding_id) FROM {};").format(
                sql.Identifier(self._table)
            )
        )
        num_dimensions = cursor.fetchone()[0]
        num_dimensions += 1

        insert_query = sql.SQL(
            """
            WITH parameters AS (
                SELECT {num_hyperplanes} AS num_hyperplanes,
                    {dims_per_hyperplane} AS dims_per_hyperplane
            ),
            seed AS (
                SELECT setseed({seed_value})
            )
            INSERT INTO {hyperplanes_table} (id, hyperplane_id, hyperplane)
                SELECT id, hyperplane_id, (random() * 2 - 1) AS hyperplane
                FROM
                (SELECT range-1 id FROM sys.rowgenerator
                    WHERE range BETWEEN 1 AND
                    (SELECT num_hyperplanes FROM parameters) AND
                    worker_lid = 0 AND thread_id = 0) a,
                (SELECT range-1 hyperplane_id FROM sys.rowgenerator
                    WHERE range BETWEEN 1 AND
                    (SELECT dims_per_hyperplane FROM parameters) AND
                    worker_lid = 0 AND thread_id = 0) b
        """
        ).format(
            num_hyperplanes=sql.Literal(num_hyperplanes),
            dims_per_hyperplane=sql.Literal(num_dimensions),
            hyperplanes_table=sql.Identifier(self._table + self.LSH_HYPERPLANE_TABLE),
            seed_value=sql.Literal(self._seed),
        )
        cursor.execute(insert_query)
        self._get_connection().commit()
        cursor.close()

    def _create_lsh_index_tables(self) -> None:
        """Create LSH index and hyperplane tables"""
        from psycopg2 import sql

        cursor = self._get_connection().cursor()
        cursor.execute(
            sql.SQL(
                """
                CREATE TABLE IF NOT EXISTS {t1} (
                doc_id UUID NOT NULL,
                hash_index SMALLINT NOT NULL,
                hash SMALLINT NOT NULL,
                CONSTRAINT {c1} PRIMARY KEY (doc_id, hash_index),
                CONSTRAINT {c2} FOREIGN KEY (doc_id) REFERENCES {t2}(doc_id))
                DISTRIBUTE ON (doc_id) SORT ON (doc_id)
            """
            ).format(
                t1=sql.Identifier(self._table + self.LSH_INDEX_TABLE),
                t2=sql.Identifier(self._table + self.CONTENT_TABLE),
                c1=sql.Identifier(self._table + self.LSH_INDEX_TABLE + "_pk_doc_id"),
                c2=sql.Identifier(self._table + self.LSH_INDEX_TABLE + "_fk_doc_id"),
            )
        )
        cursor.execute(
            sql.SQL(
                """
                CREATE TABLE IF NOT EXISTS {t} (
                id SMALLINT NOT NULL,
                hyperplane_id SMALLINT NOT NULL,
                hyperplane FLOAT NOT NULL,
                CONSTRAINT {c} PRIMARY KEY (id, hyperplane_id))
                DISTRIBUTE REPLICATE SORT ON (id)
            """
            ).format(
                t=sql.Identifier(self._table + self.LSH_HYPERPLANE_TABLE),
                c=sql.Identifier(
                    self._table + self.LSH_HYPERPLANE_TABLE + "_pk_id_hp_id"
                ),
            )
        )
        self._get_connection().commit()
        cursor.close()

    def _drop_lsh_index_tables(self) -> None:
        """Drop LSH index tables"""
        self._drop_table(self._table + self.LSH_INDEX_TABLE)
        self._drop_table(self._table + self.LSH_HYPERPLANE_TABLE)

    def create_lsh_index(self, num_hyperplanes: int) -> None:
        """Create LSH index from existing vectors using stored hyperplanes"""
        self._drop_lsh_index_tables()
        self._create_lsh_index_tables()
        self._populate_hyperplanes(num_hyperplanes)
        self._generate_lsh_hashes(embedding_table=self._table)

    def drop_lsh_index(self) -> None:
        """Drop the LSH index"""
        self._drop_lsh_index_tables()

    def update_lsh_index(self, doc_id: uuid) -> None:
        """Update LSH index with a new or modified embedding in the embeddings table"""
        self._generate_lsh_hashes(embedding_table=self._table, doc_id=doc_id)
