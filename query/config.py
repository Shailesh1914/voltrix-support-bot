"""Query-side settings (spec 02, "Configuration" and "Implementation
decisions").

Two kinds of setting:
- Fixed spec values: constants below. Each one is checked against
  specs/02-query-escalation-spec.md by a test, so they can only change
  together with the spec.
- Local settings: read from .env (or the process environment) by
  load_settings(). These say where things are, never how the bot
  decides.
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
ESCALATION_THRESHOLD: float | None = None

# Generation model on Amazon Bedrock (spec 02, decision 2). Provisional
# until the first live Bedrock test.
BEDROCK_MODEL_ID = "global.anthropic.claude-haiku-4-5-20251001-v1:0"

# Chunks retrieved per question (spec 02, Processing step 2).
SEARCH_K = 5

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
DEFAULT_KB_VERSION = "v1"
DEFAULT_HANDOFF_PATH = REPO_ROOT / "handoffs" / "handoffs.jsonl"
KB_VERSION_PATTERN = re.compile(r"v[0-9]+")

# Spec values that must never come from .env (one place only).
SPEC_ONLY_NAMES = ("ESCALATION_THRESHOLD", "BEDROCK_MODEL_ID")


class ConfigError(Exception):
    """The bot must not start with this configuration (fail loudly)."""


@dataclass(frozen=True)
class Settings:
    aws_profile: str
    aws_region: str
    active_kb_version: str
    handoff_path: Path


def load_settings(
    env_file: Path | str | None = ENV_FILE,
    environ: dict[str, str] | None = None,
) -> Settings:
    """Read local settings from env_file, overridden by environ.

    environ defaults to os.environ. Neither is modified. AWS keys are
    never read: boto3 finds them through AWS_PROFILE.
    """
    values: dict[str, str] = {}
    if env_file is not None and Path(env_file).is_file():
        values.update({k: v for k, v in dotenv_values(env_file).items() if v is not None})
    values.update(os.environ if environ is None else environ)

    for name in SPEC_ONLY_NAMES:
        if name in values:
            raise ConfigError(
                f"{name} must not be set in .env or the environment; it is a "
                "constant in query/config.py, checked against spec 02"
            )

    def required(name: str) -> str:
        value = values.get(name, "").strip()
        if not value:
            raise ConfigError(f"{name} is not set (add it to .env)")
        return value

    kb_version = values.get("ACTIVE_KB_VERSION", "").strip() or DEFAULT_KB_VERSION
    if not KB_VERSION_PATTERN.fullmatch(kb_version):
        raise ConfigError(
            f"ACTIVE_KB_VERSION must look like 'v1', got {kb_version!r}"
        )

    handoff_path = Path(values.get("HANDOFF_PATH", "").strip() or DEFAULT_HANDOFF_PATH)
    if not handoff_path.is_absolute():
        handoff_path = REPO_ROOT / handoff_path

    return Settings(
        aws_profile=required("AWS_PROFILE"),
        aws_region=required("AWS_REGION"),
        active_kb_version=kb_version,
        handoff_path=handoff_path,
    )


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
