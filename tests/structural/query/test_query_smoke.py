"""Step 8f: python -m query.smoke, the one-off check Shailesh runs by hand.
Here it only ever runs against a faked HTTP transport and a fake index:
no network, no real key, no model call.
"""

import io
import json
import logging

import httpx2
import pytest

from query import smoke
from query.anthropic_api import AnthropicGenerator, make_client
from query.config import ConfigError, MODEL_ID

pytestmark = pytest.mark.usefixtures("no_network")

KEY = "sk-ant-test-SENTINEL-KEY-0123456789"


def reply(status=200, decision="answer", answer="Check P-05 first.", used=("KB-001",), stop_reason="tool_use"):
    if status != 200:
        return status, {"type": "error", "error": {"type": "authentication_error", "message": "fake"}}
    tool_input = {"decision": decision, "answer": answer, "used_article_ids": list(used)}
    return 200, {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": MODEL_ID,
        "content": [{"type": "tool_use", "id": "toolu_1", "name": "submit_response", "input": tool_input}],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 2345, "output_tokens": 67},
    }


@pytest.fixture
def run(fake_retriever, make_chunk):
    """smoke.main() over a fake index and a faked API; returns
    (exit code, printed text, API requests, opened versions, search calls)."""

    def _run(api_reply=None, make_generator=None):
        requests, opened = [], []
        status, body = api_reply or reply()

        def handler(request):
            requests.append(request)
            return httpx2.Response(status, json=body, request=request)

        chunks = [make_chunk("KB-001", n=i, score=0.8 - i / 10, text="E-01 — Check P-05.") for i in (1, 2)]
        # A chunk search never returns: read only through article_chunks().
        stored = [make_chunk("KB-001", n=3, text="E-01 — Fixes\n\nLengthen P-05.")]
        retriever = fake_retriever(chunks=chunks, stored=stored)

        def open_index(version):
            opened.append(version)
            return retriever

        def default_generator():
            return AnthropicGenerator(make_client(KEY, httpx2.Client(transport=httpx2.MockTransport(handler))))

        out = io.StringIO()
        code = smoke.main(open_index=open_index, make_generator=make_generator or default_generator, out=out)
        return code, out.getvalue(), requests, opened, retriever.queries

    return _run


def test_fixed_question_and_kb_version():
    assert smoke.SMOKE_QUESTION == "E-01 when the motor ramps up, what do I check?"
    assert smoke.SMOKE_KB_VERSION == "v1"


def test_one_call_to_the_generator_with_real_shaped_chunks(run, spec_retrieval):
    code, text, requests, opened, queries = run()
    assert code == 0
    assert opened == ["v1"]
    # Retrieved as the flow does (spec 02 step 3): main search, then the
    # code boost for E-01 with the KB-001 title.
    assert queries == [
        (smoke.SMOKE_QUESTION, spec_retrieval.main_k),
        ("E-01 Overcurrent during acceleration", spec_retrieval.boost_k),
    ]
    assert len(requests) == 1
    body = json.loads(requests[0].content)
    assert body["model"] == MODEL_ID and body["temperature"] == 0
    assert smoke.SMOKE_QUESTION in body["messages"][0]["content"]


def test_prints_decision_ids_answer_and_usage(run):
    code, text, *_ = run()
    assert "decision:         answer" in text
    assert "used_article_ids: ['KB-001']" in text
    assert "answer (start):   'Check P-05 first.'" in text
    assert "tokens:           input 2345, output 67" in text
    assert f"model:      {MODEL_ID}" in text
    assert "KB-001#c1 (0.700)" in text


def test_long_answer_is_cut_to_a_preview(run):
    _, text, *_ = run(reply(answer="x" * 500))
    assert "'" + "x" * smoke.ANSWER_PREVIEW_CHARS + "...'" in text


def test_service_error_exits_1_with_class_only(run):
    code, text, requests, *_ = run(reply(status=401))
    assert code == smoke.EXIT_CALL_FAILED
    assert "service error: Anthropic AuthenticationError (HTTP 401)" in text
    assert "fake" not in text  # the API's own error text is never printed
    assert len(requests) == 1


def test_malformed_output_exits_1(run):
    code, text, *_ = run(reply(stop_reason="max_tokens"))
    assert code == smoke.EXIT_CALL_FAILED
    assert text.splitlines()[-1].startswith("malformed output: stop_reason is 'max_tokens'")


def test_startup_error_exits_2_before_the_index_is_opened(run):
    def no_key():
        raise ConfigError("VOLTRIX_ANTHROPIC_API_KEY is not set")

    code, text, requests, opened, _ = run(make_generator=no_key)
    assert code == smoke.EXIT_STARTUP_FAILED
    assert text == "error: VOLTRIX_ANTHROPIC_API_KEY is not set\n"
    assert (requests, opened) == ([], [])


def test_key_never_printed_or_logged(run, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    texts = [run()[1], run(reply(status=401))[1], run(reply(stop_reason="refusal"))[1]]
    captured = capsys.readouterr()
    for text in [*texts, caplog.text, captured.out, captured.err]:
        assert KEY not in text


def test_generator_only_no_flow_threshold_or_handoff():
    source = open(smoke.__file__, encoding="utf-8").read()
    for name in ("QueryFlow", "require_threshold", "ESCALATION_THRESHOLD", "handoff", "load_settings"):
        assert name not in source.replace("no handoff", "")


def test_default_generator_is_the_real_one():
    # The command a human runs uses the Anthropic generator and the real index.
    defaults = smoke.main.__defaults__
    assert defaults[0] is smoke.open_retrieval
    assert defaults[1] == AnthropicGenerator.from_environment


def test_reads_the_whole_selected_articles_like_the_bot(run, fake_retriever, make_chunk):
    """Spec 02 step 3e: smoke.py gives the model the same reading as the flow
    (all chunks of the selected articles), built by the same function."""
    from query.fault_codes import code_titles
    from query.prompt import build_user_message
    from query.retrieval import read_articles, retrieve

    code, text, requests, *_ = run()
    assert code == 0
    assert "chunks:     KB-001#c1 (0.700)\n" in text  # step d: best chunk only
    assert "reading:    KB-001#c1, KB-001#c2, KB-001#c3\n" in text
    content = json.loads(requests[0].content)["messages"][0]["content"]
    assert 'chunk_id="KB-001#c3"' in content and "Lengthen P-05." in content

    # Exactly the message the flow's reading produces.
    chunks = [make_chunk("KB-001", n=i, score=0.8 - i / 10, text="E-01 — Check P-05.") for i in (1, 2)]
    stored = [make_chunk("KB-001", n=3, text="E-01 — Fixes\n\nLengthen P-05.")]
    retriever = fake_retriever(chunks=chunks, stored=stored)
    retrieved = retrieve(retriever, smoke.SMOKE_QUESTION, code_titles(retriever.kb_info()))
    assert content == build_user_message(smoke.SMOKE_QUESTION, read_articles(retriever, retrieved))


def test_uses_the_flow_reading_function():
    source = open(smoke.__file__, encoding="utf-8").read()
    assert "read_articles(retriever, chunks)" in source
    assert "generate_with_usage(question, read)" in source
