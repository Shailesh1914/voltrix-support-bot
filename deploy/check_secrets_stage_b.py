"""AC-D9 (spec 08 section 10): no secret in the image, the repository, or
the CloudWatch logs, checked by a search. Run by the owner.

    .venv/bin/python deploy/check_secrets_stage_b.py --tag <tag>
    .venv/bin/python deploy/check_secrets_stage_b.py --tag <tag> --only repo,image

Asks with hidden prompts for the Stage B access code (required) and the
bot's Anthropic key (optional: Enter skips it; the key PATTERN is searched
for anyway). The values stay in this process's memory: they are never
printed, never written, never put on a command line and never sent to AWS
(so no filter pattern holds a secret). The searching is done here, on the
laptop. A hit is reported by the name of what was found and where (file,
commit, log stream), never by the text.

Targets:
- repo:   every tracked file as it is now, and every commit (git log --all -p).
- image:  the local release image voltrix-support-bot:<tag> (the same digest
          push_image.py pushed): every file (docker export), plus docker
          inspect and docker history.
- lambda: the function's configuration (get-function, get-function-url-config).
- logs:   every event in /aws/lambda/voltrix-support-bot (7-day retention).
          Also checks that the question texts of the AC-D4 tickets do not
          appear (spec 08 section 4.4: questions are never logged).

AWS's published documentation example key ids (KNOWN_AWS_EXAMPLE_KEY_IDS,
four exact values that boto3/botocore ship in their docs) are reported as
"known documentation example" and do not fail AC-D9; any other match does.

Exit 0 nothing found, 1 something found or a target could not be searched.
"""

import argparse
import getpass
import json
import re
import subprocess
import sys
import tarfile
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from stage_b import REPO_ROOT, REPOSITORY, TICKETS_FILE, Aws, DeployError, FUNCTION, child_env, run_process

TARGETS = ("repo", "image", "lambda", "logs")
AC_D4_TICKETS = ("T-001", "T-002", "T-043")
CHUNK = 1 << 20

