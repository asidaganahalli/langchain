"""**Vector store** stores embedded data and performs vector search.

One of the most common ways to store and search over unstructured data is to
embed it and store the resulting embedding vectors, and then query the store
and retrieve the data that are 'most similar' to the embedded query.

**Class hierarchy:**

.. code-block::

    VectorStore --> <name>  # Examples: Annoy, FAISS, Milvus

    BaseRetriever --> VectorStoreRetriever --> <name>Retriever  # Example: VespaRetriever

**Main helpers:**

.. code-block::

    Embeddings, Document
"""  # noqa: E501

from typing import TYPE_CHECKING, Any

from langchain_core.vectorstores import VectorStore

from langchain._api import create_importer

if TYPE_CHECKING:
    from langchain_community.vectorstores import (
        FAISS,
        AlibabaCloudOpenSearch,
        AlibabaCloudOpenSearchSettings,
        AnalyticDB,
        Annoy,
        AstraDB,
        AtlasDB,
        AwaDB,
        AzureCosmosDBVectorSearch,
        AzureSearch,
        Bagel,
        Cassandra,
        Chroma,
        Clarifai,
        Clickhouse,
        ClickhouseSettings,
        DashVector,
        DatabricksVectorSearch,
        DeepLake,
        Dingo,
        DocArrayHnswSearch,
        DocArrayInMemorySearch,
        DuckDB,
        EcloudESVectorStore,
        ElasticKnnSearch,
        ElasticsearchStore,
        ElasticVectorSearch,
        Epsilla,
        Hologres,
        LanceDB,
        LLMRails,
        Marqo,
        MatchingEngine,
        Meilisearch,
        Milvus,
        MomentoVectorIndex,
        MongoDBAtlasVectorSearch,
        MyScale,
        MyScaleSettings,
        Neo4jVector,
        NeuralDBClientVectorStore,
        NeuralDBVectorStore,
        OpenSearchVectorSearch,
        PGEmbedding,
        PGVector,
        Pinecone,
        Qdrant,
        Redis,
        Rockset,
        ScaNN,
        SemaDB,
        SingleStoreDB,
        SKLearnVectorStore,
        SQLiteVSS,
        StarRocks,
        SupabaseVectorStore,
        Tair,
        TencentVectorDB,
        Tigris,
        TileDB,
        TimescaleVector,
        Typesense,
        USearch,
        Vald,
        Vearch,
        Vectara,
        VespaStore,
        Weaviate,
        Yellowbrick,
        ZepVectorStore,
        Zilliz,
    )

