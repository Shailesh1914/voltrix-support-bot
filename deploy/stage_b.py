"""Shared pieces of the Stage B (AWS Lambda) scripts: spec 08 sections 3, 7,
8 and 9. Not a script itself.

- Every AWS call runs the AWS CLI with --profile voltrix-deploy and
  --region ap-south-1 given explicitly, so neither the default profile nor
  an AWS_* variable in the shell can switch the account or the region. The
  AWS_* credential and region variables are also removed from the child
  environment.
- Before any other call, Aws.identity() checks that the caller is the IAM
  user voltrix-deploy (spec 08 D6: the admin login is never used).
- Commands run through an injectable runner, so the tests use fakes and
  never reach AWS, Docker or the network.
"""

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ACTIVE_KB_VERSION_FILE = REPO_ROOT / "data" / "ACTIVE_KB_VERSION"
TICKETS_FILE = REPO_ROOT / "evals" / "support_questions.jsonl"

PROFILE = "voltrix-deploy"
DEPLOY_USER = "voltrix-deploy"
REGION = "ap-south-1"  # Asia Pacific (Mumbai), the Task 13.1 region (Stage B Round 2 Q1)
REPOSITORY = "voltrix-support-bot"  # ECR repository and the local image name
FUNCTION = "voltrix-support-bot"  # Round 2 Q2
EXECUTION_ROLE = "voltrix-support-bot-lambda"
LOG_GROUP = f"/aws/lambda/{FUNCTION}"

# Spec 08 D8 tag format, without -local (Stage A images are laptop only).
TAG_RE = re.compile(r"v[0-9]+-[0-9]{8}-[0-9a-f]{7}")

# Spec 08 section 7, and the settings of section 5 (Lambda column).
LAMBDA_SETTINGS = {"PackageType": "Image", "Architectures": ["x86_64"], "MemorySize": 2048, "Timeout": 60}
REQUIRED_ENV = {"VOLTRIX_SECRETS_SOURCE": "parameter_store", "HANDOFF_DIR": "/tmp/handoffs"}
ALLOWED_ENV = frozenset({*REQUIRED_ENV, "IMAGE_TAG", "AWS_LWA_ASYNC_INIT"})
ASYNC_INIT = "AWS_LWA_ASYNC_INIT"

# Never passed on to a child process: the profile and region are given on
# the command line, and a stray key in the shell must not take over.
CREDENTIAL_VARIABLES = (
    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_SECURITY_TOKEN",
    "AWS_PROFILE", "AWS_DEFAULT_PROFILE", "AWS_REGION", "AWS_DEFAULT_REGION",
)

EXIT_OK, EXIT_FAILED, EXIT_DRY_RUN = 0, 1, 5
HTTP_TIMEOUT_S = 90  # Lambda timeout 60 s plus a cold start


class DeployError(Exception):
    pass


class AwsError(DeployError):
    def __init__(self, message: str, code: str = ""):
        super().__init__(message)
        self.code = code


Runner = Callable[..., subprocess.CompletedProcess]


def child_env(environ: Mapping[str, str] = os.environ) -> dict[str, str]:
    return {k: v for k, v in environ.items() if k not in CREDENTIAL_VARIABLES and not k.startswith("ANTHROPIC_")}


def run_process(args: list[str], input: str | None = None, timeout: float = 900) -> subprocess.CompletedProcess:
    return subprocess.run(args, input=input, capture_output=True, text=True, timeout=timeout, env=child_env())


def check_release_tag(tag: str) -> str:
    if not TAG_RE.fullmatch(tag):
        raise DeployError(f"{tag!r} is not a release tag <kb-version>-<yyyymmdd>-<git-short-sha> "
                          "(spec 08 D8; -local images are for the laptop only)")
    return tag


def kb_version(path: Path = ACTIVE_KB_VERSION_FILE) -> str:
    return path.read_text(encoding="utf-8").strip()


def last_line(text: str, limit: int = 300) -> str:
    lines = [line for line in (text or "").strip().splitlines() if line.strip()]
    return lines[-1][-limit:] if lines else ""


