"""The query side uses ingestion only through the retrieval contract
(spec 03; CLAUDE.md hard rule 4). Static checks over query/*.py."""

import ast
import re
from pathlib import Path

import pytest

QUERY_DIR = Path(__file__).resolve().parents[3] / "query"
MODULES = sorted(QUERY_DIR.rglob("*.py"))

SPEC_03 = Path(__file__).resolve().parents[3] / "specs" / "03-retrieval-contract.md"


def contract_public_names() -> set[str]:
    """The names listed in spec 03: "The contract's public names are: ..."."""
    text = " ".join(SPEC_03.read_text(encoding="utf-8").split())
    match = re.search(r"The contract's public names are: (.+?)\. ", text)
    assert match, "spec 03 must list the contract's public names"
    names = {n.strip() for n in re.split(r",| and ", match.group(1))}
    assert all(n.isidentifier() for n in names), names
    return names


ALLOWED_FROM_INGESTION = contract_public_names()

# Index, metadata, manifest and knowledge-base file and folder names.
# The one exception is the active-version pointer data/ACTIVE_KB_VERSION,
# which spec 07 tells the query side to read (it is not an index,
# metadata or manifest file).
FORBIDDEN = re.compile(r"indexes|chunks\.jsonl|vectors\.npy|manifest\.json|kb_v[0-9]|data/(?!ACTIVE_KB_VERSION(?![\w.]))")
POINTER_NAME = "ACTIVE_KB_VERSION"


def test_contract_names_read_from_spec_03():
    assert ALLOWED_FROM_INGESTION == {"open_retrieval", "Retriever", "Chunk", "KBInfo", "RetrievalError"}


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


@pytest.mark.parametrize("text", ["indexes/v1", "data/kb_v1", "data/", "data/ACTIVE_KB_VERSION.bak", "manifest.json"])
def test_forbidden_names_still_caught(text):
    assert FORBIDDEN.search(text)


def test_pointer_mention_allowed():
    assert not FORBIDDEN.search("read from data/ACTIVE_KB_VERSION (spec 07)")


def test_only_config_names_the_pointer_file():
    # Spec 07: the pointer path is built in query/config.py only.
    for path in MODULES:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and node.value == POINTER_NAME:
                assert path.name == "config.py", f"{path.name}:{node.lineno} names {POINTER_NAME!r}"
