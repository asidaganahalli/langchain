from __future__ import annotations

from typing import Literal, Optional

from langchain_core.load.serializable import Serializable
from langchain_core.pydantic_v1 import Field


class Document(Serializable):
    """Class for storing a piece of text and associated metadata."""

    page_content: str
    """String text."""
    metadata: dict = Field(default_factory=dict)
    """Arbitrary metadata about the page content (e.g., source, relationships to other
        documents, etc.).
    """
    type: Literal["Document"] = "Document"

    parent: Optional[Document] = None
    """Parent document, optionally set by document loaders that support
    hierarchical chunking."""

    @classmethod
    def is_lc_serializable(cls) -> bool:
        """Return whether this class is serializable."""
        return True
