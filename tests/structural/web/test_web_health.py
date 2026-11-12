"""GET /health (spec 08 section 4.1)."""

import pytest

from query import config
from web_testkit import secrets_in, response_text


def test_health_without_code_is_200(make_bot):
    response = make_bot().client.get("/health")
    assert response.status_code == 200


def test_health_fields(make_bot, spec_08):
    body = make_bot(kb_version="v2", image_tag="v2-20261112-a1b2c3d").client.get("/health").json()
    assert tuple(body) == spec_08.health_fields == ("status", "kb_version", "model_id", "image_tag")
    assert body == {
        "status": "ok",
        "kb_version": "v2",
        "model_id": config.MODEL_ID,
        "image_tag": "v2-20261112-a1b2c3d",
    }


def test_health_never_calls_claude_or_retrieval(make_bot):
    bot = make_bot()
    kb_info_calls = bot.retriever.kb_info_calls  # once, when the flow was built
    for _ in range(3):
        bot.client.get("/health")
    assert bot.claude.calls == 0
    assert bot.retriever.retrieval_calls() == 0
    assert bot.retriever.kb_info_calls == kb_info_calls
    assert bot.flow.results == []


@pytest.mark.parametrize("headers", [{}, {"X-Access-Code": "wrong-code-wrong-code"}])
def test_health_ignores_the_code(make_bot, headers):
    assert make_bot().client.get("/health", headers=headers).status_code == 200


def test_health_contains_no_secret(make_bot):
    response = make_bot().client.get("/health")
    assert secrets_in(response_text(response)) == []
