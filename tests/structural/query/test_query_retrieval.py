"""Retrieval, spec 02 Processing step 3 (v1.13; E2 and E3 adopted at Step 9).

Expected k and number of articles are always read from spec 02 (the
spec_retrieval fixture), never from query/config.py.
"""

import re
from pathlib import Path

import pytest

from ingestion import KBInfo
from query import config
from query.config import ConfigError
from query.fault_codes import DuplicateFaultCode, code_titles
from query.handoff import missing_fields
from query.retrieval import boost_titles, diversify, merge, retrieve

SPEC_03 = Path(__file__).resolve().parents[3] / "specs" / "03-retrieval-contract.md"

TITLE_E01 = "E-01 Overcurrent during acceleration"
TITLE_E02 = "E-02 Overcurrent during deceleration"
TITLES = {"E-01": TITLE_E01, "E-02": TITLE_E02, "E-03": "E-03 Overcurrent at constant speed"}


def ids(chunks):
    return [c.chunk_id for c in chunks]


def scores(chunks):
    return [c.similarity_score for c in chunks]


# --- Pinned values: config equals spec 02, within spec 03 -------------------------


def test_k_and_max_articles_equal_spec_02(spec_retrieval):
    assert config.SEARCH_K == spec_retrieval.main_k
    assert config.SEARCH_K == spec_retrieval.boost_k
    assert config.MAX_ARTICLES == spec_retrieval.max_articles


def test_spec_02_k_is_allowed_by_spec_03(spec_retrieval):
    match = re.search(r"k: integer from ([0-9]+) to ([0-9]+)", SPEC_03.read_text(encoding="utf-8"))
    low, high = int(match.group(1)), int(match.group(2))
    assert low <= spec_retrieval.main_k <= high
    assert low <= spec_retrieval.boost_k <= high


def test_retrieve_uses_spec_k(fake_retriever, spec_retrieval):
    retriever = fake_retriever(scores=())
    retrieve(retriever, "E-02 when stopping", TITLES)
    assert retriever.queries == [("E-02 when stopping", spec_retrieval.main_k), (TITLE_E02, spec_retrieval.boost_k)]


# --- Step 3c: merge ----------------------------------------------------------------


def test_merge_keeps_each_chunk_once_at_its_highest_score(make_chunk):
    main = [make_chunk("KB-001", n=1, score=0.6), make_chunk("KB-002", n=1, score=0.5)]
    boost = [make_chunk("KB-001", n=1, score=0.8)]
    merged = merge(main, boost)
    assert ids(merged) == ["KB-001#c1", "KB-002#c1"]
    assert scores(merged) == [0.8, 0.5]


def test_merge_keeps_the_higher_score_whichever_search_found_it(make_chunk):
    main = [make_chunk("KB-001", n=1, score=0.9)]
    boost = [make_chunk("KB-001", n=1, score=0.4)]
    assert scores(merge(main, boost)) == [0.9]
    assert scores(merge(boost, main)) == [0.9]


def test_merge_equal_score_in_both_searches_appears_once(make_chunk):
    chunk = make_chunk("KB-001", n=1, score=0.7)
    assert ids(merge([chunk], [chunk])) == ["KB-001#c1"]


def test_merge_sorts_by_score_then_chunk_id(make_chunk):
    main = [make_chunk("KB-010", n=1, score=0.7), make_chunk("KB-002", n=3, score=0.5)]
    boost = [make_chunk("KB-002", n=1, score=0.7), make_chunk("KB-002", n=2, score=0.9)]
    assert ids(merge(main, boost)) == ["KB-002#c2", "KB-002#c1", "KB-010#c1", "KB-002#c3"]


def test_merge_of_nothing_is_empty():
    assert merge([], []) == []


# --- Step 3d: diversity --------------------------------------------------------------


def test_diversity_keeps_best_chunk_of_each_article_up_to_spec_limit(make_chunk, spec_retrieval):
    articles = [f"KB-0{n:02d}" for n in range(1, 8)]  # 7 articles, 2 chunks each
    chunks = merge([
        make_chunk(a, n=c, score=round(0.9 - i * 0.05 - c * 0.01, 4))
        for i, a in enumerate(articles) for c in (1, 2)
    ])
    kept = diversify(chunks, spec_retrieval.max_articles)
    assert ids(kept) == [f"{a}#c1" for a in articles[: spec_retrieval.max_articles]]


