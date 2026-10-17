"""Stage d: retrieval contract (specs/03-retrieval-contract.md v1.4).

Contract tests 1-12 are marked with their number. Indexes are built
from the real kb_v1 and kb_v2 into a temporary folder; tamper tests
work on copies. The query prefix tests take the expected prefix from
the spec 03 text, never from QUERY_PREFIX.
"""

import json
import re
import shutil
import subprocess
import sys

import numpy as np
import pytest
from conftest import REPO_ROOT, DATA_DIR, article_text

from ingestion import Chunk, KBInfo, RetrievalError, open_retrieval
from ingestion.build import build_index
from ingestion.config import MANIFEST_FILE, METADATA_FILE, MODEL_NAME, VECTORS_FILE
from ingestion.index_files import sha256_file

SPEC_03 = REPO_ROOT / "specs" / "03-retrieval-contract.md"

QUERIES = [
    "drive trips with overcurrent when accelerating",
    "how long to wait for the DC bus to discharge",
    "E-07",
    "what is the price of a spare cooling fan",
]
FIELD_TYPES = {
    "chunk_id": str,
    "article_id": str,
    "title": str,
    "text": str,
    "kb_version": str,
    "similarity_score": float,
}


@pytest.fixture(scope="module")
def index_root(tmp_path_factory, embedding_model, token_counter):
    root = tmp_path_factory.mktemp("indexes")
    for version in ("v1", "v2"):
        build_index(
            DATA_DIR / f"kb_{version}", root, model=embedding_model, counter=token_counter
        )
    return root


@pytest.fixture(scope="module")
def retriever(index_root):
    return open_retrieval("v1", index_root=index_root)


@pytest.fixture
def index_copy(index_root, tmp_path):
    """A writable copy of the v1 index, for tamper tests."""
    shutil.copytree(index_root / "v1", tmp_path / "v1")
    return tmp_path


def edit_manifest(root, **changes):
    path = root / "v1" / MANIFEST_FILE
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest.update(changes)
    path.write_text(json.dumps(manifest), encoding="utf-8")


def as_tuples(results):
    return [
        (c.chunk_id, c.article_id, c.title, c.text, c.kb_version, c.similarity_score)
        for c in results
    ]


def spec_query_prefix() -> str:
    """The quoted BGE prefix in spec 03, exactly as written."""
    text = SPEC_03.read_text(encoding="utf-8")
    found = re.findall(r'BGE retrieval prefix\s+"([^"\n]*)"', text)
    assert len(found) == 1, f"spec 03 must quote the BGE prefix once, found {found}"
    return found[0]


def metadata_records(root, version):
    lines = (root / version / METADATA_FILE).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


# --- search ----------------------------------------------------------------


@pytest.mark.parametrize("query", QUERIES)
def test_contract_1_six_fields_with_correct_types(retriever, query):
    results = retriever.search(query, 5)
    assert results
    for chunk in results:
        assert isinstance(chunk, Chunk)
        assert set(vars(chunk)) == set(FIELD_TYPES)
        for field, kind in FIELD_TYPES.items():
            assert type(getattr(chunk, field)) is kind, field


def test_contract_1_text_exactly_as_stored(retriever, index_root):
    stored = {r["chunk_id"]: r for r in metadata_records(index_root, "v1")}
    for chunk in retriever.search(QUERIES[0], 20):
        record = stored[chunk.chunk_id]
        assert (chunk.text, chunk.title, chunk.article_id) == (
            record["text"], record["title"], record["article_id"]
        )


@pytest.mark.parametrize("query", QUERIES)
def test_contract_2_sorted_by_score_then_chunk_id(retriever, query):
    results = retriever.search(query, 20)
    keys = [(-c.similarity_score, c.chunk_id) for c in results]
    assert keys == sorted(keys)


def test_contract_2_equal_scores_ordered_by_chunk_id(embedding_model):
    # Exact ties need bit-identical vectors. Embedding the same text at
    # different batch positions differs by ~1e-8, so the rows are set
    # directly: KB-002#c1, KB-003#c1 and KB-010#c1 share one vector.
    from ingestion.embedding import embed
    from ingestion.retrieval import Retriever

    tie, other = embed(embedding_model, ["identical text", "something else"])
    ids = ["KB-001#c1", "KB-002#c1", "KB-003#c1", "KB-010#c1", "KB-011#c1"]
    rows = [other, tie, tie, tie, other]
    records = [
        {"chunk_id": i, "article_id": i[:6], "title": "T", "text": "x",
         "category": "fault", "kb_version": "v1"}
        for i in ids
    ]
    retriever = Retriever("v1", records, np.stack(rows), embedding_model)
    results = retriever.search("identical text", 5)
    assert [c.chunk_id for c in results[:3]] == ["KB-002#c1", "KB-003#c1", "KB-010#c1"]
    assert len({c.similarity_score for c in results[:3]}) == 1
    assert [c.chunk_id for c in results[3:]] == ["KB-001#c1", "KB-011#c1"]


