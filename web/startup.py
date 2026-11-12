"""Build the web app once at start-up (spec 08 sections 4 and 5).

The flow is built by query/ask.build_flow(), exactly as the command line
bot builds it: threshold check, settings (incl. HANDOFF_DIR), then the
key, then the index. Only the generator's key source differs: the web
app reads both secrets from where VOLTRIX_SECRETS_SOURCE says, once, and
keeps them in memory.

Any problem stops the start-up with a ConfigError (or RetrievalError)
that names the setting, never its value.
"""

import os
from collections.abc import Callable, Mapping
from pathlib import Path

from fastapi import FastAPI

from query import ask
from query.anthropic_api import SECRETS_PATH, AnthropicGenerator, make_client
from query.config import Settings
from query.flow import QueryFlow
from web.app import create_app
from web.secret_source import default_ssm_client, load_secrets

IMAGE_TAG_NAME = "IMAGE_TAG"
LOCAL_IMAGE_TAG = "local"


def image_tag(environ: Mapping[str, str]) -> str:
    return environ.get(IMAGE_TAG_NAME, "").strip() or LOCAL_IMAGE_TAG


def build_app(
    environ: Mapping[str, str] | None = None,
    secrets_path: Path = SECRETS_PATH,
    ssm_client_factory: Callable[[], object] = default_ssm_client,
    build_flow: Callable[..., QueryFlow] | None = None,
) -> FastAPI:
    """environ defaults to os.environ; build_flow to query.ask.build_flow
    (looked up at call time). Both are for tests only."""
    environ = os.environ if environ is None else environ
    build_flow = build_flow or ask.build_flow
    loaded: dict[str, object] = {}

    def make_generator(settings: Settings) -> AnthropicGenerator:
        secrets = load_secrets(environ, secrets_path, ssm_client_factory)
        loaded["settings"] = settings
        loaded["access_code"] = secrets.access_code
        return AnthropicGenerator(make_client(secrets.anthropic_key))

    flow = build_flow(make_generator)
    settings: Settings = loaded["settings"]
    return create_app(
        flow,
        access_code=loaded["access_code"],
        kb_version=settings.active_kb_version,
        image_tag=image_tag(environ),
    )