def test_diversity_keeps_the_best_not_the_first_numbered_chunk(make_chunk):
    chunks = merge([make_chunk("KB-001", n=1, score=0.5), make_chunk("KB-001", n=4, score=0.8)])
    assert ids(diversify(chunks, 5)) == ["KB-001#c4"]


def test_diversity_fewer_articles_than_the_limit(make_chunk):
    chunks = merge([make_chunk(a, n=n, score=0.9 - n / 10) for a in ("KB-001", "KB-002", "KB-003") for n in (1, 2)])
    assert ids(diversify(chunks, 5)) == ["KB-001#c1", "KB-002#c1", "KB-003#c1"]


def test_diversity_one_article_filling_every_place_gives_one_chunk(make_chunk, spec_retrieval):
    chunks = merge([make_chunk("KB-001", n=n, score=1 - n / 100) for n in range(1, spec_retrieval.main_k + 1)])
    assert ids(diversify(chunks, spec_retrieval.max_articles)) == ["KB-001#c1"]


def test_diversity_ties_follow_chunk_id(make_chunk):
    # Equal scores within one article and across articles: chunk_id decides.
    chunks = merge([
        make_chunk("KB-002", n=2, score=0.7),
        make_chunk("KB-002", n=1, score=0.7),
        make_chunk("KB-010", n=1, score=0.7),
        make_chunk("KB-003", n=1, score=0.7),
    ])
    assert ids(diversify(chunks, 2)) == ["KB-002#c1", "KB-003#c1"]


def test_diversity_of_nothing_is_empty():
    assert diversify([], 5) == []


# --- Step 3b: code boost for KNOWN codes only ----------------------------------------


def test_code_titles_are_kb_info_titles_unchanged():
    info = KBInfo(kb_version="v1", articles=[("KB-001", "E1 Overcurrent"), ("KB-020", "Ramp times")])
    # The code is found in normalised form; the title is kept as given.
    assert code_titles(info) == {"E-01": "E1 Overcurrent"}


def test_two_titles_with_the_same_code_fail_loudly_at_startup(make_flow, fake_retriever):
    articles = [("KB-001", "E-01 Overcurrent"), ("KB-050", "E-01 again")]
    with pytest.raises(DuplicateFaultCode, match="E-01.*KB-001.*KB-050"):
        make_flow(retriever=fake_retriever(articles=articles))
    assert issubclass(DuplicateFaultCode, ConfigError)


@pytest.mark.parametrize(
    "question, titles",
    [
        ("E-02 when stopping", [TITLE_E02]),
        ("no code at all", []),
        ("E-33 on the display", []),  # unknown code: no boost
        ("P-05 is set to 10", []),  # parameter codes are never boosted
        ("E-02 and E-01", [TITLE_E02, TITLE_E01]),  # every known code, in question order
        ("E-02, again E-02", [TITLE_E02]),  # a repeated code is searched once
        ("E-01 and E-99", [TITLE_E01]),  # known boosted, unknown not
    ],
)
def test_boost_titles(question, titles):
    assert boost_titles(question, TITLES) == titles


# --- retrieve(): main search + boosts, merged, diversified ---------------------------


def test_boost_chunks_are_merged_with_the_main_search(scripted_retriever):
    retriever = scripted_retriever({
        "E-02 on stop": [("KB-020", 1, 0.62), ("KB-001", 1, 0.60)],
        TITLE_E02: [("KB-002", 1, 0.88), ("KB-002", 2, 0.80), ("KB-001", 1, 0.70)],
    })
    chunks = retrieve(retriever, "E-02 on stop", TITLES)
    assert ids(chunks) == ["KB-002#c1", "KB-001#c1", "KB-020#c1"]
    assert scores(chunks) == [0.88, 0.70, 0.62]  # KB-001 at its higher (boost) score


def test_several_codes_each_get_a_boost_search(scripted_retriever, spec_retrieval):
    question = "E-01 then E-02 on the same day"
    retriever = scripted_retriever({
        question: [("KB-020", 1, 0.6)],
        TITLE_E01: [("KB-001", 1, 0.9)],
        TITLE_E02: [("KB-002", 1, 0.8)],
    })
    chunks = retrieve(retriever, question, TITLES)
    assert retriever.queries == [
        (question, spec_retrieval.main_k),
        (TITLE_E01, spec_retrieval.boost_k),
        (TITLE_E02, spec_retrieval.boost_k),
    ]
    assert ids(chunks) == ["KB-001#c1", "KB-002#c1", "KB-020#c1"]


