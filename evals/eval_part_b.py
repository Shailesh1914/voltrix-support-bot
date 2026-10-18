"""Part B: every ticket through the real flow with the real model (spec 05).

The flow is QueryFlow at threshold -1.0 (passed to the flow directly, for
the evaluation only; query/config.py is never read or changed), so the
retrieval check never escalates and every model decision is recorded.
The unknown-fault-code check stays active.

Cost control (spec 05):
- plan() is free: a stand-in generator builds each request the real
  generator would send (AnthropicGenerator.request(), no key, no
  network), counts the calls and estimates the cost. The request holds
  what the model reads: every chunk of the selected articles (spec 02
  step 3e), so the estimate follows the size of those articles.
- UsageRecordingGenerator wraps the real generator, records each call's
  output and token usage, and refuses a call beyond MAX_MODEL_CALLS.
- run_tickets() stops at the first service_error: the run is invalid
  anyway (spec 02 decision 6) and every later call would be wasted.

Retrieved chunks and top score (spec 02 v1.14): the model now reads whole
articles (article_chunks(), score 0.0), so its chunks no longer carry the
step-d scores. The free planning pass escalates every ticket, so its
handoff records hold each ticket's step-d chunks with their scores (spec
02: the handoff holds all retrieved chunks). run_tickets() takes the
retrieved chunks and the top score from there, and checks the paid run
against it: an escalation's own handoff must hold the same chunks, and
the model must have read exactly the step-d articles, in order. Retrieval
is deterministic (spec 03, contract test 5), so any difference is an
error, never noise.

Run names (2026-10-17): every new run has a label, e.g.
<date>-part-b-<label>-run1.json, so runs of different code never clash.
The unlabelled run 1 (old code) stays as it is; the aggregate and the
sweep refuse to combine runs with different labels or code trees.

Token gap (approved 2026-10-17): when the model's output is malformed,
AnthropicGenerator.generate_with_usage() raises before it returns usage,
so those calls have no token counts. They are still billed; the report
counts them and says the cost is slightly underestimated.
"""

import hashlib
import json
import math
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from evals.eval_recorders import EvalError, MemoryHandoffStore
from evals.eval_scoring import ESCALATED, SERVICE_ERROR, passes, score
from evals.eval_sweep import PART_B_KIND, PART_B_THRESHOLD, outcome_from_record
from evals.eval_tickets import REPO_ROOT, SETS, Ticket, select
from ingestion import Chunk
from query.generator import GeneratorOutput, GeneratorServiceError, MalformedOutput

RUN_NUMBERS = (1, 2, 3)

# Spec 05, "Cost control": hard limit per run.
MAX_MODEL_CALLS = 100

# Claude Haiku 4.5 on the Anthropic API, USD per million tokens
# (checked 2026-10-17). Estimates only: the bill is what counts.
PRICE_INPUT_PER_MTOK = 1.00
PRICE_OUTPUT_PER_MTOK = 5.00

# Dry-run estimate, deliberately on the high side: characters of the
# request JSON per token, a fixed allowance for the tool-use overhead the
# API adds, and a typical answer length. The worst case uses
# MAX_OUTPUT_TOKENS for every call.
ESTIMATE_CHARS_PER_TOKEN = 3.0
ESTIMATE_TOOL_OVERHEAD_TOKENS = 500
ESTIMATE_OUTPUT_TOKENS = 500

# Folders whose uncommitted changes block a paid run (decision 3,
# 2026-10-17): every run must map to a commit.
PROTECTED_PATHSPECS = ("query", "ingestion", "specs", ":(glob)evals/*.py")
CODE_TREES = ("query", "ingestion")
# The evaluation's own code is part of what must match across runs; its
# reports/ folder changes between runs, so only evals/*.py counts.
EVALS_CODE = "evals/*.py"

# Run labels: lowercase words joined by hyphens. Words that already mean
# something in a run file name are not allowed.
LABEL_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
LABEL_MAX_LENGTH = 40
RESERVED_LABEL_WORD = re.compile(r"^(run\d*|invalid|handoffs|aggregate|sweep|confirm)$")

RUN_MALFORMED_NOTE = (
    "Malformed model outputs have no token counts (the generator raises before "
    "returning usage). They are still billed, so the cost is slightly underestimated "
    "for them."
)


