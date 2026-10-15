"""A generator for a Claude model on Amazon Bedrock: kept but UNUSED
(spec 02, Processing step 7). The bot uses query/anthropic_api.py.
Switching back to Bedrock is a spec change and requires re-running the
evaluation.

Converse API, temperature 0, the submit_response tool forced. Credentials
come from AWS_PROFILE through boto3; this module never reads keys.
AWS_PROFILE and AWS_REGION are required only here (spec 02,
"Configuration").

Never called by structural tests: they use FakeGenerator, or this class
with a botocore Stubber (no network).
"""

import logging

from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from ingestion import Chunk
from query.config import GENERATION_TEMPERATURE, MAX_OUTPUT_TOKENS, ConfigError, Settings
from query.generator import GeneratorOutput, GeneratorServiceError, MalformedOutput, validate_output
from query.prompt import SYSTEM_PROMPT, TOOL_CONFIG, TOOL_NAME, build_user_message

log = logging.getLogger(__name__)

# The Bedrock form of the model ID. No longer pinned by spec 02 (decision 2
# pins the Anthropic API ID in query/config.py), so no test checks it
# against the spec; it must be pinned again before Bedrock is ever used.
BEDROCK_MODEL_ID = "global.anthropic.claude-haiku-4-5-20251001-v1:0"

# Throttling and transient errors are retried by botocore (3 attempts in
# total, the first included); whatever still fails becomes "service_error".
CLIENT_CONFIG = Config(
    retries={"mode": "standard", "total_max_attempts": 3},
    connect_timeout=10,
    read_timeout=60,
)


class BedrockGenerator:
    def __init__(self, client, model_id: str = BEDROCK_MODEL_ID):
        self._client = client
        self.model_id = model_id

    @classmethod
    def from_settings(cls, settings: Settings) -> "BedrockGenerator":
        """Client for AWS_PROFILE and AWS_REGION. Fails loudly at startup
        if either is not set, or if the profile does not exist."""
        for name, value in (("AWS_PROFILE", settings.aws_profile), ("AWS_REGION", settings.aws_region)):
            if not value:
                raise ConfigError(f"{name} is not set (add it to .env); the Bedrock generator needs it")
        import boto3  # noqa: PLC0415 (only the real bot needs boto3 loaded)

        session = boto3.Session(profile_name=settings.aws_profile, region_name=settings.aws_region)
        return cls(session.client("bedrock-runtime", config=CLIENT_CONFIG))

    def request(self, question: str, chunks: list[Chunk]) -> dict:
        """The Converse request for one question (exposed for tests)."""
        return {
            "modelId": self.model_id,
            "system": [{"text": SYSTEM_PROMPT}],
            "messages": [
                {"role": "user", "content": [{"text": build_user_message(question, chunks)}]}
            ],
            "inferenceConfig": {
                "temperature": GENERATION_TEMPERATURE,
                "maxTokens": MAX_OUTPUT_TOKENS,
            },
            "toolConfig": TOOL_CONFIG,
        }

    def generate(self, question: str, chunks: list[Chunk]) -> GeneratorOutput:
        try:
            response = self._client.converse(**self.request(question, chunks))
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "Unknown")
            log.warning("Bedrock call failed: %s", code)
            raise GeneratorServiceError(f"Bedrock {code}") from e
        except BotoCoreError as e:
            log.warning("Bedrock call failed: %s", type(e).__name__)
            raise GeneratorServiceError(f"Bedrock {type(e).__name__}") from e
        return parse_response(response)


def parse_response(response: dict) -> GeneratorOutput:
    """The submit_response input from a Converse response, validated."""
    stop_reason = response.get("stopReason")
    if stop_reason != "tool_use":
        raise MalformedOutput(f"stopReason is {stop_reason!r}, expected 'tool_use'")
    content = response.get("output", {}).get("message", {}).get("content", [])
    tool_uses = [b["toolUse"] for b in content if isinstance(b, dict) and "toolUse" in b]
    if len(tool_uses) != 1:
        raise MalformedOutput(f"expected one toolUse block, got {len(tool_uses)}")
    if tool_uses[0].get("name") != TOOL_NAME:
        raise MalformedOutput(f"unexpected tool {tool_uses[0].get('name')!r}")
    return validate_output(tool_uses[0].get("input"))
