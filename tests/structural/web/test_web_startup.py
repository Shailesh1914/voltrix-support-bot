"""Start-up (spec 08 sections 4.5 and 5): web.startup.build_app() and
python -m web. The flow is built by query.ask.build_flow(); settings,
index and Parameter Store are fakes. No network, no model calls."""

import json

import pytest
from fastapi.testclient import TestClient

from ingestion import RetrievalError
from query import ask, config
from query.anthropic_api import AnthropicGenerator
from query.config import ConfigError, load_settings
from web import __main__ as web_main
from web import startup
from web_testkit import CODE, KEY, CountingRetriever, make_chunk

PS_ENV = {"VOLTRIX_SECRETS_SOURCE": "parameter_store"}


class FakeSSM:
    def __init__(self):
        self.calls = []

    def get_parameter(self, Name, WithDecryption):
        self.calls.append((Name, WithDecryption))
        value = {"/voltrix/anthropic-key": KEY, "/voltrix/access-code": CODE}[Name]
        return {"Parameter": {"Value": value}}


@pytest.fixture
def fake_world(monkeypatch, tmp_path):
    """Real build_flow() and load_settings() over a temporary pointer file
    (no .env); a counting fake index. Returns a namespace of handles."""

    class World:
        pointer = tmp_path / "ACTIVE_KB_VERSION"
        opened: list[str] = []
        retriever = None
        ssm = FakeSSM()

    World.pointer.write_text("v2\n", encoding="utf-8")

    def fake_open(version):
        World.opened.append(version)
        # Low scores: questions escalate as low_similarity, no Claude call.
        World.retriever = CountingRetriever([make_chunk(score=0.01)], kb_version=version)
        return World.retriever

    monkeypatch.setattr(ask, "load_settings", lambda: load_settings(env_file=None, kb_version_file=World.pointer))
    monkeypatch.setattr(ask, "open_retrieval", fake_open)
    return World


def build(world, environ, **kwargs):
    import os

    for name, value in environ.items():
        os.environ[name] = value  # cleaned again by the autouse fixture's monkeypatch
    return startup.build_app(ssm_client_factory=lambda: world.ssm, **kwargs)


@pytest.fixture(autouse=True)
def restore_environ(monkeypatch):
    import os

    snapshot = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(snapshot)


def test_parameter_store_app_reads_secrets_once_and_serves(fake_world, tmp_path, monkeypatch):
    monkeypatch.setenv("HANDOFF_DIR", str(tmp_path / "handoffs"))
    app = build(fake_world, PS_ENV)
    assert fake_world.ssm.calls == [("/voltrix/anthropic-key", True), ("/voltrix/access-code", True)]
    client = TestClient(app)
    assert client.get("/health").json()["kb_version"] == "v2"
    assert client.post("/ask", json={"question": "x"}, headers={"X-Access-Code": "wrong-code-wrong"}).status_code == 401
    response = client.post("/ask", json={"question": "E1 on start"}, headers={"X-Access-Code": CODE})
    assert response.status_code == 200 and response.json()["escalation_reason"] == "low_similarity"
    assert len(fake_world.ssm.calls) == 2  # never again after start-up


def test_flow_is_built_like_the_command_line_bot(fake_world, monkeypatch):
    built = []
    real_build = ask.build_flow

    def spy(make_generator=None):
        flow = real_build(make_generator)
        built.append(flow)
        return flow

    monkeypatch.setattr(ask, "build_flow", spy)
    build(fake_world, PS_ENV)
    (flow,) = built
    assert fake_world.opened == ["v2"]
    assert flow._threshold == config.ESCALATION_THRESHOLD
    assert isinstance(flow._generator, AnthropicGenerator)
    assert flow._generator._client.api_key == KEY
    assert flow._kb_version == "v2"


def test_file_mode_app(fake_world, tmp_path):
    secrets = tmp_path / "secrets.env"
    secrets.write_text(f"VOLTRIX_ANTHROPIC_API_KEY={KEY}\nVOLTRIX_ACCESS_CODE={CODE}\n", encoding="utf-8")
    app = build(fake_world, {}, secrets_path=secrets)
    client = TestClient(app)
    assert client.post("/ask", json={"question": "E1"}, headers={"X-Access-Code": CODE}).status_code == 200
    assert fake_world.ssm.calls == []


