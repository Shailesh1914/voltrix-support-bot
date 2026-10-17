"""Part A (real flow) against the committed Part A2 simulation."""

import json

import pytest

from evals import run_eval
from evals.eval_compare import ADOPTED_EXPERIMENT, compare_with_part_a2
from evals.eval_recorders import EvalError
from evals.eval_report import part_a_markdown

SHA = "c" * 64
E = ADOPTED_EXPERIMENT


@pytest.fixture
def part_a(make_ticket, fake_retriever):
    tickets = [
        make_ticket("T-001", ids=("KB-001",), question="drive shows e1 when ramping"),
        make_ticket("T-002", ids=("KB-001", "KB-020"), category="parameters", question="how do i set the ramp"),
        make_ticket("T-003", expected="escalate", question="display shows E-21, what is it"),
    ]
    data = run_eval.part_a(tickets, fake_retriever())
    return {"date": "2026-10-17", "git_commit": "abc", "git_dirty": False, "ticket_file_sha256": SHA, **data}


@pytest.fixture
def compare(tmp_path, part_a, make_part_a2):
    """compare(change) writes a Part A2 report equal to part_a, applies
    change(a2) to it, and compares."""

    def _compare(change=None):
        a2 = make_part_a2(part_a, SHA)
        if change:
            change(a2)
        path = tmp_path / "a2.json"
        path.write_text(json.dumps(a2), encoding="utf-8")
        return compare_with_part_a2(part_a, path)

    return _compare


def fields(result):
    return [(d["ticket_id"], d["field"]) for d in result["differences"]]


def test_identical_results_match(compare, tmp_path):
    result = compare()
    assert result["match"] is True
    assert (result["tickets_matching"], result["tickets_compared"]) == (3, 3)
    assert result["differences"] == [] and result["max_score_difference"] == 0.0
    assert result["part_a2_report"] == str(tmp_path / "a2.json")
    assert len(result["part_a2_report_sha256"]) == 64
    assert (result["part_a2_git_commit"], result["part_a2_git_dirty"]) == ("a2commit", True)
    assert result["summary"]["full"]["part_a"] == result["summary"]["full"]["part_a2"]


def test_chunk_order_and_ids_are_compared(compare):
    def swap(a2):
        sim = a2["tickets"][1]["results"][E]
        sim["top_chunk_ids"].reverse()

    result = compare(swap)
    assert result["match"] is False
    assert fields(result) == [("T-002", "chunk_ids")]
    assert result["tickets_matching"] == 2


def test_article_ids_are_compared(compare):
    def other(a2):
        a2["tickets"][0]["results"][E]["top_article_ids"] = ["KB-002", "KB-020"]

    assert fields(compare(other)) == [("T-001", "article_ids")]


def test_score_beyond_tolerance_is_a_difference(compare):
    def nudge(a2):
        a2["tickets"][2]["results"][E]["top_score"] += 1e-6

    result = compare(nudge)
    assert fields(result) == [("T-003", "top_score")]
    assert result["max_score_difference"] == pytest.approx(1e-6)


def test_float_noise_within_tolerance_matches(compare):
    def noise(a2):
        a2["tickets"][2]["results"][E]["top_score"] += 1e-12

    assert compare(noise)["match"] is True


def test_query_and_searched_texts_are_compared(compare):
    def change(a2):
        a2["tickets"][0]["query_sent"] = "drive shows e1 when ramping"
        a2["tickets"][1]["boost_titles"] = ["E-01 Overcurrent during acceleration"]

    assert fields(compare(change)) == [
        ("T-001", "query_sent"),
        ("T-001", "searched_texts"),
        ("T-002", "searched_texts"),
    ]


def test_recall_flags_are_compared(compare):
    def flip(a2):
        a2["tickets"][1]["results"][E]["both_hit"] = False

    assert fields(compare(flip)) == [("T-002", "both_hit")]


def test_summary_difference_alone_is_a_mismatch(compare):
    def change(a2):
        a2["summary"]["holdout"][E]["recall"] = {"passed": 0, "total": 1, "rate": 0.0}

    result = compare(change)
    assert result["differences"] == [] and result["match"] is False


@pytest.mark.parametrize(
    "change, message",
    [
        (lambda a2: a2.update(ticket_file_sha256="d" * 64), "different ticket file"),
        (lambda a2: a2.update(kb_version="v2"), "kb"),
        (lambda a2: a2.update(experiments={"E2+E3": "x"}), "no E1\\+E2\\+E3"),
        (lambda a2: a2["tickets"].pop(), "same tickets"),
        (lambda a2: a2.update(kind="part-a"), "not a Part A2 report"),
    ],
)
def test_reports_that_cannot_be_compared_fail_loudly(compare, change, message):
    with pytest.raises(EvalError, match=message):
        compare(change)


def test_missing_report_fails_loudly(part_a, tmp_path):
    with pytest.raises(EvalError, match="cannot read"):
        compare_with_part_a2(part_a, tmp_path / "missing.json")


def test_markdown_shows_the_comparison(compare, part_a):
    md = part_a_markdown({**part_a, "against_part_a2": compare()})
    assert "## Against the Part A2 simulation (E1+E2+E3)" in md
    assert "**MATCH**: 3/3 tickets match" in md
    assert "### Differences\n\nNone." in md

    def swap(a2):
        a2["tickets"][1]["results"][E]["top_chunk_ids"].reverse()

    md = part_a_markdown({**part_a, "against_part_a2": compare(swap)})
    assert "**MISMATCH**: 2/3 tickets match" in md
    assert "| T-002 | chunk_ids | KB-001#c1, KB-020#c2 | KB-020#c2, KB-001#c1 |" in md
