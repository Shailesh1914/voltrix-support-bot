"""Ingestion side of the Voltrix VX-200 support bot (specs 01 and 03).

The query side uses only the retrieval contract exported here.
"""

from ingestion.errors import RetrievalError
from ingestion.retrieval import Chunk, KBInfo, Retriever, open_retrieval

__all__ = ["Chunk", "KBInfo", "Retriever", "RetrievalError", "open_retrieval"]
