"""The free part of AC-D7 (spec 08 section 10): AC-D2 and AC-D3 again,
through the Function URL. No Claude call: every /ask here is refused with
401 before any retrieval or Claude call.

    .venv/bin/python deploy/check_stage_b.py                     # URL and tag read from AWS (voltrix-deploy)
    .venv/bin/python deploy/check_stage_b.py --url URL --tag TAG  # no AWS call

Checks: /health 200 with kb_version = data/ACTIVE_KB_VERSION and image_tag =
the deployed tag (the time of this first request is printed; after a
deploy it includes the cold start); /ask with a wrong code, with no code,
and with a wrong code and a broken body all give 401 {"error": "access
denied"} with an X-Request-Id; the page has its Content-Security-Policy;
/docs is switched off; no response contains an Anthropic key prefix.

AC-D4 through the Function URL is compare_tickets.py --url <Function URL>
(paid, run by the owner).

Exit 0 all passed, 1 otherwise.
"""

import argparse
import json
import re
import sys
import time

from check_stage_a import Report
from stage_b import (ACTIVE_KB_VERSION_FILE, Aws, DeployError, as_json, concurrency_note, environment_of, http,
                     join_url, kb_version, run_process)

DENIED = {"error": "access denied"}
WRONG_CODE = "wrong-code-0123456789"
UUID4 = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
KEY_PREFIX = "sk-ant-"


def target_from_aws(aws: Aws) -> tuple[str, str]:
    aws.identity()
    if aws.reserved_concurrency() == 0:
        raise DeployError(f"the function is {concurrency_note(0)[0]}; unthrottle it in the Lambda console first")
    url = aws.function_url()
    tag = environment_of(aws.function()["Configuration"]).get("IMAGE_TAG", "")
    if not tag:
        raise DeployError("IMAGE_TAG is not set on the function")
    return url, tag


def run(url: str, tag: str, kb: str, fetch=http, clock=time.monotonic) -> Report:
    report = Report()
    texts = []

    started = clock()
    status, _, text = fetch("GET", join_url(url, "/health"))
    seconds = clock() - started
    texts.append(text)
    body = as_json(text) or {}
    report.check("AC-D2 GET /health 200 with kb_version = data/ACTIVE_KB_VERSION",
                 status == 200 and body.get("status") == "ok" and body.get("kb_version") == kb,
                 f"HTTP {status}, kb_version {body.get('kb_version')!r} (expected {kb!r}), {seconds:.1f} s")
    report.check("/health image_tag is the deployed tag", body.get("image_tag") == tag,
                 f"{body.get('image_tag')!r} (expected {tag!r}); model_id {body.get('model_id')!r}")

    question = json.dumps({"question": "What does E-01 mean?"}).encode()
    cases = (
        ("wrong code", {"X-Access-Code": WRONG_CODE, "Content-Type": "application/json"}, question),
        ("no code", {"Content-Type": "application/json"}, question),
        ("wrong code and a broken body", {"X-Access-Code": WRONG_CODE, "Content-Type": "application/json"}, b"{not json"),
    )
    for label, headers, payload in cases:
        status, response_headers, text = fetch("POST", join_url(url, "/ask"), headers, payload)
        texts.append(text)
        report.check(f"AC-D3 POST /ask with {label} gives 401", status == 401 and as_json(text) == DENIED,
                     f"HTTP {status}, {text[:80]}")
        report.check(f"/ask ({label}) has an X-Request-Id",
                     bool(UUID4.fullmatch(response_headers.get("x-request-id", ""))))

    status, response_headers, text = fetch("GET", join_url(url, "/"))
    texts.append(text)
    report.check("GET / gives the page with a Content-Security-Policy",
                 status == 200 and bool(response_headers.get("content-security-policy"))
                 and "Synthetic data only." in text, f"HTTP {status}")
    status, _, text = fetch("GET", join_url(url, "/docs"))
    texts.append(text)
    report.check("/docs is switched off", status == 404, f"HTTP {status}")
    report.check("no Anthropic key prefix in any response", not any(KEY_PREFIX in t for t in texts))
    return report


def main(argv: list[str] | None = None, runner=run_process, fetch=http) -> int:
    parser = argparse.ArgumentParser(prog="deploy/check_stage_b.py", description="AC-D2 and AC-D3 through the Function URL.")
    parser.add_argument("--url", help="the Function URL (default: read from AWS)")
    parser.add_argument("--tag", help="the expected image tag (default: IMAGE_TAG read from AWS)")
    args = parser.parse_args(argv)
    try:
        if args.url and args.tag:
            url, tag = args.url, args.tag
        else:
            url, tag = target_from_aws(Aws(runner))
            url, tag = args.url or url, args.tag or tag
    except DeployError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"Function URL {url}, expected tag {tag}, KB {kb_version(ACTIVE_KB_VERSION_FILE)}")
    report = run(url, tag, kb_version(ACTIVE_KB_VERSION_FILE), fetch=fetch)
    failed = [name for name, passed, _ in report.rows if not passed]
    print(f"\n{len(report.rows) - len(failed)} passed, {len(failed)} failed")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
