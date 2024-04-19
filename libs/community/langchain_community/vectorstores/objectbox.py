import asyncio
import os
from typing import (
    Any,
    Iterable,
    List,
    Optional,
    Tuple,
)

import numpy as np
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore
import objectbox
from objectbox.model import *
from objectbox.model.properties import *

DIRECTORY = "data"
# TODO: get directory from constructor


class ObjectBox(VectorStore):
    """
    ObjectBox as Vector Store.
    To use, you should have the `objectbox` python package installed and `flatbuffers`.
    Args:
        embedding_function: Embedding function to use.
        vector_box: initializing objectbox
    """

    def __init__(
        self,
        embedding_function: Embeddings,
        embedding_dimensions: int,
        db_name: Optional[str] = None,
        clear_db: Optional[bool] = False,
    ):
        self._embedding_function = embedding_function
        self._embedding_dimensions = embedding_dimensions
        self._db_name = db_name
        self._clear_db = clear_db
        self._entity_model = self._create_entity_class()
        self._db = self._create_objectbox_db()
        self._vector_box = objectbox.Box(self._db, self._entity_model)

    @property
    def embeddings(self) -> Optional[Embeddings]:
        return (
            self.embedding_function
            if isinstance(self.embedding_function, Embeddings)
            else None
        )

    def add_texts(
        self,
        texts: Iterable[str],
        metadatas: Optional[List[dict]] = None,
        **kwargs: Any,
    ) -> List[str]:
        """Add list of text along with embeddings to the vector store
        Args:
            texts (Iterable[str]): collection of text to add to the database
        Returns:
            List of ids for the newly inserted documents
        """
        return asyncio.run(self.aadd_texts(texts, metadatas, **kwargs))

    async def aadd_texts(
        self,
        texts: Iterable[str],
        metadatas: Optional[List[dict]] = None,
        **kwargs: Any,
    ) -> List[str]:
        """Add list of text along with embeddings to the vector store asynchronously
        Args:
            texts (Iterable[str]): collection of text to add to the database
        Returns:
            List of ids for the newly inserted documents
        """
        embeddings = self._embedding_function.embed_documents(list(texts))
        ids = []
        with self._db.write_tx():
            for idx, text in enumerate(texts):
                record = self._vector_box.put(
                    self._entity_model(text=text, embeddings=embeddings[idx])
                )
                ids.append(record)
        return ids

    def similarity_search(
        self, query: str, k: int = 4, **kwargs: Any
    ) -> List[Document]:
        """Run similarity search on query
        Args:
            query (str): Query
            k (int): Number of results to return. Defaults to 4.
        Returns:
            List of Documents most similar to the query
        """

        async def _similarity_search() -> List[Document]:
            qb = self._vector_box.query()
            embedded_query = self._embedding_function.embed_query(query)
            qb.nearest_neighbors_f32("embeddings", embedded_query, k)
            query_build = qb.build()
            query_result = query_build.find()
            return [
                Document(page_content=result.text, metadata={"id": result.id})
                for result in query_result
            ]

        return asyncio.run(_similarity_search())

    @classmethod
    async def afrom_texts(
        cls,
        texts: List[str],
        embedding: Embeddings,
        metadatas: Optional[List[dict]] = None,
        **kwargs: Any,
    ):
        """Create ObjectBox from list of text asynchronously
        Args:
            texts (List[str]): list of text to vectorize and store
            embedding (Embeddings): Embedding function.
        Returns:
            ObjectBox object initialized and ready for use."""

        ob = cls(embedding, **kwargs)
        await ob.aadd_texts(texts)
        return ob

    @classmethod
    def from_texts(
        cls,
        texts: List[str],
        embedding: Embeddings,
        metadatas: Optional[List[dict]] = None,
        **kwargs: Any,
    ):
        """Create ObjectBox from list of text
        Args:
            texts (List[str]): list of text to vectorize and store
            embedding (Optional[Embeddings]): Embedding function.
        Returns:
            ObjectBox object initialized and ready for use."""
        ob = asyncio.run(cls.afrom_texts(texts, embedding, metadatas, **kwargs))
        return ob

    def _create_objectbox_db(self):
        db_path = (
            DIRECTORY
            if self._db_name is None
            else os.path.join(DIRECTORY, self._db_name)
        )
        if self._clear_db and path.exists(db_path):
            shutil.rmtree(db_path)
        model = objectbox.Model()
        model.entity(self._entity_model, last_property_id=IdUid(3, 1003))
        model.last_entity_id = IdUid(1, 1)
        model.last_index_id = IdUid(3, 10001)
        return objectbox.Builder().model(model).directory(db_path).build()

    def _create_entity_class(self):
        """Dynamically define an Entity class according to the parameters."""

        @Entity(id=1, uid=1)
        class VectorEntity:
            id = Id(id=1, uid=1001)
            text = Property(str, type=PropertyType.string, id=2, uid=1002)
            embeddings = Property(
                np.ndarray,
                type=PropertyType.floatVector,
                id=3,
                uid=1003,
                index=HnswIndex(
                    id=3,
                    uid=10001,
                    dimensions=self._embedding_dimensions,
                    distance_type=HnswDistanceType.EUCLIDEAN,
                ),
            )

        return VectorEntity