# Spec 02, "Escalation handoff" (criterion 3): the fields of a complete
# record, checked here from the spec, not with the bot's own code.
HANDOFF_FIELDS = (
    "handoff_id", "created_at", "question_received", "question_normalised", "retrieved_chunks",
    "escalation_reason", "kb_version", "rejected_answer", "failed_check",
)
HANDOFF_CHUNK_FIELDS = ("chunk_id", "article_id", "text", "similarity_score")


def handoff_missing_fields(record: dict) -> list[str]:
    missing = [name for name in HANDOFF_FIELDS if name not in record]
    for i, chunk in enumerate(record.get("retrieved_chunks") or []):
        missing += [f"retrieved_chunks[{i}].{name}" for name in HANDOFF_CHUNK_FIELDS if name not in chunk]
    return missing


class CallLimitExceeded(EvalError):
    """A call beyond MAX_MODEL_CALLS was refused (never caught by the flow)."""


# --- Generators passed into QueryFlow ------------------------------------------


@dataclass
class ModelCall:
    """What one generator call saw and returned."""

    question: str
    chunks: list[Chunk]
    output: GeneratorOutput | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    malformed: bool = False
    service_error: bool = False


class UsageRecordingGenerator:
    """The real generator, through its public generate_with_usage()."""

    def __init__(self, inner, max_calls: int = MAX_MODEL_CALLS):
        self._inner = inner
        self.max_calls = max_calls
        self.calls = 0
        self._last: ModelCall | None = None

    def generate(self, question: str, chunks: list[Chunk]) -> GeneratorOutput:
        if self.calls >= self.max_calls:
            raise CallLimitExceeded(f"refused model call {self.calls + 1}: the limit is {self.max_calls} per run")
        self.calls += 1
        call = self._last = ModelCall(question, list(chunks))
        try:
            output, usage = self._inner.generate_with_usage(question, chunks)
        except MalformedOutput:
            call.malformed = True
            raise
        except GeneratorServiceError:
            call.service_error = True
            raise
        call.output = output
        call.input_tokens, call.output_tokens = usage.input_tokens, usage.output_tokens
        return output

    def take(self) -> ModelCall | None:
        """The call made for the last question, if any."""
        call, self._last = self._last, None
        return call


def request_settings(generator) -> dict:
    """Model settings as the generator itself sends them, read from its
    public request() (so they are recorded, not assumed)."""
    request = generator.request("settings check", [])
    return {
        "model_id": request["model"],
        "temperature": request.get("extra_body", {}).get("temperature"),
        "max_output_tokens": request["max_tokens"],
        "system_prompt_sha256": hashlib.sha256(request["system"].encode("utf-8")).hexdigest(),
    }


@dataclass
class PlannedCall:
    estimated_input_tokens: int
    articles_read: int
    chunks_read: int


class PlanningGenerator:
    """Free stand-in: builds the exact request the real generator would
    send (no key, no network), over the chunks the flow passes it (every
    chunk of the selected articles, spec 02 step 3e), estimates its size
    and declines, so the flow escalates without an answer."""

    def __init__(self):
        from query.anthropic_api import AnthropicGenerator

        self._request_builder = AnthropicGenerator(client=None)
        self.settings = request_settings(self._request_builder)
        self.planned: list[PlannedCall] = []

    def generate(self, question: str, chunks: list[Chunk]) -> GeneratorOutput:
        request = self._request_builder.request(question, chunks)
        sent = {k: request[k] for k in ("system", "messages", "tools", "tool_choice")}
        chars = len(json.dumps(sent, ensure_ascii=False))
        tokens = math.ceil(chars / ESTIMATE_CHARS_PER_TOKEN) + ESTIMATE_TOOL_OVERHEAD_TOKENS
        self.planned.append(PlannedCall(tokens, len({c.article_id for c in chunks}), len(chunks)))
        return GeneratorOutput(decision="insufficient_context", answer="", used_article_ids=())


# --- Cost ------------------------------------------------------------------------


def cost_usd(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * PRICE_INPUT_PER_MTOK + output_tokens * PRICE_OUTPUT_PER_MTOK) / 1_000_000


@dataclass(frozen=True)
class TicketRetrieval:
    """One ticket's retrieval from the free planning pass (its handoff)."""

    question_normalised: str
    chunks: tuple[tuple[str, str, float], ...]  # (chunk_id, article_id, similarity_score), step d

    @property
    def article_ids(self) -> list[str]:
        return [a for _, a, _ in self.chunks]


def chunk_triples(chunks) -> tuple[tuple[str, str, float], ...]:
    return tuple((c.chunk_id, c.article_id, c.similarity_score) for c in chunks)


