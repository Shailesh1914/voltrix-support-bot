"""Query-side settings (spec 02, "Configuration" and "Implementation
decisions").

Two kinds of setting:
- Fixed spec values: constants below. Each one is checked against
  specs/02-query-escalation-spec.md by a test, so they can only change
  together with the spec.
- Local settings: read from .env (or the process environment) by
  load_settings(). These say where things are, never how the bot
  decides.
- The active KB version: read ONLY from the committed one-line file
  data/ACTIVE_KB_VERSION (spec 07). Setting ACTIVE_KB_VERSION in .env
  or the environment is refused, so there is one source only.
"""

import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

# --- Fixed spec values --------------------------------------------------------

# The ONE config setting for the escalation threshold (spec 02,
# decision 1). NOT YET SET: Shailesh chooses it at Step 9 and records it
# in spec 02 as "Value: <number>". Never choose or change it here alone.
ESCALATION_THRESHOLD: float | None = 0.60

# Generation model via the Anthropic API (spec 02, Processing step 7 and
# decision 2).
MODEL_ID = "claude-haiku-4-5-20251001"

# Generation settings (spec 02, Processing step 7: temperature 0).
# MAX_OUTPUT_TOKENS bounds one answer; a reply cut off at this limit is
# treated as malformed output (decision 6).
GENERATION_TEMPERATURE = 0
MAX_OUTPUT_TOKENS = 2048

# Retrieval (spec 02, Processing step 3, chosen at Step 9): k of the main
# search and of each code-boost search, and the number of different
# articles kept (one chunk each). Both are checked against spec 02.
SEARCH_K = 20
MAX_ARTICLES = 5

# Units for the grounding check of criterion 7 (spec 02, decision 9).
# Matching is tolerant of spacing and aliases; see the grounding check.
UNITS = (
    "V", "kV", "A", "mA", "Hz", "kHz", "W", "kW", "hp", "ms", "s", "sec",
    "min", "minutes", "h", "hours", "°C", "%", "mm", "mm²", "m", "Nm",
    "rpm", "Ω", "kΩ", "µF", "VAC", "VDC",
)

# --- Local settings ------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = REPO_ROOT / ".env"
ACTIVE_KB_VERSION_FILE = REPO_ROOT / "data" / "ACTIVE_KB_VERSION"
DEFAULT_HANDOFF_PATH = REPO_ROOT / "handoffs" / "handoffs.jsonl"
# Spec 08 section 4.5: HANDOFF_DIR names a folder; records go to this file
# inside it. Without HANDOFF_DIR, HANDOFF_PATH applies (spec 02 decision 8).
HANDOFF_FILE_NAME = "handoffs.jsonl"
KB_VERSION_PATTERN = re.compile(r"v[0-9]+")

# Spec values that must never come from .env (one place only).
SPEC_ONLY_NAMES = ("ESCALATION_THRESHOLD", "MODEL_ID")

# Spec 07: the served version comes only from ACTIVE_KB_VERSION_FILE.
KB_VERSION_NAME = "ACTIVE_KB_VERSION"


class ConfigError(Exception):
    """The bot must not start with this configuration (fail loudly)."""


@dataclass(frozen=True)
class Settings:
    active_kb_version: str
    handoff_path: Path
    # Optional: needed only if the Bedrock generator is selected (spec 02,
    # "Configuration"); BedrockGenerator.from_settings() checks them.
    aws_profile: str | None = None
    aws_region: str | None = None


def _env_values(env_file: Path | str | None, environ: dict[str, str] | None) -> dict[str, str]:
    """env_file's values, overridden by environ (default os.environ)."""
    values: dict[str, str] = {}
    if env_file is not None and Path(env_file).is_file():
        values.update({k: v for k, v in dotenv_values(env_file).items() if v is not None})
    values.update(os.environ if environ is None else environ)
    return values


def _refuse_kb_version_setting(values: dict[str, str]) -> None:
    if KB_VERSION_NAME in values:
        raise ConfigError(
            f"{KB_VERSION_NAME} must not be set in .env or the environment; the "
            f"active KB version is read only from {ACTIVE_KB_VERSION_FILE} (spec 07)"
        )


