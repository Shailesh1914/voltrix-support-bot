"""The web layer only wraps the flow (spec 08 section 4.2; CLAUDE.md
rules 4 and 5). Static checks over web/*.py."""

import ast
import re
from pathlib import Path

import pytest

WEB_DIR = Path(__file__).resolve().parents[3] / "web"
MODULES = sorted(WEB_DIR.rglob("*.py"))
ALL_FILES = sorted(p for p in WEB_DIR.rglob("*") if p.is_file() and "__pycache__" not in p.parts)

CONTRACT_NAMES = {"open_retrieval", "Retriever", "Chunk", "KBInfo", "RetrievalError"}
FORBIDDEN_FILES = re.compile(r"indexes|chunks\.jsonl|vectors\.npy|manifest\.json|kb_v[0-9]|ACTIVE_KB_VERSION")
# Behaviour lives in query/: the web layer imports none of it.
BEHAVIOUR_MODULES = {"query.prompt", "query.checks", "query.retrieval", "query.masking", "query.normalise", "query.fault_codes", "query.generator"}


def imports(path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, set()
        elif isinstance(node, ast.ImportFrom):
            yield node.module or "", {a.name for a in node.names}


def test_there_are_modules_to_check():
    assert {p.name for p in MODULES} >= {"app.py", "startup.py", "secret_source.py", "__main__.py"}


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.name)
def test_only_contract_names_from_ingestion(path):
    for module, names in imports(path):
        if module.split(".")[0] == "ingestion":
            assert module == "ingestion" and names <= CONTRACT_NAMES, f"{path.name}: {module} {names}"


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.name)
def test_no_behaviour_modules_imported(path):
    for module, _ in imports(path):
        assert module not in BEHAVIOUR_MODULES, f"{path.name} imports {module}"


FORBIDDEN_WORDS = ("threshold", "system_prompt", "temperature", "similarity_score", "prompt")


def code_names(tree):
    """Every name the code uses (not docstrings or comments)."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            yield node.id
        elif isinstance(node, ast.Attribute):
            yield node.attr
        elif isinstance(node, ast.alias):
            yield node.name
        elif isinstance(node, ast.keyword) and node.arg:
            yield node.arg
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield node.name


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.name)
def test_no_threshold_prompt_or_index_files_in_code(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for name in code_names(tree):
        assert not any(w in name.lower() for w in FORBIDDEN_WORDS), f"{path.name} uses {name}"
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert not FORBIDDEN_FILES.search(node.value), f"{path.name}:{node.lineno} {node.value!r}"


@pytest.mark.parametrize("path", ALL_FILES, ids=lambda p: p.name)
def test_threshold_setting_never_named(path):
    assert "ESCALATION_THRESHOLD" not in path.read_text(encoding="utf-8"), path.name


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.name)
def test_flow_never_built_by_the_web_layer(path):
    # Only query.ask.build_flow() builds it, as for the command line bot.
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"QueryFlow", "open_retrieval", "JsonlHandoffStore"}, path.name
