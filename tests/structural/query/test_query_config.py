"""Stage a: settings, and spec values that must match spec 02
(criterion 9; decisions 1 and 2)."""

import ast
import re

import pytest

from query import config
from query.config import ConfigError, load_settings, require_threshold

GOOD_ENV = {"AWS_PROFILE": "test-profile", "AWS_REGION": "ap-south-1", "ACTIVE_KB_VERSION": "v2"}

# Any Claude model ID: Anthropic API IDs (claude-haiku-4-5-20251001) and,
# inside Bedrock IDs (global.anthropic.claude-...-v1:0), their claude- part,
# so a Bedrock ID in the spec also fails the comparison.
MODEL_ID_PATTERN = re.compile(r"\bclaude-[A-Za-z0-9-]*[A-Za-z0-9]")


def spec_threshold_line(spec_text: str) -> str:
    lines = [line for line in spec_text.splitlines() if line.startswith("Value:")]
    assert len(lines) == 1, f"spec 02 must have exactly one 'Value:' line, found {lines}"
    return lines[0][len("Value:"):].strip()


# --- Criterion 9 and decision 2: config equals spec 02 -----------------------


def test_criterion_9_threshold_in_config_equals_spec(spec_02_text):
    value = spec_threshold_line(spec_02_text)
    if value.startswith("NOT YET SET"):
        assert config.ESCALATION_THRESHOLD is None
    else:
        match = re.match(r"(-?[0-9]+(?:\.[0-9]+)?)\b", value)
        assert match, f"spec 02 'Value:' line is not a number: {value!r}"
        assert config.ESCALATION_THRESHOLD == float(match.group(1))


def test_model_id_in_config_equals_spec(spec_02_text):
    ids_in_spec = set(MODEL_ID_PATTERN.findall(spec_02_text))
    assert ids_in_spec == {config.MODEL_ID}


@pytest.mark.parametrize(
    "text, found",
    [
        ("Model ID: claude-haiku-4-5-20251001. Temperature 0.", {"claude-haiku-4-5-20251001"}),
        ("global.anthropic.claude-haiku-4-5-20251001-v1:0", {"claude-haiku-4-5-20251001-v1"}),
        ("Claude Haiku 4.5 via the Anthropic API (Claude Console).", set()),
    ],
)
def test_model_id_pattern(text, found):
    assert set(MODEL_ID_PATTERN.findall(text)) == found


def test_threshold_is_assigned_only_in_config(query_dir):
    # "The value lives in this spec and in ONE config setting."
    for path in query_dir.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
                targets = [node.target]
            names = {t.id for t in targets if isinstance(t, ast.Name)}
            if "ESCALATION_THRESHOLD" in names:
                assert path.name == "config.py" and node.col_offset == 0, (
                    f"ESCALATION_THRESHOLD assigned in {path}:{node.lineno}"
                )


# --- Threshold: the real bot fails loudly while unset -------------------------


def test_unset_threshold_fails_loudly():
    with pytest.raises(ConfigError, match="NOT YET SET"):
        require_threshold(None)


def test_default_is_the_config_constant(monkeypatch):
    # require_threshold() with no argument reads the config constant.
    if config.ESCALATION_THRESHOLD is None:
        with pytest.raises(ConfigError, match="NOT YET SET"):
            require_threshold()
    else:
        assert require_threshold() == config.ESCALATION_THRESHOLD


@pytest.mark.parametrize("value", [0.0, 0.65, -1.0, 1.0, 1])
def test_threshold_passed_in_is_accepted(value):
    assert require_threshold(value) == float(value)


@pytest.mark.parametrize("value", [1.01, -1.5, "0.6", True, float("nan")])
def test_invalid_threshold_fails(value):
    with pytest.raises(ConfigError):
        require_threshold(value)


# --- Local settings from .env --------------------------------------------------


def test_settings_from_environ_only():
    settings = load_settings(env_file=None, environ=GOOD_ENV)
    assert settings.aws_profile == "test-profile"
    assert settings.aws_region == "ap-south-1"
    assert settings.active_kb_version == "v2"
    assert settings.handoff_path == config.REPO_ROOT / "handoffs" / "handoffs.jsonl"


def test_settings_from_env_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("AWS_PROFILE=file-profile\nAWS_REGION=eu-west-2\n", encoding="utf-8")
    settings = load_settings(env_file=env_file, environ={})
    assert settings.aws_profile == "file-profile"
    assert settings.active_kb_version == "v1"  # spec 02 default


def test_environment_overrides_env_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("AWS_PROFILE=file-profile\nAWS_REGION=eu-west-2\n", encoding="utf-8")
    settings = load_settings(env_file=env_file, environ={"AWS_PROFILE": "env-profile"})
    assert settings.aws_profile == "env-profile"
    assert settings.aws_region == "eu-west-2"


def test_missing_env_file_is_allowed(tmp_path):
    settings = load_settings(env_file=tmp_path / "absent.env", environ=GOOD_ENV)
    assert settings.aws_profile == "test-profile"


def test_handoff_path_relative_to_repo_root():
    settings = load_settings(env_file=None, environ={**GOOD_ENV, "HANDOFF_PATH": "x/h.jsonl"})
    assert settings.handoff_path == config.REPO_ROOT / "x" / "h.jsonl"


def test_absolute_handoff_path_kept(tmp_path):
    path = tmp_path / "h.jsonl"
    settings = load_settings(env_file=None, environ={**GOOD_ENV, "HANDOFF_PATH": str(path)})
    assert settings.handoff_path == path


@pytest.mark.parametrize("name", ["AWS_PROFILE", "AWS_REGION"])
def test_aws_settings_are_optional(name):
    # spec 02 "Configuration": needed only if Bedrock is selected.
    env = {k: v for k, v in GOOD_ENV.items() if k != name}
    settings = load_settings(env_file=None, environ=env)
    assert getattr(settings, name.lower()) is None


def test_settings_with_no_aws_values_at_all():
    settings = load_settings(env_file=None, environ={"AWS_PROFILE": "  "})
    assert (settings.aws_profile, settings.aws_region, settings.active_kb_version) == (None, None, "v1")


@pytest.mark.parametrize("version", ["1", "kb_v1", "v", "V1", "v1.0"])
def test_invalid_kb_version_fails(version):
    with pytest.raises(ConfigError, match="ACTIVE_KB_VERSION"):
        load_settings(env_file=None, environ={**GOOD_ENV, "ACTIVE_KB_VERSION": version})


@pytest.mark.parametrize("name", ["ESCALATION_THRESHOLD", "MODEL_ID"])
def test_spec_values_in_env_fail_loudly(name, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(f"{name}=0.5\nAWS_PROFILE=p\nAWS_REGION=r\n", encoding="utf-8")
    with pytest.raises(ConfigError, match=name):
        load_settings(env_file=env_file, environ={})


def test_aws_keys_are_never_part_of_settings():
    env = {**GOOD_ENV, "AWS_ACCESS_KEY_ID": "AKIAEXAMPLE", "AWS_SECRET_ACCESS_KEY": "secret"}
    settings = load_settings(env_file=None, environ=env)
    assert "AKIAEXAMPLE" not in repr(settings) and "secret" not in repr(settings)