def plan(tickets: list[Ticket], flow, planner: PlanningGenerator, store: MemoryHandoffStore
         ) -> tuple[dict, dict[str, TicketRetrieval]]:
    """Planned model calls and estimated cost, and each ticket's retrieval
    (step-d chunks with scores, from its handoff record). Nothing is called
    or written. The planner declines every call, so every ticket escalates
    and has a handoff record."""
    retrieval: dict[str, TicketRetrieval] = {}
    for ticket in tickets:
        response = flow.ask(ticket.question)
        record = store.by_id(response.handoff_id) if response.handoff_id else None
        if record is None:
            raise EvalError(f"{ticket.ticket_id}: the planning pass left no handoff record (status {response.status!r})")
        if not record.retrieved_chunks:
            raise EvalError(f"{ticket.ticket_id}: the flow retrieved no chunks")
        retrieval[ticket.ticket_id] = TicketRetrieval(record.question_normalised, chunk_triples(record.retrieved_chunks))
    n = len(planner.planned)
    input_tokens = sum(p.estimated_input_tokens for p in planner.planned)
    expected_output = n * ESTIMATE_OUTPUT_TOKENS
    worst_output = n * planner.settings["max_output_tokens"]
    return {
        "tickets": len(tickets),
        "planned_model_calls": n,
        "max_model_calls": MAX_MODEL_CALLS,
        "within_limit": n <= MAX_MODEL_CALLS,
        "estimated_input_tokens": input_tokens,
        "estimated_output_tokens": expected_output,
        "worst_case_output_tokens": worst_output,
        "estimated_cost_usd": cost_usd(input_tokens, expected_output),
        "worst_case_cost_usd": cost_usd(input_tokens, worst_output),
        # What the requests carry (spec 02 step 3e: whole selected articles).
        "articles_read": sum(p.articles_read for p in planner.planned),
        "chunks_read": sum(p.chunks_read for p in planner.planned),
        "max_estimated_input_tokens_per_call": max((p.estimated_input_tokens for p in planner.planned), default=0),
    }, retrieval


def plan_lines(p: dict) -> list[str]:
    return [
        f"tickets:              {p['tickets']}",
        f"planned model calls:  {p['planned_model_calls']} (limit {p['max_model_calls']} per run)",
        f"model reads (total):  {p['articles_read']} whole articles, {p['chunks_read']} chunks "
        f"(avg {p['chunks_read'] / max(p['planned_model_calls'], 1):.1f} chunks per call)",
        f"input tokens (est.):  {p['estimated_input_tokens']:,} "
        f"(largest call {p['max_estimated_input_tokens_per_call']:,})",
        f"output tokens (est.): {p['estimated_output_tokens']:,} typical, {p['worst_case_output_tokens']:,} worst case",
        f"cost (est.):          ${p['estimated_cost_usd']:.2f} typical, ${p['worst_case_cost_usd']:.2f} worst case "
        f"(${PRICE_INPUT_PER_MTOK:.2f} / ${PRICE_OUTPUT_PER_MTOK:.2f} per million input / output tokens)",
    ]


# --- The run ---------------------------------------------------------------------


@dataclass
class RunOutcome:
    rows: list[dict]
    handoffs: list[dict]
    stopped: dict | None = None  # None = every ticket ran
    model_calls: int = 0
    extra: dict = field(default_factory=dict)


def read_article_ids(chunks) -> list[str]:
    """The articles the model read, in the order it read them."""
    return list(dict.fromkeys(c.article_id for c in chunks))


