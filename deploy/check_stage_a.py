"""Stage A checks on the laptop image (spec 08 section 10): AC-D2, AC-D3,
AC-D5, the non-root user, the image contents, start-up time, and that no
secret value appears in the image, its history or its settings.

Usage, from the project root:
    .venv/bin/python deploy/check_stage_a.py voltrix-support-bot:<tag>

Makes NO Claude call and never touches the real secrets file. It writes a
FAKE secrets file (random dummy key, random access code) into a temporary
folder, mounts it read-only, and deletes it at the end. In the AC-D5 run
the container has no network at all, so its one /ask call cannot reach
Anthropic and must come back as a service_error escalation.

Exit 0 if every check passes, 1 otherwise.
"""

import argparse
import json
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ACTIVE_KB_VERSION_FILE = REPO_ROOT / "data" / "ACTIVE_KB_VERSION"
TICKETS_FILE = REPO_ROOT / "evals" / "support_questions.jsonl"
ANSWERABLE_TICKET = "T-001"  # labelled "answer": retrieval passes, so the flow calls Claude

CONTAINER_SECRETS = "/home/app/.config/voltrix/secrets.env"
CONTAINER_HANDOFFS = "/app/handoffs"
APP_UID = "1000"
APP_PORT = 8080
HEALTH_TIMEOUT_S = 300
ASK_TIMEOUT_S = 120
DENIED = {"error": "access denied"}

# Paths that must not be in the image (spec 08 section 6; Round 2 Q4).
ABSENT_PATHS = (
    "/app/.env", "/app/.venv", "/app/.git", "/app/evals", "/app/notes",
    "/app/tests", "/app/specs", "/app/deploy", "/app/.github", "/app/requirements.txt",
)

# Run inside the container with the image's own Python (no curl in slim).
IN_CONTAINER_HTTP = r"""
import json, sys, urllib.request, urllib.error
method, url, headers, body = json.loads(sys.argv[1])
data = None if body is None else body.encode()
req = urllib.request.Request(url, data=data, method=method, headers=headers)
try:
    with urllib.request.urlopen(req, timeout=110) as r:
        print(json.dumps([r.status, r.read().decode()]))
except urllib.error.HTTPError as e:
    print(json.dumps([e.code, e.read().decode()]))
except Exception as e:
    print(json.dumps([0, type(e).__name__]))
"""

IN_CONTAINER_FACTS = r"""
import json, os, sys
absent = json.loads(sys.argv[1])
def writable(p):
    return os.access(p, os.W_OK)
print(json.dumps({
    "uid": os.getuid(),
    "present": [p for p in absent if os.path.lexists(p)],
    "indexes": sorted(os.listdir("/app/indexes")),
    "data": sorted(os.listdir("/app/data")),
    "adapter_executable": os.access("/opt/extensions/lambda-adapter", os.X_OK),
    "build_info": open("/app/BUILD_INFO.txt").read().splitlines()[:7],
    "freeze_lines": sum(1 for l in open("/app/BUILD_INFO.txt") if "==" in l),
    "hf_writable": writable("/opt/hf"),
    "app_writable": writable("/app") or writable("/app/query"),
    "handoffs_writable": writable("/app/handoffs"),
    "env": {k: os.environ.get(k) for k in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HOME",
            "AWS_LWA_PORT", "AWS_LWA_READINESS_CHECK_PATH", "IMAGE_TAG", "HANDOFF_DIR")},
}))
"""


@dataclass
class Report:
    rows: list[tuple[str, bool, str]] = field(default_factory=list)

    def check(self, name: str, passed: bool, detail: str = "") -> bool:
        self.rows.append((name, bool(passed), detail))
        print(f"[{'PASS' if passed else 'FAIL'}] {name}" + (f": {detail}" if detail else ""), flush=True)
        return bool(passed)

    @property
    def ok(self) -> bool:
        return all(passed for _, passed, _ in self.rows)


@dataclass(frozen=True)
class FakeSecrets:
    path: Path
    key: str
    code: str

    def values(self) -> dict[str, str]:
        return {"fake key": self.key, "fake access code": self.code}


