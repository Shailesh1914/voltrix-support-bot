"""Escalation handoff record and local store (spec 02, "Escalation
handoff", decision 8, criterion 3).

Questions reach this module already masked (decision 3). Nothing else
about the person asking is stored.
"""

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from ingestion import Chunk

ESCALATION_REASONS = frozenset(
    {"low_similarity", "insufficient_context", "out_of_scope", "service_error"}
)

# Every field a complete record has (criterion 3), in stored order.
HANDOFF_FIELDS = (
    "handoff_id",
    "created_at",
    "question_received",
    "question_normalised",
    "retrieved_chunks",
    "escalation_reason",
    "kb_version",
)
CHUNK_FIELDS = ("chunk_id", "article_id", "text", "similarity_score")


@dataclass(frozen=True)
class HandoffChunk:
    chunk_id: str
    article_id: str
    text: str
    similarity_score: float


@dataclass(frozen=True)
class HandoffRecord:
    handoff_id: str
    created_at: str  # ISO 8601, UTC
    question_received: str  # masked
    question_normalised: str  # masked, then normalised
    retrieved_chunks: tuple[HandoffChunk, ...]
    escalation_reason: str
    kb_version: str

    def to_dict(self) -> dict:
        record = asdict(self)
        record["retrieved_chunks"] = [asdict(c) for c in self.retrieved_chunks]
        return {name: record[name] for name in HANDOFF_FIELDS}


def new_handoff_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def build_handoff(
    *,
    question_received: str,
    question_normalised: str,
    chunks: list[Chunk],
    escalation_reason: str,
    kb_version: str,
    created_at: datetime,
    handoff_id: str | None = None,
) -> HandoffRecord:
    if escalation_reason not in ESCALATION_REASONS:
        raise ValueError(f"unknown escalation_reason {escalation_reason!r}")
    if created_at.utcoffset() is None:
        raise ValueError("created_at must be timezone-aware (UTC)")
    return HandoffRecord(
        handoff_id=handoff_id or new_handoff_id(),
        created_at=created_at.astimezone(timezone.utc).isoformat(),
        question_received=question_received,
        question_normalised=question_normalised,
        retrieved_chunks=tuple(
            HandoffChunk(c.chunk_id, c.article_id, c.text, c.similarity_score) for c in chunks
        ),
        escalation_reason=escalation_reason,
        kb_version=kb_version,
    )


def missing_fields(record: dict) -> list[str]:
    """Fields a stored record lacks (empty list = complete, criterion 3).

    Works on the plain dict, so it checks a record however it was stored.
    """
    missing = [name for name in HANDOFF_FIELDS if name not in record]
    for i, chunk in enumerate(record.get("retrieved_chunks") or []):
        missing += [f"retrieved_chunks[{i}].{name}" for name in CHUNK_FIELDS if name not in chunk]
    return missing


class HandoffStore(Protocol):
    def append(self, record: HandoffRecord) -> None: ...


class JsonlHandoffStore:
    """Appends one JSON line per record (spec 02, "Locally")."""

    def __init__(self, path: Path | str):
        self.path = Path(path)

    def append(self, record: HandoffRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record.to_dict(), ensure_ascii=False)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
