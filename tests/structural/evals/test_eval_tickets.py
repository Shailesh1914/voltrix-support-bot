"""Ticket loading and the fixed odd/even split (spec 05, "Data split")."""

import json

import pytest

from evals.eval_scoring import Outcome, ac1_pass, counts_for_both_cited, retrieval_row
from evals.eval_tickets import (
    CALIBRATION,
    FULL,
    HOLDOUT,
    TICKETS_PATH,
    TicketError,
    file_sha256,
    load_tickets,
    select,
    ticket_number,
)


def write_lines(path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return path


def raw(ticket_id="T-001", **overrides):
    row = {
        "ticket_id": ticket_id,
        "question": "q",
        "expected": "answer",
        "expected_article_ids": ["KB-001"],
        "category": "fault",
        "notes": "",
    }
    row.update(overrides)
    return row


@pytest.mark.parametrize(
    "ticket_id, number",
    [("T-001", 1), ("T-002", 2), ("T-060", 60), ("T-101", 101), ("T-110", 110)],
)
def test_ticket_number(ticket_id, number):
    assert ticket_number(ticket_id) == number


@pytest.mark.parametrize("bad", ["T001", "T-", "T-1a", "X-001", "t-001", " T-001", "", None, 1])
def test_ticket_number_rejects_bad_ids(bad):
    with pytest.raises(TicketError):
        ticket_number(bad)


@pytest.mark.parametrize(
    "ticket_id, split", [("T-001", CALIBRATION), ("T-002", HOLDOUT), ("T-101", CALIBRATION), ("T-110", HOLDOUT)]
)
def test_odd_numbers_calibrate_even_numbers_are_holdout(make_ticket, ticket_id, split):
    assert make_ticket(ticket_id).split == split


def test_real_ticket_file_split():
    tickets = load_tickets()
    assert len(tickets) == 70
    for name in (CALIBRATION, HOLDOUT):
        part = select(tickets, name)
        assert len(part) == 35
        assert sum(t.expected == "answer" for t in part) == 24
        assert sum(t.expected == "escalate" for t in part) == 11
        assert all(t.split == name for t in part)
    assert select(tickets, FULL) == tickets
    calibration_ids = {t.ticket_id for t in select(tickets, CALIBRATION)}
    holdout_ids = {t.ticket_id for t in select(tickets, HOLDOUT)}
    assert not calibration_ids & holdout_ids


def test_real_ticket_file_any_match_ticket():
    # Which tickets use "any" changes with each label review (spec 07 step 2),
    # so this checks how "any" tickets are parsed and scored, not which ones
    # they are. The raw file is read independently of load_tickets().
    raw_rows = [json.loads(line) for line in TICKETS_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    by_id = {t.ticket_id: t for t in load_tickets()}
    assert set(by_id) == {r["ticket_id"] for r in raw_rows}
    any_ids = []
    for r in raw_rows:
        t = by_id[r["ticket_id"]]
        assert t.article_match == r.get("article_match", "all")  # absent means "all"
        assert t.expected_article_ids == tuple(r["expected_article_ids"])
        if t.article_match == "any":
            any_ids.append(t.ticket_id)
    assert any_ids, "the ticket file has no article_match 'any' ticket to check"

    for ticket_id in any_ids:
        t = by_id[ticket_id]
        # "any" widens an answer label: at least two accepted articles.
        assert t.expected == "answer" and len(t.expected_article_ids) >= 2, ticket_id
        # Never counted as needing both articles (clarification 2) ...
        assert not counts_for_both_cited(t), ticket_id
        for article in t.expected_article_ids:
            # ... and any ONE accepted article is enough, for retrieval recall
            # and for AC1 ...
            assert retrieval_row(t, [article, "KB-999"]) == {"recall_hit": True, "both_hit": None}, ticket_id
            assert ac1_pass(t, Outcome("answered", cited_article_ids=(article,))), ticket_id
        # ... but none of them is a miss.
        assert retrieval_row(t, ["KB-999"])["recall_hit"] is False, ticket_id
        assert not ac1_pass(t, Outcome("answered", cited_article_ids=("KB-999",))), ticket_id
        assert not ac1_pass(t, Outcome("escalated", "insufficient_context", t.expected_article_ids)), ticket_id


def test_loading_never_changes_the_ticket_file():
    before = file_sha256(TICKETS_PATH)
    load_tickets()
    assert file_sha256(TICKETS_PATH) == before


def test_duplicate_ticket_id_fails(tmp_path):
    path = write_lines(tmp_path / "t.jsonl", [raw("T-001"), raw("T-001")])
    with pytest.raises(TicketError, match="duplicate"):
        load_tickets(path)


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"expected": "maybe"}, "expected must be"),
        ({"expected_article_ids": []}, "at least one expected article"),
        ({"expected_article_ids": "KB-001"}, "list of strings"),
        ({"article_match": "some"}, "article_match"),
        ({"ticket_id": "T1"}, "ticket_id"),
    ],
)
def test_bad_ticket_fails_loudly(tmp_path, overrides, message):
    path = write_lines(tmp_path / "t.jsonl", [raw(**overrides)])
    with pytest.raises(TicketError, match=message):
        load_tickets(path)


def test_missing_field_fails(tmp_path):
    row = raw()
    del row["category"]
    with pytest.raises(TicketError, match="category"):
        load_tickets(write_lines(tmp_path / "t.jsonl", [row]))


def test_invalid_json_and_empty_file_fail(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text("{not json\n", encoding="utf-8")
    with pytest.raises(TicketError, match="line 1"):
        load_tickets(bad)
    empty = tmp_path / "empty.jsonl"
    empty.write_text("\n", encoding="utf-8")
    with pytest.raises(TicketError, match="no tickets"):
        load_tickets(empty)


def test_unknown_set_name(make_ticket):
    with pytest.raises(ValueError):
        select([make_ticket()], "everything")