def make_fake_secrets(folder: Path) -> FakeSecrets:
    """A secrets file with random dummy values. The key is not a real
    Anthropic key; the code is long enough (spec 08 section 5: >= 12)."""
    key = f"fake-key-not-real-{secrets.token_hex(16)}"
    code = f"fake-code-{secrets.token_hex(10)}"
    path = folder / "secrets.env"
    path.write_text(f"VOLTRIX_ANTHROPIC_API_KEY={key}\nVOLTRIX_ACCESS_CODE={code}\n", encoding="utf-8")
    path.chmod(0o600)
    return FakeSecrets(path, key, code)


def find_values(text: str, values: dict[str, str]) -> list[str]:
    """Names (never the values) of the values that occur in text."""
    return sorted(name for name, value in values.items() if value and value in text)


def ticket_question(ticket_id: str, path: Path = TICKETS_FILE) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            ticket = json.loads(line)
            if ticket["ticket_id"] == ticket_id:
                return ticket["question"]
    raise KeyError(ticket_id)


def docker(*args: str, check: bool = True, timeout: float = 600) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=check, timeout=timeout)


def http_from_host(method: str, url: str, headers: dict | None = None, body: str | None = None):
    data = None if body is None else body.encode()
    request = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=ASK_TIMEOUT_S) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        return 0, type(e).__name__


def http_in_container(container: str, method: str, path: str, headers: dict | None = None, body: str | None = None):
    payload = json.dumps([method, f"http://127.0.0.1:{APP_PORT}{path}", headers or {}, body])
    result = docker("exec", container, "python", "-c", IN_CONTAINER_HTTP, payload, check=False, timeout=ASK_TIMEOUT_S + 10)
    if result.returncode != 0 or not result.stdout.strip():
        return 0, "exec failed"
    status, text = json.loads(result.stdout)
    return status, text


def wait_for_health(fetch: Callable[[], tuple[int, str]], started: float, timeout: float = HEALTH_TIMEOUT_S,
                    clock: Callable[[], float] = time.monotonic, pause: Callable[[float], None] = time.sleep) -> float | None:
    """Seconds from `started` until fetch() gives 200, or None on timeout."""
    while clock() - started < timeout:
        status, _ = fetch()
        if status == 200:
            return clock() - started
        pause(0.25)
    return None


def as_json(text: str):
    try:
        return json.loads(text)
    except ValueError:
        return None


class Containers:
    """Starts containers and remembers them, so all are removed at the end."""

    def __init__(self, image: str):
        self.image = image
        self.names: list[str] = []

    def start(self, name: str, secrets_file: Path, handoffs: Path, *, network_none: bool = False, port: int | None = None) -> float:
        args = ["run", "--detach", "--name", name,
                "--mount", f"type=bind,src={secrets_file},dst={CONTAINER_SECRETS},readonly",
                "--mount", f"type=bind,src={handoffs},dst={CONTAINER_HANDOFFS}"]
        if network_none:
            args += ["--network", "none"]
        if port is not None:
            args += ["--publish", f"127.0.0.1:{port}:{APP_PORT}"]
        started = time.monotonic()
        docker(*args, self.image)
        self.names.append(name)
        return started

    def remove(self, name: str) -> None:
        docker("rm", "--force", name, check=False)

    def remove_all(self) -> None:
        for name in self.names:
            self.remove(name)


