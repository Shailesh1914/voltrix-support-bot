"""Static checks of Dockerfile and .dockerignore against spec 08 section 6
and the Round 1/2 decisions. Expected values come from the spec text where
the spec states them."""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
DOCKERIGNORE = (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8")
SPEC_08 = (REPO_ROOT / "specs" / "08-deployment-spec.md").read_text(encoding="utf-8")

PYTHON_BASE = "python:3.14.10-slim-trixie@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f"
ADAPTER = "public.ecr.aws/awsguru/aws-lambda-adapter:1.1.0@sha256:17cfd08eff1dfea3f6a9a1e9c65fdac80aa4919b6085e746615530f43f57d2f1"


def instructions(text: str) -> list[str]:
    """Dockerfile instructions with continuation lines joined, comments dropped."""
    joined = re.sub(r"\\\n", " ", text)
    return [line.strip() for line in joined.splitlines() if line.strip() and not line.strip().startswith("#")]


INSTRUCTIONS = instructions(DOCKERFILE)
FROMS = [i for i in INSTRUCTIONS if i.startswith("FROM ")]


def spec_section(number: int) -> str:
    match = re.search(rf"^## {number}\. .*?(?=^## )", SPEC_08, re.S | re.M)
    assert match, f"spec 08 section {number} not found"
    return match.group(0)


def test_every_base_image_is_pinned_by_digest_and_x86_64():
    assert len(FROMS) == 3
    for line in FROMS:
        assert "--platform=linux/amd64" in line, line
        assert re.search(r"@sha256:[0-9a-f]{64}", line), line
    assert "x86_64" in spec_section(6)


def test_python_base_is_official_3_14_slim_same_minor_as_project():
    python_froms = [f for f in FROMS if " python:" in f]
    assert len(python_froms) == 2
    assert all(PYTHON_BASE in f for f in python_froms)
    assert "Python 3.14" in spec_section(6) and "slim" in spec_section(6)


def test_lambda_web_adapter_pinned_and_copied_to_extensions():
    assert any(ADAPTER in f for f in FROMS)
    assert "COPY --from=lambda-adapter /lambda-adapter /opt/extensions/lambda-adapter" in INSTRUCTIONS


def test_no_latest_tag_anywhere():
    assert ":latest" not in DOCKERFILE


def test_readiness_check_points_at_health_and_port_8080():
    runtime_env = " ".join(i for i in INSTRUCTIONS if i.startswith("ENV "))
    assert "AWS_LWA_READINESS_CHECK_PATH=/health" in runtime_env
    assert "AWS_LWA_PORT=8080" in runtime_env
    assert "EXPOSE 8080" in INSTRUCTIONS
    assert "/health" in spec_section(6) and "port 8080" in spec_section(6)


def test_runtime_is_offline_for_the_model():
    runtime = DOCKERFILE.split("AS runtime", 1)[1]
    assert "HF_HUB_OFFLINE=1" in runtime
    assert "TRANSFORMERS_OFFLINE=1" in runtime
    assert "HF_HUB_OFFLINE=1" in spec_section(6)


def test_index_is_built_offline_after_the_model_download():
    download = DOCKERFILE.index("load_model(); load_token_counter()")
    offline = DOCKERFILE.index("HF_HUB_OFFLINE=1")
    build = DOCKERFILE.index("python -m ingestion.build")
    assert download < offline < build


def test_index_built_with_the_ci_command_and_reader_then_manifest_checked():
    run = next(i for i in INSTRUCTIONS if "ingestion.build" in i)
    assert 'active="$(python .github/scripts/active_kb_version.py)"' in run
    assert 'python -m ingestion.build "$active"' in run
    assert 'python deploy/check_manifest.py "$active"' in run
    ci = (REPO_ROOT / ".github" / "actions" / "setup-bot" / "action.yml").read_text(encoding="utf-8")
    assert "python .github/scripts/active_kb_version.py" in ci
    assert 'python -m ingestion.build "$folder"' in ci


def test_requirements_installed_as_ci_does_and_checked():
    assert "RUN pip install -r requirements.txt" in INSTRUCTIONS
    assert "RUN python deploy/check_pins.py requirements.txt" in INSTRUCTIONS
    assert "--extra-index-url https://download.pytorch.org/whl/cpu" in (REPO_ROOT / "requirements.txt").read_text()


def test_runs_as_non_root_uid_1000_with_python_m_web():
    users = [i for i in INSTRUCTIONS if i.startswith("USER ")]
    assert users == ["USER app"]
    assert INSTRUCTIONS[-1] == 'CMD ["python", "-m", "web"]'
    assert INSTRUCTIONS.index("USER app") > max(i for i, line in enumerate(INSTRUCTIONS) if line.startswith("RUN "))
    assert "useradd --uid 1000" in DOCKERFILE


def test_only_the_active_index_and_pointer_file_go_into_the_runtime():
    runtime = DOCKERFILE.split("AS runtime", 1)[1]
    assert "COPY --from=builder /app/indexes/ indexes/" in runtime
    assert "COPY data/ACTIVE_KB_VERSION data/ACTIVE_KB_VERSION" in runtime
    assert not re.search(r"^COPY data/ ", runtime, re.M)


def test_build_info_written_last_with_commit_date_and_freeze():
    runtime = DOCKERFILE.split("AS runtime", 1)[1]
    assert "BUILD_INFO.txt" in runtime and "pip freeze --all" in runtime
    for arg in ("GIT_COMMIT", "BUILD_DATE"):
        assert f"ARG {arg}" in runtime
        assert runtime.index(f"ARG {arg}") > runtime.index("COPY web/ web/")


SECRET_WORDS = ("VOLTRIX_ANTHROPIC_API_KEY", "VOLTRIX_ACCESS_CODE", "sk-ant", "secrets.env")


@pytest.mark.parametrize("word", SECRET_WORDS)
def test_no_secret_setting_in_env_arg_or_label(word):
    for line in INSTRUCTIONS:
        if line.startswith(("ENV ", "ARG ", "LABEL ")):
            assert word not in line, line
    assert "--env-file" not in DOCKERFILE


# --- .dockerignore ------------------------------------------------------------

IGNORE_LINES = [l.strip() for l in DOCKERIGNORE.splitlines() if l.strip() and not l.startswith("#")]


@pytest.mark.parametrize("entry", [".env", ".venv/", ".git/", "handoffs/", "notes/"])
def test_dockerignore_keeps_out_what_spec_08_names(entry):
    assert entry in spec_section(6)
    assert entry in IGNORE_LINES
    assert f"!{entry}" not in IGNORE_LINES


def test_dockerignore_keeps_out_evals_and_starts_from_nothing():
    assert "`evals/` results" in spec_section(6)
    assert "evals/" in IGNORE_LINES
    assert IGNORE_LINES[0] == "*"


def test_dockerignore_lets_in_only_what_the_build_copies():
    allowed = sorted(l[1:] for l in IGNORE_LINES if l.startswith("!"))
    assert allowed == sorted([
        "requirements.txt", "ingestion/", "query/", "web/", "data/",
        ".github/scripts/active_kb_version.py", "deploy/check_pins.py", "deploy/check_manifest.py",
    ])
    copied = set()
    for line in INSTRUCTIONS:
        if line.startswith("COPY ") and "--from=" not in line:
            copied.update(line.split()[1:-1])
    assert copied <= set(allowed) | {"data/ACTIVE_KB_VERSION"}
