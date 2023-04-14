import os
from typing import Generator, List, Union

import pytest
from vcr.request import Request

from langchain.document_loaders import TextLoader
from langchain.embeddings import OpenAIEmbeddings
from langchain.schema import Document
from langchain.text_splitter import CharacterTextSplitter


# This fixture returns a dictionary containing filter_headers options
# for replacing certain headers with dummy values during cassette playback
# Specifically, it replaces the authorization header with a dummy value to
# prevent sensitive data from being recorded in the cassette.
@pytest.fixture(scope="module")
def vcr_config() -> dict:
    def before_record_response(response: dict) -> Union[dict, None]:
        return response

    def before_record_request(request: Request) -> Union[Request, None]:
        return request

    return {
        "before_record_request": before_record_request,
        "before_record_response": before_record_response,
        "filter_headers": [
            ("authorization", "authorization-DUMMY"),
            ("X-OpenAI-Client-User-Agent", "X-OpenAI-Client-User-Agent-DUMMY"),
            ("Api-Key", "Api-Key-DUMMY"),
            ("User-Agent", "User-Agent-DUMMY"),
        ],
        "ignore_localhost": True,
    }


# Define a fixture that yields a generator object returning a list of documents
@pytest.fixture(scope="function")
def documents() -> Generator[List[Document], None, None]:
    """Return a generator that yields a list of documents."""

    # Create a CharacterTextSplitter object for splitting the documents into chunks
    text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)

    # Load the documents from a file located in the fixtures directory
    documents = TextLoader(
        os.path.join(os.path.dirname(__file__), "fixtures", "sharks.txt")
    ).load()

    # Yield the documents split into chunks
    yield text_splitter.split_documents(documents)


@pytest.fixture(scope="function")
def texts() -> Generator[List[str], None, None]:
    # Load the documents from a file located in the fixtures directory
    documents = TextLoader(
        os.path.join(os.path.dirname(__file__), "fixtures", "sharks.txt")
    ).load()

    yield [doc.page_content for doc in documents]


@pytest.fixture(scope="module")
def embedding() -> OpenAIEmbeddings:
    # double check that the API key is set
    assert os.getenv("OPENAI_API_KEY") is not None
    return OpenAIEmbeddings()


@pytest.fixture(scope="module")
def query() -> str:
    return "sharks"
