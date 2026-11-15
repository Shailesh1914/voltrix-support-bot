"""Tests of ci_passed.py and build_release.sh. The release build runs for
real against a local bare git repository standing in for GitHub, with fake
gh, docker and check_stage_a.py: no network, no image is built."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import ci_passed as ci
from stage_b_fakes import cp

REPO_ROOT = Path(__file__).resolve().parents[2]
SHA = "406e022" + "0" * 33


def run(**fields):
    base = {"databaseId": 1, "workflowName": "Structural tests", "event": "push", "headBranch": "main",
            "headSha": SHA, "status": "completed", "conclusion": "success", "url": "https://x/1"}
    return {**base, **fields}


# --- ci_passed.py -----------------------------------------------------------------


def test_a_successful_push_run_on_main_passes():
    ok, message = ci.verdict([run(), run(workflowName="Evaluation gate", event="pull_request", headBranch="b")], SHA)
    assert ok, message


@pytest.mark.parametrize("runs, why", [
    ([], "no 'Structural tests' run"),
    ([run(headSha="f" * 40)], "no 'Structural tests' run"),
    ([run(event="pull_request")], "no 'Structural tests' run"),
    ([run(headBranch="stage-b")], "no 'Structural tests' run"),
    ([run(status="in_progress", conclusion="")], "still running"),
    ([run(conclusion="failure")], "failed runs"),
    ([run(), run(workflowName="Evaluation gate", conclusion="failure")], "failed runs"),
    ([run(conclusion="cancelled")], "no 'Structural tests' run"),
])
def test_ci_not_passed(runs, why):
    ok, message = ci.verdict(runs, SHA)
    assert not ok and why in message


def test_a_cancelled_run_next_to_a_successful_one_is_ignored():
    assert ci.verdict([run(conclusion="cancelled"), run(databaseId=2)], SHA)[0]


def test_ci_passed_only_lists_runs(capsys):
    seen = []

    def runner(args, input=None, timeout=None):
        seen.append(args)
        return cp(json.dumps([run()]))

    assert ci.main([SHA], runner=runner) == 0
    assert seen == [["gh", "run", "list", "--commit", SHA, "--limit", "100", "--json", ci.FIELDS]]


def test_ci_passed_needs_a_full_sha_and_reports_gh_failures(capsys):
    assert ci.main(["406e022"], runner=lambda *a, **k: pytest.fail("called gh")) == 2
    assert ci.main([SHA], runner=lambda *a, **k: cp(returncode=4, stderr="not logged in")) == 1
    assert "not logged in" in capsys.readouterr().err


# --- build_release.sh ---------------------------------------------------------------


def sh(*args, cwd, env=None):
    return subprocess.run(list(args), cwd=cwd, capture_output=True, text=True, env=env, timeout=120)


FAKE_DOCKER = """#!/usr/bin/env bash
echo "docker $*" >> "$FAKE_LOG"
if [[ "$1 $2" == "image inspect" ]]; then
  [[ -n "${FAKE_IMAGE_EXISTS:-}" ]] && exit 0 || exit 1
fi
exit 0
"""
FAKE_GH = """#!/usr/bin/env bash
echo "gh $*" >> "$FAKE_LOG"
sha="$4"  # gh run list --commit <sha> ...
cat <<EOF
[{"databaseId": 1, "workflowName": "Structural tests", "event": "push", "headBranch": "main",
  "headSha": "$sha", "status": "completed", "conclusion": "${FAKE_CONCLUSION:-success}", "url": "u"}]
