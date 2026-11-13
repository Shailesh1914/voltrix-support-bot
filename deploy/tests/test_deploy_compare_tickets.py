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


def test_cited_articles_compared_as_a_set_ignoring_order():
    a = ct.outcome_of(response("answered", ["KB-002", "KB-001"]))
    b = ct.outcome_of(response("answered", ["KB-001", "KB-002", "KB-001"]))
    assert ct.verdict(a, b) == "match"


@pytest.mark.parametrize("laptop, container", [
    (response("answered", ["KB-001"]), response("answered", ["KB-001", "KB-030"])),
    (response("answered", ["KB-001"]), response("escalated", reason="low_similarity")),
    (response("escalated", reason="low_similarity"), response("answered", [])),
])
def test_a_different_decision_or_article_set_is_a_mismatch(laptop, container):
    assert ct.verdict(ct.outcome_of(laptop), ct.outcome_of(container)) == "MISMATCH"


def test_two_escalations_match_on_decision_even_with_different_reasons():
    """AC-D4 compares the decision and the cited articles only."""
    a = ct.outcome_of(response("escalated", reason="low_similarity"))
    b = ct.outcome_of(response("escalated", reason="no_grounding"))
    assert ct.verdict(a, b) == "match"


@pytest.mark.parametrize("side", ["laptop", "container"])
def test_a_service_error_on_either_side_is_inconclusive(side):
    ok = ct.outcome_of(response("escalated", reason="low_similarity"))
    err = ct.outcome_of(response("escalated", reason="service_error"))
    pair = (err, ok) if side == "laptop" else (ok, err)
    assert ct.verdict(*pair) == "inconclusive"


def test_not_a_response_object_is_an_error():
    with pytest.raises(ct.CompareError):
        ct.outcome_of({"answer": "no status"})


def test_compare_asks_both_sides_with_the_ticket_text_unchanged():
    tickets = ct.load_tickets()
    seen = {"laptop": [], "container": []}

    def bot(side, reason):
        def ask(q):
            seen[side].append(q)
            if q == tickets[0]["question"]:
                return response("answered", ["KB-001"])
            return response("escalated", reason=reason)
        return ask

    laptop, container = bot("laptop", "x"), bot("container", "y")

    rows = ct.compare(tickets, laptop, container)
    assert seen["laptop"] == seen["container"] == [t["question"] for t in tickets]
    assert [r[4] for r in rows] == ["match", "match", "match"]
    assert ct.exit_code(rows) == ct.EXIT_MATCH


def test_exit_codes():
    m = ("T", "answer", None, None, "match")
    x = ("T", "answer", None, None, "MISMATCH")
    i = ("T", "answer", None, None, "inconclusive")
    assert ct.exit_code([m, m, m]) == 0
    assert ct.exit_code([m, i, m]) == 4
    assert ct.exit_code([i, x, m]) == 1


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
    http, _ = fake_http({
        ("GET", "health"): lambda h, b: (200, {"kb_version": "v2"}),
        ("POST", "ask"): lambda h, b: (
            (400, {"error": "question is empty"}) if b["question"] == " "
            else (200, response("answered", ["KB-001"]))),
    })
    monkeypatch.setattr(ct, "http", http)
    monkeypatch.setattr(ct, "laptop_asker", lambda: (lambda q: response("answered", ["KB-001"])))
    kb_file = tmp_path / "ACTIVE_KB_VERSION"
    kb_file.write_text("v2\n")
    monkeypatch.setattr(ct, "ACTIVE_KB_VERSION_FILE", kb_file)
    code = ct.main(["--confirm"])
    out = capsys.readouterr()
    assert CODE not in out.out + out.err
    assert code == ct.EXIT_MATCH