@pytest.mark.parametrize("k", [1, 2, 5, 20])
def test_contract_3_at_most_k_results(retriever, k):
    assert len(retriever.search(QUERIES[1], k)) == k


def test_contract_3_fewer_only_if_index_is_smaller(make_kb, tmp_path, embedding_model, token_counter):
    folder = make_kb({"a.md": article_text(body="# T\n\n## A\n\nOne.\n\n## B\n\nTwo.\n")})
    build_index(folder, tmp_path / "idx", model=embedding_model, counter=token_counter)
    assert len(open_retrieval("v1", index_root=tmp_path / "idx").search("one", 20)) == 2


@pytest.mark.parametrize("query", QUERIES + ["zzzz qqqq", "¿Qué pasa? 🚀"])
def test_contract_4_scores_within_range(retriever, query):
    for chunk in retriever.search(query, 20):
        assert -1.0 <= chunk.similarity_score <= 1.0


def test_contract_4_scores_are_capped(index_copy, monkeypatch):
    # Exactly-duplicated unit vectors can round to just above 1.0.
    retriever = open_retrieval("v1", index_root=index_copy)
    monkeypatch.setattr(retriever, "_vectors", retriever._vectors * 1.5)
    scores = [c.similarity_score for c in retriever.search(QUERIES[0], 20)]
    assert max(scores) <= 1.0 and min(scores) >= -1.0


def test_contract_4_scores_are_cosine_similarity(retriever, embedding_model, index_root):
    # Cosine similarity with the PREFIXED query (spec 03 v1.3).
    from ingestion.embedding import embed

    vectors = np.load(index_root / "v1" / VECTORS_FILE)
    ids = [r["chunk_id"] for r in metadata_records(index_root, "v1")]
    prefixed, bare = embed(embedding_model, [spec_query_prefix() + QUERIES[0], QUERIES[0]])
    for chunk in retriever.search(QUERIES[0], 5):
        row = vectors[ids.index(chunk.chunk_id)]
        assert chunk.similarity_score == pytest.approx(float(row @ prefixed), abs=1e-5)
        assert abs(chunk.similarity_score - float(row @ bare)) > 1e-4


def test_contract_5_same_query_same_results_within_run(retriever):
    for query in QUERIES:
        assert as_tuples(retriever.search(query, 20)) == as_tuples(retriever.search(query, 20))


def test_contract_5_same_results_across_process_restarts(retriever, index_root):
    script = (
        "import json, sys\n"
        "from ingestion import open_retrieval\n"
        "r = open_retrieval('v1', index_root=sys.argv[1])\n"
        "queries = json.loads(sys.argv[2])\n"
        "out = [[[c.chunk_id, c.article_id, c.title, c.text, c.kb_version,"
        " c.similarity_score.hex()] for c in r.search(q, 20)] for q in queries]\n"
        "print(json.dumps(out))\n"
    )
    runs = []
    for _ in range(2):
        result = subprocess.run(
            [sys.executable, "-c", script, str(index_root), json.dumps(QUERIES)],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=600,
        )
        assert result.returncode == 0, result.stderr
        runs.append(json.loads(result.stdout.strip().splitlines()[-1]))
    here = [
        [[*t[:5], t[5].hex()] for t in as_tuples(retriever.search(q, 20))]
        for q in QUERIES
    ]
    assert runs[0] == runs[1] == here


def test_contract_6_kb_version_matches_requested(index_root):
    for version in ("v1", "v2"):
        retriever = open_retrieval(version, index_root=index_root)
        for query in QUERIES:
            assert {c.kb_version for c in retriever.search(query, 20)} == {version}


def test_contract_6_searches_only_the_requested_index(retriever, index_root):
    # E-17 exists only in kb_v2 (KB-037).
    query = "E-17 Motor underload (loss of load)"
    v2 = open_retrieval("v2", index_root=index_root).search(query, 1)
    assert v2[0].article_id == "KB-037"
    assert all(c.article_id != "KB-037" for c in retriever.search(query, 20))


