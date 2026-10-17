"""Wrappers passed into QueryFlow so the evaluation sees what the flow did.

They use only QueryFlow's public constructor arguments (a retriever, a
generator and a handoff store); no query/ internals are read.
"""

from dataclasses import dataclass

from ingestion import Chunk, KBInfo
from query.generator import GeneratorOutput
from query.handoff import HandoffRecord


class EvalError(Exception):
    """The evaluation run cannot continue (fail loudly)."""


@dataclass(frozen=True)
class SearchCall:
    query: str
    k: int
    chunks: tuple[Chunk, ...]

    @property
    def top_score(self) -> float | None:
        return self.chunks[0].similarity_score if self.chunks else None


@dataclass(frozen=True)
class ReadCall:
    article_id: str
    chunks: tuple[Chunk, ...]


class RecordingRetriever:
    """Records the exact query the flow sends to search() and the result
    (spec 05 clarification 3: Part A uses the flow's own query), and the
    articles it reads whole with article_chunks() (spec 02 step 3e,
    spec 03 v1.5)."""

    def __init__(self, inner):
        self._inner = inner
        self.calls: list[SearchCall] = []
        self.reads: list[ReadCall] = []

    def search(self, query: str, k: int) -> list[Chunk]:
        chunks = self._inner.search(query, k)
        self.calls.append(SearchCall(query, k, tuple(chunks)))
        return chunks

    def kb_info(self) -> KBInfo:
        return self._inner.kb_info()

    def article_chunks(self, article_id: str) -> list[Chunk]:
        chunks = self._inner.article_chunks(article_id)
        self.reads.append(ReadCall(article_id, tuple(chunks)))
        return chunks

    def take(self) -> list[SearchCall]:
        """The search() calls since the last take()."""
        calls, self.calls = self.calls, []
        return calls

    def take_reads(self) -> list[ReadCall]:
        """The article_chunks() calls since the last take_reads()."""
        reads, self.reads = self.reads, []
        return reads


class NoCallGenerator:
    """Stands in for the model in free runs: never calls anything, counts how
    often the flow WOULD have called the model, and declines every time so
    the flow escalates without producing an answer."""

    def __init__(self):
        self.calls = 0

    def generate(self, question: str, chunks: list[Chunk]) -> GeneratorOutput:
        self.calls += 1
        return GeneratorOutput(decision="insufficient_context", answer="", used_article_ids=())


class MemoryHandoffStore:
    """Keeps handoff records in memory, so nothing reaches handoffs/
    (spec 05, Part B). The runner decides which file, if any, to write."""

    def __init__(self):
        self.records: list[HandoffRecord] = []

    def append(self, record: HandoffRecord) -> None:
        self.records.append(record)

    def by_id(self, handoff_id: str) -> HandoffRecord | None:
        for record in self.records:
            if record.handoff_id == handoff_id:
                return record
        return None