# Shapes of real credentials. The test sentinels in the repository
# ("sk-ant-test-...") deliberately do not match the key shape.
PATTERNS = {
    "Anthropic API key pattern": re.compile(rb"sk-ant-(?:api|admin)\d{2}-[A-Za-z0-9_\-]{20,}"),
    "AWS access key id pattern": re.compile(rb"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "AWS secret key setting": re.compile(rb"(?i)aws_secret_access_key\s*[=:]\s*['\"]?[A-Za-z0-9/+]{40}"),
}


AWS_KEY_ID = "AWS access key id pattern"

# AWS's own documentation example access key ids. They are not credentials:
# AWS publishes them as examples, and boto3/botocore ship them in their docs
# and example data (found in the image under boto3/examples/cloudfront.rst
# and botocore/data/{iam,sts}/*/examples-1.json, boto3/botocore 1.43.111).
# Only these EXACT values are accepted, only for the AWS key id pattern, and
# each one is still reported as a known documentation example. Any other
# match, in any file, is a finding. (Stage B Round 4, owner's decision.)
KNOWN_AWS_EXAMPLE_KEY_IDS = {
    # IAM User Guide, "Manage access keys": "access key ID (for example,
    # AKIAIOSFODNN7EXAMPLE)"; also the AWS CLI config-files guide.
    b"AKIAIOSFODNN7EXAMPLE",
    # AWS CLI guide, "Configuration and credential file settings" ([user1]),
    # and the AWS CLI reference for iam list-access-keys.
    b"AKIAI44QH8DHBEXAMPLE",
    # AWS's IAM API example data for ListAccessKeys (user "Alice"), shipped
    # in botocore/data/iam/2010-05-08/examples-1.json. Not seen on the
    # published web pages checked on 2026-11-15.
    b"AKIA111111111EXAMPLE",
    b"AKIA222222222EXAMPLE",
}


@dataclass
class Scanner:
    """Looks for exact values and for the credential patterns."""
    values: dict[str, bytes]
    patterns: dict[str, re.Pattern] = field(default_factory=lambda: dict(PATTERNS))
    hits: list[tuple[str, str]] = field(default_factory=list)  # (what, where)
    examples: list[tuple[str, str]] = field(default_factory=list)  # (known example value, where)

    @property
    def overlap(self) -> int:
        return max([len(v) for v in self.values.values()] + [200])

    def names_in(self, data: bytes) -> tuple[set[str], set[bytes]]:
        """(names of findings, known AWS example key ids seen)."""
        found = {name for name, value in self.values.items() if value and value in data}
        examples: set[bytes] = set()
        for name, pattern in self.patterns.items():
            matches = {m.group(0) for m in pattern.finditer(data)}
            if name == AWS_KEY_ID:
                examples |= matches & KNOWN_AWS_EXAMPLE_KEY_IDS
                matches -= KNOWN_AWS_EXAMPLE_KEY_IDS
            if matches:
                found.add(name)
        return found, examples

    def _record(self, where: str, found: set[str], examples: set[bytes]) -> None:
        for name in sorted(found):
            self.hits.append((name, where))
        for value in sorted(examples):
            self.examples.append((value.decode(), where))

    def scan_bytes(self, where: str, data: bytes) -> None:
        self._record(where, *self.names_in(data))

    def scan_stream(self, where: str, stream) -> None:
        """Chunked, with an overlap so a value across two chunks is found."""
        found, examples, tail = set(), set(), b""
        while chunk := stream.read(CHUNK):
            data = tail + chunk
            chunk_found, chunk_examples = self.names_in(data)
            found |= chunk_found
            examples |= chunk_examples
            tail = data[-self.overlap:]
        self._record(where, found, examples)


def scan_tar(scanner: Scanner, stream, label: str) -> int:
    count = 0
    with tarfile.open(fileobj=stream, mode="r|") as archive:
        for member in archive:
            if member.isfile():
                handle = archive.extractfile(member)
                if handle is not None:
                    scanner.scan_stream(f"{label}:/{member.name}", handle)
                    count += 1
    return count


def git(*args: str, runner=run_process) -> str:
    result = runner(["git", "-C", str(REPO_ROOT), *args])
    if result.returncode != 0:
        raise DeployError(f"git {args[0]} failed: {(result.stderr or '').strip()[-200:]}")
    return result.stdout


def scan_history(scanner: Scanner, log_text: str) -> None:
    """git log --all -p output: hits are located by commit and file."""
    commit, path, block = "", "", []

    def flush():
        if block:
            scanner.scan_bytes(f"commit {commit[:7]} {path or '(message)'}", "\n".join(block).encode())

    for line in log_text.splitlines():
        if line.startswith("commit ") and re.fullmatch(r"commit [0-9a-f]{40}.*", line):
            flush()
            commit, path, block = line.split()[1], "", []
        elif line.startswith("diff --git "):
            flush()
            path, block = line.split(" b/", 1)[-1], []
        else:
            block.append(line)
    flush()


def scan_repo(scanner: Scanner, runner=run_process) -> str:
    files = [f for f in git("ls-files", "-z", runner=runner).split("\0") if f]
    for name in files:
        path = REPO_ROOT / name
        if path.is_file():
            with open(path, "rb") as handle:
                scanner.scan_stream(f"file {name}", handle)
    history = git("log", "--all", "-p", "--no-color", "--no-ext-diff", "--format=commit %H%n%B", runner=runner)
    scan_history(scanner, history)
    commits = git("rev-list", "--all", "--count", runner=runner).strip()
    return f"{len(files)} tracked files, {commits} commits"


def scan_image(scanner: Scanner, tag: str, runner=run_process, popen=subprocess.Popen) -> str:
    image = f"{REPOSITORY}:{tag}"
    for args in (("image", "inspect", image), ("history", "--no-trunc", image)):
        result = runner(["docker", *args])
        if result.returncode != 0:
            raise DeployError(f"docker {' '.join(args[:2])} failed; is {image} built locally?")
        scanner.scan_bytes(f"docker {args[0]} {args[1]}", result.stdout.encode())
    created = runner(["docker", "create", image])
    if created.returncode != 0:
        raise DeployError(f"docker create {image} failed")
    container = created.stdout.strip()
    try:
        process = popen(["docker", "export", container], stdout=subprocess.PIPE, env=child_env())
        count = scan_tar(scanner, process.stdout, "image")
        if process.wait() != 0:
            raise DeployError("docker export failed")
    finally:
        runner(["docker", "rm", container])
    return f"{count} files in {image}"


def scan_lambda(scanner: Scanner, aws: Aws) -> str:
    scanner.scan_bytes("lambda get-function", json.dumps(aws.function()).encode())
    scanner.scan_bytes("lambda get-function-url-config",
                       json.dumps(aws.json("lambda", "get-function-url-config", "--function-name", FUNCTION)).encode())
    return f"configuration of {FUNCTION}"


def scan_logs(scanner: Scanner, aws: Aws, questions: dict[str, bytes]) -> str:
    events = aws.log_events(0)
    for event in events:
        when = datetime.fromtimestamp(event.get("timestamp", 0) / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
        where = f"log {event.get('logStreamName', '?')} {when}"
        data = event.get("message", "").encode()
        scanner.scan_bytes(where, data)
        for name, text in questions.items():
            if text in data:
                scanner.hits.append((name, where))
    streams = len({e.get("logStreamName") for e in events})
    return f"{len(events)} log events in {streams} streams"


def ticket_questions(path=TICKETS_FILE, wanted: Iterable[str] = AC_D4_TICKETS) -> dict[str, bytes]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            ticket = json.loads(line)
            if ticket["ticket_id"] in wanted:
                out[f"question text of {ticket['ticket_id']}"] = ticket["question"].encode()
    return out


def ask_values(prompt=getpass.getpass) -> dict[str, bytes]:
    code = prompt("Stage B access code (hidden): ")
    if len(code) < 12:
        raise DeployError("the access code has at least 12 characters (spec 08 section 5)")
    values = {"the access code": code.encode()}
    key = prompt("The bot's Anthropic key (hidden; Enter to skip, the key pattern is searched anyway): ")
    if key:
        values["the Anthropic key"] = key.encode()
    return values


def main(argv: list[str] | None = None, runner=run_process, prompt=getpass.getpass, popen=subprocess.Popen) -> int:
    parser = argparse.ArgumentParser(prog="deploy/check_secrets_stage_b.py", description="AC-D9: search for secrets.")
    parser.add_argument("--tag", help="the release image tag (needed for the image target)")
    parser.add_argument("--only", default=",".join(TARGETS), help=f"comma-separated subset of {','.join(TARGETS)}")
    args = parser.parse_args(argv)
    targets = [t for t in args.only.split(",") if t]
    unknown = sorted(set(targets) - set(TARGETS))
    if unknown or not targets:
        print(f"error: unknown target(s) {', '.join(unknown)}; choose from {', '.join(TARGETS)}", file=sys.stderr)
        return 2
    if "image" in targets and not args.tag:
        print("error: the image target needs --tag", file=sys.stderr)
        return 2

    try:
        scanner = Scanner(ask_values(prompt))
    except DeployError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    aws = Aws(runner)
    failed = False
    for target in targets:
        try:
            if target in ("lambda", "logs") and aws.account is None:
                aws.identity()
            summary = {
                "repo": lambda: scan_repo(scanner, runner),
                "image": lambda: scan_image(scanner, args.tag, runner, popen),
                "lambda": lambda: scan_lambda(scanner, aws),
                "logs": lambda: scan_logs(scanner, aws, ticket_questions()),
            }[target]()
            print(f"[searched] {target}: {summary}")
        except (DeployError, OSError, tarfile.TarError) as e:
            failed = True
            print(f"[NOT SEARCHED] {target}: {e}", file=sys.stderr)
    for value, where in scanner.examples:
        print(f"[known documentation example] {value} (AWS example access key id, not a credential) in {where}")
    for what, where in scanner.hits:
        print(f"[FOUND] {what} in {where}")
    if scanner.hits or failed:
        print(f"AC-D9 NOT passed: {len(scanner.hits)} finding(s){', some targets not searched' if failed else ''}")
        return 1
    note = f" ({len(scanner.examples)} known AWS documentation example key id(s), not secrets)" if scanner.examples else ""
    print(f"AC-D9 passed for {', '.join(targets)}: no secret found{note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