def ticket_row(ticket: Ticket, response, record, call: ModelCall | None, planned: TicketRetrieval) -> dict:
    """planned is this ticket's retrieval from the free planning pass: the
    step-d chunks with their scores. The paid run must agree with it."""
    tid = ticket.ticket_id
    if call is None and record is None:
        raise EvalError(f"{tid}: answered without a model call")
    if not planned.chunks:
        raise EvalError(f"{tid}: the flow retrieved no chunks")
    if record is not None and chunk_triples(record.retrieved_chunks) != planned.chunks:
        raise EvalError(f"{tid}: the handoff's retrieved chunks differ from the planning pass (retrieval not repeatable)")
    question_sent = call.question if call is not None else record.question_normalised
    if question_sent != planned.question_normalised:
        raise EvalError(f"{tid}: the question sent differs from the planning pass")
    read = read_article_ids(call.chunks) if call is not None else []
    if call is not None and read != planned.article_ids:
        raise EvalError(
            f"{tid}: the model read articles {read}, but step d selected {planned.article_ids} (spec 02 step 3e)"
        )
    chunks = planned.chunks
    output = call.output if call else None
    row = {
        "ticket_id": ticket.ticket_id,
        "split": ticket.split,
        "expected": ticket.expected,
        "category": ticket.category,
        "expected_article_ids": list(ticket.expected_article_ids),
        "article_match": ticket.article_match,
        "question_sent": question_sent,
        "top_score": max(s for _, _, s in chunks),
        # Step d (spec 02): the chunks the retrieval check and citations use.
        "retrieved_chunks": [{"chunk_id": c, "article_id": a, "similarity_score": s} for c, a, s in chunks],
        # Step e: what the model read (whole articles), if it was called.
        "read_article_ids": read,
        "read_chunks": len(call.chunks) if call is not None else 0,
        "status": response.status,
        "escalation_reason": response.escalation_reason,
        "citations": [{"article_id": c.article_id, "title": c.title} for c in response.citations],
        "failed_check": record.failed_check if record else "",
        "rejected_answer": record.rejected_answer if record else "",
        "answer": response.answer,
        "handoff_id": response.handoff_id,
        "model_called": call is not None,
        "model_output": (
            {"decision": output.decision, "answer": output.answer, "used_article_ids": list(output.used_article_ids)}
            if output else None
        ),
        "malformed_output": bool(call and call.malformed),
        "input_tokens": call.input_tokens if call else None,
        "output_tokens": call.output_tokens if call else None,
    }
    row["ac_pass"] = passes(ticket, outcome_from_record(row))
    return row


def run_tickets(tickets: list[Ticket], flow, generator: UsageRecordingGenerator, store: MemoryHandoffStore,
                retrieval: dict[str, TicketRetrieval]) -> RunOutcome:
    """Every ticket once, in file order. Stops at the first service_error.
    retrieval comes from plan() (the free planning pass).

    Any other failure after a paid call is returned as a stopped run (so
    the paid results are kept as an invalid run); a failure before the
    first paid call is raised and nothing is written.
    """
    rows: list[dict] = []
    stopped = None
    current = None
    try:
        for ticket in tickets:
            current = ticket.ticket_id
            response = flow.ask(ticket.question)
            call = generator.take()
            record = store.by_id(response.handoff_id) if response.handoff_id else None
            if response.status == ESCALATED and record is None:
                raise EvalError(f"{ticket.ticket_id}: escalated without a handoff record")
            if ticket.ticket_id not in retrieval:
                raise EvalError(f"{ticket.ticket_id}: not in the planning pass")
            rows.append(ticket_row(ticket, response, record, call, retrieval[ticket.ticket_id]))
            if response.escalation_reason == SERVICE_ERROR:
                stopped = {"reason": "service_error", "ticket_id": ticket.ticket_id}
                break
    except (Exception, KeyboardInterrupt) as e:
        if generator.calls == 0:
            raise
        stopped = {"reason": f"aborted: {type(e).__name__}: {e}", "ticket_id": current}
    return RunOutcome(
        rows=rows,
        handoffs=[r.to_dict() for r in store.records],
        stopped=stopped,
        model_calls=generator.calls,
    )


def run_data(tickets: list[Ticket], outcome: RunOutcome, run_number: int | None, label: str | None = None, *,
             kind: str = PART_B_KIND, threshold: float = PART_B_THRESHOLD) -> dict:
    """The run file body (provenance is added by the runner). kind and
    threshold differ only for the confirmation run (eval_confirm), whose
    file must never be read as a Part B run."""
    rows = outcome.rows
    called = [r for r in rows if r["model_called"]]
    with_usage = [r for r in called if r["input_tokens"] is not None]
    input_tokens = sum(r["input_tokens"] for r in with_usage)
    output_tokens = sum(r["output_tokens"] for r in with_usage)
    incomplete = [h["handoff_id"] for h in outcome.handoffs if handoff_missing_fields(h)]
    valid = outcome.stopped is None and len(rows) == len(tickets) and not incomplete
    data = {
        "kind": kind,
        "run": run_number,
        "label": label,
        "threshold": threshold,
        "valid": valid,
        "stopped": outcome.stopped,
        "tickets_run": len(rows),
        "tickets_total": len(tickets),
        "model_calls": outcome.model_calls,
        "tokens": {
            "input": input_tokens,
            "output": output_tokens,
            "calls_without_usage": len(called) - len(with_usage),
        },
        "malformed_outputs": sum(r["malformed_output"] for r in rows),
        "cost_usd": cost_usd(input_tokens, output_tokens),
        "cost_note": RUN_MALFORMED_NOTE,
        "prices_usd_per_mtok": {"input": PRICE_INPUT_PER_MTOK, "output": PRICE_OUTPUT_PER_MTOK},
        "handoff_records": len(outcome.handoffs),
        "incomplete_handoff_records": incomplete,
        "summary": None,
        "tickets": rows,
    }
    if valid:
        outcomes = {r["ticket_id"]: outcome_from_record(r) for r in rows}
        data["summary"] = {name: score(select(tickets, name), outcomes) for name in SETS}
    return data


