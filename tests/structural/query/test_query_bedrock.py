"""Stage c: BedrockGenerator with a botocore Stubber (spec 02, step 7;
decisions 2 and 6). Kept but unused since spec 02 v1.7. No network:
every socket connection fails."""

import boto3
import pytest
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import EndpointConnectionError, NoCredentialsError, ReadTimeoutError
from botocore.stub import Stubber

from query import bedrock
from query.bedrock import BEDROCK_MODEL_ID, CLIENT_CONFIG, BedrockGenerator, parse_response
from query.config import ConfigError, Settings
from query.generator import GeneratorOutput, GeneratorServiceError, MalformedOutput
from query.prompt import SYSTEM_PROMPT, TOOL_CONFIG, build_user_message


pytestmark = pytest.mark.usefixtures("no_network")


@pytest.fixture
def client():
    # Unsigned: no credentials of any kind are needed or read.
    return boto3.client(
        "bedrock-runtime",
        region_name="ap-south-1",
        config=CLIENT_CONFIG.merge(Config(signature_version=UNSIGNED)),
    )


def converse_response(tool_input=None, stop_reason="tool_use", content=None):
    if content is None:
        content = [
            {"text": "Here is my response."},
            {"toolUse": {"toolUseId": "tooluse_1", "name": "submit_response", "input": tool_input}},
        ]
    return {
        "output": {"message": {"role": "assistant", "content": content}},
        "stopReason": stop_reason,
        "usage": {"inputTokens": 1000, "outputTokens": 100, "totalTokens": 1100},
        "metrics": {"latencyMs": 900},
    }


ANSWER = {"decision": "answer", "answer": "Lengthen P-06.", "used_article_ids": ["KB-002"]}


# --- Request ------------------------------------------------------------------------


def test_request_shape(make_chunk):
    chunks = [make_chunk("KB-002", n=1)]
    request = BedrockGenerator(client=None).request("E-02 on stop", chunks)
    assert request == {
        "modelId": BEDROCK_MODEL_ID,
        "system": [{"text": SYSTEM_PROMPT}],
        "messages": [{"role": "user", "content": [{"text": build_user_message("E-02 on stop", chunks)}]}],
        "inferenceConfig": {"temperature": 0, "maxTokens": 2048},
        "toolConfig": TOOL_CONFIG,
    }


def test_model_id_comes_from_config():
    assert BedrockGenerator(client=None).model_id == BEDROCK_MODEL_ID


def test_one_call_with_exact_request(client, make_chunk):
    chunks = [make_chunk("KB-002", n=1), make_chunk("KB-001", n=2)]
    generator = BedrockGenerator(client)
    with Stubber(client) as stub:
        stub.add_response("converse", converse_response(ANSWER), generator.request("E-02 on stop", chunks))
        output = generator.generate("E-02 on stop", chunks)
        stub.assert_no_pending_responses()
    assert output == GeneratorOutput("answer", "Lengthen P-06.", ("KB-002",))


def test_escalation_decision_is_returned(client, make_chunk):
    out = {"decision": "out_of_scope", "answer": "", "used_article_ids": []}
    with Stubber(client) as stub:
        stub.add_response("converse", converse_response(out))
        assert BedrockGenerator(client).generate("price?", [make_chunk()]).decision == "out_of_scope"


# --- Malformed output -> MalformedOutput ---------------------------------------------


@pytest.mark.parametrize(
    "response",
    [
        converse_response(content=[{"text": "E-02 means overcurrent."}], stop_reason="end_turn"),
        converse_response(ANSWER, stop_reason="max_tokens"),
        converse_response(ANSWER, stop_reason="malformed_tool_use"),
        converse_response(ANSWER, stop_reason="content_filtered"),
        converse_response(content=[], stop_reason="tool_use"),
        converse_response(
            content=[
                {"toolUse": {"toolUseId": "a", "name": "submit_response", "input": ANSWER}},
                {"toolUse": {"toolUseId": "b", "name": "submit_response", "input": ANSWER}},
            ]
        ),
        converse_response(content=[{"toolUse": {"toolUseId": "a", "name": "other_tool", "input": ANSWER}}]),
        converse_response({"decision": "maybe", "answer": "", "used_article_ids": []}),
        converse_response({"decision": "answer", "answer": "x"}),
        converse_response("not an object"),
    ],
    ids=[
        "text_only",
        "max_tokens",
        "malformed_tool_use",
        "content_filtered",
        "no_content",
        "two_tool_uses",
        "wrong_tool",
        "bad_decision",
        "missing_field",
        "input_not_object",
    ],
)
def test_malformed_output(client, make_chunk, response):
    with Stubber(client) as stub:
        stub.add_response("converse", response)
        with pytest.raises(MalformedOutput):
            BedrockGenerator(client).generate("q", [make_chunk()])


