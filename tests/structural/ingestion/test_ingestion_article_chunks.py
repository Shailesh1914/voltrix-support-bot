"""Retriever.article_chunks (specs/03-retrieval-contract.md v1.5, Function 3).

Contract test 13. Expected values come from the spec 03 text and from
the stored metadata file (chunks.jsonl), never from the code under test.
Indexes are built from the real kb_v1 and kb_v2 into a temporary
folder; the real indexes/ folder is only read, and checked unchanged.
"""

import json
import re

import pytest
from conftest import DATA_DIR, REPO_ROOT, article_text

from ingestion import Chunk, open_retrieval
from ingestion.build import build_index
from ingestion.config import MANIFEST_FILE, METADATA_FILE, VECTORS_FILE
from ingestion.index_files import sha256_file

SPEC_03 = REPO_ROOT / "specs" / "03-retrieval-contract.md"
INDEX_FILES = (VECTORS_FILE, METADATA_FILE, MANIFEST_FILE)
FIELD_TYPES = {
    "chunk_id": str,
    "article_id": str,
    "title": str,
    "text": str,
    "kb_version": str,
    "similarity_score": float,
}


def spec_function_3() -> str:
    text = SPEC_03.read_text(encoding="utf-8")
    match = re.search(r"## Function 3: article_chunks\n(.*?)\n## ", text, re.S)
    assert match, "spec 03 must have a 'Function 3: article_chunks' section"
    return match.group(1)


def spec_score() -> float:
    """The fixed similarity_score that spec 03 Function 3 states."""
    found = re.findall(r"similarity_score is ([0-9.]+)", spec_function_3())
    assert len(found) == 1, f"spec 03 Function 3 must state the score once, found {found}"
    return float(found[0])


def stored_records(root, version):
    lines = (root / version / METADATA_FILE).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def stored_by_article(root, version) -> dict[str, dict[str, dict]]:
    """{article_id: {chunk_id: record}} straight from chunks.jsonl."""
    articles: dict[str, dict[str, dict]] = {}
    for record in stored_records(root, version):
        articles.setdefault(record["article_id"], {})[record["chunk_id"]] = record
    return articles


def expected_ids(article_id: str, count: int) -> list[str]:
    """Chunk order c1, c2, ... (spec 03 Function 3; ID format from spec 01)."""
    return [f"{article_id}#c{n}" for n in range(1, count + 1)]


def file_hashes(folder):
    return {name: sha256_file(folder / name) for name in INDEX_FILES}


@pytest.fixture(scope="module")
def index_root(tmp_path_factory, embedding_model, token_counter):
    root = tmp_path_factory.mktemp("indexes")
    for version in ("v1", "v2"):
        build_index(
            DATA_DIR / f"kb_{version}", root, model=embedding_model, counter=token_counter
        )
    return root


@pytest.fixture(scope="module")
def retrievers(index_root):
    return {v: open_retrieval(v, index_root=index_root) for v in ("v1", "v2")}


@pytest.fixture(scope="module")
def long_index(tmp_path_factory, embedding_model, token_counter):
    """A synthetic article with 11 sections, so chunk numbers pass c9."""
    sections = "".join(f"## Section {n}\n\nBody text of section {n}.\n\n" for n in range(1, 12))
    kb = tmp_path_factory.mktemp("kb") / "kb_v1"
    kb.mkdir()
    (kb / "long.md").write_text(
        article_text(article_id="KB-900", title="Eleven sections", body=f"# Eleven sections\n\n{sections}"),
        encoding="utf-8",
    )
    (kb / "short.md").write_text(article_text(article_id="KB-901"), encoding="utf-8")
    root = tmp_path_factory.mktemp("long_indexes")
    build_index(kb, root, model=embedding_model, counter=token_counter)
    return root


# --- The spec text this file tests against ----------------------------------


def test_spec_03_states_score_zero():
    assert spec_score() == 0.0


# --- Contract test 13: every chunk, in order, text as stored ----------------


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_contract_13_every_article_every_chunk_in_order(retrievers, index_root, version):
    stored = stored_by_article(index_root, version)
    for article_id, records in stored.items():
        chunks = retrievers[version].article_chunks(article_id)
        assert [c.chunk_id for c in chunks] == expected_ids(article_id, len(records)), article_id


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_contract_13_text_exactly_as_stored(retrievers, index_root, version):
    stored = stored_by_article(index_root, version)
    for article_id, records in stored.items():
        for chunk in retrievers[version].article_chunks(article_id):
            record = records[chunk.chunk_id]
            assert (chunk.article_id, chunk.title, chunk.text) == (
                record["article_id"], record["title"], record["text"]
            ), chunk.chunk_id


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_contract_13_all_chunks_of_the_index_covered(retrievers, index_root, version):
    returned = [
        c.chunk_id
        for article_id in stored_by_article(index_root, version)
        for c in retrievers[version].article_chunks(article_id)
    ]
    assert sorted(returned) == sorted(r["chunk_id"] for r in stored_records(index_root, version))


