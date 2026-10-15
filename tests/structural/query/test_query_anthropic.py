"""Step 8f: AnthropicGenerator over a faked HTTP transport (spec 02,
Processing step 7; decisions 2 and 6). The real SDK runs, including its
retries, but every response comes from MockTransport. No network: every
socket connection fails. Every environment is passed in explicitly.
"""

import json
import logging

import anthropic
import httpx2
import pytest

from query import anthropic_api
from query.anthropic_api import (
    API_BASE_URL,
    KEY_NAME,
    MAX_RETRIES,
    REFUSED_ENV_NAMES,
    SECRETS_PATH,
    TIMEOUT,
    TOOL,
    TOOL_CHOICE,
    AnthropicGenerator,
    Usage,
    load_api_key,
    make_client,
)
from query.config import MODEL_ID, REPO_ROOT, ConfigError
from query.flow import QueryFlow
from query.generator import GeneratorOutput, GeneratorServiceError, MalformedOutput
from query.prompt import SYSTEM_PROMPT, TOOL_DESCRIPTION, TOOL_SCHEMA, build_user_message

pytestmark = pytest.mark.usefixtures("no_network")

KEY = "sk-ant-test-SENTINEL-KEY-0123456789"
ANSWER = {"decision": "answer", "answer": "Lengthen P-06.", "used_article_ids": ["KB-002"]}


@pytest.fixture(autouse=True)
def no_retry_sleep(monkeypatch):
    """Retries happen for real, without waiting; delays are recorded."""
    delays = []
    monkeypatch.setattr(anthropic._base_client.time, "sleep", delays.append)
    return delays


def message(tool_input=None, stop_reason="tool_use", content=None, usage=(1000, 100)):
    if content is None:
        content = [
            {"type": "text", "text": "Here is my response."},
            {"type": "tool_use", "id": "toolu_1", "name": "submit_response", "input": tool_input},
        ]
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": MODEL_ID,
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": usage[0], "output_tokens": usage[1]},
    }


def error_body(error_type):
    return {"type": "error", "error": {"type": error_type, "message": "fake error text"}}