@pytest.mark.parametrize("question", ["E-33 on the display", "P-02 set to 5", "the drive is noisy"])
def test_no_known_code_means_one_search(scripted_retriever, spec_retrieval, question):
    retriever = scripted_retriever({question: [("KB-020", 1, 0.6)]})
    assert ids(retrieve(retriever, question, TITLES)) == ["KB-020#c1"]
    assert retriever.queries == [(question, spec_retrieval.main_k)]


def test_retrieve_keeps_spec_number_of_articles(scripted_retriever, spec_retrieval):
    many = [(f"KB-0{n:02d}", 1, 0.9 - n / 100) for n in range(1, 13)]
    retriever = scripted_retriever({"q": many})
    chunks = retrieve(retriever, "q", TITLES)
    assert len(chunks) == spec_retrieval.max_articles
    assert len({c.article_id for c in chunks}) == spec_retrieval.max_articles


# --- The flow uses the final chunks everywhere ------------------------------------------


QUESTION = "E-02 on stop"


@pytest.fixture
def boosted(scripted_retriever):
    """Main search best 0.40; the boost search for E-02 finds KB-002 at 0.90."""
    return scripted_retriever({
        QUESTION: [("KB-020", 1, 0.40), ("KB-020", 2, 0.35), ("KB-001", 1, 0.30)],
        TITLE_E02: [("KB-002", 1, 0.90), ("KB-002", 2, 0.85)],
    })


FINAL = ["KB-002#c1", "KB-020#c1", "KB-001#c1"]


def test_retrieval_check_uses_the_top_score_of_the_final_list(make_flow, boosted, stub_generator):
    # Main search alone (0.40) is below 0.5; the boost chunk (0.90) is not.
    with pytest.raises(AssertionError, match="generator called"):
        make_flow(threshold=0.5, retriever=boosted).ask(QUESTION)
    (question, chunks), = stub_generator.calls
    assert ids(chunks) == FINAL


def test_retrieval_check_escalates_when_final_top_score_is_low(make_flow, boosted, stub_generator, memory_store):
    response = make_flow(threshold=0.95, retriever=boosted).ask(QUESTION)
    assert response.escalation_reason == "low_similarity"
    assert stub_generator.calls == []
    assert ids(memory_store.records[0].retrieved_chunks) == FINAL


def test_handoff_stores_the_final_chunks(make_flow, boosted, memory_store):
    from query.generator import FakeGenerator

    generator = FakeGenerator({"decision": "out_of_scope", "answer": "", "used_article_ids": []})
    make_flow(threshold=0.5, retriever=boosted, generator=generator).ask(QUESTION)
    record = memory_store.records[0]
    assert missing_fields(record.to_dict()) == []
    assert ids(record.retrieved_chunks) == FINAL
    assert [c.similarity_score for c in record.retrieved_chunks] == [0.90, 0.40, 0.30]


def test_citation_check_uses_the_final_chunks(make_flow, boosted, memory_store):
    # KB-002 is retrieved only through the boost: citing it is allowed.
    from query.generator import FakeGenerator

    generator = FakeGenerator({"decision": "answer", "answer": "See the E-02 article.", "used_article_ids": ["KB-002"]})
    response = make_flow(threshold=0.5, retriever=boosted, generator=generator).ask(QUESTION)
    assert response.status == "answered", response
    assert [c.article_id for c in response.citations] == ["KB-002"]


def test_known_and_unknown_code_boosts_the_known_and_still_escalates(
    make_flow, scripted_retriever, stub_generator, memory_store, spec_retrieval
):
    question = "E-01 and E-99 together"
    retriever = scripted_retriever({
        question: [("KB-020", 1, 0.5)],
        TITLE_E01: [("KB-001", 1, 0.9)],
    })
    response = make_flow(threshold=0.5, retriever=retriever).ask(question)
    assert response.escalation_reason == "insufficient_context"
    assert stub_generator.calls == []
    assert retriever.queries == [(question, spec_retrieval.main_k), (TITLE_E01, spec_retrieval.boost_k)]
    assert ids(memory_store.records[0].retrieved_chunks) == ["KB-001#c1", "KB-020#c1"]
