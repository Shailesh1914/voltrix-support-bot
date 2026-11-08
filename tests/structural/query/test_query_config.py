"""Stage a: settings, and spec values that must match spec 02
(criterion 9; decisions 1 and 2). The active KB version comes only
from the pointer file data/ACTIVE_KB_VERSION (spec 07); these tests use
temporary pointer files, never the real one."""

import ast
import re

import pytest

from query import config
from query.config import ConfigError, active_kb_version, load_settings, read_active_kb_version, require_threshold

GOOD_ENV = {"AWS_PROFILE": "test-profile", "AWS_REGION": "ap-south-1"}


@pytest.fixture
def pointer(tmp_path):
    """Write a temporary data/ACTIVE_KB_VERSION; return its path."""

    def _write(content: str | bytes = "v2\n"):
        path = tmp_path / "data" / "ACTIVE_KB_VERSION"
        path.parent.mkdir(exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
        return path

    return _write

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


def test_settings_from_environ_only(pointer):
    settings = load_settings(env_file=None, environ=GOOD_ENV, kb_version_file=pointer())
    assert settings.aws_profile == "test-profile"
    assert settings.aws_region == "ap-south-1"
    assert settings.active_kb_version == "v2"
    assert settings.handoff_path == config.REPO_ROOT / "handoffs" / "handoffs.jsonl"


def test_settings_from_env_file(tmp_path, pointer):
    env_file = tmp_path / ".env"
    env_file.write_text("AWS_PROFILE=file-profile\nAWS_REGION=eu-west-2\n", encoding="utf-8")
    settings = load_settings(env_file=env_file, environ={}, kb_version_file=pointer("v1\n"))
    assert settings.aws_profile == "file-profile"
    assert settings.active_kb_version == "v1"


def test_environment_overrides_env_file(tmp_path, pointer):
    env_file = tmp_path / ".env"
    env_file.write_text("AWS_PROFILE=file-profile\nAWS_REGION=eu-west-2\n", encoding="utf-8")
    settings = load_settings(env_file=env_file, environ={"AWS_PROFILE": "env-profile"}, kb_version_file=pointer())
    assert settings.aws_profile == "env-profile"
    assert settings.aws_region == "eu-west-2"


def test_missing_env_file_is_allowed(tmp_path, pointer):
    settings = load_settings(env_file=tmp_path / "absent.env", environ=GOOD_ENV, kb_version_file=pointer())
    assert settings.aws_profile == "test-profile"


def test_handoff_path_relative_to_repo_root(pointer):
    settings = load_settings(env_file=None, environ={**GOOD_ENV, "HANDOFF_PATH": "x/h.jsonl"}, kb_version_file=pointer())
    assert settings.handoff_path == config.REPO_ROOT / "x" / "h.jsonl"


def test_absolute_handoff_path_kept(tmp_path, pointer):
    path = tmp_path / "h.jsonl"
    settings = load_settings(env_file=None, environ={**GOOD_ENV, "HANDOFF_PATH": str(path)}, kb_version_file=pointer())
    assert settings.handoff_path == path


@pytest.mark.parametrize("name", ["AWS_PROFILE", "AWS_REGION"])
def test_aws_settings_are_optional(name, pointer):
    # spec 02 "Configuration": needed only if Bedrock is selected.
    env = {k: v for k, v in GOOD_ENV.items() if k != name}
    settings = load_settings(env_file=None, environ=env, kb_version_file=pointer())
    assert getattr(settings, name.lower()) is None


def test_settings_with_no_aws_values_at_all(pointer):
    settings = load_settings(env_file=None, environ={"AWS_PROFILE": "  "}, kb_version_file=pointer("v1"))
    assert (settings.aws_profile, settings.aws_region, settings.active_kb_version) == (None, None, "v1")


# --- Spec 07: the active version comes only from data/ACTIVE_KB_VERSION ---------


def test_pointer_file_is_data_active_kb_version():
    assert config.ACTIVE_KB_VERSION_FILE == config.REPO_ROOT / "data" / "ACTIVE_KB_VERSION"
    # The real bot's defaults point at that file (not read here).
    for function in (load_settings, active_kb_version):
        assert function.__defaults__[-1] == config.ACTIVE_KB_VERSION_FILE
    assert read_active_kb_version.__defaults__ == (config.ACTIVE_KB_VERSION_FILE,)


def test_real_pointer_file_is_never_read_by_tests():
    # The autouse guard in conftest.py.
    with pytest.raises(AssertionError, match="real data/ACTIVE_KB_VERSION"):
        read_active_kb_version()


@pytest.mark.parametrize(
    "content, version",
    [("v1", "v1"), ("v2\n", "v2"), ("  v3 \r\n", "v3"), ("\n\tv12\n\n", "v12")],
)
def test_pointer_value_with_surrounding_whitespace(pointer, content, version):
    path = pointer(content)
    assert read_active_kb_version(path) == version
    assert active_kb_version(env_file=None, environ={}, kb_version_file=path) == version
    assert load_settings(env_file=None, environ={}, kb_version_file=path).active_kb_version == version


@pytest.mark.parametrize(
    "content",
    ["", "  \n", "1", "kb_v1", "v", "V1", "v1.0", "v 1", "v1 v2", "v1\nv2", "v-1", "vx", '"v1"'],
)
def test_invalid_pointer_value_refuses_to_start(pointer, content):
    path = pointer(content)
    with pytest.raises(ConfigError, match="ACTIVE_KB_VERSION"):
        read_active_kb_version(path)
    with pytest.raises(ConfigError, match="ACTIVE_KB_VERSION"):
        load_settings(env_file=None, environ=GOOD_ENV, kb_version_file=path)


def test_missing_pointer_file_refuses_to_start(tmp_path):
    # Never a silent default such as v1.
    absent = tmp_path / "data" / "ACTIVE_KB_VERSION"
    with pytest.raises(ConfigError, match="does not exist"):
        read_active_kb_version(absent)
    with pytest.raises(ConfigError, match="ACTIVE_KB_VERSION"):
        load_settings(env_file=None, environ=GOOD_ENV, kb_version_file=absent)
    with pytest.raises(ConfigError, match="ACTIVE_KB_VERSION"):
        active_kb_version(env_file=None, environ={}, kb_version_file=absent)


def test_unreadable_pointer_refuses_to_start(pointer, tmp_path):
    with pytest.raises(ConfigError, match="ACTIVE_KB_VERSION"):
        read_active_kb_version(pointer(b"\xff\xfe v1"))
    folder = tmp_path / "folder"
    folder.mkdir()
    with pytest.raises(ConfigError, match="cannot read"):
        read_active_kb_version(folder)


@pytest.mark.parametrize("value", ["v2", "v1", ""])
def test_kb_version_in_env_file_refuses_to_start(tmp_path, pointer, value):
    # Spec 07: refused even when it agrees with the file, or is empty.
    env_file = tmp_path / ".env"
    env_file.write_text(f"AWS_PROFILE=p\nACTIVE_KB_VERSION={value}\n", encoding="utf-8")
    path = pointer("v1")
    with pytest.raises(ConfigError, match="ACTIVE_KB_VERSION must not be set in .env"):
        load_settings(env_file=env_file, environ={}, kb_version_file=path)
    with pytest.raises(ConfigError, match="ACTIVE_KB_VERSION must not be set in .env"):
        active_kb_version(env_file=env_file, environ={}, kb_version_file=path)


@pytest.mark.parametrize("value", ["v2", "v1", ""])
def test_kb_version_in_environment_refuses_to_start(pointer, value):
    path = pointer("v1")
    environ = {**GOOD_ENV, "ACTIVE_KB_VERSION": value}
    with pytest.raises(ConfigError, match="ACTIVE_KB_VERSION must not be set in .env or the environment"):
        load_settings(env_file=None, environ=environ, kb_version_file=path)
    with pytest.raises(ConfigError, match="ACTIVE_KB_VERSION must not be set"):
        active_kb_version(env_file=None, environ=environ, kb_version_file=path)


def test_kb_version_setting_refused_even_without_pointer_file(tmp_path):
    # One source only: the .env setting is never a fallback.
    with pytest.raises(ConfigError, match="must not be set"):
        load_settings(env_file=None, environ={"ACTIVE_KB_VERSION": "v1"}, kb_version_file=tmp_path / "absent")


def test_active_kb_version_reads_os_environ_by_default(pointer, monkeypatch):
    monkeypatch.setenv("ACTIVE_KB_VERSION", "v2")
    with pytest.raises(ConfigError, match="must not be set"):
        active_kb_version(env_file=None, kb_version_file=pointer("v2"))
    with pytest.raises(ConfigError, match="must not be set"):
        load_settings(env_file=None, kb_version_file=pointer("v2"))


@pytest.mark.parametrize("name", ["ESCALATION_THRESHOLD", "MODEL_ID"])
def test_spec_values_in_env_fail_loudly(name, tmp_path, pointer):
    env_file = tmp_path / ".env"
    env_file.write_text(f"{name}=0.5\nAWS_PROFILE=p\nAWS_REGION=r\n", encoding="utf-8")
    with pytest.raises(ConfigError, match=name):
        load_settings(env_file=env_file, environ={}, kb_version_file=pointer())


def test_aws_keys_are_never_part_of_settings(pointer):
    env = {**GOOD_ENV, "AWS_ACCESS_KEY_ID": "AKIAEXAMPLE", "AWS_SECRET_ACCESS_KEY": "secret"}
    settings = load_settings(env_file=None, environ=env, kb_version_file=pointer())
    assert "AKIAEXAMPLE" not in repr(settings) and "secret" not in repr(settings)