def test_contract_13_chunk_order_is_numeric_past_c9(long_index):
    retriever = open_retrieval("v1", index_root=long_index)
    chunks = retriever.article_chunks("KB-900")
    assert [c.chunk_id for c in chunks] == expected_ids("KB-900", 11)
    stored = stored_by_article(long_index, "v1")["KB-900"]
    assert [c.text for c in chunks] == [stored[c.chunk_id]["text"] for c in chunks]
    assert chunks[-1].text.startswith("Eleven sections — Section 11")


def test_contract_13_last_chunk_included(retrievers, index_root):
    stored = stored_by_article(index_root, "v1")
    article_id = max(stored, key=lambda a: len(stored[a]))
    chunks = retrievers["v1"].article_chunks(article_id)
    assert chunks[-1].chunk_id == f"{article_id}#c{len(stored[article_id])}"


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_six_fields_kb_version_and_score(retrievers, index_root, version):
    for article_id in stored_by_article(index_root, version):
        for chunk in retrievers[version].article_chunks(article_id):
            assert isinstance(chunk, Chunk)
            assert set(vars(chunk)) == set(FIELD_TYPES)
            for field, kind in FIELD_TYPES.items():
                assert type(getattr(chunk, field)) is kind, field
            assert chunk.kb_version == version
            assert chunk.similarity_score == spec_score()


# --- Contract test 13: unknown article_id raises -----------------------------


@pytest.mark.parametrize(
    "article_id",
    ["KB-999", "", "kb-001", "KB-001 ", "KB-00", "KB-001#c1", "KB-0011", None, 1],
)
def test_contract_13_unknown_article_id_raises(retrievers, article_id):
    with pytest.raises(ValueError):
        retrievers["v1"].article_chunks(article_id)


def test_article_only_in_other_kb_version_raises(retrievers, index_root):
    only_v2 = set(stored_by_article(index_root, "v2")) - set(stored_by_article(index_root, "v1"))
    assert only_v2, "kb_v2 is expected to have articles that kb_v1 lacks"
    for article_id in sorted(only_v2):
        assert retrievers["v2"].article_chunks(article_id)
        with pytest.raises(ValueError):
            retrievers["v1"].article_chunks(article_id)


# --- Read-only ---------------------------------------------------------------


def test_read_only_files_unchanged(index_root, tmp_path):
    before = {v: file_hashes(index_root / v) for v in ("v1", "v2")}
    retriever = open_retrieval("v1", index_root=index_root)
    for article_id in stored_by_article(index_root, "v1"):
        retriever.article_chunks(article_id)
    with pytest.raises(ValueError):
        retriever.article_chunks("KB-999")
    assert {v: file_hashes(index_root / v) for v in ("v1", "v2")} == before


def test_read_only_state_unchanged(index_root):
    retriever = open_retrieval("v1", index_root=index_root)
    query = "drive trips with overcurrent when accelerating"
    search_before = retriever.search(query, 20)
    info_before = retriever.kb_info()
    article_id = search_before[0].article_id
    first = retriever.article_chunks(article_id)
    first.clear()  # changing the returned list must not affect the retriever
    second = retriever.article_chunks(article_id)
    assert second == retriever.article_chunks(article_id)
    assert len(second) == len(stored_by_article(index_root, "v1")[article_id])
    assert retriever.search(query, 20) == search_before
    assert retriever.kb_info() == info_before


def test_real_index_read_only():
    """On the real indexes/ folder: hashes unchanged after article_chunks."""
    root = REPO_ROOT / "indexes"
    if not (root / "v1" / MANIFEST_FILE).is_file():
        pytest.skip("real index not built")
    before = file_hashes(root / "v1")
    retriever = open_retrieval("v1")
    stored = stored_by_article(root, "v1")
    for article_id, records in stored.items():
        chunks = retriever.article_chunks(article_id)
        assert [c.chunk_id for c in chunks] == expected_ids(article_id, len(records))
        assert [c.text for c in chunks] == [records[c.chunk_id]["text"] for c in chunks]
    assert file_hashes(root / "v1") == before
