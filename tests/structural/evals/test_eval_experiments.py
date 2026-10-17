"""Part A2: retrieval experiments, simulated with a fake retriever."""

import json

import pytest

import ingestion
from evals import run_eval
from evals.eval_experiments import (
    BGE_QUERY_PREFIX,
    EXPERIMENTS,
    boost_queries,
    code_titles,
    diversify,
    fault_codes_in,
    merge,
    run_experiment,
)
from evals.eval_tickets import TICKETS_PATH, file_sha256
from ingestion import KBInfo

E01_TITLE = "E-01 Overcurrent during acceleration"
E02_TITLE = "E-02 Overcurrent during deceleration"


class ScriptedRetriever:
    """search() returns results[query] cut to k, and records every call."""

    def __init__(self, results, articles):
        self.results = results
        self.articles = articles
        self.calls: list[tuple[str, int]] = []

    def search(self, query, k):
        self.calls.append((query, k))
        return self.results.get(query, [])[:k]

    def kb_info(self):
        return KBInfo("v1", self.articles)


def test_fault_codes_in():
    assert fault_codes_in("E-01 then E-09 and E-01 again") == ["E-01", "E-09"]
    assert fault_codes_in("XE-01 or E-012 or E-1") == ["E-012"]
    assert fault_codes_in("no codes") == []


def test_code_titles_and_boost_queries(fake_articles):
    titles = code_titles(KBInfo("v1", fake_articles))
    assert titles == {"E-01": [E01_TITLE], "E-02": [E02_TITLE]}
    assert boost_queries("trips with E-02 then E-01", titles) == [E02_TITLE, E01_TITLE]
    # Unknown codes are not boosted.
    assert boost_queries("display shows E-21", titles) == []


def test_merge_keeps_higher_score_and_spec_03_order(make_chunk):
    a = [make_chunk("KB-001#c1", 0.70), make_chunk("KB-002#c1", 0.60)]
    b = [make_chunk("KB-002#c1", 0.90), make_chunk("KB-020#c2", 0.70), make_chunk("KB-020#c1", 0.70)]
    merged = merge(a, b)
    assert [(c.chunk_id, c.similarity_score) for c in merged] == [
        ("KB-002#c1", 0.90),
        ("KB-001#c1", 0.70),
        ("KB-020#c1", 0.70),
        ("KB-020#c2", 0.70),
    ]


def test_diversify_best_chunk_per_article_up_to_five(make_chunk):
    chunks = [make_chunk(f"KB-00{n % 3 + 1}#c{n}", 0.9 - n * 0.01) for n in range(1, 10)]
    picked = diversify(chunks)
    assert [c.chunk_id for c in picked] == ["KB-002#c1", "KB-003#c2", "KB-001#c3"]
    many = [make_chunk(f"KB-0{n:02d}#c1", 0.9 - n * 0.01) for n in range(1, 9)]
    assert [c.article_id for c in diversify(many)] == ["KB-001", "KB-002", "KB-003", "KB-004", "KB-005"]


@pytest.fixture
def scripted(make_chunk, fake_articles):
    question = "drive trips with E-02 when stopping"
    wide = [make_chunk("KB-020#c1", 0.80), make_chunk("KB-020#c2", 0.79), make_chunk("KB-020#c3", 0.78),
            make_chunk("KB-020#c4", 0.77), make_chunk("KB-020#c5", 0.76), make_chunk("KB-019#c1", 0.70),
            make_chunk("KB-002#c3", 0.65)]
    results = {
        question: wide,
        BGE_QUERY_PREFIX + question: [make_chunk("KB-002#c1", 0.85), make_chunk("KB-019#c2", 0.84),
                                      make_chunk("KB-019#c3", 0.83), make_chunk("KB-001#c1", 0.60)],
        E02_TITLE: [make_chunk("KB-002#c1", 0.95), make_chunk("KB-002#c2", 0.90)],
        BGE_QUERY_PREFIX + E02_TITLE: [make_chunk("KB-002#c2", 0.93), make_chunk("KB-022#c1", 0.88)],
    }
    return question, ScriptedRetriever(results, fake_articles)


def ids(chunks):
    return [c.chunk_id for c in chunks]


def test_baseline_and_e1(scripted):
    question, r = scripted
    titles = code_titles(r.kb_info())
    assert ids(run_experiment("baseline", r, question, titles)) == [f"KB-020#c{n}" for n in range(1, 6)]
    assert ids(run_experiment("E1", r, question, titles)) == ["KB-002#c1", "KB-019#c2", "KB-019#c3", "KB-001#c1"]
    assert r.calls == [(question, 5), (BGE_QUERY_PREFIX + question, 5)]


def test_e2_searches_wide_and_diversifies(scripted):
    question, r = scripted
    assert ids(run_experiment("E2", r, question, code_titles(r.kb_info()))) == ["KB-020#c1", "KB-019#c1", "KB-002#c3"]
    assert r.calls == [(question, 20)]


def test_e3_adds_title_search_and_merges_top_five(scripted):
    question, r = scripted
    got = ids(run_experiment("E3", r, question, code_titles(r.kb_info())))
    assert got == ["KB-002#c1", "KB-002#c2", "KB-020#c1", "KB-020#c2", "KB-020#c3"]
    assert r.calls == [(question, 5), (E02_TITLE, 5)]


def test_e2_plus_e3(scripted):
    question, r = scripted
    got = ids(run_experiment("E2+E3", r, question, code_titles(r.kb_info())))
    assert got == ["KB-002#c1", "KB-020#c1", "KB-019#c1"]
    assert r.calls == [(question, 20), (E02_TITLE, 20)]


