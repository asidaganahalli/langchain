"""Search index commands are only supported on Atlas Clusters >=M10"""

import os
from time import sleep

import pytest
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import OperationFailure

from langchain_mongodb import index


@pytest.fixture
def collection() -> Collection:
    """Depending on uri, this could point to any type of cluster.

    For unit tests, MONGODB_URI should be localhost, None, or Atlas cluster <M10.
    """
    uri = os.environ.get("MONGODB_URI")
    client: MongoClient = MongoClient(uri)
    return client["db"]["collection"]


def test_create_vector_search_index(collection: Collection) -> None:
    with pytest.raises(OperationFailure):
        index.create_vector_search_index(
            collection, "index_name", 1536, "embedding", "cosine", []
        )


def test_drop_vector_search_index(collection: Collection) -> None:
    with pytest.raises(OperationFailure):
        index.drop_vector_search_index(collection, "index_name")


def test_update_vector_search_index(collection: Collection) -> None:
    with pytest.raises(OperationFailure):
        index.update_vector_search_index(
            collection, "index_name", 1536, "embedding", "cosine", []
        )


def test___is_index_ready(collection: Collection) -> None:
    with pytest.raises(OperationFailure):
        index._is_index_ready(collection, "index_name")


def test__wait_for_predicate() -> None:
    err = "error string"
    with pytest.raises(TimeoutError) as e:
        index._wait_for_predicate(lambda: sleep(5), err=err, timeout=0.5, interval=0.1)
        assert err in str(e)

    index._wait_for_predicate(lambda: True, err=err, timeout=1.0, interval=0.5)