@pytest.mark.parametrize(
    "query,k",
    [
        ("", 5), ("   \n\t", 5), (None, 5), (42, 5),
        ("ok", 0), ("ok", 21), ("ok", -1), ("ok", 5.0), ("ok", "5"),
        ("ok", True), ("ok", None),
    ],
)
def test_contract_7_invalid_input_raises(retriever, query, k):
    with pytest.raises(ValueError):
        retriever.search(query, k)


def test_query_used_exactly_as_given(retriever):
    # No normalisation in search, only the fixed prefix: different
    # spellings, different vectors.
    a = retriever.search("E1 fault", 1)[0].similarity_score
    b = retriever.search("E-01 fault", 1)[0].similarity_score
    assert a != b


# --- Query prefix (spec 03 v1.3-v1.4) ------------------------------------------


def test_query_prefix_constant_equals_spec_text():
    from ingestion.config import QUERY_PREFIX

    assert QUERY_PREFIX == spec_query_prefix()


@pytest.mark.parametrize("query", QUERIES)
def test_query_is_embedded_once_with_spec_prefix(retriever, monkeypatch, query):
    from ingestion import retrieval

    calls = []
    real_embed = retrieval.embed

    def spy(model, texts):
        calls.append(list(texts))
        return real_embed(model, texts)

    monkeypatch.setattr(retrieval, "embed", spy)
    retriever.search(query, 5)
    assert calls == [[spec_query_prefix() + query]]


def test_chunks_are_embedded_without_prefix(index_root, embedding_model):
    from ingestion.embedding import embed

    texts = [r["text"] for r in metadata_records(index_root, "v1")]
    stored = np.load(index_root / "v1" / VECTORS_FILE)
    bare = embed(embedding_model, texts)
    prefixed = embed(embedding_model, [spec_query_prefix() + t for t in texts])
    np.testing.assert_allclose(stored, bare, atol=1e-5)
    assert np.all(np.abs(stored - prefixed).max(axis=1) > 1e-3)


def test_build_does_not_depend_on_query_prefix(tmp_path, monkeypatch, embedding_model, token_counter):
    # Same index bytes whatever the prefix is, so the index never needs
    # rebuilding for a prefix change. Patch every ingestion module's copy.
    import sys as _sys

    kb_folder = DATA_DIR / "kb_v1"
    names = (VECTORS_FILE, METADATA_FILE, MANIFEST_FILE)
    normal = build_index(kb_folder, tmp_path / "a", model=embedding_model, counter=token_counter)
    patched_modules = [
        m for name, m in list(_sys.modules.items())
        if name.startswith("ingestion") and hasattr(m, "QUERY_PREFIX")
    ]
    assert patched_modules
    for module in patched_modules:
        monkeypatch.setattr(module, "QUERY_PREFIX", "something completely different: ")
    patched = build_index(kb_folder, tmp_path / "b", model=embedding_model, counter=token_counter)
    assert {n: sha256_file(normal / n) for n in names} == {
        n: sha256_file(patched / n) for n in names
    }


def test_empty_query_checked_before_prefix(retriever, monkeypatch):
    from ingestion import retrieval

    monkeypatch.setattr(retrieval, "embed", lambda *a: pytest.fail("embed called"))
    for query in ("", "   \n\t"):
        with pytest.raises(ValueError, match="non-empty"):
            retriever.search(query, 5)


# --- kb_info -----------------------------------------------------------------


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_contract_9_kb_info_every_article_sorted(index_root, version):
    info = open_retrieval(version, index_root=index_root).kb_info()
    records = metadata_records(index_root, version)
    expected = sorted({(r["article_id"], r["title"]) for r in records})
    assert isinstance(info, KBInfo)
    assert info.kb_version == version
    assert info.articles == expected
    assert [a for a, _ in info.articles] == sorted(a for a, _ in info.articles)
    assert all(type(a) is str and type(t) is str for a, t in info.articles)


def test_kb_info_is_read_only(retriever):
    info = retriever.kb_info()
    info.articles.clear()
    assert retriever.kb_info().articles  # caller cannot change the index
    with pytest.raises(AttributeError):
        info.kb_version = "v9"


def test_kb_info_titles_include_fault_codes(retriever):
    titles = [t for _, t in retriever.kb_info().articles]
    assert any(t.startswith("E-01 ") for t in titles)


