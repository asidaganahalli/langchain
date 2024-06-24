"""Test cohere embeddings."""
from langchain_community.embeddings.cohere import CohereEmbeddings


def test_cohere_embedding_documents() -> None:
    """Test cohere embeddings."""
    documents = ["foo bar"]
    embedding = CohereEmbeddings(model="embed-english-v2.0")  # type: ignore[call-arg]
    output = embedding.embed_documents(documents)
    assert len(output) == 1
    assert len(output[0]) == 2048


def test_cohere_embedding_query() -> None:
    """Test cohere embeddings."""
    document = "foo bar"
    embedding = CohereEmbeddings(model="embed-english-v2.0")  # type: ignore[call-arg]
    output = embedding.embed_query(document)
    assert len(output) == 2048