def check_image_contents(report: Report, image: str, kb_version: str) -> None:
    result = docker("run", "--rm", "--network", "none", "--entrypoint", "python", image,
                    "-c", IN_CONTAINER_FACTS, json.dumps(list(ABSENT_PATHS)), check=False)
    facts = as_json(result.stdout)
    if not report.check("image facts readable", result.returncode == 0 and isinstance(facts, dict), result.stderr.strip()[-200:]):
        return
    report.check("runs as uid 1000 (non-root)", facts["uid"] == int(APP_UID), f"uid {facts['uid']}")
    report.check("left-out paths are absent", not facts["present"], ", ".join(facts["present"]) or "none present")
    report.check("only the active index is in the image", facts["indexes"] == [kb_version], f"indexes/: {facts['indexes']}")
    report.check("only data/ACTIVE_KB_VERSION from data/", facts["data"] == ["ACTIVE_KB_VERSION"], f"data/: {facts['data']}")
    report.check("Lambda Web Adapter present", facts["adapter_executable"])
    report.check("BUILD_INFO.txt has commit, date and pip freeze",
                 any(l.startswith("git_commit: ") and "unknown" not in l for l in facts["build_info"])
                 and any(l.startswith("build_date: ") and "unknown" not in l for l in facts["build_info"])
                 and facts["freeze_lines"] > 0,
                 f"{facts['freeze_lines']} freeze lines; " + "; ".join(facts["build_info"][:3]))
    report.check("model folder not writable by the app", not facts["hf_writable"])
    report.check("app code not writable by the app", not facts["app_writable"])
    report.check("handoffs/ writable by the app", facts["handoffs_writable"])
    env = facts["env"]
    report.check("offline and adapter settings",
                 env["HF_HUB_OFFLINE"] == "1" and env["TRANSFORMERS_OFFLINE"] == "1"
                 and env["AWS_LWA_PORT"] == str(APP_PORT) and env["AWS_LWA_READINESS_CHECK_PATH"] == "/health",
                 json.dumps(env))
    report.check("IMAGE_TAG and HANDOFF_DIR not set (spec 08 section 5, laptop)",
                 env["IMAGE_TAG"] is None and env["HANDOFF_DIR"] is None)


def check_secrets_absent(report: Report, image: str, containers: Iterable[str], fake: FakeSecrets) -> None:
    values = fake.values()
    texts = {
        "docker inspect (image)": docker("image", "inspect", image).stdout,
        "docker history --no-trunc": docker("history", "--no-trunc", "--format", "{{.CreatedBy}}", image).stdout,
    }
    for name in containers:
        texts[f"docker inspect ({name})"] = docker("container", "inspect", name).stdout
        logs = docker("logs", name, check=False)
        texts[f"docker logs ({name})"] = logs.stdout + logs.stderr
    for label, text in texts.items():
        found = find_values(text, values)
        report.check(f"no fake secret in {label}", not found, ", ".join(found) or "none found")
    for label in ("docker inspect (image)", "docker history --no-trunc"):
        hits = [w for w in ("VOLTRIX_ANTHROPIC_API_KEY=", "VOLTRIX_ACCESS_CODE=", "sk-ant-") if w in texts[label]]
        report.check(f"no secret setting or key prefix in {label}", not hits, ", ".join(hits) or "none found")
    for label, text in texts.items():
        if label.startswith("docker inspect (") and label != "docker inspect (image)":
            env = (as_json(text) or [{}])[0].get("Config", {}).get("Env", [])
            names = sorted(e.split("=", 1)[0] for e in env if e.startswith(("VOLTRIX_", "ANTHROPIC_")))
            report.check(f"no secret variable in the environment of {label[16:-1]}", not names, ", ".join(names) or "none")

    # The image's own files: the fake values (never built in) and the key
    # prefix. Only file NAMES are printed, never contents. Run as root so
    # every file is read (exit 1 = no match; 2 would mean unread files).
    patterns = [fake.key, fake.code, "sk-ant-api"]
    grep = ["grep", "-rIlF", "--exclude-dir=proc", "--exclude-dir=sys", "--exclude-dir=dev"]
    for p in patterns:
        grep += ["-e", p]
    result = docker("run", "--rm", "--network", "none", "--user", "0", "--entrypoint", grep[0], image,
                    *grep[1:], "/", check=False, timeout=900)
    files = [f for f in result.stdout.splitlines() if f.strip()]
    report.check("no fake secret or 'sk-ant-api' key text in the image files",
                 result.returncode == 1 and not files,
                 f"{len(files)} files: {', '.join(files[:5])}" if files else f"none found (grep exit {result.returncode})")