# --- Startup checks ----------------------------------------------------------


def test_contract_8_model_revision_mismatch_fails(index_copy):
    edit_manifest(index_copy, model_revision="0" * 40)
    with pytest.raises(RetrievalError, match="rebuild the index"):
        open_retrieval("v1", index_root=index_copy)


def test_contract_8_model_name_mismatch_fails(index_copy):
    edit_manifest(index_copy, model_name="BAAI/bge-base-en-v1.5")
    with pytest.raises(RetrievalError, match="bge-base-en-v1.5"):
        open_retrieval("v1", index_root=index_copy)


def test_contract_10_missing_index_fails(index_root, tmp_path):
    with pytest.raises(RetrievalError, match="no index for kb_version 'v3'"):
        open_retrieval("v3", index_root=index_root)
    with pytest.raises(RetrievalError, match="no index"):
        open_retrieval("v1", index_root=tmp_path / "nowhere")


def test_contract_10_missing_manifest_fails(index_copy):
    (index_copy / "v1" / MANIFEST_FILE).unlink()
    with pytest.raises(RetrievalError, match="no index"):
        open_retrieval("v1", index_root=index_copy)


def test_contract_11_manifest_kb_version_mismatch_fails(index_copy):
    edit_manifest(index_copy, kb_version="v2")
    with pytest.raises(RetrievalError, match="manifest kb_version is 'v2'"):
        open_retrieval("v1", index_root=index_copy)


def test_contract_11_index_in_wrong_folder_fails(index_root, tmp_path):
    shutil.copytree(index_root / "v2", tmp_path / "v1")
    with pytest.raises(RetrievalError, match="manifest kb_version"):
        open_retrieval("v1", index_root=tmp_path)


@pytest.mark.parametrize("filename", [VECTORS_FILE, METADATA_FILE])
def test_contract_12_changed_file_fails_hash_check(index_copy, filename):
    path = index_copy / "v1" / filename
    data = bytearray(path.read_bytes())
    data[-2] ^= 0x01  # flip one bit
    path.write_bytes(bytes(data))
    with pytest.raises(RetrievalError, match=f"SHA-256 of {filename}"):
        open_retrieval("v1", index_root=index_copy)


@pytest.mark.parametrize("field", ["index_sha256", "metadata_sha256"])
def test_contract_12_wrong_manifest_hash_fails(index_copy, field):
    edit_manifest(index_copy, **{field: "f" * 64})
    with pytest.raises(RetrievalError, match="SHA-256"):
        open_retrieval("v1", index_root=index_copy)


@pytest.mark.parametrize("filename", [VECTORS_FILE, METADATA_FILE])
def test_missing_index_file_fails(index_copy, filename):
    (index_copy / "v1" / filename).unlink()
    with pytest.raises(RetrievalError, match=f"{filename} is missing"):
        open_retrieval("v1", index_root=index_copy)


def test_unreadable_manifest_fails(index_copy):
    (index_copy / "v1" / MANIFEST_FILE).write_text("{not json", encoding="utf-8")
    with pytest.raises(RetrievalError, match="cannot be read"):
        open_retrieval("v1", index_root=index_copy)


def test_manifest_missing_field_fails(index_copy):
    path = index_copy / "v1" / MANIFEST_FILE
    manifest = json.loads(path.read_text(encoding="utf-8"))
    del manifest["model_revision"]
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(RetrievalError, match="missing model_revision"):
        open_retrieval("v1", index_root=index_copy)


def test_manifest_chunk_count_mismatch_fails(index_copy):
    edit_manifest(index_copy, chunk_count=1)
    with pytest.raises(RetrievalError, match="chunk counts differ"):
        open_retrieval("v1", index_root=index_copy)


@pytest.mark.parametrize("version", ["", "1", "V1", "../v1", "v1/..", None, 1])
def test_bad_kb_version_argument_fails(index_root, version):
    with pytest.raises(RetrievalError, match="kb_version must look like"):
        open_retrieval(version, index_root=index_root)


def test_default_index_root_is_repo_indexes(monkeypatch, tmp_path):
    from ingestion import retrieval

    monkeypatch.setattr(retrieval, "DEFAULT_INDEX_ROOT", tmp_path)
    with pytest.raises(RetrievalError, match=str(tmp_path / "v1")):
        open_retrieval("v1")


def test_model_name_constant_is_bge_small():
    assert MODEL_NAME == "BAAI/bge-small-en-v1.5"
