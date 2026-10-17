"""Shared fixtures for the evaluation structural tests (Session E).

Fakes only: no network, no model calls, no real index. Helpers are
fixtures, not importable names, so this conftest never clashes with the
ingestion and query ones when all suites run together.
"""

import socket
from pathlib import Path

import pytest

from evals.eval_scoring import Outcome
from evals.eval_sweep import RunResult
from evals.eval_tickets import Ticket
from ingestion import Chunk, KBInfo

REPO_ROOT = Path(__file__).resolve().parents[3]

# A small KB in the shape kb_info() returns: fault codes E-01 and E-02.
FAKE_ARTICLES = [
    ("KB-001", "E-01 Overcurrent during acceleration"),
    ("KB-002", "E-02 Overcurrent during deceleration"),
    ("KB-019", "Motor wiring"),
    ("KB-020", "Setting acceleration and deceleration ramp times"),
    ("KB-022", "Commissioning checklist"),
]


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Every socket connection fails, and no Anthropic key is visible."""

    def refuse(*args, **kwargs):
        raise AssertionError("network access in a structural test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    for name in ("VOLTRIX_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL"):
        monkeypatch.delenv(name, raising=False)


class FakeRetriever:
    """Returns scripted chunks: scores(query) -> [(article_id, score), ...]."""

    def __init__(self, scores=None, kb_version="v1"):
        self._scores = scores or (lambda query: [("KB-001", 0.80), ("KB-020", 0.60)])
        self._kb_version = kb_version
        self.queries: list[tuple[str, int]] = []

    def search(self, query: str, k: int) -> list[Chunk]:
        self.queries.append((query, k))
        titles = dict(FAKE_ARTICLES)
        hits = sorted(self._scores(query), key=lambda h: -h[1])[:k]
        return [
            Chunk(
                chunk_id=f"{aid}#c{n}",
                article_id=aid,
                title=titles.get(aid, aid),
                text=f"{titles.get(aid, aid)} — Section\n\nText of {aid}.",
                kb_version=self._kb_version,
                similarity_score=score,
            )
            for n, (aid, score) in enumerate(hits, start=1)
        ]

    def kb_info(self) -> KBInfo:
        return KBInfo(kb_version=self._kb_version, articles=list(FAKE_ARTICLES))


@pytest.fixture
def fake_retriever():
    return FakeRetriever


@pytest.fixture
def make_chunk():
    def _make(chunk_id, score) -> Chunk:
        article_id = chunk_id.split("#")[0]
        title = dict(FAKE_ARTICLES).get(article_id, article_id)
        return Chunk(chunk_id, article_id, title, f"{title} — Section", "v1", score)

    return _make


@pytest.fixture
def fake_articles():
    return list(FAKE_ARTICLES)


@pytest.fixture
def make_ticket():
    def _make(ticket_id="T-001", expected="answer", ids=("KB-001",), category="fault", question=None, match="all"):
        if expected == "escalate" and ids == ("KB-001",):
            ids = ()
        return Ticket(
            ticket_id=ticket_id,
            question=question or f"question of {ticket_id}",
            expected=expected,
            expected_article_ids=tuple(ids),
            category=category,
            article_match=match,
        )

    return _make


@pytest.fixture
def answered():
    def _make(*cited, failed_check=""):
        return Outcome(status="answered", cited_article_ids=tuple(cited), failed_check=failed_check)

    return _make


@pytest.fixture
def escalated():
    def _make(reason="insufficient_context", failed_check="", model_called=True):
        return Outcome(status="escalated", escalation_reason=reason, failed_check=failed_check, model_called=model_called)

    return _make


@pytest.fixture
def run_result():
    def _make(top_score, outcome):
        return RunResult(top_score=top_score, outcome=outcome)

    return _make


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def make_part_a2():
    """A Part A2 report whose E1+E2+E3 results equal the given Part A data,
    so a comparison matches until a test changes something."""

    def _make(part_a: dict, ticket_file_sha256: str) -> dict:
        tickets = []
        for r in part_a["tickets"]:
            tickets.append(
                {
                    "ticket_id": r["ticket_id"],
                    "query_sent": r["query_sent"],
                    "boost_titles": [s["query"] for s in r["searches"][1:]],
                    "results": {
                        "E1+E2+E3": {
                            "top_score": r["top_score"],
                            "top_article_ids": list(r["top_article_ids"]),
                            "top_chunk_ids": [c["chunk_id"] for c in r["top_chunks"]],
                            "recall_hit": r["recall_hit"],
                            "both_hit": r["both_hit"],
                        }
                    },
                }
            )
        return {
            "kind": "part-a2",
            "date": "2026-10-17",
            "git_commit": "a2commit",
            "git_dirty": True,
            "ticket_file_sha256": ticket_file_sha256,
            "kb_version": part_a["kb_version"],
            "experiments": {"E1+E2+E3": "simulated"},
            "summary": {
                name: {"E1+E2+E3": {k: s[k] for k in ("recall", "both_recall")}}
                for name, s in part_a["summary"].items()
            },
            "tickets": tickets,
        }

    return _make