@pytest.mark.parametrize("environ, expected", [({}, "local"), ({"IMAGE_TAG": "v2-20261112-a1b2c3d"}, "v2-20261112-a1b2c3d")])
def test_image_tag(fake_world, environ, expected):
    client = TestClient(build(fake_world, {**PS_ENV, **environ}))
    assert client.get("/health").json()["image_tag"] == expected


def test_health_kb_version_is_the_pointer_file(fake_world):
    fake_world.pointer.write_text("v7\n", encoding="utf-8")
    client = TestClient(build(fake_world, PS_ENV))
    assert client.get("/health").json()["kb_version"] == "v7"


# --- HANDOFF_DIR (section 4.5) ------------------------------------------------------------------


def test_handoffs_go_to_handoff_dir(fake_world, tmp_path, monkeypatch):
    handoff_dir = tmp_path / "tmp" / "handoffs"
    monkeypatch.setenv("HANDOFF_DIR", str(handoff_dir))
    client = TestClient(build(fake_world, PS_ENV))
    body = client.post("/ask", json={"question": "E1 on start"}, headers={"X-Access-Code": CODE}).json()
    (line,) = (handoff_dir / "handoffs.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(line)["handoff_id"] == body["handoff_id"]


def test_handoff_dir_and_path_together_stop_the_start_up(fake_world, tmp_path, monkeypatch):
    monkeypatch.setenv("HANDOFF_DIR", str(tmp_path / "a"))
    monkeypatch.setenv("HANDOFF_PATH", str(tmp_path / "b.jsonl"))
    with pytest.raises(ConfigError, match="HANDOFF_DIR.*HANDOFF_PATH"):
        build(fake_world, PS_ENV)
    assert fake_world.ssm.calls == [] and fake_world.opened == []


# --- Start-up order and failures ------------------------------------------------------------------


def test_secrets_checked_before_the_index_is_opened(fake_world):
    with pytest.raises(ConfigError, match="VOLTRIX_SECRETS_SOURCE"):
        build(fake_world, {"VOLTRIX_SECRETS_SOURCE": "nope"})
    assert fake_world.opened == []


def test_threshold_checked_before_secrets(fake_world, monkeypatch):
    monkeypatch.setattr(config, "ESCALATION_THRESHOLD", None)  # test value only
    with pytest.raises(ConfigError, match="NOT YET SET"):
        build(fake_world, PS_ENV)
    assert fake_world.ssm.calls == [] and fake_world.opened == []


def test_anthropic_variable_stops_the_start_up(fake_world):
    with pytest.raises(ConfigError, match="ANTHROPIC_BASE_URL"):
        build(fake_world, {**PS_ENV, "ANTHROPIC_BASE_URL": "https://example.invalid"})
    assert fake_world.ssm.calls == [] and fake_world.opened == []


@pytest.mark.parametrize(
    "error",
    [
        ConfigError("VOLTRIX_ACCESS_CODE must be at least 12 characters"),
        RetrievalError("indexes/v3: index folder does not exist"),
    ],
    ids=lambda e: type(e).__name__,
)
def test_python_m_web_start_up_error_is_one_line(capsys, production_logs, error):
    def failing_build():
        raise error

    def must_not_run(*args, **kwargs):
        raise AssertionError("uvicorn started after a start-up error")

    assert web_main.main(build=failing_build, run=must_not_run) == web_main.EXIT_STARTUP_FAILED
    captured = capsys.readouterr()
    assert captured.err == f"error: {error}\n"
    assert "Traceback" not in captured.err and captured.out == ""


def test_start_up_error_never_shows_a_secret(fake_world, capsys, production_logs, tmp_path):
    secrets = tmp_path / "secrets.env"
    short = "short-code"
    secrets.write_text(f"VOLTRIX_ANTHROPIC_API_KEY={KEY}\nVOLTRIX_ACCESS_CODE={short}\n", encoding="utf-8")

    def failing_build():
        return build(fake_world, {}, secrets_path=secrets)

    assert web_main.main(build=failing_build, run=lambda *a, **k: None) == web_main.EXIT_STARTUP_FAILED
    err = capsys.readouterr().err
    assert "VOLTRIX_ACCESS_CODE" in err
    assert short not in err and KEY not in err
