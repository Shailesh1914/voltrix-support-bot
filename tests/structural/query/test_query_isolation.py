"""The query side uses ingestion only through the retrieval contract
(spec 03; CLAUDE.md hard rule 4). Static checks over query/*.py."""

import ast
import re
from pathlib import Path

import pytest

QUERY_DIR = Path(__file__).resolve().parents[3] / "query"
MODULES = sorted(QUERY_DIR.rglob("*.py"))

# The contract's entry point plus the types its functions return.
ALLOWED_FROM_INGESTION = {"open_retrieval", "Chunk", "KBInfo", "RetrievalError"}

# Index, metadata, manifest and knowledge-base file and folder names.
FORBIDDEN = re.compile(r"indexes|chunks\.jsonl|vectors\.npy|manifest\.json|kb_v[0-9]|data/")


def test_there_are_modules_to_check():
    assert len(MODULES) >= 5


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.name)
def test_only_contract_imports_from_ingestion(path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            assert not any(a.name.split(".")[0] == "ingestion" for a in node.names), (
                f"{path.name}:{node.lineno} uses 'import ingestion...'"
            )
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "ingestion":
            assert node.module == "ingestion", f"{path.name}:{node.lineno} imports {node.module}"
            names = {a.name for a in node.names}
            assert names <= ALLOWED_FROM_INGESTION, f"{path.name}:{node.lineno} imports {names}"


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.name)
def test_no_index_or_kb_file_names(path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            found = FORBIDDEN.search(node.value)
            assert not found, f"{path.name}:{node.lineno} mentions {found.group(0)!r}"
