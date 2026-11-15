"""Tests of compare_tickets.py (AC-D4) with fakes: no Claude call, no
container, no secrets file."""

import json

import pytest

import compare_tickets as ct


def response(status, articles=(), reason=""):
    return {
        "status": status,
        "answer": "text",
        "citations": [{"article_id": a, "title": f"title {a}"} for a in articles],
        "escalation_reason": reason,
        "handoff_id": "H-1" if status == "escalated" else "",
    }


def test_the_three_tickets_have_the_labels_round_2_names():
    tickets = ct.load_tickets()
    assert [(t["ticket_id"], t["expected"]) for t in tickets] == [
        ("T-001", "answer"), ("T-002", "answer"), ("T-043", "escalate")]


def test_a_wrong_label_or_missing_ticket_stops(tmp_path):
    path = tmp_path / "t.jsonl"
    path.write_text(json.dumps({"ticket_id": "T-001", "question": "q", "expected": "escalate"}) + "\n")
    with pytest.raises(ct.CompareError, match="labelled 'escalate'"):
        ct.load_tickets(path, (("T-001", "answer"),))
    with pytest.raises(ct.CompareError, match="T-002 is not in"):
        ct.load_tickets(path, (("T-002", "answer"),))


def tickets_by_id():
    return {t["ticket_id"]: t for t in ct.load_tickets()}


def v(ticket_id, laptop, container):
    return ct.verdict(tickets_by_id()[ticket_id], ct.outcome_of(laptop), ct.outcome_of(container))


def test_the_labels_the_rule_uses_come_from_the_frozen_file():
    t = tickets_by_id()
    assert (t["T-001"]["expected"], t["T-001"]["expected_article_ids"]) == ("answer", ["KB-001"])
    assert (t["T-002"]["expected"], t["T-002"]["expected_article_ids"]) == ("answer", ["KB-002"])
    assert (t["T-043"]["expected"], t["T-043"]["expected_article_ids"]) == ("escalate", [])


def test_the_round_4_t002_result_passes_as_differs_both_valid():
    """Laptop [KB-002, KB-025], Lambda [KB-002]: both cite KB-002, which
    is T-002's expected article, so both pass spec 05 AC1."""
    assert v("T-002", response("answered", ["KB-002", "KB-025"]), response("answered", ["KB-002"])) == ct.DIFFERS_VALID


def test_cited_articles_compared_as_a_set_ignoring_order():
    a = response("answered", ["KB-025", "KB-002"])
    b = response("answered", ["KB-002", "KB-025", "KB-002"])
    assert v("T-002", a, b) == ct.MATCH


@pytest.mark.parametrize("laptop, container", [
    (response("answered", ["KB-001"]), response("escalated", reason="low_similarity")),
    (response("escalated", reason="low_similarity"), response("answered", ["KB-001"])),
])
def test_a_different_decision_is_a_mismatch(laptop, container):
    assert v("T-001", laptop, container) == ct.MISMATCH


@pytest.mark.parametrize("laptop, container, result", [
    (response("answered", ["KB-001"]), response("answered", ["KB-030"]), "INVALID (container)"),
    (response("answered", ["KB-030"]), response("answered", ["KB-001", "KB-030"]), "INVALID (laptop)"),
    (response("answered", []), response("answered", ["KB-002"]), "INVALID (both)"),
])
def test_citations_not_acceptable_for_the_label_fail(laptop, container, result):
    assert v("T-001", laptop, container) == result


def test_an_escalate_ticket_answered_on_both_sides_is_invalid():
    """The same decision is not enough: it must also be the labelled one."""
    assert v("T-043", response("answered", ["KB-001"]), response("answered", ["KB-001"])) == "INVALID (both)"


def test_two_escalations_match_on_decision_even_with_different_reasons():
    """AC2 accepts any escalation reason except service_error."""
    a = response("escalated", reason="low_similarity")
    b = response("escalated", reason="no_grounding")
    assert v("T-043", a, b) == ct.MATCH


@pytest.mark.parametrize("side", ["laptop", "container"])
def test_a_service_error_on_either_side_is_inconclusive(side):
    ok = response("escalated", reason="low_similarity")
    err = response("escalated", reason="service_error")
    pair = (err, ok) if side == "laptop" else (ok, err)
    assert v("T-043", *pair) == ct.INCONCLUSIVE


def test_the_rule_is_spec_05s_own_scoring():
    """valid_for_label agrees with evals/eval_scoring.passes on every case."""
    from evals.eval_scoring import Outcome as Scored, passes
    from evals.eval_tickets import parse_ticket
    for ticket in ct.load_tickets():
        for o in (response("answered", ["KB-001"]), response("answered", ["KB-002"]), response("answered", []),
                  response("escalated", reason="low_similarity"), response("escalated", reason="service_error")):
            mine = ct.valid_for_label(ticket, ct.outcome_of(o))
            theirs = passes(parse_ticket(ticket, 0), Scored(o["status"], o["escalation_reason"],
                                                           tuple(c["article_id"] for c in o["citations"])))
            assert mine == theirs


