"""**Index** is used to avoid writing duplicated content
into the vectostore and to avoid over-writing content if it's unchanged.

Indexes also :

* Create knowledge graphs from data.

* Support indexing workflows from LangChain data loaders to vectorstores.

Importantly, Index keeps on working even if the content being written is derived
via a set of transformations from some source content (e.g., indexing children
documents that were derived from parent documents by chunking.)
"""
from langchain_community.indexes._sql_record_manager import SQLRecordManager
from langchain_community.indexes._memory_recordmanager import MemoryRecordManager

__all__ = ["SQLRecordManager", "MemoryRecordManager"]