# --- Provenance and file names ---------------------------------------------------


def git(args: list[str], repo_root: Path) -> str:
    return subprocess.run(["git", *args], cwd=repo_root, capture_output=True, text=True, check=True).stdout


def uncommitted_code_changes(repo_root: Path = REPO_ROOT) -> list[str]:
    """Changed or untracked files in the protected folders. Fails loudly if
    git cannot tell (a paid run must map to a commit)."""
    try:
        out = git(["status", "--porcelain", "--untracked-files=all", "--", *PROTECTED_PATHSPECS], repo_root)
    except (OSError, subprocess.CalledProcessError) as e:
        raise EvalError(f"cannot check for uncommitted changes with git ({type(e).__name__})") from None
    return [line[3:] for line in out.splitlines() if line.strip()]


def evals_code_id(repo_root: Path = REPO_ROOT) -> str | None:
    """One id for evals/*.py at HEAD: SHA-256 of their names and blob ids
    (equal ids = identical evaluation code; reports/ is left out)."""
    try:
        out = git(["ls-tree", "HEAD", "evals/"], repo_root)
    except (OSError, subprocess.CalledProcessError):
        return None
    lines = sorted(line for line in out.splitlines() if line.split("\t")[-1].endswith(".py"))
    if not lines:
        return None
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def code_trees(repo_root: Path = REPO_ROOT) -> dict[str, str | None]:
    """Git tree id of each code folder at HEAD, and the id of evals/*.py
    (equal ids = identical code)."""
    trees = {}
    for name in CODE_TREES:
        try:
            trees[name] = git(["rev-parse", f"HEAD:{name}"], repo_root).strip()
        except (OSError, subprocess.CalledProcessError):
            trees[name] = None
    trees[EVALS_CODE] = evals_code_id(repo_root)
    return trees


def check_label(label: str) -> str:
    """A run label, or EvalError. Lowercase words joined by hyphens."""
    if not isinstance(label, str) or not LABEL_PATTERN.match(label) or len(label) > LABEL_MAX_LENGTH:
        raise EvalError(
            f"label {label!r}: use lowercase letters and digits, words joined by single hyphens, "
            f"at most {LABEL_MAX_LENGTH} characters (e.g. whole-articles)"
        )
    reserved = [w for w in label.split("-") if RESERVED_LABEL_WORD.match(w)]
    if reserved:
        raise EvalError(f"label {label!r}: {', '.join(reserved)} already means something in report names")
    return label


def run_name(label: str, run_number: int) -> str:
    return f"part-b-{check_label(label)}-run{run_number}"


def existing_valid_runs(reports_dir: Path, label: str, run_number: int) -> list[Path]:
    """Valid run files for this label and run number, any date. Invalid
    attempts are named ...-invalid-<k> and never block a re-run."""
    return sorted(Path(reports_dir).glob(f"*-{run_name(label, run_number)}.json"))


def invalid_name(reports_dir: Path, date: str, label: str, run_number: int) -> str:
    k = 1
    while (Path(reports_dir) / f"{date}-{run_name(label, run_number)}-invalid-{k}.json").exists():
        k += 1
    return f"{run_name(label, run_number)}-invalid-{k}"


def handoffs_path(reports_dir: Path, date: str, name: str) -> Path:
    return Path(reports_dir) / f"{date}-{name}-handoffs.jsonl"


def write_handoffs(path: Path, handoffs: list[dict]) -> Path:
    if path.exists():
        raise EvalError(f"{path} already exists; Part B files are never replaced")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as f:
        for record in handoffs:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


def folder_snapshot(folder: Path):
    """Contents of a folder (None if absent), to prove a run left it alone."""
    if not folder.exists():
        return None
    return {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob("*") if p.is_file()}
