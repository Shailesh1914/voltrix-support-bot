"""Stage b: the flow over the real v1 and v2 indexes, through the
retrieval contract only (open_retrieval). No model call: the stub
generator fails if called.

Skipped when indexes/ has not been built (e.g. a fresh CI checkout).
"""

import pytest

from ingestion import open_retrieval
from query.config import REPO_ROOT, SEARCH_K
from query.handoff import missing_fields

pytestmark = pytest.mark.skipif(
    not all((REPO_ROOT / "indexes" / v / "manifest.json").is_file() for v in ("v1", "v2")),
    reason="real indexes not built",
)

V1_CODES = {f"E-{n:02d}" for n in range(1, 17)}


@pytest.fixture(scope="module")
def real_retrievers():
    return {v: open_retrieval(v) for v in ("v1", "v2")}


def test_known_codes_v1(make_flow, real_retrievers):
    assert make_flow(retriever=real_retrievers["v1"]).known_fault_codes == V1_CODES


def test_known_codes_v2_adds_E_17(make_flow, real_retrievers):
    flow = make_flow(retriever=real_retrievers["v2"], kb_version="v2")
    assert flow.known_fault_codes == V1_CODES | {"E-17"}


@pytest.mark.parametrize("question", ["E33 keeps showing after power up", "e-18 on the display, what is it"])
def test_unknown_code_escalates_with_real_chunks(make_flow, real_retrievers, stub_generator, memory_store, question):
    flow = make_flow(threshold=-1.0, retriever=real_retrievers["v1"])
    response = flow.ask(question)
    assert response.escalation_reason == "insufficient_context"
    assert stub_generator.calls == []
    record = memory_store.records[0]
    assert missing_fields(record.to_dict()) == []
    assert len(record.retrieved_chunks) == SEARCH_K
    assert record.kb_version == "v1"


def test_E_17_is_unknown_in_v1_but_known_in_v2(make_flow, real_retrievers, stub_generator, memory_store):
    question = "E17 on the display"
    assert make_flow(threshold=-1.0, retriever=real_retrievers["v1"]).ask(question).status == "escalated"
    with pytest.raises(AssertionError, match="generator called"):
        make_flow(threshold=-1.0, retriever=real_retrievers["v2"], kb_version="v2").ask(question)
    assert len(stub_generator.calls) == 1


def test_low_similarity_with_real_scores(make_flow, real_retrievers, stub_generator, memory_store):
    # Threshold 1.0 is a test value only: no real score reaches it.
    response = make_flow(threshold=1.0, retriever=real_retrievers["v1"]).ask("E1 when ramping up")
    assert response.escalation_reason == "low_similarity"
    assert stub_generator.calls == []
    scores = [c.similarity_score for c in memory_store.records[0].retrieved_chunks]
    assert len(scores) == SEARCH_K and scores == sorted(scores, reverse=True)


# --- Answer path over real chunks, fake generator (stage d) ---------------------------

QUESTIONS = [
    "vx200 trips every time it ramps up, E1 flashing. what to check first",
    "Getting E-02 when we stop the mixer. Ramp down is 3 sec.",
    "how long must I wait after isolating before opening the terminal cover",
    "what is the routine maintenance schedule",
]


def copy_top_chunk(question, chunks):
    """A fake model that answers with the top chunk, word for word."""
    return {"decision": "answer", "answer": chunks[0].text, "used_article_ids": [chunks[0].article_id]}


@pytest.mark.parametrize("version", ["v1", "v2"])
@pytest.mark.parametrize("question", QUESTIONS)
def test_answer_from_real_chunk_is_answered(make_flow, real_retrievers, memory_store, version, question):
    from query.generator import FakeGenerator

    retriever = real_retrievers[version]
    generator = FakeGenerator(copy_top_chunk)
    response = make_flow(threshold=-1.0, retriever=retriever, generator=generator, kb_version=version).ask(question)

    assert response.status == "answered", response
    (_, chunks), = generator.calls
    top = chunks[0]
    assert response.answer.startswith(top.text)
    assert [(c.article_id, c.title) for c in response.citations] == [(top.article_id, top.title)]
    assert memory_store.records == []


@pytest.mark.parametrize(
    "reply",
    [
        lambda chunks: {"answer": chunks[0].text + "\nAlso set P-99 to 999 s."},
        lambda chunks: {"used_article_ids": ["KB-999"]},
        lambda chunks: {"used_article_ids": []},
    ],
    ids=["invented_values", "not_retrieved", "no_citation"],
)
def test_bad_answers_over_real_chunks_escalate(make_flow, real_retrievers, memory_store, reply):
    from query.generator import FakeGenerator

    def respond(question, chunks):
        return {**copy_top_chunk(question, chunks), **reply(chunks)}

    flow = make_flow(threshold=-1.0, retriever=real_retrievers["v1"], generator=FakeGenerator(respond))
    response = flow.ask(QUESTIONS[0])
    assert response.escalation_reason == "insufficient_context"
    record = memory_store.records[0]
    assert missing_fields(record.to_dict()) == []
    assert len(record.retrieved_chunks) == SEARCH_K