class FakeAPI:
    """MockTransport handler: replies in order (the last one repeats) and
    records every request."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, BaseException):
            raise reply
        if isinstance(reply, tuple):
            status, body = reply
            return httpx2.Response(status, json=body, request=request)
        return httpx2.Response(200, json=reply, request=request)

    def generator(self) -> AnthropicGenerator:
        http_client = httpx2.Client(transport=httpx2.MockTransport(self))
        return AnthropicGenerator(make_client(KEY, http_client))


# --- Request (decision 2; step 7: temperature 0, tool forced) ---------------------------


def wire_body(question, chunks):
    """The JSON the API must receive (spec 02 step 7: temperature 0)."""
    return {
        "model": MODEL_ID,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": build_user_message(question, chunks)}],
        "temperature": 0,
        "max_tokens": 2048,
        "tools": [{"name": "submit_response", "description": TOOL_DESCRIPTION, "input_schema": TOOL_SCHEMA}],
        "tool_choice": {"type": "tool", "name": "submit_response"},
    }


def test_request_shape(make_chunk):
    # anthropic 1.x has no temperature argument; it travels in extra_body.
    chunks = [make_chunk("KB-002", n=1)]
    request = AnthropicGenerator(client=None).request("E-02 on stop", chunks)
    assert request.pop("extra_body") == {"temperature": 0}
    assert request == {k: v for k, v in wire_body("E-02 on stop", chunks).items() if k != "temperature"}
    assert (TOOL["name"], TOOL_CHOICE["name"]) == ("submit_response", "submit_response")


def test_model_id_comes_from_config():
    assert AnthropicGenerator(client=None).model_id == MODEL_ID == "claude-haiku-4-5-20251001"


def test_one_call_with_exact_request_on_the_wire(make_chunk):
    chunks = [make_chunk("KB-002", n=1), make_chunk("KB-001", n=2)]
    api = FakeAPI(message(ANSWER, usage=(1234, 56)))
    generator = api.generator()

    output, usage = generator.generate_with_usage("E-02 on stop", chunks)

    assert output == GeneratorOutput("answer", "Lengthen P-06.", ("KB-002",))
    assert usage == Usage(1234, 56)
    (request,) = api.requests
    assert request.method == "POST"
    assert str(request.url) == "https://api.anthropic.com/v1/messages"
    assert request.headers["x-api-key"] == KEY
    # Exactly the spec's request on the wire, temperature 0 included.
    assert json.loads(request.content) == wire_body("E-02 on stop", chunks)


def test_generate_returns_only_the_output(make_chunk):
    output = FakeAPI(message(ANSWER)).generator().generate("q", [make_chunk("KB-002")])
    assert output == GeneratorOutput("answer", "Lengthen P-06.", ("KB-002",))


def test_escalation_decision_is_returned(make_chunk):
    out = {"decision": "out_of_scope", "answer": "", "used_article_ids": []}
    assert FakeAPI(message(out)).generator().generate("price?", [make_chunk()]).decision == "out_of_scope"


# --- Retries and timeouts: explicit, never SDK defaults -----------------------------------


def test_retries_timeout_and_address_are_explicit():
    assert MAX_RETRIES == 2  # 3 attempts in total, the first included
    assert (TIMEOUT.connect, TIMEOUT.read, TIMEOUT.write, TIMEOUT.pool) == (10.0, 60.0, 60.0, 60.0)
    assert API_BASE_URL == "https://api.anthropic.com"
    client = make_client(KEY)
    assert client.max_retries == MAX_RETRIES
    assert client.timeout == TIMEOUT
    assert str(client.base_url).rstrip("/") == API_BASE_URL


def test_every_connection_setting_is_passed_explicitly(monkeypatch):
    # max_retries=2 and the base URL equal the SDK defaults, so comparing
    # values cannot show an argument was dropped; the call itself is checked.
    calls = []
    monkeypatch.setattr(anthropic_api.anthropic, "Anthropic", lambda **kwargs: calls.append(kwargs))
    make_client(KEY)
    assert calls == [
        {"api_key": KEY, "base_url": API_BASE_URL, "max_retries": MAX_RETRIES, "timeout": TIMEOUT, "http_client": None}
    ]


def test_explicit_values_differ_from_sdk_defaults():
    # Guards against "explicit" silently meaning "the same as the default".
    from anthropic._constants import DEFAULT_MAX_RETRIES, DEFAULT_TIMEOUT

    assert (MAX_RETRIES, TIMEOUT) != (DEFAULT_MAX_RETRIES, DEFAULT_TIMEOUT)
    assert TIMEOUT.read != DEFAULT_TIMEOUT.read


def test_timeout_reaches_every_request(make_chunk):
    api = FakeAPI(message(ANSWER))
    api.generator().generate("q", [make_chunk("KB-002")])
    assert api.requests[0].extensions["timeout"] == {"connect": 10.0, "read": 60.0, "write": 60.0, "pool": 60.0}


def test_rate_limit_is_retried_then_succeeds(make_chunk, no_retry_sleep):
    api = FakeAPI((429, error_body("rate_limit_error")), message(ANSWER))
    assert api.generator().generate("q", [make_chunk("KB-002")]).decision == "answer"
    assert len(api.requests) == 2 and len(no_retry_sleep) == 1


@pytest.mark.parametrize(
    "reply",
    [
        (429, error_body("rate_limit_error")),
        (529, error_body("overloaded_error")),
        (500, error_body("api_error")),
        httpx2.ConnectError("refused"),
        httpx2.ReadTimeout("slow"),
    ],
    ids=["429", "529", "500", "connect_error", "timeout"],
)
def test_retryable_errors_stop_after_three_attempts(make_chunk, reply):
    api = FakeAPI(reply)
    with pytest.raises(GeneratorServiceError):
        api.generator().generate("q", [make_chunk()])
    assert len(api.requests) == MAX_RETRIES + 1 == 3


@pytest.mark.parametrize("status", [400, 401, 403, 404, 413])
def test_client_errors_are_not_retried(make_chunk, status):
    api = FakeAPI((status, error_body("invalid_request_error")))
    with pytest.raises(GeneratorServiceError):
        api.generator().generate("q", [make_chunk()])
    assert len(api.requests) == 1


# --- Every API, connection, auth and rate-limit error -> service_error -------------------


@pytest.mark.parametrize(
    "status, error_type, sdk_class",
    [
        (400, "invalid_request_error", "BadRequestError"),
        (401, "authentication_error", "AuthenticationError"),
        (403, "permission_error", "PermissionDeniedError"),
        (404, "not_found_error", "NotFoundError"),
        (413, "request_too_large", "RequestTooLargeError"),
        (429, "rate_limit_error", "RateLimitError"),
        (500, "api_error", "InternalServerError"),
        (529, "overloaded_error", "OverloadedError"),
    ],
)
def test_status_errors_are_service_errors(make_chunk, status, error_type, sdk_class):
    with pytest.raises(GeneratorServiceError) as raised:
        FakeAPI((status, error_body(error_type))).generator().generate("q", [make_chunk()])
    assert str(raised.value) == f"Anthropic {sdk_class} (HTTP {status})"


@pytest.mark.parametrize(
    "error, sdk_class",
    [(httpx2.ConnectError("refused"), "APIConnectionError"), (httpx2.ReadTimeout("slow"), "APITimeoutError")],
    ids=["connect_error", "timeout"],
)
def test_connection_errors_are_service_errors(make_chunk, error, sdk_class):
    with pytest.raises(GeneratorServiceError) as raised:
        FakeAPI(error).generator().generate("q", [make_chunk()])
    assert str(raised.value) == f"Anthropic {sdk_class}"


@pytest.mark.parametrize(
    "error",
    [
        anthropic.AnthropicError("any SDK failure"),
        anthropic.CredentialsError("credential problem"),
        anthropic.APIResponseValidationError(
            httpx2.Response(200, request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages")), body=None
        ),
    ],
    ids=lambda e: type(e).__name__,
)
def test_any_sdk_error_is_a_service_error(make_chunk, error):
    class FailingMessages:
        def create(self, **kwargs):
            raise error

    class FailingClient:
        messages = FailingMessages()

    with pytest.raises(GeneratorServiceError, match=type(error).__name__):
        AnthropicGenerator(FailingClient()).generate("q", [make_chunk()])


def test_service_error_escalates_through_the_flow(fake_retriever, make_chunk, memory_store):
    chunks = [make_chunk("KB-002", n=1, score=0.9, text="E-02 — Lengthen P-06.")]
    flow = QueryFlow(
        fake_retriever(chunks=chunks),
        FakeAPI((529, error_body("overloaded_error"))).generator(),
        threshold=0.5,
        handoff_store=memory_store,
        kb_version="v1",
    )
    response = flow.ask("E2 on stop")
    assert (response.status, response.escalation_reason) == ("escalated", "service_error")
    assert memory_store.records[0].escalation_reason == "service_error"


def test_errors_are_logged_without_question_text(make_chunk, caplog):
    # Only this module's records: the SDK's own DEBUG logging (switched on by
    # ANTHROPIC_LOG in the shell) logs whole requests and is not ours to test.
    with pytest.raises(GeneratorServiceError):
        FakeAPI((401, error_body("authentication_error"))).generator().generate("secret question text", [make_chunk()])
    ours = "\n".join(r.getMessage() for r in caplog.records if r.name == anthropic_api.__name__)
    assert "AuthenticationError (HTTP 401)" in ours
    assert "secret question text" not in ours


# --- Malformed output -> MalformedOutput ("insufficient_context") ------------------------


@pytest.mark.parametrize(
    "reply",
    [
        message(content=[{"type": "text", "text": "E-02 means overcurrent."}], stop_reason="end_turn"),
        message(ANSWER, stop_reason="max_tokens"),
        message(ANSWER, stop_reason="refusal"),
        message(content=[], stop_reason="tool_use"),
        message(
            content=[
                {"type": "tool_use", "id": "a", "name": "submit_response", "input": ANSWER},
                {"type": "tool_use", "id": "b", "name": "submit_response", "input": ANSWER},
            ]
        ),
        message(content=[{"type": "tool_use", "id": "a", "name": "other_tool", "input": ANSWER}]),
        message({"decision": "maybe", "answer": "", "used_article_ids": []}),
        message({"decision": "answer", "answer": "x"}),
        message({**ANSWER, "extra": 1}),
    ],
    ids=[
        "text_only",
        "max_tokens",
        "refusal",
        "no_content",
        "two_tool_uses",
        "wrong_tool",
        "bad_decision",
        "missing_field",
        "extra_field",
    ],
)
def test_malformed_output(make_chunk, reply):
    with pytest.raises(MalformedOutput):
        FakeAPI(reply).generator().generate("q", [make_chunk()])


# --- The key: environment, else secrets file; never inside the project ----------------------


@pytest.fixture
def secrets_file(tmp_path):
    def _make(text):
        path = tmp_path / "voltrix" / "secrets.env"
        path.parent.mkdir(exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    return _make


def test_key_from_environment_first(secrets_file):
    path = secrets_file(f"{KEY_NAME}=file-key\n")
    assert load_api_key({KEY_NAME: KEY}, path) == KEY


def test_key_from_secrets_file_when_not_in_environment(secrets_file):
    path = secrets_file(f"# Voltrix secrets\n{KEY_NAME}={KEY}\n")
    assert load_api_key({}, path) == KEY
    assert load_api_key({KEY_NAME: "   "}, path) == KEY


def test_only_the_voltrix_name_is_read_from_the_file(secrets_file):
    path = secrets_file(f"OTHER_KEY={KEY}\n")
    with pytest.raises(ConfigError, match=KEY_NAME):
        load_api_key({}, path)


def test_missing_key_fails_loudly(tmp_path):
    with pytest.raises(ConfigError, match=f"{KEY_NAME} is not set"):
        load_api_key({}, tmp_path / "absent.env")


def test_default_secrets_path_is_outside_the_project():
    assert SECRETS_PATH == anthropic_api.Path.home() / ".config" / "voltrix" / "secrets.env"
    assert not SECRETS_PATH.resolve().is_relative_to(REPO_ROOT.resolve())


@pytest.mark.parametrize("inside", [".env", ".env.example", "query/secrets.env"])
def test_files_inside_the_project_are_never_read(monkeypatch, inside):
    def must_not_read(*args, **kwargs):
        raise AssertionError("a file inside the project was read")

    monkeypatch.setattr(anthropic_api, "dotenv_values", must_not_read)
    with pytest.raises(ConfigError, match="outside the project"):
        load_api_key({}, REPO_ROOT / inside)


def test_symlink_into_the_project_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(anthropic_api, "dotenv_values", lambda *a, **k: pytest.fail("read through a symlink"))
    link = tmp_path / "secrets.env"
    link.symlink_to(REPO_ROOT / ".env.example")
    with pytest.raises(ConfigError, match="outside the project"):
        load_api_key({}, link)


# Written out from spec 02 v1.10, step 7, never read from the code: a name
# dropped from REFUSED_ENV_NAMES must not also drop its test case.
SPEC_REFUSED_NAMES = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_CUSTOM_HEADERS",
    "ANTHROPIC_LOG",
)


@pytest.mark.parametrize("name", SPEC_REFUSED_NAMES)
@pytest.mark.parametrize("value", ["something", ""])
def test_refuses_to_start_if_an_sdk_variable_is_set(secrets_file, name, value):
    path = secrets_file(f"{KEY_NAME}={KEY}\n")
    with pytest.raises(ConfigError, match=name):
        AnthropicGenerator.from_environment(environ={KEY_NAME: KEY, name: value}, secrets_path=path)


def test_refused_names_are_the_five_in_spec_02(spec_02_text):
    assert REFUSED_ENV_NAMES == SPEC_REFUSED_NAMES
    flat = " ".join(spec_02_text.split())
    assert all(name in flat for name in SPEC_REFUSED_NAMES)
    assert "API address is fixed explicitly to https://api.anthropic.com" in flat


def test_from_environment_builds_the_configured_client(secrets_file):
    generator = AnthropicGenerator.from_environment(environ={}, secrets_path=secrets_file(f"{KEY_NAME}={KEY}\n"))
    client = generator._client
    assert client.api_key == KEY
    assert client.auth_token is None
    assert str(client.base_url).rstrip("/") == API_BASE_URL
    assert (client.max_retries, client.timeout) == (MAX_RETRIES, TIMEOUT)


# --- The key never leaks ----------------------------------------------------------------------


def test_key_never_in_logs_errors_or_output(make_chunk, secrets_file, caplog, capsys):
    caplog.set_level(logging.DEBUG)  # SDK and HTTP debug logging on
    seen = []
    replies = [
        message(ANSWER),
        message(ANSWER, stop_reason="max_tokens"),
        (401, error_body("authentication_error")),
        (429, error_body("rate_limit_error")),
        (529, error_body("overloaded_error")),
        httpx2.ConnectError("refused"),
    ]
    for reply in replies:
        api = FakeAPI(reply)
        generator = api.generator()
        seen.append(repr(generator))
        try:
            generator.generate_with_usage("q", [make_chunk("KB-002")])
        except (GeneratorServiceError, MalformedOutput) as e:
            seen += [str(e), repr(e), str(e.__cause__), repr(e.__cause__)]
        assert api.requests[0].headers["x-api-key"] == KEY  # the key was really in play
    for environ in ({KEY_NAME: KEY, "ANTHROPIC_API_KEY": KEY}, {"ANTHROPIC_BASE_URL": KEY}):
        with pytest.raises(ConfigError) as raised:
            AnthropicGenerator.from_environment(environ=environ, secrets_path=secrets_file(f"{KEY_NAME}={KEY}\n"))
        seen.append(str(raised.value))

    captured = capsys.readouterr()
    for text in [*seen, caplog.text, captured.out, captured.err]:
        assert KEY not in text


def test_module_never_names_the_sdk_default_key_variable_as_a_source():
    # ANTHROPIC_API_KEY appears only in the refusal list.
    source = open(anthropic_api.__file__, encoding="utf-8").read()
    assert source.count('"ANTHROPIC_API_KEY"') == 1
    assert "os.environ.get" not in source and "getenv" not in source
