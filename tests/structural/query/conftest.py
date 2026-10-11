"""Shared fixtures for the query structural tests (Session Q).

Helpers are fixtures, not importable names, so this conftest never
clashes with the ingestion one when both suites run together.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def spec_02_text() -> str:
    return (REPO_ROOT / "specs" / "02-query-escalation-spec.md").read_text(encoding="utf-8")


@pytest.fixture
def query_dir() -> Path:
    return REPO_ROOT / "query"