def test_not_a_response_object_is_an_error():
    with pytest.raises(ct.CompareError):
        ct.outcome_of({"answer": "no status"})


def good_bot(seen=None, side="", t002=("KB-002",)):
    """Answers T-001 and T-002 with their expected articles, escalates T-043."""
    t = tickets_by_id()
    answers = {t["T-001"]["question"]: response("answered", ["KB-001"]),
               t["T-002"]["question"]: response("answered", list(t002)),
               t["T-043"]["question"]: response("escalated", reason="insufficient_context")}

    def ask(q):
        if seen is not None:
            seen[side].append(q)
        return answers[q]
    return ask


def test_compare_asks_both_sides_with_the_ticket_text_unchanged():
    tickets = ct.load_tickets()
    seen = {"laptop": [], "container": []}
    rows = ct.compare(tickets, good_bot(seen, "laptop", ("KB-002", "KB-025")), good_bot(seen, "container"))
    assert seen["laptop"] == seen["container"] == [t["question"] for t in tickets]
    assert [r[4] for r in rows] == [ct.MATCH, ct.DIFFERS_VALID, ct.MATCH]
    assert ct.exit_code(rows) == ct.EXIT_MATCH


def test_exit_codes():
    def row(result):
        return ("T", "answer", None, None, result)

    m, d, i = row(ct.MATCH), row(ct.DIFFERS_VALID), row(ct.INCONCLUSIVE)
    assert ct.exit_code([m, d, m]) == ct.EXIT_MATCH
    assert ct.exit_code([m, i, d]) == ct.EXIT_INCONCLUSIVE
    assert ct.exit_code([i, row(ct.MISMATCH), m]) == ct.EXIT_FAILED
    assert ct.exit_code([d, row("INVALID (container)"), m]) == ct.EXIT_FAILED


def test_without_confirm_nothing_is_called(monkeypatch, capsys):
    def fail(*a, **k):
        raise AssertionError("no call may be made in a dry run")

    monkeypatch.setattr(ct, "http", fail)
    monkeypatch.setattr(ct.subprocess, "run", fail)
    monkeypatch.setattr(ct.getpass, "getpass", fail)
    for name in [n for n in ct.os.environ if n.startswith("ANTHROPIC_")]:
        monkeypatch.delenv(name)
    assert ct.main([]) == ct.EXIT_DRY_RUN
    assert "no calls made" in capsys.readouterr().out


def test_an_anthropic_variable_stops_before_any_call(monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr(ct.getpass, "getpass", lambda *a: pytest.fail("asked for the code"))
    assert ct.main(["--confirm"]) == ct.EXIT_FAILED
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err


CODE = "the-access-code-123"


def fake_http(answers):
    calls = []

    def http(method, url, headers=None, body=None):
        calls.append((method, url, headers, body))
        return answers[(method, url.rsplit("/", 1)[1])](headers, body)

    return http, calls


def test_preflight_checks_kb_version_and_the_code_without_a_paid_call(monkeypatch):
    http, calls = fake_http({
        ("GET", "health"): lambda h, b: (200, {"status": "ok", "kb_version": "v2"}),
        ("POST", "ask"): lambda h, b: (400, {"error": "question is empty"}),
    })
    monkeypatch.setattr(ct, "http", http)
    ct.preflight("http://x", CODE, "v2")
    assert calls[1][3] == {"question": " "}  # blank: refused before retrieval or Claude


def test_preflight_stops_on_a_wrong_code_or_kb_version(monkeypatch):
    http, _ = fake_http({
        ("GET", "health"): lambda h, b: (200, {"kb_version": "v2"}),
        ("POST", "ask"): lambda h, b: (401, {"error": "access denied"}),
    })
    monkeypatch.setattr(ct, "http", http)
    with pytest.raises(ct.CompareError, match="refused the access code"):
        ct.preflight("http://x", CODE, "v2")
    with pytest.raises(ct.CompareError, match="kb_version"):
        ct.preflight("http://x", CODE, "v1")


def test_the_access_code_is_never_printed(monkeypatch, capsys, tmp_path):
    for name in [n for n in ct.os.environ if n.startswith("ANTHROPIC_")]:
        monkeypatch.delenv(name)
    monkeypatch.setattr(ct.getpass, "getpass", lambda *a: CODE)
    container = good_bot()
    http, _ = fake_http({
        ("GET", "health"): lambda h, b: (200, {"kb_version": "v2"}),
        ("POST", "ask"): lambda h, b: (
            (400, {"error": "question is empty"}) if b["question"] == " "
            else (200, container(b["question"]))),
    })
    monkeypatch.setattr(ct, "http", http)
    monkeypatch.setattr(ct, "laptop_asker", lambda: good_bot(t002=("KB-002", "KB-025")))
    kb_file = tmp_path / "ACTIVE_KB_VERSION"
    kb_file.write_text("v2\n")
    monkeypatch.setattr(ct, "ACTIVE_KB_VERSION_FILE", kb_file)
    code = ct.main(["--confirm"])
    out = capsys.readouterr()
    assert CODE not in out.out + out.err
    assert code == ct.EXIT_MATCH
