"""Run the web app:  python -m web

Listens on 0.0.0.0:8080 (spec 08 section 6). The app is built before
uvicorn starts, so a start-up problem is one "error: ..." line on stderr
and exit code 2, never a stack trace.

Logging (spec 08 section 4.4): uvicorn's access log is off. Only the
web app's request lines (INFO) and warnings or worse from other code
(e.g. the Anthropic API warning) are written, to stderr.
"""

import logging
import sys
from collections.abc import Callable

import uvicorn
from fastapi import FastAPI

from ingestion import RetrievalError
from query.config import ConfigError
from web import startup

HOST = "0.0.0.0"
PORT = 8080
EXIT_STARTUP_FAILED = 2
LOG_FORMAT = "%(levelname)s %(name)s %(message)s"


def configure_logging() -> None:
    """Root at WARNING keeps every library's INFO and DEBUG lines out. The
    Anthropic SDK logs whole requests (question included) at DEBUG, and
    the HTTP client one line per call at INFO. The request log line is
    INFO on the web app's own logger."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.WARNING)
    logging.getLogger("voltrix.web").setLevel(logging.INFO)


def main(build: Callable[[], FastAPI] | None = None, run: Callable[..., None] | None = None) -> int:
    configure_logging()
    try:
        app = (build or startup.build_app)()
    except (ConfigError, RetrievalError) as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_STARTUP_FAILED
    (run or uvicorn.run)(app, host=HOST, port=PORT, access_log=False, log_config=None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
