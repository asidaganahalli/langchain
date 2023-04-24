"""Test Weaviate functionality."""
import logging
import os
from typing import Generator, Union

import pytest
from weaviate import Client

from langchain.docstore.document import Document
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores.weaviate import Weaviate

logging.basicConfig(level=logging.DEBUG)

"""
cd tests/integration_tests/vectorstores/docker-compose
docker compose -f weaviate.yml up
"""


class TestWeaviate:
    @classmethod
    def setup_class(cls) -> None:
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY environment variable is not set")

    @pytest.fixture(scope="class", autouse=True)
    def weaviate_url(self) -> Union[str, Generator[str, None, None]]:
        """Return the weaviate url."""
        url = "http://localhost:8080"
        yield url

        # Clear the test index
        client = Client(url)
        client.schema.delete_all()

    @pytest.mark.vcr(ignore_localhost=True)
    def test_similarity_search_without_metadata(
        self, weaviate_url: str, embedding_openai: OpenAIEmbeddings
    ) -> None:
        """Test end to end construction and search without metadata."""
        texts = ["foo", "bar", "baz"]
        docsearch = Weaviate.from_texts(
            texts,
            embedding_openai,
            weaviate_url=weaviate_url,
        )

        output = docsearch.similarity_search("foo", k=1)
        assert output == [Document(page_content="foo")]

    @pytest.mark.vcr(ignore_localhost=True)
    def test_similarity_search_with_metadata(
        self, weaviate_url: str, embedding_openai: OpenAIEmbeddings
    ) -> None:
        """Test end to end construction and search with metadata."""
        texts = ["foo", "bar", "baz"]
        metadatas = [{"page": i} for i in range(len(texts))]
        docsearch = Weaviate.from_texts(
            texts, embedding_openai, metadatas=metadatas, weaviate_url=weaviate_url
        )
        output = docsearch.similarity_search("foo", k=1)
        assert output == [Document(page_content="foo", metadata={"page": 0})]

    @pytest.mark.vcr(ignore_localhost=True)
    def test_similarity_search_with_metadata_and_filter(
        self, weaviate_url: str, embedding_openai: OpenAIEmbeddings
    ) -> None:
        """Test end to end construction and search with metadata."""
        texts = ["foo", "bar", "baz"]
        metadatas = [{"page": i} for i in range(len(texts))]
        docsearch = Weaviate.from_texts(
            texts, embedding_openai, metadatas=metadatas, weaviate_url=weaviate_url
        )
        output = docsearch.similarity_search(
            "foo",
            k=2,
            where_filter={"path": ["page"], "operator": "Equal", "valueNumber": 0},
        )
        assert output == [Document(page_content="foo", metadata={"page": 0})]

    @pytest.mark.vcr(ignore_localhost=True)
    def test_max_marginal_relevance_search(
        self, weaviate_url: str, embedding_openai: OpenAIEmbeddings
    ) -> None:
        """Test end to end construction and MRR search."""
        texts = ["foo", "bar", "baz"]
        metadatas = [{"page": i} for i in range(len(texts))]

        docsearch = Weaviate.from_texts(
            texts, embedding_openai, metadatas=metadatas, weaviate_url=weaviate_url
        )
        # if lambda=1 the algorithm should be equivalent to standard ranking
        standard_ranking = docsearch.similarity_search("foo", k=2)
        output = docsearch.max_marginal_relevance_search(
            "foo", k=2, fetch_k=3, lambda_mult=1.0
        )
        assert output == standard_ranking

        # if lambda=0 the algorithm should favour maximal diversity
        output = docsearch.max_marginal_relevance_search(
            "foo", k=2, fetch_k=3, lambda_mult=0.0
        )
        assert output == [
            Document(page_content="foo", metadata={"page": 0}),
            Document(page_content="bar", metadata={"page": 1}),
        ]

    @pytest.mark.vcr(ignore_localhost=True)
    def test_max_marginal_relevance_search_with_filter(
        self, weaviate_url: str, embedding_openai: OpenAIEmbeddings
    ) -> None:
        """Test end to end construction and MRR search."""
        texts = ["foo", "bar", "baz"]
        metadatas = [{"page": i} for i in range(len(texts))]

        docsearch = Weaviate.from_texts(
            texts, embedding_openai, metadatas=metadatas, weaviate_url=weaviate_url
        )
        where_filter = {"path": ["page"], "operator": "Equal", "valueNumber": 0}
        # if lambda=1 the algorithm should be equivalent to standard ranking
        standard_ranking = docsearch.similarity_search(
            "foo", k=2, where_filter=where_filter
        )
        output = docsearch.max_marginal_relevance_search(
            "foo", k=2, fetch_k=3, lambda_mult=1.0, where_filter=where_filter
        )
        assert output == standard_ranking

        # if lambda=0 the algorithm should favour maximal diversity
        output = docsearch.max_marginal_relevance_search(
            "foo", k=2, fetch_k=3, lambda_mult=0.0, where_filter=where_filter
        )
        assert output == [
            Document(page_content="foo", metadata={"page": 0}),
        ]
