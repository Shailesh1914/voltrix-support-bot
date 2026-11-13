"""Tests of the shell scripts and of check_stage_a.py's helpers. No image
is built or run here (check_stage_a.py itself does that)."""

import os
import re
import subprocess
from pathlib import Path

import pytest

import check_stage_a as cs

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD = REPO_ROOT / "deploy" / "build_image.sh"
RUN = REPO_ROOT / "deploy" / "run_local.sh"


def bash(script: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(script), *args], capture_output=True, text=True,
                          cwd=REPO_ROOT, env={**os.environ, **(env or {})}, timeout=60)


# --- build_image.sh -------------------------------------------------------------


def test_tag_has_the_d8_format_plus_local():
    result = bash(BUILD, "--print-tag")
    assert result.returncode == 0, result.stderr
    tag = result.stdout.strip()
    assert re.fullmatch(r"v[0-9]+-[0-9]{8}-[0-9a-f]{7}-local", tag), tag
    kb = (REPO_ROOT / "data" / "ACTIVE_KB_VERSION").read_text().strip()
    sha = subprocess.run(["git", "rev-parse", "--short=7", "HEAD"], capture_output=True, text=True, cwd=REPO_ROOT).stdout.strip()
    assert tag.startswith(f"{kb}-") and f"-{sha}-" in tag


def test_build_script_targets_x86_64_and_never_latest_or_push():
    text = BUILD.read_text()
    assert "--platform linux/amd64" in text
    assert "latest" not in text
    assert "push" not in text and "aws " not in text


def test_build_script_refuses_unknown_arguments():
    assert bash(BUILD, "--bogus").returncode == 2


# --- run_local.sh ---------------------------------------------------------------


@pytest.fixture
def fake_home(tmp_path):
    """A HOME with an (empty, fake) secrets file, so the real one is never used."""
    secrets = tmp_path / ".config" / "voltrix" / "secrets.env"
    secrets.parent.mkdir(parents=True)
    secrets.write_text("")
    return tmp_path


def test_run_local_mounts_the_secrets_read_only_and_publishes_on_localhost(fake_home):
    result = bash(RUN, "--dry-run", "some-image:tag", env={"HOME": str(fake_home)})
    assert result.returncode == 0, result.stderr
    cmd = result.stdout
    secrets = fake_home / ".config" / "voltrix" / "secrets.env"
    assert f"type=bind\\,src={secrets}\\,dst=/home/app/.config/voltrix/secrets.env\\,readonly" in cmd \
        or f"type=bind,src={secrets},dst=/home/app/.config/voltrix/secrets.env,readonly" in cmd
    assert "127.0.0.1:8080:8080" in cmd
    assert f"dst=/app/handoffs" in cmd and str(REPO_ROOT / "handoffs") in cmd
    assert "--env-file" not in cmd and " -e " not in cmd and "--env " not in cmd
    assert cmd.rstrip().endswith("some-image:tag")


def test_run_local_stops_when_the_secrets_file_is_missing(tmp_path):
    result = bash(RUN, "--dry-run", "some-image:tag", env={"HOME": str(tmp_path)})
    assert result.returncode == 1
    assert "does not exist" in result.stderr


def test_run_local_never_reads_the_secrets_file():
    text = "\n".join(l for l in RUN.read_text().splitlines() if not l.lstrip().startswith("#"))
    for reader in ("cat ", "source ", ". \"$SECRETS", "grep ", "--env-file", "read "):
        assert reader not in text, reader


# --- check_stage_a helpers --------------------------------------------------------


def test_fake_secrets_are_random_long_enough_and_owner_only(tmp_path):
    a = cs.make_fake_secrets(tmp_path)
    assert a.path.stat().st_mode & 0o777 == 0o600
    assert len(a.code) >= 12
    assert not a.key.startswith("sk-ant")
    text = a.path.read_text()
    assert f"VOLTRIX_ANTHROPIC_API_KEY={a.key}\n" in text and f"VOLTRIX_ACCESS_CODE={a.code}\n" in text
    other = tmp_path / "b"
    other.mkdir()
    b = cs.make_fake_secrets(other)
    assert a.key != b.key and a.code != b.code


def test_find_values_gives_names_never_values():
    values = {"fake key": "KEY123", "fake access code": "CODE456"}
    assert cs.find_values("xx KEY123 yy", values) == ["fake key"]
    assert cs.find_values("nothing", values) == []
    assert cs.find_values("", {"empty": ""}) == []


def test_wait_for_health_measures_from_docker_run():
    now = [100.0]
    answers = iter([(0, "refused"), (503, ""), (200, "{}")])

    def clock():
        return now[0]

    def pause(s):
        now[0] += 1.0

    assert cs.wait_for_health(lambda: next(answers), 99.5, clock=clock, pause=pause) == pytest.approx(2.5)


def test_wait_for_health_times_out():
    now = [0.0]

    def pause(s):
        now[0] += 10.0

    assert cs.wait_for_health(lambda: (0, ""), 0.0, timeout=30, clock=lambda: now[0], pause=pause) is None


def test_the_offline_ask_uses_an_answerable_ticket():
    """A ticket labelled "answer" passes retrieval, so the flow reaches the
    (blocked) Claude call: that is what proves the offline model ran."""
    question = cs.ticket_question(cs.ANSWERABLE_TICKET)
    tickets = [__import__("json").loads(l) for l in cs.TICKETS_FILE.read_text().splitlines() if l.strip()]
    assert next(t for t in tickets if t["ticket_id"] == cs.ANSWERABLE_TICKET)["expected"] == "answer"
    assert question
