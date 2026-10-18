"""Labelled tickets and the fixed calibration/holdout split (spec 05).

The ticket file is frozen: it is only ever read here, never written.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TICKETS_PATH = REPO_ROOT / "evals" / "support_questions.jsonl"

TICKET_ID_PATTERN = re.compile(r"T-([0-9]+)")
EXPECTED_VALUES = ("answer", "escalate")
ARTICLE_MATCH_VALUES = ("all", "any")

# Spec 05, "Data split": odd ticket numbers calibrate, even ones are holdout.
CALIBRATION = "calibration"
HOLDOUT = "holdout"
FULL = "full"
SETS = (CALIBRATION, HOLDOUT, FULL)


class TicketError(Exception):
    """The ticket file cannot be evaluated as it is (fail loudly)."""


@dataclass(frozen=True)
class Ticket:
    ticket_id: str
    question: str
    expected: str  # "answer" | "escalate"
    expected_article_ids: tuple[str, ...]
    category: str
    # "all" unless the ticket says "any" (spec 05 clarification 2).
    article_match: str = "all"

    @property
    def number(self) -> int:
        return ticket_number(self.ticket_id)

    @property
    def split(self) -> str:
        return CALIBRATION if self.number % 2 == 1 else HOLDOUT

    @property
    def is_two_article(self) -> bool:
        return len(self.expected_article_ids) == 2


def ticket_number(ticket_id: str) -> int:
    match = TICKET_ID_PATTERN.fullmatch(ticket_id) if isinstance(ticket_id, str) else None
    if match is None:
        raise TicketError(f"ticket_id must look like 'T-001', got {ticket_id!r}")
    return int(match.group(1))


def parse_ticket(raw: dict, line_no: int) -> Ticket:
    where = f"ticket file line {line_no}"
    for name in ("ticket_id", "question", "expected", "expected_article_ids", "category"):
        if name not in raw:
            raise TicketError(f"{where}: missing field {name!r}")
    ticket_number(raw["ticket_id"])
    if raw["expected"] not in EXPECTED_VALUES:
        raise TicketError(f"{where}: expected must be one of {EXPECTED_VALUES}, got {raw['expected']!r}")
    ids = raw["expected_article_ids"]
    if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
        raise TicketError(f"{where}: expected_article_ids must be a list of strings")
    if raw["expected"] == "answer" and not ids:
        raise TicketError(f"{where}: an 'answer' ticket needs at least one expected article")
    article_match = raw.get("article_match", "all")
    if article_match not in ARTICLE_MATCH_VALUES:
        raise TicketError(f"{where}: article_match must be one of {ARTICLE_MATCH_VALUES}, got {article_match!r}")
    return Ticket(
        ticket_id=raw["ticket_id"],
        question=raw["question"],
        expected=raw["expected"],
        expected_article_ids=tuple(ids),
        category=raw["category"],
        article_match=article_match,
    )


def read_records(text: str, source: str = "ticket file") -> list[tuple[dict, Ticket]]:
    """(raw JSON record, Ticket) per line, in file order. Fails loudly on bad
    lines or duplicate IDs. The raw record keeps fields Ticket ignores (notes)."""
    records: list[tuple[dict, Ticket]] = []
    seen: set[str] = set()
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as e:
            raise TicketError(f"ticket file line {line_no}: not valid JSON ({e.msg})") from None
        ticket = parse_ticket(raw, line_no)
        if ticket.ticket_id in seen:
            raise TicketError(f"duplicate ticket_id {ticket.ticket_id}")
        seen.add(ticket.ticket_id)
        records.append((raw, ticket))
    if not records:
        raise TicketError(f"no tickets in {source}")
    return records


def load_tickets(path: Path | str = TICKETS_PATH) -> list[Ticket]:
    """All tickets in file order. Fails loudly on bad lines or duplicate IDs."""
    return [t for _, t in read_records(Path(path).read_text(encoding="utf-8"), str(path))]


def select(tickets: list[Ticket], set_name: str) -> list[Ticket]:
    if set_name == FULL:
        return list(tickets)
    if set_name not in (CALIBRATION, HOLDOUT):
        raise ValueError(f"unknown set {set_name!r}")
    return [t for t in tickets if t.split == set_name]


def file_sha256(path: Path | str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