def test_parse_response_ignores_text_blocks():
    assert parse_response(converse_response(ANSWER)).answer == "Lengthen P-06."


# --- API errors -> GeneratorServiceError ("service_error") -----------------------


@pytest.mark.parametrize(
    "code",
    [
        "AccessDeniedException",
        "ThrottlingException",
        "ResourceNotFoundException",
        "ModelTimeoutException",
        "InternalServerException",
        "ServiceUnavailableException",
        "ValidationException",
        "ModelNotReadyException",
        "ModelErrorException",
    ],
)
def test_client_errors_are_service_errors(client, make_chunk, code):
    with Stubber(client) as stub:
        stub.add_client_error("converse", service_error_code=code, http_status_code=400)
        with pytest.raises(GeneratorServiceError, match=code):
            BedrockGenerator(client).generate("q", [make_chunk()])


@pytest.mark.parametrize(
    "error",
    [
        EndpointConnectionError(endpoint_url="https://bedrock-runtime.ap-south-1.amazonaws.com"),
        ReadTimeoutError(endpoint_url="https://bedrock-runtime.ap-south-1.amazonaws.com"),
        NoCredentialsError(),
    ],
    ids=lambda e: type(e).__name__,
)
def test_connection_and_credential_errors_are_service_errors(make_chunk, error):
    class FailingClient:
        def converse(self, **kwargs):
            raise error

    with pytest.raises(GeneratorServiceError, match=type(error).__name__):
        BedrockGenerator(FailingClient()).generate("q", [make_chunk()])


def test_errors_are_logged_without_question_text(client, make_chunk, caplog):
    with Stubber(client) as stub:
        stub.add_client_error("converse", service_error_code="ThrottlingException")
        with pytest.raises(GeneratorServiceError):
            BedrockGenerator(client).generate("secret question text", [make_chunk()])
    assert "ThrottlingException" in caplog.text
    assert "secret question text" not in caplog.text


# --- Client from settings: AWS_PROFILE, never keys -----------------------------------


def test_client_uses_profile_and_region(monkeypatch, tmp_path):
    created = {}

    class FakeSession:
        def __init__(self, **kwargs):
            created["session"] = kwargs

        def client(self, service, config=None):
            created["client"] = (service, config)
            return "client"

    monkeypatch.setattr(boto3, "Session", FakeSession)
    settings = Settings("v1", tmp_path / "h.jsonl", aws_profile="my-profile", aws_region="ap-south-1")
    generator = BedrockGenerator.from_settings(settings)
    assert created["session"] == {"profile_name": "my-profile", "region_name": "ap-south-1"}
    assert created["client"] == ("bedrock-runtime", CLIENT_CONFIG)
    assert generator.model_id == BEDROCK_MODEL_ID


@pytest.mark.parametrize("missing", ["AWS_PROFILE", "AWS_REGION"])
def test_aws_settings_required_only_when_bedrock_is_selected(monkeypatch, tmp_path, missing):
    # spec 02 "Configuration": optional for the bot, required for Bedrock.
    def must_not_run(**kwargs):
        raise AssertionError("session created without AWS settings")

    monkeypatch.setattr(boto3, "Session", must_not_run)
    values = {"aws_profile": "my-profile", "aws_region": "ap-south-1"}
    values["aws_profile" if missing == "AWS_PROFILE" else "aws_region"] = None
    with pytest.raises(ConfigError, match=missing):
        BedrockGenerator.from_settings(Settings("v1", tmp_path / "h.jsonl", **values))


def test_retries_and_timeouts():
    assert CLIENT_CONFIG.retries == {"mode": "standard", "total_max_attempts": 3}
    assert (CLIENT_CONFIG.connect_timeout, CLIENT_CONFIG.read_timeout) == (10, 60)


def test_module_never_reads_keys():
    source = open(bedrock.__file__, encoding="utf-8").read()
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "aws_access_key_id", "aws_secret_access_key"):
        assert name not in source