EOF
"""
FAKE_CHECK = """import sys, os
open(os.environ["FAKE_LOG"], "a").write("check_stage_a " + " ".join(sys.argv[1:]) + " from " + __file__ + "\\n")
"""


@pytest.fixture
def project(tmp_path):
    """origin.git (stands in for GitHub) with a main branch, a project
    checkout with the scripts under test and local changes, and fakes."""
    git_env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}
    seed = tmp_path / "seed"
    (seed / "data").mkdir(parents=True)
    (seed / "deploy").mkdir()
    (seed / "data" / "ACTIVE_KB_VERSION").write_text("v2\n")
    (seed / "deploy" / "check_stage_a.py").write_text(FAKE_CHECK)
    (seed / "Dockerfile").write_text("FROM scratch\n")
    for args in (["git", "init", "-q", "-b", "main"], ["git", "add", "."], ["git", "commit", "-q", "-m", "main"]):
        assert sh(*args, cwd=seed, env=git_env).returncode == 0
    origin = tmp_path / "origin.git"
    assert sh("git", "clone", "-q", "--bare", str(seed), str(origin), cwd=tmp_path).returncode == 0

    work = tmp_path / "work"
    assert sh("git", "clone", "-q", str(origin), str(work), cwd=tmp_path).returncode == 0
    for name in ("build_release.sh", "ci_passed.py", "stage_b.py"):
        shutil.copy(REPO_ROOT / "deploy" / name, work / "deploy" / name)
    (work / "data" / "ACTIVE_KB_VERSION").write_text("v9\n")  # a local change that must not get in
    (work / "LOCAL-ONLY").write_text("x")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, text in (("docker", FAKE_DOCKER), ("gh", FAKE_GH)):
        (bin_dir / name).write_text(text)
        (bin_dir / name).chmod(0o755)
    log = tmp_path / "log"
    log.touch()
    env = {**git_env, "PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_LOG": str(log),
           "PYTHON": sys.executable, "TMPDIR": str(tmp_path)}
    main_sha = sh("git", "rev-parse", "HEAD", cwd=seed).stdout.strip()
    return {"work": work, "env": env, "log": log, "sha": main_sha}


def build(project, **extra_env):
    return sh("bash", str(project["work"] / "deploy" / "build_release.sh"), cwd=project["work"],
              env={**project["env"], **extra_env})


def test_build_release_builds_main_with_the_d8_tag_and_runs_the_stage_a_checks(project):
    result = build(project)
    assert result.returncode == 0, result.stderr + result.stdout
    log = project["log"].read_text().splitlines()
    sha, short = project["sha"], project["sha"][:7]
    assert log[0] == f"gh run list --commit {sha} --limit 100 --json {ci.FIELDS}"
    (docker_build,) = [l for l in log if l.startswith("docker build")]
    for part in ("--platform linux/amd64", "--provenance=false", "--sbom=false", f"--build-arg GIT_COMMIT={sha}",
                 "--build-arg GIT_TREE=clean"):
        assert part in docker_build
    tag = docker_build.split("--tag voltrix-support-bot:", 1)[1].split()[0]
    assert tag.startswith("v2-") and tag.endswith(f"-{short}") and "-local" not in tag  # main's KB, not v9
    context = docker_build.split()[-1]
    assert "voltrix-release-" in context and not Path(context).exists()  # temporary, removed afterwards
    (check,) = [l for l in log if l.startswith("check_stage_a")]
    assert check.startswith(f"check_stage_a voltrix-support-bot:{tag} from {context}/deploy/")  # main's own checks
    assert f"push_image.py {tag}" in result.stdout
    assert not any("push" in l.split()[1] for l in log if l.startswith("docker"))


def test_build_release_stops_before_building_when_ci_did_not_pass(project):
    result = build(project, FAKE_CONCLUSION="failure")
    assert result.returncode == 1
    assert "CI NOT passed" in result.stderr
    assert not any(l.startswith("docker build") for l in project["log"].read_text().splitlines())


def test_build_release_never_rebuilds_an_existing_tag(project):
    result = build(project, FAKE_IMAGE_EXISTS="1")
    assert result.returncode == 1 and "already exists locally" in result.stderr
    assert not any(l.startswith("docker build") for l in project["log"].read_text().splitlines())


def test_build_release_takes_no_arguments(project):
    assert build_with_args(project, "--local").returncode == 2


def build_with_args(project, *args):
    return sh("bash", str(project["work"] / "deploy" / "build_release.sh"), *args, cwd=project["work"], env=project["env"])


def test_build_release_has_no_aws_or_push():
    text = (REPO_ROOT / "deploy" / "build_release.sh").read_text()
    code = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
    assert "aws " not in code and "docker push" not in code and "latest" not in code
    assert "-local" not in code
