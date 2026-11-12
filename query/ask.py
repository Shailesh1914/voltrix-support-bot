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
from query.config import ConfigError, Settings, load_settings, require_threshold
from query.flow import QueryFlow
from query.generator import Generator
from query.handoff import JsonlHandoffStore

EXIT_STARTUP_FAILED = 2


def _anthropic_from_environment(settings: Settings) -> Generator:
    return AnthropicGenerator.from_environment()


def build_flow(make_generator: Callable[[Settings], Generator] | None = None) -> QueryFlow:
    """The real bot: config threshold, the index of the version in
    data/ACTIVE_KB_VERSION (spec 07), Anthropic API.

    The threshold is checked first, so nothing is loaded while it is unset.
    The API key is checked before the (slower) index is opened.

    make_generator(settings) builds the generator; by default it reads the
    key as spec 02 says. The web app (spec 08) passes its own, which reads
    the key from where VOLTRIX_SECRETS_SOURCE says. Everything else is the
    same for both, so the deployed bot is built exactly like this command.
    """
    threshold = require_threshold(config.ESCALATION_THRESHOLD)
    settings = load_settings()
    generator = (make_generator or _anthropic_from_environment)(settings)
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
