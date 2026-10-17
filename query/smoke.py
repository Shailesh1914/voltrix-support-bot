"""Manual smoke test of the real generator. Run by Shailesh only:

    python -m query.smoke

Sends ONE fixed question, with real chunks retrieved as the flow does
(spec 02, step 3: query/retrieval.py) on KB version v1,
to the Anthropic generator ONLY: no flow, no threshold, no handoff.
Prints the decision, used_article_ids, the start of the answer and the
token usage. Never prints the API key.

Exit codes: 0 the call returned valid output; 1 the call failed
(service error or malformed output); 2 startup failed (key, environment
or index).
"""

import sys
from collections.abc import Callable
from typing import TextIO

from ingestion import RetrievalError, open_retrieval
from query.anthropic_api import AnthropicGenerator
from query.config import ConfigError
from query.fault_codes import code_titles
from query.generator import GeneratorServiceError, MalformedOutput
from query.masking import mask_personal_data
from query.normalise import normalise_codes
from query.retrieval import retrieve

SMOKE_QUESTION = "E-01 when the motor ramps up, what do I check?"
SMOKE_KB_VERSION = "v1"
ANSWER_PREVIEW_CHARS = 200

EXIT_CALL_FAILED = 1
EXIT_STARTUP_FAILED = 2


def main(
    open_index: Callable = open_retrieval,
    make_generator: Callable[[], AnthropicGenerator] = AnthropicGenerator.from_environment,
    out: TextIO = sys.stdout,
) -> int:
    def say(line: str = "") -> None:
        print(line, file=out)

    try:
        generator = make_generator()
        retriever = open_index(SMOKE_KB_VERSION)
        titles = code_titles(retriever.kb_info())
    except (ConfigError, RetrievalError) as e:
        say(f"error: {e}")
        return EXIT_STARTUP_FAILED

    # The same question preparation and retrieval as the flow (spec 02,
    # steps 1-3).
    question = normalise_codes(mask_personal_data(SMOKE_QUESTION))
    chunks = retrieve(retriever, question, titles)
    say(f"question:   {question}")
    say(f"kb_version: {SMOKE_KB_VERSION}")
    say(f"model:      {generator.model_id}")
    say("chunks:     " + ", ".join(f"{c.chunk_id} ({c.similarity_score:.3f})" for c in chunks))

    try:
        output, usage = generator.generate_with_usage(question, chunks)
    except GeneratorServiceError as e:
        say(f"service error: {e}")
        return EXIT_CALL_FAILED
    except MalformedOutput as e:
        say(f"malformed output: {e}")
        return EXIT_CALL_FAILED

    say()
    say(f"decision:         {output.decision}")
    say(f"used_article_ids: {list(output.used_article_ids)}")
    preview = output.answer[:ANSWER_PREVIEW_CHARS] + ("..." if len(output.answer) > ANSWER_PREVIEW_CHARS else "")
    say(f"answer (start):   {preview!r}")
    say(f"tokens:           input {usage.input_tokens}, output {usage.output_tokens}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