def read_active_kb_version(path: Path | str = ACTIVE_KB_VERSION_FILE) -> str:
    """The KB version in the one-line pointer file (spec 07).

    Surrounding whitespace is ignored; the value must look like 'v1'.
    A missing, unreadable or invalid file fails loudly.
    """
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigError(
            f"the active KB version file {path} does not exist (spec 07); "
            "it must contain one line such as 'v1'"
        ) from None
    except (OSError, UnicodeDecodeError) as e:
        raise ConfigError(f"cannot read the active KB version file {path}: {e}") from None
    version = text.strip()
    if not KB_VERSION_PATTERN.fullmatch(version):
        raise ConfigError(
            f"the active KB version file {path} must contain one version such "
            f"as 'v1', got {version!r}"
        )
    return version


def active_kb_version(
    env_file: Path | str | None = ENV_FILE,
    environ: dict[str, str] | None = None,
    kb_version_file: Path | str = ACTIVE_KB_VERSION_FILE,
) -> str:
    """The served KB version: refuses an .env/environment setting for it,
    then reads kb_version_file (spec 07)."""
    _refuse_kb_version_setting(_env_values(env_file, environ))
    return read_active_kb_version(kb_version_file)


def load_settings(
    env_file: Path | str | None = ENV_FILE,
    environ: dict[str, str] | None = None,
    kb_version_file: Path | str = ACTIVE_KB_VERSION_FILE,
) -> Settings:
    """Read local settings from env_file, overridden by environ, and the
    active KB version from kb_version_file (spec 07).

    environ defaults to os.environ. Neither is modified. AWS keys are
    never read: boto3 finds them through AWS_PROFILE. The Anthropic API
    key is never read here either (query/anthropic_api.py).
    """
    values = _env_values(env_file, environ)

    for name in SPEC_ONLY_NAMES:
        if name in values:
            raise ConfigError(
                f"{name} must not be set in .env or the environment; it is a "
                "constant in query/config.py, checked against spec 02"
            )
    _refuse_kb_version_setting(values)

    def optional(name: str) -> str | None:
        return values.get(name, "").strip() or None

    kb_version = read_active_kb_version(kb_version_file)

    handoff_path = _handoff_path(optional("HANDOFF_DIR"), optional("HANDOFF_PATH"))
    if not handoff_path.is_absolute():
        handoff_path = REPO_ROOT / handoff_path

    return Settings(
        active_kb_version=kb_version,
        handoff_path=handoff_path,
        aws_profile=optional("AWS_PROFILE"),
        aws_region=optional("AWS_REGION"),
    )


def _handoff_path(handoff_dir: str | None, handoff_path: str | None) -> Path:
    """Where handoff records go (spec 02 decision 8; spec 08 section 4.5)."""
    if handoff_dir and handoff_path:
        raise ConfigError(
            "HANDOFF_DIR and HANDOFF_PATH must not both be set (spec 08 section 4.5)"
        )
    if handoff_dir:
        return Path(handoff_dir) / HANDOFF_FILE_NAME
    return Path(handoff_path or DEFAULT_HANDOFF_PATH)


def require_threshold(threshold: float | None = ESCALATION_THRESHOLD) -> float:
    """The threshold for running the real bot; fails loudly if unset."""
    if threshold is None:
        raise ConfigError(
            "ESCALATION_THRESHOLD is NOT YET SET (spec 02). The real bot "
            "cannot run until Shailesh sets it at Step 9 in spec 02 and "
            "query/config.py."
        )
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
        raise ConfigError(f"ESCALATION_THRESHOLD must be a number, got {threshold!r}")
    if not -1.0 <= threshold <= 1.0:
        raise ConfigError(
            f"ESCALATION_THRESHOLD must be within -1.0..1.0 (the similarity "
            f"score range of spec 03), got {threshold!r}"
        )
    return float(threshold)
