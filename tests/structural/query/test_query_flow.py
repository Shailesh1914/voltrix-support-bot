"""Stage b: flow skeleton over fakes (spec 02, steps 1-4a; criteria 3,
6 and 8 for the escalations that need no model call).

The generator is a stub that fails if called, so every test that
reaches the model call shows it by the stub's AssertionError.
"""

import pytest

from query.config import SEARCH_K, ConfigError
from query.handoff import missing_fields
from query.response import ESCALATION_MESSAGE


def assert_complete_escalation(response, store, reason):
    """Criteria 3 and 6 for one escalated response."""
    assert response.status == "escalated"
    assert response.escalation_reason == reason
    assert response.handoff_id
    assert response.answer == ESCALATION_MESSAGE.format(handoff_id=response.handoff_id)
    assert response.citations == []
    assert len(store.records) == 1
    record = store.records[0]
    assert record.handoff_id == response.handoff_id
    assert record.escalation_reason == reason
    assert missing_fields(record.to_dict()) == []
    return record


# --- Startup --------------------------------------------------------------------


def test_threshold_none_fails_at_startup(make_flow):
    with pytest.raises(ConfigError, match="NOT YET SET"):
        make_flow(threshold=None)


def test_kb_version_mismatch_fails_at_startup(make_flow, fake_retriever):
    with pytest.raises(ConfigError, match="ACTIVE_KB_VERSION"):
        make_flow(retriever=fake_retriever(kb_version="v2"), kb_version="v1")


def test_known_codes_built_at_startup(make_flow):
    assert make_flow().known_fault_codes == {"E-01", "E-02", "E-03"}


@pytest.mark.parametrize("question", ["", "   ", None])
def test_empty_question_is_rejected(make_flow, question):
    with pytest.raises(ValueError):
        make_flow().ask(question)


# --- Steps 1 and 2: masked, normalised query, k=5 ------------------------------


def test_search_gets_masked_normalised_question_and_k_5(make_flow, fake_retriever, stub_generator):
    retriever = fake_retriever()
    with pytest.raises(AssertionError, match="generator called"):
        make_flow(retriever=retriever).ask("e1 when ramping, mail tech@example.com")
    assert retriever.queries == [("E-01 when ramping, mail [EMAIL]", SEARCH_K)]
    assert SEARCH_K == 5
    # The model gets the same masked, normalised text (decision 3).
    assert stub_generator.calls[0][0] == "E-01 when ramping, mail [EMAIL]"


# --- Step 3: unknown fault code (criterion 8) ----------------------------------


@pytest.mark.parametrize("question", ["E33 on the display", "e-47 after power up", "E-01 and E 99 together"])
def test_criterion_8_unknown_code_escalates_without_model_call(
    make_flow, fake_retriever, stub_generator, memory_store, question
):
    retriever = fake_retriever(scores=(0.9, 0.8, 0.7, 0.6, 0.5))  # high scores: still escalates
    response = make_flow(retriever=retriever).ask(question)
    record = assert_complete_escalation(response, memory_store, "insufficient_context")
    assert stub_generator.calls == []
    assert [c.chunk_id for c in record.retrieved_chunks] == [c.chunk_id for c in retriever.chunks[:5]]
    assert [c.similarity_score for c in record.retrieved_chunks] == [0.9, 0.8, 0.7, 0.6, 0.5]


def test_unknown_code_wins_over_low_similarity(make_flow, fake_retriever, memory_store):
    response = make_flow(retriever=fake_retriever(scores=(0.1,))).ask("E-33 again")
    assert response.escalation_reason == "insufficient_context"


def test_known_code_goes_on_to_the_model(make_flow, stub_generator):
    with pytest.raises(AssertionError, match="generator called"):
        make_flow().ask("E1 on start")
    assert len(stub_generator.calls) == 1


# --- Step 4a: low similarity -----------------------------------------------------


def test_low_similarity_escalates_without_model_call(make_flow, fake_retriever, stub_generator, memory_store):
    retriever = fake_retriever(scores=(0.49, 0.3))
    response = make_flow(threshold=0.5, retriever=retriever).ask("how do I size a drive")
    record = assert_complete_escalation(response, memory_store, "low_similarity")
    assert stub_generator.calls == []
    assert [c.chunk_id for c in record.retrieved_chunks] == ["KB-001#c1", "KB-001#c2"]


def test_score_equal_to_threshold_is_not_low(make_flow, fake_retriever, stub_generator):
    # "below ESCALATION_THRESHOLD" escalates; equal does not.
    with pytest.raises(AssertionError, match="generator called"):
        make_flow(threshold=0.5, retriever=fake_retriever(scores=(0.5,))).ask("question")


def test_highest_score_is_used_not_the_first(make_flow, make_chunk, fake_retriever):
    retriever = fake_retriever(chunks=[make_chunk(n=1, score=0.2), make_chunk(n=2, score=0.8)])
    with pytest.raises(AssertionError, match="generator called"):
        make_flow(threshold=0.5, retriever=retriever).ask("question")


