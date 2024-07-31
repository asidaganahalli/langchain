import os

from langchain_community.embeddings import YandexGPTEmbeddings


def test_init() -> None:
    os.environ["YC_API_KEY"] = "foo"
    models = [
        YandexGPTEmbeddings(folder_id="bar"),  # type: ignore[call-arg]
        YandexGPTEmbeddings(  # type: ignore[call-arg]
            query_model_uri="emb://bar/text-search-query/latest",
            doc_model_uri="emb://bar/text-search-doc/latest",
        ),
        YandexGPTEmbeddings(  # type: ignore[call-arg]
            folder_id="bar",
            query_model_name="text-search-query",
            doc_model_name="text-search-doc",
        ),
    ]
    for embeddings in models:
        assert embeddings.model_uri == "emb://bar/text-search-query/latest"
        assert embeddings.doc_model_uri == "emb://bar/text-search-doc/latest"
        assert embeddings.model_name == "text-search-query"
        assert embeddings.doc_model_name == "text-search-doc"

def test_yandexgptembeddings_grpc_metadata() -> None:
    llm = YandexGPTEmbeddings(
        iam_token="your_iam_token",
        folder_id="your_folder_id",
    )
    expected_metadata = [
        ("authorization", "Bearer your_iam_token"),
        ("x-folder-id", "your_folder_id")
    ]
    assert llm.grpc_metadata == expected_metadata