def test_e1_plus_e3_prefixes_every_search(scripted):
    question, r = scripted
    got = ids(run_experiment("E1+E3", r, question, code_titles(r.kb_info())))
    assert got == ["KB-002#c2", "KB-022#c1", "KB-002#c1", "KB-019#c2", "KB-019#c3"]
    assert r.calls == [(BGE_QUERY_PREFIX + question, 5), (BGE_QUERY_PREFIX + E02_TITLE, 5)]


def test_e1_plus_e2_plus_e3(scripted):
    question, r = scripted
    got = ids(run_experiment("E1+E2+E3", r, question, code_titles(r.kb_info())))
    assert got == ["KB-002#c2", "KB-022#c1", "KB-019#c2", "KB-001#c1"]
    assert r.calls == [(BGE_QUERY_PREFIX + question, 20), (BGE_QUERY_PREFIX + E02_TITLE, 20)]


def test_codes_are_found_in_the_query_not_the_prefix(make_chunk, fake_articles):
    # The prefix holds no fault code, so a code-free query gets no boost.
    r = ScriptedRetriever({}, fake_articles)
    run_experiment("E1+E3", r, "how do i set the ramp", code_titles(r.kb_info()))
    assert r.calls == [(BGE_QUERY_PREFIX + "how do i set the ramp", 5)]


def test_every_listed_experiment_runs(scripted):
    question, r = scripted
    titles = code_titles(r.kb_info())
    assert EXPERIMENTS == ("baseline", "E1", "E2", "E3", "E2+E3", "E1+E3", "E1+E2+E3")
    for name in EXPERIMENTS:
        chunks = run_experiment(name, r, question, titles)
        assert 1 <= len(chunks) <= 5
        assert len({c.chunk_id for c in chunks}) == len(chunks)


def test_e3_without_known_code_equals_baseline(make_chunk, fake_articles):
    r = ScriptedRetriever({"q E-21": [make_chunk("KB-001#c1", 0.5)]}, fake_articles)
    titles = code_titles(r.kb_info())
    assert ids(run_experiment("E3", r, "q E-21", titles)) == ids(run_experiment("baseline", r, "q E-21", titles))


def test_unknown_experiment(scripted):
    question, r = scripted
    for bad in ("E9", "E1+E2", "E3+E2", ""):
        with pytest.raises(ValueError):
            run_experiment(bad, r, question, {})


def boosted_fake(fake_retriever):
    """Baseline finds only KB-020; the E-02 title search finds KB-002."""

    def scores(query):
        if query == E02_TITLE:
            return [("KB-002", 0.95)]
        if query.startswith(BGE_QUERY_PREFIX):
            return [("KB-019", 0.80)]
        return [("KB-020", 0.80), ("KB-001", 0.60)]

    return fake_retriever(scores)


def test_part_a2_compares_with_baseline(make_ticket, fake_retriever):
    tickets = [
        make_ticket("T-001", ids=("KB-002",), question="E2 when stopping the mixer"),
        make_ticket("T-002", ids=("KB-020",), category="parameters", question="how do i set the ramp"),
        make_ticket("T-003", expected="escalate", question="display shows E-21"),
    ]
    data = run_eval.part_a2(tickets, boosted_fake(fake_retriever))
    rows = {r["ticket_id"]: r for r in data["tickets"]}

    # Starts from the flow's own normalised query (E2 -> E-02).
    assert "E-02" in rows["T-001"]["query_sent"]
    assert rows["T-001"]["boost_titles"] == [E02_TITLE]
    assert rows["T-003"]["boost_titles"] == []
    assert set(rows["T-001"]["results"]) == set(EXPERIMENTS)
    assert rows["T-001"]["results"]["baseline"]["recall_hit"] is False
    assert rows["T-001"]["results"]["E3"]["recall_hit"] is True

    full = data["summary"]["full"]
    assert full["baseline"]["recall"] == {"passed": 1, "total": 2, "rate": 0.5}
    assert full["E3"]["recall"]["passed"] == 2
    assert full["E3"]["gained"] == ["T-001"] and full["E3"]["lost"] == []
    assert full["E3"]["recall_change"] == 1
    # E1 finds only KB-019 here: it loses T-002 and gains nothing.
    assert full["E1"]["lost"] == ["T-002"] and full["E1"]["recall_change"] == -1
    assert data["summary"]["calibration"]["E3"]["improves_on_baseline"] is True
    assert data["summary"]["holdout"]["E3"]["improves_on_baseline"] is False
    assert full["baseline"]["improves_on_baseline"] is False


def test_part_a2_command_writes_reports_only(tmp_path, monkeypatch, fake_retriever):
    monkeypatch.setattr(ingestion, "open_retrieval", lambda kb_version: boosted_fake(fake_retriever))
    before = file_sha256(TICKETS_PATH)
    assert run_eval.main(["part-a2", "--date", "2026-10-17", "--reports-dir", str(tmp_path)]) == 0
    data = json.loads((tmp_path / "2026-10-17-part-a2-retrieval-experiments.json").read_text(encoding="utf-8"))
    md = (tmp_path / "2026-10-17-part-a2-retrieval-experiments.md").read_text(encoding="utf-8")
    assert data["kind"] == "part-a2" and len(data["tickets"]) == 70
    assert data["bge_query_prefix"] == BGE_QUERY_PREFIX
    assert "This report does not choose" in md and "## Against the baseline" in md
    assert file_sha256(TICKETS_PATH) == before
    assert len(list(tmp_path.iterdir())) == 2