def test_no_chunks_is_low_similarity(make_flow, fake_retriever, memory_store):
    response = make_flow(retriever=fake_retriever(scores=())).ask("question")
    record = assert_complete_escalation(response, memory_store, "low_similarity")
    assert record.retrieved_chunks == ()


def test_threshold_is_the_one_passed_in(make_flow, fake_retriever, stub_generator, memory_store):
    retriever = fake_retriever(scores=(0.6,))
    assert make_flow(threshold=0.7, retriever=retriever).ask("q").escalation_reason == "low_similarity"
    with pytest.raises(AssertionError, match="generator called"):
        make_flow(threshold=0.55, retriever=retriever).ask("q")


# --- Handoff contents ------------------------------------------------------------


def test_handoff_stores_only_masked_questions(make_flow, fake_retriever, memory_store):
    question = "E-33 on line 2, call +44 20 7946 0958 or tech@example.com"
    make_flow(retriever=fake_retriever()).ask(question)
    record = memory_store.records[0]
    assert record.question_received == "E-33 on line 2, call [PHONE] or [EMAIL]"
    assert record.question_normalised == "E-33 on line 2, call [PHONE] or [EMAIL]"
    stored = str(record.to_dict())
    assert "7946" not in stored and "example.com" not in stored


def test_handoff_keeps_received_and_normalised_forms(make_flow, memory_store):
    make_flow().ask("e 33 flashing")
    record = memory_store.records[0]
    assert (record.question_received, record.question_normalised) == ("e 33 flashing", "E-33 flashing")


def test_handoff_records_kb_version_and_time(make_flow, fake_retriever, memory_store):
    make_flow(retriever=fake_retriever(kb_version="v2"), kb_version="v2").ask("E-33")
    record = memory_store.records[0]
    assert record.kb_version == "v2"
    assert record.created_at == "2026-10-11T09:30:00+00:00"


def test_each_escalation_gets_its_own_handoff(make_flow, memory_store):
    flow = make_flow()
    first, second = flow.ask("E-33"), flow.ask("E-33")
    assert first.handoff_id != second.handoff_id
    assert [r.handoff_id for r in memory_store.records] == [first.handoff_id, second.handoff_id]


def test_failed_handoff_write_raises_and_gives_no_reference(make_flow):
    class BrokenStore:
        def append(self, record):
            raise OSError("disk full")

    with pytest.raises(OSError, match="disk full"):
        make_flow(store=BrokenStore()).ask("E-33")


def test_jsonl_store_end_to_end(make_flow, tmp_path):
    import json

    from query.handoff import JsonlHandoffStore

    path = tmp_path / "handoffs" / "handoffs.jsonl"
    response = make_flow(store=JsonlHandoffStore(path)).ask("E-33")
    (stored,) = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert stored["handoff_id"] == response.handoff_id
    assert missing_fields(stored) == []


# --- Step 4b: generator outcomes (stage c; decision 6) ---------------------------


@pytest.fixture
def flow_with(make_flow, fake_retriever):
    def _make(response, store):
        from query.generator import FakeGenerator

        generator = FakeGenerator(response)
        retriever = fake_retriever(scores=(0.8, 0.7))
        return make_flow(threshold=0.5, retriever=retriever, generator=generator, store=store), generator, retriever

    return _make


@pytest.mark.parametrize("decision", ["insufficient_context", "out_of_scope"])
def test_model_escalation_decision(flow_with, memory_store, decision):
    flow, generator, retriever = flow_with({"decision": decision, "answer": "", "used_article_ids": []}, memory_store)
    response = flow.ask("e2 when stopping, call 020 7946 0958")
    record = assert_complete_escalation(response, memory_store, decision)
    assert generator.calls == [("E-02 when stopping, call [PHONE]", retriever.chunks)]
    assert [c.chunk_id for c in record.retrieved_chunks] == ["KB-001#c1", "KB-001#c2"]


def test_malformed_output_escalates_insufficient_context(flow_with, memory_store):
    flow, generator, _ = flow_with({"decision": "maybe", "answer": "x", "used_article_ids": []}, memory_store)
    assert_complete_escalation(flow.ask("q"), memory_store, "insufficient_context")
    assert len(generator.calls) == 1


def test_service_error_escalates_with_handoff(flow_with, memory_store):
    from query.generator import GeneratorServiceError

    flow, generator, _ = flow_with(GeneratorServiceError("Bedrock ThrottlingException"), memory_store)
    record = assert_complete_escalation(flow.ask("q"), memory_store, "service_error")
    assert len(record.retrieved_chunks) == 2
    assert len(generator.calls) == 1


def test_other_generator_errors_are_not_hidden(flow_with, memory_store):
    # Only the two known failures become escalations; a bug must fail loudly.
    flow, _, _ = flow_with(RuntimeError("bug"), memory_store)
    with pytest.raises(RuntimeError, match="bug"):
        flow.ask("q")
    assert memory_store.records == []


def test_answer_path_is_not_built_yet(flow_with, memory_store):
    flow, _, _ = flow_with({"decision": "answer", "answer": "x", "used_article_ids": ["KB-001"]}, memory_store)
    with pytest.raises(NotImplementedError, match="stage d"):
        flow.ask("q")
