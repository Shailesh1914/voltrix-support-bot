"""The web interface (spec 08 section 4): GET /, GET /health, POST /ask.

The web layer only wraps the existing query flow (query/flow.py). It adds
no prompt text, no checks on the bot's decision and no escalation settings: the
flow's result goes back unchanged, escalations included (a service error
is a 200 escalation, spec 02 decision 6).

POST /ask, in this order:
1. X-Access-Code missing or wrong -> 401. Checked with a constant-time
   compare before the body is read, so nothing else runs.
2. Body problems -> 400 with the exact texts of spec 08 section 4.2.
3. flow.ask(question) -> 200 with the response object of spec 02 "Output".
Anything unexpected -> 500 {"error": "internal error"}, no stack trace.

Every /ask response carries X-Request-Id, and one log line is written
per request: request id, decision ("-" for 400, 401 and 500), latency in
milliseconds and HTTP status. Nothing else is logged here: never the
question, the answer, the access code or the key.
"""

import hmac
import json
import logging
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Protocol

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.concurrency import run_in_threadpool

from query.config import MODEL_ID
from query.response import QueryResponse

log = logging.getLogger("voltrix.web")

ACCESS_CODE_HEADER = "X-Access-Code"
REQUEST_ID_HEADER = "X-Request-Id"
MAX_QUESTION_CHARS = 1000
NO_DECISION = "-"

ACCESS_DENIED = "access denied"
INVALID_BODY = "invalid request body"
QUESTION_REQUIRED = "question is required"
QUESTION_NOT_TEXT = "question must be text"
QUESTION_EMPTY = "question is empty"
QUESTION_TOO_LONG = f"question is longer than {MAX_QUESTION_CHARS} characters"
INTERNAL_ERROR = "internal error"

PAGE_PATH = Path(__file__).with_name("page.html")

# The page loads nothing from elsewhere (spec 08 section 4.3); the browser
# is told so too.
PAGE_SECURITY_POLICY = (
    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
    "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)

# FastAPI's own OpenTelemetry hooks are switched off: they could add
# telemetry about requests that the spec does not ask for.
NO_TELEMETRY = {"tracing": False, "metrics": False, "logs": False, "auto_configure": False}


class Flow(Protocol):
    def ask(self, question: str) -> QueryResponse: ...


class BadRequest(Exception):
    """A 400 case; the message is one of the spec 08 texts."""


def parse_question(body: bytes) -> str:
    """The question from a /ask body, or BadRequest (spec 08 section 4.2)."""
    try:
        data = json.loads(body)
    except ValueError:  # includes bad UTF-8
        raise BadRequest(INVALID_BODY) from None
    if not isinstance(data, dict):
        raise BadRequest(INVALID_BODY)
    if "question" not in data:
        raise BadRequest(QUESTION_REQUIRED)
    question = data["question"]
    if not isinstance(question, str):
        raise BadRequest(QUESTION_NOT_TEXT)
    if not question.strip():
        raise BadRequest(QUESTION_EMPTY)
    if len(question) > MAX_QUESTION_CHARS:
        raise BadRequest(QUESTION_TOO_LONG)
    return question


def code_matches(given: str | None, expected: str) -> bool:
    if given is None:
        return False
    return hmac.compare_digest(given.encode("utf-8"), expected.encode("utf-8"))


def create_app(flow: Flow, *, access_code: str, kb_version: str, image_tag: str) -> FastAPI:
    """The app over a ready flow. Nothing here reads settings or secrets."""
    page = PAGE_PATH.read_text(encoding="utf-8")
    health = {"status": "ok", "kb_version": kb_version, "model_id": MODEL_ID, "image_tag": image_tag}

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, telemetry=NO_TELEMETRY)

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        return HTMLResponse(page, headers={"Content-Security-Policy": PAGE_SECURITY_POLICY})

    @app.get("/health")
    def health_check() -> JSONResponse:
        return JSONResponse(health)

    @app.post("/ask")
    async def ask(request: Request) -> JSONResponse:
        request_id = str(uuid.uuid4())
        started = time.perf_counter()
        decision = NO_DECISION
        try:
            if not code_matches(request.headers.get(ACCESS_CODE_HEADER), access_code):
                status, body = 401, {"error": ACCESS_DENIED}
            else:
                try:
                    question = parse_question(await request.body())
                except BadRequest as e:
                    status, body = 400, {"error": str(e)}
                else:
                    result = await run_in_threadpool(flow.ask, question)
                    status, body = 200, asdict(result)
                    decision = result.status
        except Exception:
            # Never passed on or logged: the error text could hold the question.
            status, body, decision = 500, {"error": INTERNAL_ERROR}, NO_DECISION
        latency_ms = round((time.perf_counter() - started) * 1000)
        log.info("request_id=%s decision=%s latency_ms=%d status=%d", request_id, decision, latency_ms, status)
        return JSONResponse(body, status_code=status, headers={REQUEST_ID_HEADER: request_id})

    return app
