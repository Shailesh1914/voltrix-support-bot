"""The real generator: Claude Haiku 4.5 via the Anthropic API (spec 02,
Processing step 7; decisions 2 and 6).

Messages API, temperature 0, the submit_response tool forced, model ID
from query/config.py, API address fixed to https://api.anthropic.com.

The key (spec 02, Processing step 7):
- read from VOLTRIX_ANTHROPIC_API_KEY in the process environment, or
  else from ~/.config/voltrix/secrets.env. Never from any file inside
  the project.
- never logged, printed or put in an error message.
- the bot refuses to start if any variable the SDK would read on its own
  (REFUSED_ENV_NAMES) is set.

Never called by structural tests: they use FakeGenerator, or this class
over a faked HTTP transport (no network).
"""

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import anthropic
import httpx2
from dotenv import dotenv_values

from ingestion import Chunk
from query.config import GENERATION_TEMPERATURE, MAX_OUTPUT_TOKENS, MODEL_ID, REPO_ROOT, ConfigError
from query.generator import GeneratorOutput, GeneratorServiceError, MalformedOutput, validate_output
from query.prompt import SYSTEM_PROMPT, TOOL_DESCRIPTION, TOOL_NAME, TOOL_SCHEMA, build_user_message

log = logging.getLogger(__name__)

API_BASE_URL = "https://api.anthropic.com"

# Set explicitly, never SDK defaults. Rate limits, overload and transient
# errors are retried by the SDK (3 attempts in total, the first
# included); whatever still fails becomes "service_error".
MAX_RETRIES = 2
TIMEOUT = httpx2.Timeout(60.0, connect=10.0)

KEY_NAME = "VOLTRIX_ANTHROPIC_API_KEY"
SECRETS_PATH = Path.home() / ".config" / "voltrix" / "secrets.env"

# Variables the SDK reads from the environment by itself (spec 02,
# Processing step 7). Any of them set -> refuse to start. ANTHROPIC_LOG
# (v1.10) would make the SDK log whole requests, question included.
REFUSED_ENV_NAMES = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_CUSTOM_HEADERS",
    "ANTHROPIC_LOG",
)

TOOL = {"name": TOOL_NAME, "description": TOOL_DESCRIPTION, "input_schema": TOOL_SCHEMA}
TOOL_CHOICE = {"type": "tool", "name": TOOL_NAME}


def check_environment(environ: Mapping[str, str]) -> None:
    """Refuse to start if the SDK could pick up settings on its own."""
    found = [name for name in REFUSED_ENV_NAMES if name in environ]
    if found:
        raise ConfigError(
            f"{', '.join(found)} must not be set in the bot's environment "
            f"(spec 02); the key is read from {KEY_NAME} only"
        )


def load_api_key(environ: Mapping[str, str], secrets_path: Path = SECRETS_PATH) -> str:
    """The key from environ, or else from secrets_path (outside the project).

    Error messages name the variable or file, never the value.
    """
    check_environment(environ)
    key = environ.get(KEY_NAME, "").strip()
    if key:
        return key
    path = Path(secrets_path).expanduser().resolve()
    if path.is_relative_to(REPO_ROOT.resolve()):
        raise ConfigError(f"the API key file must be outside the project, got {path}")
    if path.is_file():
        key = (dotenv_values(path).get(KEY_NAME) or "").strip()
    if not key:
        raise ConfigError(f"{KEY_NAME} is not set (in the environment or in {path})")
    return key


def make_client(api_key: str, http_client: httpx2.Client | None = None) -> anthropic.Anthropic:
    """The SDK client with every connection setting given explicitly.

    An explicit api_key also stops the SDK from looking for credentials in
    the environment or in profile files. http_client is for tests only.
    """
    return anthropic.Anthropic(
        api_key=api_key,
        base_url=API_BASE_URL,
        max_retries=MAX_RETRIES,
        timeout=TIMEOUT,
        http_client=http_client,
    )


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    output_tokens: int


class AnthropicGenerator:
    def __init__(self, client, model_id: str = MODEL_ID):
        self._client = client
        self.model_id = model_id

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
        secrets_path: Path = SECRETS_PATH,
        http_client: httpx2.Client | None = None,
    ) -> "AnthropicGenerator":
        """Fails loudly at startup (ConfigError) on a refused variable or a
        missing key. environ defaults to os.environ."""
        environ = os.environ if environ is None else environ
        return cls(make_client(load_api_key(environ, secrets_path), http_client))

    def request(self, question: str, chunks: list[Chunk]) -> dict:
        """The messages.create() arguments for one question (exposed for tests).

        anthropic 1.x removed temperature from the SDK's signatures, not from
        the API, and Haiku 4.5 still accepts it. extra_body puts it into the
        request JSON as is, so spec 02's "Temperature 0" is still sent.
        """
        return {
            "model": self.model_id,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": build_user_message(question, chunks)}],
            "max_tokens": MAX_OUTPUT_TOKENS,
            "tools": [TOOL],
            "tool_choice": TOOL_CHOICE,
            "extra_body": {"temperature": GENERATION_TEMPERATURE},
        }

    def generate(self, question: str, chunks: list[Chunk]) -> GeneratorOutput:
        return self.generate_with_usage(question, chunks)[0]

    def generate_with_usage(self, question: str, chunks: list[Chunk]) -> tuple[GeneratorOutput, Usage]:
        """One model call; also returns token usage (for the smoke test)."""
        try:
            message = self._client.messages.create(**self.request(question, chunks))
        except anthropic.AnthropicError as e:
            # Class name and HTTP status only: the SDK's message text is
            # never passed on.
            status = getattr(e, "status_code", None)
            name = type(e).__name__ + (f" (HTTP {status})" if status is not None else "")
            log.warning("Anthropic API call failed: %s", name)
            raise GeneratorServiceError(f"Anthropic {name}") from e
        return parse_message(message), Usage(message.usage.input_tokens, message.usage.output_tokens)


def parse_message(message) -> GeneratorOutput:
    """The submit_response input from a Messages API response, validated."""
    if message.stop_reason != "tool_use":
        raise MalformedOutput(f"stop_reason is {message.stop_reason!r}, expected 'tool_use'")
    tool_uses = [b for b in message.content if getattr(b, "type", None) == "tool_use"]
    if len(tool_uses) != 1:
        raise MalformedOutput(f"expected one tool_use block, got {len(tool_uses)}")
    if tool_uses[0].name != TOOL_NAME:
        raise MalformedOutput(f"unexpected tool {tool_uses[0].name!r}")
    return validate_output(tool_uses[0].input)