class Aws:
    """The AWS CLI, always as the voltrix-deploy profile in ap-south-1."""

    def __init__(self, runner: Runner = run_process):
        self.runner = runner
        self.account: str | None = None

    def _run(self, args: list[str], output: str) -> str:
        command = ["aws", *args, "--profile", PROFILE, "--region", REGION, "--output", output]
        result = self.runner(command)
        if result.returncode != 0:
            match = re.search(r"An error occurred \((\w+)\)", result.stderr or "")
            raise AwsError(f"aws {' '.join(args[:2])} failed (exit {result.returncode}): {last_line(result.stderr)}",
                           match.group(1) if match else "")
        return result.stdout or ""

    def json(self, *args: str) -> dict:
        out = self._run(list(args), "json")
        return json.loads(out) if out.strip() else {}

    def secret_text(self, *args: str) -> str:
        """Output that is a credential (the ECR login token): returned, never printed."""
        return self._run(list(args), "text").strip()

    def identity(self) -> str:
        info = self.json("sts", "get-caller-identity")
        account, arn = info.get("Account", ""), info.get("Arn", "")
        if not account or arn != f"arn:aws:iam::{account}:user/{DEPLOY_USER}":
            raise DeployError(f"these scripts run only as the IAM user {DEPLOY_USER} (spec 08 D6); "
                              f"the profile {PROFILE} is {arn or 'unknown'}")
        self.account = account
        return account

    def registry(self) -> str:
        if self.account is None:
            raise DeployError("identity() must be checked first")
        return f"{self.account}.dkr.ecr.{REGION}.amazonaws.com"

    def image_uri(self, tag: str) -> str:
        return f"{self.registry()}/{REPOSITORY}:{tag}"

    def digest_uri(self, digest: str) -> str:
        return f"{self.registry()}/{REPOSITORY}@{digest}"

    def repository(self) -> dict:
        return self.json("ecr", "describe-repositories", "--repository-names", REPOSITORY)["repositories"][0]

    def ecr_image(self, tag: str) -> dict | None:
        try:
            details = self.json("ecr", "describe-images", "--repository-name", REPOSITORY,
                                "--image-ids", f"imageTag={tag}")["imageDetails"]
        except AwsError as e:
            if e.code == "ImageNotFoundException":
                return None
            raise
        return details[0] if details else None

    def function(self) -> dict:
        return self.json("lambda", "get-function", "--function-name", FUNCTION)

    def function_url(self) -> str:
        return self.json("lambda", "get-function-url-config", "--function-name", FUNCTION)["FunctionUrl"]

    def reserved_concurrency(self) -> int | None:
        return self.json("lambda", "get-function-concurrency", "--function-name", FUNCTION).get("ReservedConcurrentExecutions")

    def wait_updated(self) -> None:
        self.json("lambda", "wait", "function-updated-v2", "--function-name", FUNCTION)

    def update_code(self, image_uri: str) -> None:
        self.json("lambda", "update-function-code", "--function-name", FUNCTION, "--image-uri", image_uri)

    def update_environment(self, variables: Mapping[str, str]) -> None:
        self.json("lambda", "update-function-configuration", "--function-name", FUNCTION,
                  "--environment", json.dumps({"Variables": dict(variables)}, sort_keys=True))

    def log_events(self, start_ms: int, pattern: str | None = None) -> list[dict]:
        args = ["logs", "filter-log-events", "--log-group-name", LOG_GROUP, "--start-time", str(start_ms)]
        if pattern:
            args += ["--filter-pattern", pattern]
        return self.json(*args).get("events", [])


def concurrency_note(reserved: int | None) -> tuple[str, bool]:
    """(text, as expected?) for the function's concurrency setting.

    Stage B Round 3 decision: no reserved concurrency (the account limit is
    10, and Lambda keeps at least 10 unreserved, so 2 cannot be reserved);
    the account limit of 10 is the cap. Pausing is Lambda's Throttle, which
    sets the function concurrency to 0."""
    if reserved is None:
        return "no reserved concurrency (the account limit of 10 is the cap)", True
    if reserved == 0:
        return "THROTTLED (function concurrency 0): paused, the Function URL refuses requests", True
    return f"{reserved} reserved, but the decision is no reserved concurrency", False


def environment_of(configuration: Mapping) -> dict[str, str]:
    return dict((configuration.get("Environment") or {}).get("Variables") or {})


def lambda_problems(configuration: Mapping) -> list[str]:
    """Where the function differs from spec 08 sections 5 and 7. Names
    variables, never their values (a secret value must never be printed)."""
    problems = []
    for name, wanted in LAMBDA_SETTINGS.items():
        if configuration.get(name) != wanted:
            problems.append(f"{name} is {configuration.get(name)!r}, spec 08 wants {wanted!r}")
    if not str(configuration.get("Role", "")).endswith(f":role/{EXECUTION_ROLE}"):
        problems.append(f"the execution role is not {EXECUTION_ROLE}")
    if (configuration.get("VpcConfig") or {}).get("SubnetIds"):
        problems.append("the function is in a VPC (it needs the internet for Anthropic and Parameter Store)")
    env = environment_of(configuration)
    for name, wanted in REQUIRED_ENV.items():
        if env.get(name) != wanted:
            problems.append(f"{name} must be {wanted!r}")
    unexpected = sorted(set(env) - ALLOWED_ENV)
    if unexpected:
        problems.append(f"unexpected environment variables (spec 08 section 5): {', '.join(unexpected)}")
    return problems


def http(method: str, url: str, headers: Mapping[str, str] | None = None, body: bytes | None = None,
         timeout: float = HTTP_TIMEOUT_S) -> tuple[int, dict[str, str], str]:
    """(status, lower-cased headers, text). Status 0 means no answer."""
    request = urllib.request.Request(url, data=body, method=method, headers=dict(headers or {}))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, {k.lower(): v for k, v in response.headers.items()}, response.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in (e.headers or {}).items()}, e.read().decode()
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        return 0, {}, type(e).__name__


def join_url(base: str, path: str) -> str:
    return base.rstrip("/") + path


def as_json(text: str):
    try:
        return json.loads(text)
    except ValueError:
        return None