def run(image: str, starts: int, port: int, workdir: Path) -> Report:
    report = Report()
    kb_version = ACTIVE_KB_VERSION_FILE.read_text(encoding="utf-8").strip()
    fake = make_fake_secrets(workdir)
    handoffs = workdir / "handoffs"
    handoffs.mkdir()
    containers = Containers(image)
    run_id = secrets.token_hex(3)
    kept_for_scan: list[str] = []
    base = f"http://127.0.0.1:{port}"
    try:
        check_image_contents(report, image, kb_version)

        # Start-up time (Round 2 Q10) and AC-D2 / AC-D3 on the first start.
        times = []
        for i in range(1, starts + 1):
            name = f"voltrix-check-{run_id}-start{i}"
            started = containers.start(name, fake.path, handoffs, port=port)
            seconds = wait_for_health(lambda: http_from_host("GET", f"{base}/health"), started)
            report.check(f"start {i}: /health answers 200", seconds is not None,
                         f"{seconds:.1f} s after docker run" if seconds is not None else "timed out")
            if seconds is not None:
                times.append(seconds)
            if i == 1 and seconds is not None:
                status, text = http_from_host("GET", f"{base}/health")
                body = as_json(text) or {}
                report.check("AC-D2 GET /health 200 with kb_version = data/ACTIVE_KB_VERSION",
                             status == 200 and body.get("kb_version") == kb_version and body.get("status") == "ok",
                             f"HTTP {status}, {text}")
                report.check("/health image_tag is 'local' (IMAGE_TAG not set)", body.get("image_tag") == "local")
                question = json.dumps({"question": "What does E-01 mean?"})
                for label, headers in (("wrong code", {"X-Access-Code": "wrong-code-0123456789"}), ("no code", {})):
                    status, text = http_from_host("POST", f"{base}/ask", {"Content-Type": "application/json", **headers}, question)
                    report.check(f"AC-D3 POST /ask with {label} gives 401", status == 401 and as_json(text) == DENIED,
                                 f"HTTP {status}, {text}")
                top = docker("top", name, check=False).stdout
                report.check("Lambda Web Adapter not running on the laptop", "lambda-adapter" not in top and "python -m web" in top)
                user = docker("exec", name, "id", "-u", check=False).stdout.strip()
                report.check("container process runs as uid 1000", user == APP_UID, f"uid {user}")
                kept_for_scan.append(name)
            if i != 1:
                containers.remove(name)
            else:
                docker("stop", name, check=False)
        if times:
            print(f"start-up times (docker run -> /health 200): {', '.join(f'{t:.1f} s' for t in times)}")

        # AC-D5: no network at all; checked from inside the container.
        name = f"voltrix-check-{run_id}-nonetwork"
        started = containers.start(name, fake.path, handoffs, network_none=True)
        seconds = wait_for_health(lambda: http_in_container(name, "GET", "/health"), started)
        report.check("AC-D5 start-up with --network none, /health 200", seconds is not None,
                     f"{seconds:.1f} s" if seconds is not None else "timed out")
        if seconds is not None:
            question = json.dumps({"question": ticket_question(ANSWERABLE_TICKET)})
            status, text = http_in_container(name, "POST", "/ask",
                                             {"X-Access-Code": fake.code, "Content-Type": "application/json"}, question)
            body = as_json(text) or {}
            report.check(f"AC-D5 POST /ask ({ANSWERABLE_TICKET}) runs retrieval offline: 200 service_error escalation",
                         status == 200 and body.get("status") == "escalated" and body.get("escalation_reason") == "service_error"
                         and bool(body.get("handoff_id")),
                         f"HTTP {status}, status {body.get('status')!r}, reason {body.get('escalation_reason')!r}")
            records = (handoffs / "handoffs.jsonl")
            report.check("handoff record written to the mounted handoffs/", records.is_file() and records.stat().st_size > 0)
            logs = docker("logs", name, check=False)
            text = logs.stdout + logs.stderr
            report.check("no model download attempt in the logs", "huggingface.co" not in text and "Traceback" not in text)
        docker("stop", name, check=False)
        kept_for_scan.append(name)

        check_secrets_absent(report, image, kept_for_scan, fake)
    finally:
        containers.remove_all()
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="deploy/check_stage_a.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("image", help="e.g. voltrix-support-bot:v2-20261112-d98f7e5-local")
    parser.add_argument("--starts", type=int, default=3, help="start-ups to time (default 3)")
    parser.add_argument("--port", type=int, default=18080, help="host port for the checks (default 18080)")
    args = parser.parse_args(argv)
    workdir = Path(tempfile.mkdtemp(prefix="voltrix-stage-a-"))
    try:
        report = run(args.image, args.starts, args.port, workdir)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    failed = [name for name, passed, _ in report.rows if not passed]
    print(f"\n{len(report.rows) - len(failed)} passed, {len(failed)} failed")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
