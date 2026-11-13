"""AC-D4 (spec 08 section 10): for 3 tickets, the container gives the same
decision and the same cited articles as query/ask.py on the laptop.

PAID: 6 Claude calls (3 laptop + 3 container). Run by the owner only.

    deploy/run_local.sh                                    # terminal 1
    .venv/bin/python deploy/compare_tickets.py             # terminal 2: dry run, no calls
    .venv/bin/python deploy/compare_tickets.py --confirm   # terminal 2: the paid run

The access code is asked for with a hidden prompt (it is never echoed,
printed or stored). The script never reads the secrets file; the laptop
bot and the container each read it themselves.

Tickets (Round 2 Q7): T-001 and T-002 (labelled "answer") and T-043
(labelled "escalate"); the labels are checked against the frozen file
first. "Same" means the same status and the same SET of cited
article_ids, order ignored. A service_error on either side proves
nothing about the bot, so it makes the run inconclusive, not a pass.

Exit codes: 0 all three match; 1 a mismatch or an error; 4 inconclusive
(service_error, re-run); 5 dry run (nothing was compared).
"""

import argparse
import getpass
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TICKETS_FILE = REPO_ROOT / "evals" / "support_questions.jsonl"
ACTIVE_KB_VERSION_FILE = REPO_ROOT / "data" / "ACTIVE_KB_VERSION"
DEFAULT_URL = "http://127.0.0.1:8080"

TICKETS = (("T-001", "answer"), ("T-002", "answer"), ("T-043", "escalate"))
LABEL_TO_STATUS = {"answer": "answered", "escalate": "escalated"}
SERVICE_ERROR = "service_error"
LAPTOP_TIMEOUT_S = 300
HTTP_TIMEOUT_S = 120

EXIT_MATCH, EXIT_FAILED, EXIT_INCONCLUSIVE, EXIT_DRY_RUN = 0, 1, 4, 5


class CompareError(Exception):
    pass


@dataclass(frozen=True)
class Outcome:
    status: str
    reason: str
    articles: frozenset[str]

    def show(self) -> str:
        reason = f" ({self.reason})" if self.reason else ""
        return f"{self.status}{reason} {sorted(self.articles)}"


def outcome_of(response: dict) -> Outcome:
    """The parts AC-D4 compares, from a spec 02 response object."""
    try:
        return Outcome(
            status=response["status"],
            reason=response.get("escalation_reason") or "",
            articles=frozenset(c["article_id"] for c in response.get("citations") or []),
        )
    except (KeyError, TypeError) as e:
        raise CompareError(f"not a spec 02 response object ({type(e).__name__})") from None


def load_tickets(path: Path = TICKETS_FILE, wanted=TICKETS) -> list[dict]:
    """The chosen tickets, in order; their labels must be the expected ones."""
    by_id = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            ticket = json.loads(line)
            by_id[ticket["ticket_id"]] = ticket
    chosen = []
    for ticket_id, label in wanted:
        ticket = by_id.get(ticket_id)
        if ticket is None:
            raise CompareError(f"{ticket_id} is not in {path.name}")
        if ticket["expected"] != label:
            raise CompareError(f"{ticket_id} is labelled {ticket['expected']!r}, expected {label!r}")
        chosen.append(ticket)
    return chosen


def verdict(laptop: Outcome, container: Outcome) -> str:
    if SERVICE_ERROR in (laptop.reason, container.reason):
        return "inconclusive"
    if laptop.status == container.status and laptop.articles == container.articles:
        return "match"
    return "MISMATCH"


def compare(tickets: list[dict], ask_laptop: Callable[[str], dict], ask_container: Callable[[str], dict]) -> list[tuple]:
    rows = []
    for ticket in tickets:
        laptop = outcome_of(ask_laptop(ticket["question"]))
        container = outcome_of(ask_container(ticket["question"]))
        rows.append((ticket["ticket_id"], ticket["expected"], laptop, container, verdict(laptop, container)))
    return rows


def exit_code(rows: list[tuple]) -> int:
    results = [row[4] for row in rows]
    if "MISMATCH" in results:
        return EXIT_FAILED
    if "inconclusive" in results:
        return EXIT_INCONCLUSIVE
    return EXIT_MATCH