# Create a way to dynamically look up deprecated imports.
# Used to consolidate logic for raising deprecation warnings and
# handling optional imports.
DEPRECATED_LOOKUP = {
    "AlibabaCloudOpenSearch": "langchain_community.vectorstores",
    "AlibabaCloudOpenSearchSettings": "langchain_community.vectorstores",
    "AnalyticDB": "langchain_community.vectorstores",
    "Annoy": "langchain_community.vectorstores",
    "AstraDB": "langchain_community.vectorstores",
    "AtlasDB": "langchain_community.vectorstores",
    "AwaDB": "langchain_community.vectorstores",
    "AzureCosmosDBVectorSearch": "langchain_community.vectorstores",
    "AzureSearch": "langchain_community.vectorstores",
    "Bagel": "langchain_community.vectorstores",
    "Cassandra": "langchain_community.vectorstores",
    "Chroma": "langchain_community.vectorstores",
    "Clarifai": "langchain_community.vectorstores",
    "Clickhouse": "langchain_community.vectorstores",
    "ClickhouseSettings": "langchain_community.vectorstores",
    "DashVector": "langchain_community.vectorstores",
    "DatabricksVectorSearch": "langchain_community.vectorstores",
    "DeepLake": "langchain_community.vectorstores",
    "Dingo": "langchain_community.vectorstores",
    "DocArrayHnswSearch": "langchain_community.vectorstores",
    "DocArrayInMemorySearch": "langchain_community.vectorstores",
    "DuckDB": "langchain_community.vectorstores",
    "EcloudESVectorStore": "langchain_community.vectorstores",
    "ElasticKnnSearch": "langchain_community.vectorstores",
    "ElasticsearchStore": "langchain_community.vectorstores",
    "ElasticVectorSearch": "langchain_community.vectorstores",
    "Epsilla": "langchain_community.vectorstores",
    "FAISS": "langchain_community.vectorstores",
    "Hologres": "langchain_community.vectorstores",
    "LanceDB": "langchain_community.vectorstores",
    "LLMRails": "langchain_community.vectorstores",
    "Marqo": "langchain_community.vectorstores",
    "MatchingEngine": "langchain_community.vectorstores",
    "Meilisearch": "langchain_community.vectorstores",
    "Milvus": "langchain_community.vectorstores",
    "MomentoVectorIndex": "langchain_community.vectorstores",
    "MongoDBAtlasVectorSearch": "langchain_community.vectorstores",
    "MyScale": "langchain_community.vectorstores",
    "MyScaleSettings": "langchain_community.vectorstores",
    "Neo4jVector": "langchain_community.vectorstores",
    "NeuralDBClientVectorStore": "langchain_community.vectorstores",
    "NeuralDBVectorStore": "langchain_community.vectorstores",
    "NEuralDBVectorStore": "langchain_community.vectorstores",
    "OpenSearchVectorSearch": "langchain_community.vectorstores",
    "PGEmbedding": "langchain_community.vectorstores",
    "PGVector": "langchain_community.vectorstores",
    "Pinecone": "langchain_community.vectorstores",
    "Qdrant": "langchain_community.vectorstores",
    "Redis": "langchain_community.vectorstores",
    "Rockset": "langchain_community.vectorstores",
    "ScaNN": "langchain_community.vectorstores",
    "SemaDB": "langchain_community.vectorstores",
    "SingleStoreDB": "langchain_community.vectorstores",
    "SKLearnVectorStore": "langchain_community.vectorstores",
    "SQLiteVSS": "langchain_community.vectorstores",
    "StarRocks": "langchain_community.vectorstores",
    "SupabaseVectorStore": "langchain_community.vectorstores",
    "Tair": "langchain_community.vectorstores",
    "TencentVectorDB": "langchain_community.vectorstores",
    "Tigris": "langchain_community.vectorstores",
    "TileDB": "langchain_community.vectorstores",
    "TimescaleVector": "langchain_community.vectorstores",
    "Typesense": "langchain_community.vectorstores",
    "USearch": "langchain_community.vectorstores",
    "Vald": "langchain_community.vectorstores",
    "Vearch": "langchain_community.vectorstores",
    "Vectara": "langchain_community.vectorstores",
    "VespaStore": "langchain_community.vectorstores",
    "Weaviate": "langchain_community.vectorstores",
    "Yellowbrick": "langchain_community.vectorstores",
    "ZepVectorStore": "langchain_community.vectorstores",
    "Zilliz": "langchain_community.vectorstores",
}

_import_attribute = create_importer(__package__, deprecated_lookups=DEPRECATED_LOOKUP)


def __getattr__(name: str) -> Any:
    """Look up attributes dynamically."""
    return _import_attribute(name)


__all__ = [
    "AlibabaCloudOpenSearch",
    "AlibabaCloudOpenSearchSettings",
    "AnalyticDB",
    "Annoy",
    "AstraDB",
    "AtlasDB",
    "AwaDB",
    "AzureCosmosDBVectorSearch",
    "AzureSearch",
    "Bagel",
    "Cassandra",
    "Chroma",
    "Clarifai",
    "Clickhouse",
    "ClickhouseSettings",
    "DashVector",
    "DatabricksVectorSearch",
    "DeepLake",
    "Dingo",
    "DocArrayHnswSearch",
    "DocArrayInMemorySearch",
    "DuckDB",
    "EcloudESVectorStore",
    "ElasticKnnSearch",
    "ElasticsearchStore",
    "ElasticVectorSearch",
    "Epsilla",
    "FAISS",
    "Hologres",
    "LanceDB",
    "LLMRails",
    "Marqo",
    "MatchingEngine",
    "Meilisearch",
    "Milvus",
    "MomentoVectorIndex",
    "MongoDBAtlasVectorSearch",
    "MyScale",
    "MyScaleSettings",
    "Neo4jVector",
    "NeuralDBClientVectorStore",
    "NeuralDBVectorStore",
    "OpenSearchVectorSearch",
    "PGEmbedding",
    "PGVector",
    "Pinecone",
    "Qdrant",
    "Redis",
    "Rockset",
    "ScaNN",
    "SemaDB",
    "SingleStoreDB",
    "SKLearnVectorStore",
    "SQLiteVSS",
    "StarRocks",
    "SupabaseVectorStore",
    "Tair",
    "TencentVectorDB",
    "Tigris",
    "TileDB",
    "TimescaleVector",
    "Typesense",
    "USearch",
    "Vald",
    "Vearch",
    "Vectara",
    "VectorStore",
    "VespaStore",
    "Weaviate",
    "Yellowbrick",
    "ZepVectorStore",
    "Zilliz",
]
