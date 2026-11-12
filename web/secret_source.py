"""Where the web app's two secrets come from (spec 08 section 5).

VOLTRIX_SECRETS_SOURCE (not a secret) chooses:
- "file" (or not set): VOLTRIX_ANTHROPIC_API_KEY and VOLTRIX_ACCESS_CODE
  from the secrets file outside the project (~/.config/voltrix/secrets.env,
  mounted read-only into the laptop container). The key is found exactly
  as the command line bot finds it (query/anthropic_api.load_api_key).
- "parameter_store": the SecureStrings /voltrix/anthropic-key and
  /voltrix/access-code, read once at start-up with decryption. The key or
  the code also set as an environment variable stops the start-up.
Any other value stops the start-up.

In both modes: any variable starting with ANTHROPIC_ stops the start-up,
and the access code must be at least 12 characters.

Error messages name the setting, never its value.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

from query.anthropic_api import KEY_NAME, SECRETS_PATH, load_api_key
from query.config import REPO_ROOT, ConfigError

SOURCE_NAME = "VOLTRIX_SECRETS_SOURCE"
FILE_SOURCE = "file"
PARAMETER_STORE_SOURCE = "parameter_store"

ACCESS_CODE_NAME = "VOLTRIX_ACCESS_CODE"
MIN_ACCESS_CODE_LENGTH = 12

KEY_PARAMETER = "/voltrix/anthropic-key"
ACCESS_CODE_PARAMETER = "/voltrix/access-code"

REFUSED_PREFIX = "ANTHROPIC_"


@dataclass(frozen=True, repr=False)
class Secrets:
    anthropic_key: str
    access_code: str

    def __repr__(self) -> str:
        return "Secrets(<hidden>)"


def default_ssm_client():
    """A Parameter Store client. boto3 is imported only in this mode."""
    import boto3

    return boto3.client("ssm")


def refuse_anthropic_variables(environ: Mapping[str, str]) -> None:
    found = sorted(name for name in environ if name.startswith(REFUSED_PREFIX))
    if found:
        raise ConfigError(
            f"{', '.join(found)} must not be set in the bot's environment "
            f"(spec 08 section 5: variables starting with {REFUSED_PREFIX} are refused)"
        )


def load_secrets(
    environ: Mapping[str, str],
    secrets_path: Path = SECRETS_PATH,
    ssm_client_factory: Callable[[], object] = default_ssm_client,
) -> Secrets:
    refuse_anthropic_variables(environ)
    source = environ.get(SOURCE_NAME, FILE_SOURCE)
    if source == FILE_SOURCE:
        secrets = _from_file(environ, secrets_path)
        code_setting = ACCESS_CODE_NAME
    elif source == PARAMETER_STORE_SOURCE:
        secrets = _from_parameter_store(environ, ssm_client_factory)
        code_setting = ACCESS_CODE_PARAMETER
    else:
        raise ConfigError(
            f"{SOURCE_NAME} must be {FILE_SOURCE!r} or {PARAMETER_STORE_SOURCE!r} (spec 08 section 5)"
        )
    if len(secrets.access_code) < MIN_ACCESS_CODE_LENGTH:
        raise ConfigError(
            f"{code_setting} must be at least {MIN_ACCESS_CODE_LENGTH} characters (spec 08 section 5)"
        )
    return secrets


def _from_file(environ: Mapping[str, str], secrets_path: Path) -> Secrets:
    """Like load_api_key(): the environment first, else the secrets file."""
    key = load_api_key(environ, secrets_path)
    code = environ.get(ACCESS_CODE_NAME, "").strip()
    if not code:
        path = Path(secrets_path).expanduser().resolve()
        if path.is_relative_to(REPO_ROOT.resolve()):
            raise ConfigError(f"the secrets file must be outside the project, got {path}")
        if path.is_file():
            code = (dotenv_values(path).get(ACCESS_CODE_NAME) or "").strip()
    if not code:
        raise ConfigError(f"{ACCESS_CODE_NAME} is not set (in the environment or in {secrets_path})")
    return Secrets(key, code)


def _from_parameter_store(environ: Mapping[str, str], ssm_client_factory: Callable[[], object]) -> Secrets:
    in_environment = [name for name in (KEY_NAME, ACCESS_CODE_NAME) if name in environ]
    if in_environment:
        raise ConfigError(
            f"{', '.join(in_environment)} must not be set as an environment variable when "
            f"{SOURCE_NAME}={PARAMETER_STORE_SOURCE} (spec 08 section 5)"
        )
    client = ssm_client_factory()
    return Secrets(_parameter(client, KEY_PARAMETER), _parameter(client, ACCESS_CODE_PARAMETER))


def _parameter(client, name: str) -> str:
    try:
        response = client.get_parameter(Name=name, WithDecryption=True)
        value = response["Parameter"]["Value"]
    except Exception as e:
        # Class name only: the SDK's message text is never passed on.
        raise ConfigError(f"cannot read the Parameter Store parameter {name}: {type(e).__name__}") from None
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"the Parameter Store parameter {name} is empty")
    return value.strip()
