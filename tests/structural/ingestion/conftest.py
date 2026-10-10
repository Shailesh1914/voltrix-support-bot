"""Shared helpers for the ingestion structural tests (Session I)."""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"


def article_text(
    article_id="KB-001",
    title="Test article",
    category="fault",
    kb_version="v1",
    body="# Test article\n\n## Section\n\nSome text.\n",
) -> str:
    return (
        "---\n"
        f"article_id: {article_id}\n"
        f"title: {title}\n"
        f"category: {category}\n"
        f"kb_version: {kb_version}\n"
        "---\n\n"
        f"{body}"
    )


@pytest.fixture
def make_kb(tmp_path):
    """Create a kb_<version> folder in tmp_path from {filename: text|bytes}."""

    def _make(files: dict, version: str = "v1") -> Path:
        folder = tmp_path / f"kb_{version}"
        folder.mkdir()
        for name, content in files.items():
            path = folder / name
            if isinstance(content, bytes):
                path.write_bytes(content)
            else:
                path.write_text(content, encoding="utf-8")
        return folder

    return _make
