"""Shared fixtures for the query structural tests (Session Q).

Helpers are fixtures, not importable names, so this conftest never
clashes with the ingestion one when both suites run together.
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from ingestion import Chunk, KBInfo

REPO_ROOT = Path(__file__).resolve().parents[3]

FIXED_TIME = datetime(2026, 10, 11, 9, 30, tzinfo=timezone.utc)

# A small KB in the shape kb_info() returns: fault codes E-01..E-03.
FAKE_ARTICLES = [
    ("KB-001", "E-01 Overcurrent during acceleration"),
    ("KB-002", "E-02 Overcurrent during deceleration"),
    ("KB-003", "E-03 Overcurrent at constant speed"),
    ("KB-020", "Setting acceleration and deceleration ramp times"),
]


@pytest.fixture
def spec_02_text() -> str:
    return (REPO_ROOT / "specs" / "02-query-escalation-spec.md").read_text(encoding="utf-8")


@pytest.fixture
def query_dir() -> Path:
    return REPO_ROOT / "query"


@pytest.fixture
def make_chunk():
    def _make(article_id="KB-001", n=1, score=0.7, text=None, kb_version="v1") -> Chunk:
        title = dict(FAKE_ARTICLES).get(article_id, f"Article {article_id}")
        return Chunk(
            chunk_id=f"{article_id}#c{n}",
            article_id=article_id,
            title=title,
            text=text or f"{title} — Section {n}\n\nText of {article_id} chunk {n}.",
            kb_version=kb_version,
            similarity_score=score,
        )

    return _make


class FakeRetriever:
    """Contract-shaped retriever returning fixed chunks; records queries."""

    def __init__(self, chunks, articles=FAKE_ARTICLES, kb_version="v1"):
        self.chunks = list(chunks)
        self.articles = list(articles)
        self.kb_version = kb_version
        self.queries: list[tuple[str, int]] = []

    def search(self, query: str, k: int):
        self.queries.append((query, k))
        return self.chunks[:k]

    def kb_info(self):
        return KBInfo(kb_version=self.kb_version, articles=sorted(self.articles))


class StubGenerator:
    """Stage b stub: records the call, then fails."""

    def __init__(self):
        self.calls = []

    def generate(self, question, chunks):
        self.calls.append((question, list(chunks)))
        raise AssertionError("generator called")


class MemoryHandoffStore:
    def __init__(self):
        self.records = []

    def append(self, record):
        self.records.append(record)


@pytest.fixture
def fake_retriever(make_chunk):
    def _make(scores=(0.7, 0.6, 0.5, 0.4, 0.3, 0.2), chunks=None, **kwargs):
        if chunks is None:
            chunks = [make_chunk("KB-001", n=i + 1, score=s) for i, s in enumerate(scores)]
        return FakeRetriever(chunks, **kwargs)

    return _make


@pytest.fixture
def stub_generator():
    return StubGenerator()


@pytest.fixture
def memory_store():
    return MemoryHandoffStore()


@pytest.fixture
def make_flow(fake_retriever, stub_generator, memory_store):
    """A QueryFlow over fakes. Threshold is always passed explicitly."""
    from query.flow import QueryFlow

    def _make(threshold=0.5, retriever=None, generator=None, store=None, kb_version="v1"):
        return QueryFlow(
            retriever if retriever is not None else fake_retriever(),
            generator if generator is not None else stub_generator,
            threshold=threshold,
            handoff_store=store if store is not None else memory_store,
            kb_version=kb_version,
            clock=lambda: FIXED_TIME,
        )

    return _make
