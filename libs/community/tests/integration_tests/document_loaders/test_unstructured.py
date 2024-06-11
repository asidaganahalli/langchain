import os
from contextlib import ExitStack
from pathlib import Path
import pytest

import pytest

from langchain_community.document_loaders import (
    UnstructuredAPIFileIOLoader,
    UnstructuredAPIFileLoader,
    UnstructuredFileLoader,
)
from langchain_community.document_loaders.unstructured import _get_content

EXAMPLE_DOCS_DIRECTORY = str(Path(__file__).parent.parent / "examples/")


def test_unstructured_loader_with_post_processor() -> None:
    def add_the_end(text: str) -> str:
        return text + "THE END!"

    file_path = os.path.join(EXAMPLE_DOCS_DIRECTORY, "layout-parser-paper.pdf")
    loader = UnstructuredFileLoader(
        file_path=file_path,
        post_processors=[add_the_end],
        strategy="fast",
        mode="elements",
    )
    docs = loader.load()

    assert len(docs) > 1
    assert docs[0].page_content.endswith("THE END!")


def test_unstructured_file_loader_multiple_files() -> None:
    """Test unstructured loader."""
    file_paths = [
        os.path.join(EXAMPLE_DOCS_DIRECTORY, "layout-parser-paper.pdf"),
        os.path.join(EXAMPLE_DOCS_DIRECTORY, "whatsapp_chat.txt"),
    ]

    loader = UnstructuredFileLoader(
        file_path=file_paths,
        strategy="fast",
        mode="elements",
    )
    docs = loader.load()

    assert len(docs) > 1


@pytest.mark.parametrize(
    ("file_paths"),
    [
        (os.path.join(EXAMPLE_DOCS_DIRECTORY, "layout-parser-paper.pdf")),
        (
            [
                os.path.join(EXAMPLE_DOCS_DIRECTORY, "layout-parser-paper.pdf"),
                os.path.join(EXAMPLE_DOCS_DIRECTORY, "whatsapp_chat.txt"),
            ]
        ),
    ],
)
def test_unstructured_api_file_loader(file_paths) -> None:
    """Test unstructured loader."""

    loader = UnstructuredAPIFileLoader(
        file_path=file_paths,
        api_key="FAKE_API_KEY",
        strategy="fast",
        mode="elements",
    )
    docs = loader.load()

    assert len(docs) > 1


def test_unstructured_api_file_io_loader() -> None:
    """Test unstructured loader."""
    file_path = os.path.join(EXAMPLE_DOCS_DIRECTORY, "layout-parser-paper.pdf")

    with open(file_path, "rb") as f:
        loader = UnstructuredAPIFileIOLoader(
            file=f,
            api_key="FAKE_API_KEY",
            strategy="fast",
            mode="elements",
            metadata_filename=file_path,
        )
        docs = loader.load()

    assert len(docs) > 1


def test_unstructured_api_file_loader_io_multiple_files() -> None:
    """Test unstructured loader."""
    file_paths = [
        os.path.join(EXAMPLE_DOCS_DIRECTORY, "layout-parser-paper.pdf"),
        os.path.join(EXAMPLE_DOCS_DIRECTORY, "whatsapp_chat.txt"),
    ]

    with ExitStack() as stack:
        files = [stack.enter_context(open(file_path, "rb")) for file_path in file_paths]

        loader = UnstructuredAPIFileIOLoader(
            file=files,  # type: ignore
            api_key="FAKE_API_KEY",
            strategy="fast",
            mode="elements",
            metadata_filename=file_paths,
        )

        docs = loader.load()

    assert len(docs) > 1


def test_get_content_from_file() -> None:
    with open(os.path.join(EXAMPLE_DOCS_DIRECTORY, "layout-parser-paper.pdf"), "rb") as f:
        content = _get_content(
            file_path=os.path.join(EXAMPLE_DOCS_DIRECTORY,"layout-parser-paper.pdf"),
            file=f,
        )
    
    assert type(content)==bytes
    assert content[:50]==b'%PDF-1.5\n%\x8f\n47 0 obj\n<< /Filter /FlateDecode /Leng'


def test_get_content_from_file_path() -> None:
    content = _get_content(file_path=os.path.join(EXAMPLE_DOCS_DIRECTORY, "layout-parser-paper.pdf"))
    
    assert type(content)==bytes
    assert content[:50]==b'%PDF-1.5\n%\x8f\n47 0 obj\n<< /Filter /FlateDecode /Leng'