# --- The two real sides ------------------------------------------------------


def laptop_asker(python: str = sys.executable) -> Callable[[str], dict]:
    def ask(question: str) -> dict:
        result = subprocess.run([python, "-m", "query.ask", question], cwd=REPO_ROOT,
                                capture_output=True, text=True, timeout=LAPTOP_TIMEOUT_S)
        if result.returncode != 0:
            raise CompareError(f"query.ask failed (exit {result.returncode}): {result.stderr.strip()[-300:]}")
        return json.loads(result.stdout)
    return ask


def http(method: str, url: str, headers: dict | None = None, body: dict | None = None) -> tuple[int, dict | None]:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(url, data=data, method=method,
                                     headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_S) as response:
            status, text = response.status, response.read().decode()
    except urllib.error.HTTPError as e:
        status, text = e.code, e.read().decode()
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        raise CompareError(f"cannot reach the container at {url}: {type(e).__name__}") from None
    try:
        return status, json.loads(text)
    except ValueError:
        return status, None


def container_asker(base_url: str, access_code: str) -> Callable[[str], dict]:
    def ask(question: str) -> dict:
        status, body = http("POST", f"{base_url}/ask", {"X-Access-Code": access_code}, {"question": question})
        if status != 200 or body is None:
            raise CompareError(f"container /ask gave HTTP {status}")
        return body
    return ask


def preflight(base_url: str, access_code: str, kb_version: str) -> None:
    """Free checks before any paid call: same KB version, and the code is
    accepted (an empty question is refused with 400 after the code check,
    before any retrieval or Claude call)."""
    status, body = http("GET", f"{base_url}/health")
    if status != 200 or not body or body.get("kb_version") != kb_version:
        raise CompareError(f"container /health gave HTTP {status}, kb_version {(body or {}).get('kb_version')!r}; "
                           f"data/ACTIVE_KB_VERSION is {kb_version!r}")
    status, body = http("POST", f"{base_url}/ask", {"X-Access-Code": access_code}, {"question": " "})
    if status == 401:
        raise CompareError("the container refused the access code (401)")
    if status != 400 or (body or {}).get("error") != "question is empty":
        raise CompareError(f"unexpected answer to the free code check: HTTP {status}")


def print_rows(rows: list[tuple]) -> None:
    print(f"{'ticket':<7} {'label':<9} {'laptop (query/ask.py)':<40} {'container':<40} result")
    for ticket_id, label, laptop, container, result in rows:
        print(f"{ticket_id:<7} {label:<9} {laptop.show():<40} {container.show():<40} {result}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="deploy/compare_tickets.py", description="AC-D4: laptop bot vs container (6 paid calls).")
    parser.add_argument("--confirm", action="store_true", help="really make the 6 paid Claude calls")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"the running container (default {DEFAULT_URL})")
    args = parser.parse_args(argv)
    try:
        tickets = load_tickets()
        refused = sorted(name for name in os.environ if name.startswith("ANTHROPIC_"))
        if refused:
            raise CompareError(f"unset these first: {', '.join(refused)}")
        kb_version = ACTIVE_KB_VERSION_FILE.read_text(encoding="utf-8").strip()
        print(f"Tickets: {', '.join(f'{t['ticket_id']} ({t['expected']})' for t in tickets)}; KB {kb_version}; container {args.url}")
        if not args.confirm:
            print("Dry run: no calls made. Add --confirm for the paid run (6 Claude calls).")
            return EXIT_DRY_RUN
        access_code = getpass.getpass("Access code (hidden): ")
        preflight(args.url, access_code, kb_version)
        rows = compare(tickets, laptop_asker(), container_asker(args.url, access_code))
    except CompareError as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_FAILED
    print_rows(rows)
    code = exit_code(rows)
    print({EXIT_MATCH: "AC-D4 PASSED: same decision and cited articles for all 3 tickets",
           EXIT_FAILED: "AC-D4 FAILED: see MISMATCH above",
           EXIT_INCONCLUSIVE: "AC-D4 INCONCLUSIVE: a service_error on one side; re-run"}[code])
    return code


if __name__ == "__main__":
    sys.exit(main())
