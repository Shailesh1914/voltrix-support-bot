"""Stage c: validate_output() and FakeGenerator (spec 02, steps 4b and
6; decision 6)."""

import pytest

from query.generator import (
    DECISIONS,
    FakeGenerator,
    GeneratorOutput,
    GeneratorServiceError,
    MalformedOutput,
    validate_output,
)


def raw(**overrides):
    output = {"decision": "answer", "answer": "Lengthen P-06.", "used_article_ids": ["KB-002"]}
    output.update(overrides)
    return output


# --- validate_output ----------------------------------------------------------------


def test_valid_answer():
    assert validate_output(raw()) == GeneratorOutput("answer", "Lengthen P-06.", ("KB-002",))


@pytest.mark.parametrize("decision", ["insufficient_context", "out_of_scope"])
def test_escalation_decisions_may_have_empty_answer(decision):
    assert validate_output(raw(decision=decision, answer="", used_article_ids=[])).decision == decision


def test_answer_with_empty_used_ids_is_structurally_valid():
    # Decision 7 escalates this, but in the flow (stage d), not here.
    assert validate_output(raw(used_article_ids=[])).used_article_ids == ()


def test_repeated_ids_kept_once_in_order():
    output = validate_output(raw(used_article_ids=["KB-002", "KB-001", "KB-002"]))
    assert output.used_article_ids == ("KB-002", "KB-001")


@pytest.mark.parametrize(
    "bad",
    [
        None,
        "answer",
        ["answer"],
        {},
        {"decision": "answer", "answer": "x"},  # field missing
        raw(extra="field"),
        raw(decision="escalate"),
        raw(decision="Answer"),
        raw(decision=None),
        raw(answer=None),
        raw(answer=42),
        raw(answer=""),  # answer decision needs text
        raw(answer="   \n"),
        raw(used_article_ids="KB-001"),
        raw(used_article_ids=[1]),
        raw(used_article_ids=[""]),
        raw(used_article_ids=None),
    ],
)
def test_malformed_output_is_rejected(bad):
    with pytest.raises(MalformedOutput):
        validate_output(bad)


def test_decisions_are_the_spec_values():
    assert DECISIONS == ("answer", "insufficient_context", "out_of_scope")


# --- FakeGenerator -----------------------------------------------------------------


def test_fake_returns_output_and_records_calls(make_chunk):
    chunks = [make_chunk()]
    output = GeneratorOutput("answer", "text", ("KB-001",))
    fake = FakeGenerator(output)
    assert fake.generate("q", chunks) is output
    assert fake.calls == [("q", chunks)]


def test_fake_dict_goes_through_validation():
    assert FakeGenerator(raw()).generate("q", []).used_article_ids == ("KB-002",)
    with pytest.raises(MalformedOutput):
        FakeGenerator(raw(decision="maybe")).generate("q", [])


def test_fake_raises_exceptions():
    with pytest.raises(GeneratorServiceError):
        FakeGenerator(GeneratorServiceError("down")).generate("q", [])


def test_fake_function_sees_question_and_chunks(make_chunk):
    def respond(question, chunks):
        return raw(used_article_ids=[c.article_id for c in chunks], answer=question)

    output = FakeGenerator(respond).generate("why E-01", [make_chunk("KB-001"), make_chunk("KB-003")])
    assert output.answer == "why E-01"
    assert output.used_article_ids == ("KB-001", "KB-003")
