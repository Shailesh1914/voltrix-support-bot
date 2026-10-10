"""Stage c: embedding, index, metadata and manifest (spec 01, "Output").

Builds the real kb_v1 and kb_v2 into temporary folders and checks
acceptance criteria 1, 2, 3, 4, 6 and 7 on the written files, plus
"fail loudly" (non-zero exit, message naming the file, no partial
output).
"""

import json
import re
import subprocess
import sys

import numpy as np
import pytest
from conftest import DATA_DIR, FIXTURES_DIR, REPO_ROOT

from ingestion import build
from ingestion.build import METADATA_FIELDS, build_index, main, sha256_file
from ingestion.config import (
    ARTICLE_ID_PATTERN,
    MANIFEST_FILE,
    METADATA_FILE,
    MODEL_NAME,
    MODEL_REVISION,
    VECTORS_FILE,
)
from ingestion.embedding import embed

INDEX_FILES = {VECTORS_FILE, METADATA_FILE, MANIFEST_FILE}


def read_index(folder):
    manifest = json.loads((folder / MANIFEST_FILE).read_text(encoding="utf-8"))
    lines = (folder / METADATA_FILE).read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines]
    vectors = np.load(folder / VECTORS_FILE, allow_pickle=False)
    return manifest, records, vectors


def source_articles(version):
    """{article_id: title} read straight from the files, README excluded."""
    import yaml

    result = {}
    for path in (DATA_DIR / f"kb_{version}").glob("*.md"):
        if path.name == "README.md":
            continue
        header = path.read_text(encoding="utf-8").split("---\n")[1]
        data = yaml.safe_load(header)
        result[data["article_id"]] = data["title"]
    return result


@pytest.fixture(scope="module", params=["v1", "v2"])
def built(request, tmp_path_factory, embedding_model, token_counter):
    version = request.param
    root = tmp_path_factory.mktemp(f"index_{version}")
    folder = build_index(
        DATA_DIR / f"kb_{version}", root, model=embedding_model, counter=token_counter
    )
    return version, root, folder, *read_index(folder)


# --- Output files ----------------------------------------------------------


def test_output_folder_contains_exactly_the_index_files(built):
    version, root, folder, *_ = built
    assert folder == root / version
    assert {p.name for p in folder.iterdir()} == INDEX_FILES
    assert [p.name for p in root.iterdir()] == [version]  # no temp leftovers


def test_output_folder_is_readable_by_others(built):
    _, _, folder, *_ = built
    assert folder.stat().st_mode & 0o777 == build.INDEX_DIR_MODE


def test_metadata_records_have_exactly_the_spec_fields(built):
    *_, records, _ = built
    for record in records:
        assert tuple(record) == METADATA_FIELDS
        assert all(isinstance(record[f], str) and record[f] for f in METADATA_FIELDS)


def test_metadata_sorted_by_chunk_id(built):
    *_, records, _ = built
    ids = [r["chunk_id"] for r in records]
    assert ids == sorted(ids)


def test_metadata_is_utf8_jsonl_with_lf(built):
    _, _, folder, *_ = built
    raw = (folder / METADATA_FILE).read_bytes()
    assert b"\r" not in raw and raw.endswith(b"\n")
    assert "—".encode("utf-8") in raw  # em dash kept, not —


def test_vectors_unit_length_float32_aligned_with_metadata(built, embedding_model):
    *_, records, vectors = built
    assert vectors.dtype == np.float32
    assert vectors.shape == (len(records), 384)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-4)
    # Row i is the embedding of record i's text.
    picks = [0, len(records) // 2, len(records) - 1]
    again = embed(embedding_model, [records[i]["text"] for i in picks])
    assert np.allclose(vectors[picks], again, atol=1e-5)


# --- Acceptance criteria ---------------------------------------------------


def test_criterion_1_every_article_represented(built):
    version, *_, records, _ = built
    assert {r["article_id"] for r in records} == set(source_articles(version))


def test_criterion_2_token_limits(built, token_counter):
    *_, records, _ = built
    for record in records:
        tokens = token_counter.count(record["text"])
        assert tokens <= 300 and tokens <= 512, record["chunk_id"]


def test_criterion_3_valid_article_id_from_source(built):
    version, *_, records, _ = built
    sources = source_articles(version)
    for record in records:
        assert ARTICLE_ID_PATTERN.fullmatch(record["article_id"])
        assert record["title"] == sources[record["article_id"]]
        assert record["chunk_id"].startswith(record["article_id"] + "#c")
        assert record["kb_version"] == version


def test_criterion_4_readme_never_in_index(built):
    version, *_, records, _ = built
    readme = (DATA_DIR / f"kb_{version}" / "README.md").read_text(encoding="utf-8").strip()
    assert all(readme not in r["text"] for r in records)


def test_criterion_6_chunk_ids_unique_and_gapless(built):
    *_, records, _ = built
    ids = [r["chunk_id"] for r in records]
    assert len(ids) == len(set(ids))
    numbers: dict[str, list[int]] = {}
    for chunk_id in ids:
        article_id, number = re.fullmatch(r"(KB-\d{3})#c(\d+)", chunk_id).groups()
        numbers.setdefault(article_id, []).append(int(number))
    for article_id, nums in numbers.items():
        assert sorted(nums) == list(range(1, len(nums) + 1)), article_id


def test_criterion_7_manifest_counts(built):
    version, _, _, manifest, records, vectors = built
    assert manifest["article_count"] == len(source_articles(version))
    assert manifest["article_count"] == len({r["article_id"] for r in records})
    assert manifest["chunk_count"] == len(records) == vectors.shape[0]


# --- Manifest --------------------------------------------------------------


def test_manifest_fields(built):
    version, _, folder, manifest, *_ = built
    assert manifest["kb_version"] == version
    assert manifest["model_name"] == MODEL_NAME
    assert manifest["model_revision"] == MODEL_REVISION
    assert manifest["max_chunk_tokens"] == 300
    assert manifest["max_overlap_tokens"] == 50
    assert manifest["index_file"] == VECTORS_FILE
    assert manifest["metadata_file"] == METADATA_FILE
    assert manifest["index_sha256"] == sha256_file(folder / VECTORS_FILE)
    assert manifest["metadata_sha256"] == sha256_file(folder / METADATA_FILE)
    assert set(manifest["library_versions"]) == set(build.RECORDED_LIBRARIES)


def test_manifest_has_no_timestamps(built):
    _, _, folder, manifest, *_ = built
    text = (folder / MANIFEST_FILE).read_text(encoding="utf-8")
    assert not re.search(r"\d{4}-\d{2}-\d{2}|\d{2}:\d{2}", text)
    assert not any(
        word in key.lower()
        for key in manifest
        for word in ("time", "date", "built_at", "created")
    )


# --- Fail loudly -----------------------------------------------------------


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "ingestion.build", *map(str, args)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )


def test_cli_broken_header_exits_non_zero_and_leaves_nothing(tmp_path):
    out = tmp_path / "indexes"
    result = run_cli(FIXTURES_DIR / "broken_header" / "kb_v1", "--out-root", out)
    assert result.returncode != 0
    assert "broken-header.md" in result.stderr
    assert not out.exists() or not any(out.iterdir())


def test_cli_big_table_exits_non_zero_and_leaves_nothing(tmp_path):
    out = tmp_path / "indexes"
    result = run_cli(FIXTURES_DIR / "big_table" / "kb_v1", "--out-root", out)
    assert result.returncode != 0
    assert "big-table.md" in result.stderr
    assert not out.exists() or not any(out.iterdir())


def test_cli_success_on_small_fixture(tmp_path):
    out = tmp_path / "indexes"
    result = run_cli(FIXTURES_DIR / "long_article" / "kb_v1", "--out-root", out)
    assert result.returncode == 0, result.stderr
    assert "1 articles" in result.stdout
    assert [p.name for p in out.iterdir()] == ["v1"]
    assert {p.name for p in (out / "v1").iterdir()} == INDEX_FILES


def test_main_returns_1_with_message(tmp_path, capsys):
    code = main([str(FIXTURES_DIR / "broken_header" / "kb_v1"), "--out-root", str(tmp_path)])
    assert code == 1
    assert "broken-header.md" in capsys.readouterr().err


def test_main_bad_folder_name_returns_1(tmp_path, capsys):
    code = main([str(tmp_path / "not_a_kb"), "--out-root", str(tmp_path / "out")])
    assert code == 1
    assert "not_a_kb" in capsys.readouterr().err


def _small_kb_build(root, model, counter):
    return build_index(
        FIXTURES_DIR / "long_article" / "kb_v1", root, model=model, counter=counter
    )


def test_failure_while_writing_leaves_no_partial_output(
    tmp_path, monkeypatch, embedding_model, token_counter
):
    def fail_after_vectors(folder, *args):
        np.save(folder / VECTORS_FILE, np.zeros((1, 1), dtype=np.float32))
        raise OSError("disk full (simulated)")

    monkeypatch.setattr(build, "_write_index", fail_after_vectors)
    with pytest.raises(OSError):
        _small_kb_build(tmp_path, embedding_model, token_counter)
    assert list(tmp_path.iterdir()) == []


def test_failed_rebuild_keeps_existing_index(
    tmp_path, monkeypatch, embedding_model, token_counter
):
    folder = _small_kb_build(tmp_path, embedding_model, token_counter)
    before = {p.name: p.read_bytes() for p in folder.iterdir()}

    def fail(*args):
        raise OSError("simulated")

    monkeypatch.setattr(build, "_write_index", fail)
    with pytest.raises(OSError):
        _small_kb_build(tmp_path, embedding_model, token_counter)
    assert [p.name for p in tmp_path.iterdir()] == ["v1"]
    assert {p.name: p.read_bytes() for p in folder.iterdir()} == before


def test_rebuild_replaces_existing_index(tmp_path, embedding_model, token_counter):
    folder = _small_kb_build(tmp_path, embedding_model, token_counter)
    (folder / "stray.txt").write_text("old", encoding="utf-8")
    _small_kb_build(tmp_path, embedding_model, token_counter)
    assert {p.name for p in folder.iterdir()} == INDEX_FILES
    assert [p.name for p in tmp_path.iterdir()] == ["v1"]


def test_bad_vectors_fail_before_writing(tmp_path, monkeypatch, embedding_model, token_counter):
    monkeypatch.setattr(build, "embed", lambda model, texts: np.zeros((len(texts), 384), np.float32))
    with pytest.raises(build.IngestionError, match="not unit length"):
        _small_kb_build(tmp_path, embedding_model, token_counter)
    assert list(tmp_path.iterdir()) == []
