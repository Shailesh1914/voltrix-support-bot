"""The two small query-side changes for spec 08 (Session Q):
- HANDOFF_DIR (spec 08 section 4.5) in query/config.py
- build_flow(make_generator) in query/ask.py, used by the web app
"""

import pytest

from query import ask, config
from query.config import ConfigError, Settings, load_settings
from query.generator import FakeGenerator

ANSWER = {"decision": "answer", "answer": "Lengthen P-06.", "used_article_ids": ["KB-001"]}


@pytest.fixture
def pointer(tmp_path):
    path = tmp_path / "ACTIVE_KB_VERSION"
    path.write_text("v2\n", encoding="utf-8")
    return path


def settings(pointer, **environ):
    return load_settings(env_file=None, environ=environ, kb_version_file=pointer)


# --- HANDOFF_DIR ------------------------------------------------------------------------


def test_handoff_dir_names_the_folder_of_handoffs_jsonl(pointer, tmp_path):
    folder = tmp_path / "tmp" / "handoffs"
    assert settings(pointer, HANDOFF_DIR=str(folder)).handoff_path == folder / "handoffs.jsonl"


def test_lambda_handoff_dir(pointer):
    assert settings(pointer, HANDOFF_DIR="/tmp/handoffs").handoff_path.as_posix() == "/tmp/handoffs/handoffs.jsonl"


def test_relative_handoff_dir_is_under_the_repo_root(pointer):
    assert settings(pointer, HANDOFF_DIR="x").handoff_path == config.REPO_ROOT / "x" / "handoffs.jsonl"


def test_without_handoff_dir_spec_02_applies_unchanged(pointer, tmp_path):
    assert settings(pointer).handoff_path == config.REPO_ROOT / "handoffs" / "handoffs.jsonl"
    assert settings(pointer, HANDOFF_PATH=str(tmp_path / "h.jsonl")).handoff_path == tmp_path / "h.jsonl"


def test_handoff_dir_and_path_together_stop_the_start_up(pointer, tmp_path):
    with pytest.raises(ConfigError, match="HANDOFF_DIR and HANDOFF_PATH"):
        settings(pointer, HANDOFF_DIR=str(tmp_path), HANDOFF_PATH=str(tmp_path / "h.jsonl"))


def test_handoff_dir_from_env_file_and_path_from_environment_also_refused(pointer, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(f"HANDOFF_PATH={tmp_path / 'h.jsonl'}\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="HANDOFF_DIR and HANDOFF_PATH"):
        load_settings(env_file=env_file, environ={"HANDOFF_DIR": str(tmp_path)}, kb_version_file=pointer)


# --- build_flow(make_generator) ---------------------------------------------------------------


def test_make_generator_gets_the_settings_and_builds_the_generator(monkeypatch, tmp_path, fake_retriever):
    the_settings = Settings("v2", tmp_path / "h.jsonl")
    generator = FakeGenerator(ANSWER)
    seen = []

    def must_not_run():
        raise AssertionError("the default key reader ran")

    monkeypatch.setattr(config, "ESCALATION_THRESHOLD", 0.42)  # test value only
    monkeypatch.setattr(ask, "load_settings", lambda: the_settings)
    monkeypatch.setattr(ask, "open_retrieval", lambda version: fake_retriever(kb_version=version))
    monkeypatch.setattr(ask.AnthropicGenerator, "from_environment", must_not_run)

    flow = ask.build_flow(lambda s: seen.append(s) or generator)
    assert seen == [the_settings]
    assert flow._generator is generator
    assert flow._threshold == 0.42 and flow._kb_version == "v2"
    assert flow._handoff_store.path == the_settings.handoff_path


def test_make_generator_runs_before_the_index_is_opened(monkeypatch, tmp_path):
    def no_secrets(settings):
        raise ConfigError("VOLTRIX_ACCESS_CODE is not set")

    def must_not_run(version):
        raise AssertionError("index opened before the generator was built")

    monkeypatch.setattr(config, "ESCALATION_THRESHOLD", 0.42)  # test value only
    monkeypatch.setattr(ask, "load_settings", lambda: Settings("v1", tmp_path / "h.jsonl"))
    monkeypatch.setattr(ask, "open_retrieval", must_not_run)
    with pytest.raises(ConfigError, match="VOLTRIX_ACCESS_CODE"):
        ask.build_flow(no_secrets)
