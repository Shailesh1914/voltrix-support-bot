"""Tests of the build-time checks: check_pins.py and check_manifest.py.
No model, no network: fake index folders in tmp_path."""

import hashlib
import json
from pathlib import Path

import pytest

import check_manifest
import check_pins

REPO_ROOT = Path(__file__).resolve().parents[2]

# --- check_pins ---------------------------------------------------------------


def test_parse_pins_reads_the_real_requirements_file():
    pins = check_pins.parse_pins((REPO_ROOT / "requirements.txt").read_text(encoding="utf-8"))
    assert pins["torch"] == "2.14.1+cpu"
    assert pins["huggingface-hub"] == "1.33.0"
    assert "pytest" in pins  # Round 2 Q2: the whole file


def test_parse_pins_skips_comments_options_and_blank_lines():
    text = "--extra-index-url https://x\n\n# comment\nFoo_Bar==1.0  # why\nbaz.qux==2\n"
    assert check_pins.parse_pins(text) == {"foo-bar": "1.0", "baz-qux": "2"}


@pytest.mark.parametrize("line", ["foo>=1.0", "foo", "foo==1.0; python_version<'4'", "foo ~= 1"])
def test_parse_pins_refuses_a_loose_requirement(line):
    with pytest.raises(ValueError):
        check_pins.parse_pins(line + "\n")


def test_parse_pins_refuses_a_duplicate_and_an_empty_file():
    with pytest.raises(ValueError):
        check_pins.parse_pins("foo==1\nFoo==2\n")
    with pytest.raises(ValueError):
        check_pins.parse_pins("# nothing\n")


def test_pin_problems_names_wrong_and_missing_packages():
    installed = {"a": "1", "b": "3"}.get
    problems = check_pins.pin_problems({"a": "1", "b": "2", "c": "1"}, installed)
    assert problems == ["b: pinned 2, installed 3", "c: pinned 1, not installed"]
    assert check_pins.pin_problems({"a": "1"}, installed) == []


# --- check_manifest -------------------------------------------------------------

MODEL = "BAAI/bge-small-en-v1.5"
REVISION = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
LIBS = {"torch": "2.14.1+cpu", "numpy": "2.5.3"}


def make_index(tmp_path: Path, version: str = "v2", articles: int = 3, chunks: int = 4):
    kb = tmp_path / "data" / f"kb_{version}"
    kb.mkdir(parents=True)
    for i in range(articles):
        (kb / f"KB-{i:03}.md").write_text("x", encoding="utf-8")
    (kb / "README.md").write_text("not an article", encoding="utf-8")
    (kb / "sub").mkdir()
    (kb / "sub" / "KB-999.md").write_text("subfolders are not read", encoding="utf-8")
    index = tmp_path / "indexes" / version
    index.mkdir(parents=True)
    (index / "vectors.npy").write_bytes(b"vectors")
    (index / "chunks.jsonl").write_text("".join(f'{{"n": {i}}}\n' for i in range(chunks)), encoding="utf-8")
    manifest = {
        "kb_version": version,
        "model_name": MODEL,
        "model_revision": REVISION,
        "library_versions": dict(LIBS),
        "index_file": "vectors.npy",
        "index_sha256": hashlib.sha256(b"vectors").hexdigest(),
        "metadata_file": "chunks.jsonl",
        "metadata_sha256": hashlib.sha256((index / "chunks.jsonl").read_bytes()).hexdigest(),
        "article_count": articles,
        "chunk_count": chunks,
    }
    (index / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return index, kb, manifest


def problems(index, kb, active="v2", installed=LIBS.get):
    return check_manifest.manifest_problems(index, kb, active, MODEL, REVISION, installed)


def rewrite(index, **changes):
    manifest = json.loads((index / "manifest.json").read_text())
    manifest.update(changes)
    (index / "manifest.json").write_text(json.dumps(manifest))


def test_a_consistent_index_has_no_problems(tmp_path):
    index, kb, _ = make_index(tmp_path)
    assert problems(index, kb) == []


@pytest.mark.parametrize("field, value", [
    ("kb_version", "v1"),
    ("model_name", "other/model"),
    ("model_revision", "0" * 40),
    ("index_sha256", "0" * 64),
    ("metadata_sha256", "0" * 64),
    ("article_count", 4),
    ("chunk_count", 3),
    ("library_versions", {"torch": "2.0.0", "numpy": "2.5.3"}),
    ("library_versions", {}),
    ("index_file", "missing.npy"),
    ("metadata_file", "../chunks.jsonl"),
])
def test_each_manifest_mismatch_is_found(tmp_path, field, value):
    index, kb, _ = make_index(tmp_path)
    rewrite(index, **{field: value})
    found = problems(index, kb)
    assert found and any(field in p for p in found), found


def test_a_changed_index_file_is_found(tmp_path):
    index, kb, _ = make_index(tmp_path)
    (index / "vectors.npy").write_bytes(b"changed")
    assert any("index_sha256" in p for p in problems(index, kb))


def test_articles_counted_as_spec_01_says(tmp_path):
    """README.md and subfolders do not count."""
    kb = tmp_path / "kb_v2"
    kb.mkdir()
    for name in ("KB-001.md", "KB-002.md", "README.md", "notes.txt"):
        (kb / name).write_text("x")
    (kb / "sub").mkdir()
    (kb / "sub" / "KB-003.md").write_text("x")
    assert check_manifest.count_articles(kb) == 2


def test_not_the_active_version_is_found(tmp_path):
    index, kb, _ = make_index(tmp_path, version="v1")
    found = problems(index, kb, active="v2")
    assert any("KB folder kb_v1" in p for p in found)
    assert any("index folder v1" in p for p in found)


def test_unreadable_manifest_is_one_problem_without_its_text(tmp_path):
    index, kb, _ = make_index(tmp_path)
    (index / "manifest.json").write_text("{not json")
    assert problems(index, kb) == ["manifest.json cannot be read: JSONDecodeError"]


def test_other_index_versions_are_found(tmp_path):
    (tmp_path / "v1").mkdir()
    (tmp_path / "v2").mkdir()
    assert check_manifest.other_indexes(tmp_path, "v2") == ["v1"]
    assert check_manifest.other_indexes(tmp_path, "v1") == ["v2"]
