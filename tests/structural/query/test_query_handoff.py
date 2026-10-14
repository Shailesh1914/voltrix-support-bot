"""Stage b: handoff record and JSONL store (spec 02, "Escalation
handoff", decision 8, criterion 3)."""

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from query.handoff import (
    CHUNK_FIELDS,
    ESCALATION_REASONS,
    HANDOFF_FIELDS,
    JsonlHandoffStore,
    build_handoff,
    missing_fields,
)

TIME = datetime(2026, 10, 11, 9, 30, tzinfo=timezone.utc)


@pytest.fixture
def record(make_chunk):
    def _make(reason="low_similarity", chunks=None, created_at=TIME):
        return build_handoff(
            question_received="e1 again, call [PHONE]",
            question_normalised="E-01 again, call [PHONE]",
            chunks=chunks if chunks is not None else [make_chunk(n=1, score=0.4), make_chunk(n=2, score=0.3)],
            escalation_reason=reason,
            kb_version="v1",
            created_at=created_at,
        )

    return _make


def test_field_lists_match_spec_02():
    # Written out from spec 02 "Escalation handoff" and decision 8, so the
    # completeness check cannot lose a field along with the code.
    assert set(HANDOFF_FIELDS) == {
        "handoff_id",
        "created_at",
        "question_received",
        "question_normalised",
        "retrieved_chunks",
        "escalation_reason",
        "kb_version",
        "rejected_answer",  # decision 11
        "failed_check",  # decision 11
    }
    assert set(CHUNK_FIELDS) == {"chunk_id", "article_id", "text", "similarity_score"}


def test_spec_fields_and_nothing_else(record):
    assert list(record().to_dict()) == list(HANDOFF_FIELDS)


def test_record_is_complete(record):
    assert missing_fields(record().to_dict()) == []


@pytest.mark.parametrize("field", HANDOFF_FIELDS)
def test_missing_field_is_detected(record, field):
    data = record().to_dict()
    del data[field]
    assert field in missing_fields(data)


@pytest.mark.parametrize("field", CHUNK_FIELDS)
def test_missing_chunk_field_is_detected(record, field):
    data = record().to_dict()
    del data["retrieved_chunks"][1][field]
    assert missing_fields(data) == [f"retrieved_chunks[1].{field}"]


def test_chunks_keep_spec_fields_and_order(record, make_chunk):
    chunks = [make_chunk("KB-002", n=3, score=0.41), make_chunk("KB-001", n=1, score=0.40)]
    stored = record(chunks=chunks).to_dict()["retrieved_chunks"]
    assert stored == [
        {"chunk_id": c.chunk_id, "article_id": c.article_id, "text": c.text, "similarity_score": c.similarity_score}
        for c in chunks
    ]


def test_handoff_id_is_unique_uuid4(record):
    ids = {record().handoff_id for _ in range(100)}
    assert len(ids) == 100
    assert all(uuid.UUID(i).version == 4 for i in ids)


def test_created_at_is_utc_iso(record):
    other_zone = TIME.astimezone(timezone(timedelta(hours=5, minutes=30)))
    assert record(created_at=other_zone).created_at == "2026-10-11T09:30:00+00:00"


def test_naive_time_is_rejected(record):
    with pytest.raises(ValueError, match="timezone"):
        record(created_at=datetime(2026, 10, 11, 9, 30))


@pytest.mark.parametrize("reason", sorted(ESCALATION_REASONS))
def test_every_spec_reason_is_accepted(record, reason):
    assert record(reason=reason).escalation_reason == reason


def test_unknown_reason_is_rejected(record):
    with pytest.raises(ValueError, match="escalation_reason"):
        record(reason="low_confidence")


def test_jsonl_store_appends_one_line_per_record(tmp_path, record):
    path = tmp_path / "handoffs" / "handoffs.jsonl"  # folder created on demand
    store = JsonlHandoffStore(path)
    first, second = record(), record(reason="out_of_scope")
    store.append(first)
    store.append(second)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line) for line in lines] == [first.to_dict(), second.to_dict()]
    assert all(missing_fields(json.loads(line)) == [] for line in lines)


def test_jsonl_store_keeps_existing_records(tmp_path, record):
    path = tmp_path / "handoffs.jsonl"
    path.write_text('{"earlier": true}\n', encoding="utf-8")
    JsonlHandoffStore(path).append(record())
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2


def test_non_ascii_text_stored_readably(tmp_path, make_chunk, record):
    path = tmp_path / "h.jsonl"
    JsonlHandoffStore(path).append(record(chunks=[make_chunk(text="85 °C, 10 kΩ, 4700 µF")]))
    assert "85 °C, 10 kΩ, 4700 µF" in path.read_text(encoding="utf-8")


# --- Decision 11: rejected_answer and failed_check ------------------------------------


def test_rejected_answer_and_failed_check_default_empty(record):
    data = record().to_dict()
    assert (data["rejected_answer"], data["failed_check"]) == ("", "")


@pytest.mark.parametrize("check", ["no_citations", "citation", "grounding"])
def test_rejected_answer_stored_with_its_check(make_chunk, check):
    stored = build_handoff(
        question_received="q",
        question_normalised="q",
        chunks=[make_chunk()],
        escalation_reason="insufficient_context",
        kb_version="v1",
        created_at=TIME,
        rejected_answer="Set P-09.",
        failed_check=check,
    ).to_dict()
    assert (stored["rejected_answer"], stored["failed_check"]) == ("Set P-09.", check)


@pytest.mark.parametrize(
    "rejected_answer, failed_check",
    [("draft", ""), ("", "grounding"), ("draft", "safety")],
)
def test_invalid_rejected_answer_and_failed_check(make_chunk, rejected_answer, failed_check):
    with pytest.raises(ValueError):
        build_handoff(
            question_received="q",
            question_normalised="q",
            chunks=[make_chunk()],
            escalation_reason="insufficient_context",
            kb_version="v1",
            created_at=TIME,
            rejected_answer=rejected_answer,
            failed_check=failed_check,
        )
