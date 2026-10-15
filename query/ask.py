"""Ask the real bot one question locally:

    python -m query.ask "E-01 when the motor ramps up, what do I check?"

Prints the response object (spec 02, "Output") as JSON. Escalations are
appended to HANDOFF_PATH.

Fails loudly (message on stderr, exit code 2, no model call) while
ESCALATION_THRESHOLD is not set, or if the settings, API key or index
are wrong.
"""

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import asdict

from ingestion import RetrievalError, open_retrieval
from query import config
from query.anthropic_api import AnthropicGenerator
from query.config import ConfigError, load_settings, require_threshold
from query.flow import QueryFlow
from query.handoff import JsonlHandoffStore

EXIT_STARTUP_FAILED = 2


def build_flow() -> QueryFlow:
    """The real bot: config threshold, ACTIVE_KB_VERSION index, Anthropic API.

    The threshold is checked first, so nothing is loaded while it is unset.
    The API key is checked before the (slower) index is opened.
    """
    threshold = require_threshold(config.ESCALATION_THRESHOLD)
    settings = load_settings()
    generator = AnthropicGenerator.from_environment()
    return QueryFlow(
        open_retrieval(settings.active_kb_version),
        generator,
        threshold=threshold,
        handoff_store=JsonlHandoffStore(settings.handoff_path),
        kb_version=settings.active_kb_version,
    )


def main(argv: list[str] | None = None, build: Callable[[], QueryFlow] = build_flow) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m query.ask",
        description="Ask the Voltrix VX-200 support bot one question.",
    )
    parser.add_argument("question", nargs="+", help="the question (quote it, or give it as several words)")
    args = parser.parse_args(argv)
    question = " ".join(args.question)
    if not question.strip():
        parser.error("the question is empty")

    try:
        flow = build()
    except (ConfigError, RetrievalError) as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_STARTUP_FAILED

    response = flow.ask(question)
    print(json.dumps(asdict(response), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
