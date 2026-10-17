"""Retrieval contract, ingestion side (specs/03-retrieval-contract.md).

    retriever = open_retrieval("v1")
    retriever.search("drive trips on start", k=5) -> list[Chunk]
    retriever.kb_info() -> KBInfo
    retriever.article_chunks("KB-007") -> list[Chunk]

open_retrieval() runs every startup check before returning; any
failure raises RetrievalError. This module is the only code that reads
the index files.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ingestion.config import (
    DEFAULT_INDEX_ROOT,
    MANIFEST_FILE,
    METADATA_FILE,
    MODEL_NAME,
    MODEL_REVISION,
    QUERY_PREFIX,
    VECTORS_FILE,
)
from ingestion.embedding import embed, load_model
from ingestion.errors import RetrievalError
from ingestion.index_files import METADATA_FIELDS, sha256_file

MIN_K = 1
MAX_K = 20
KB_VERSION_PATTERN = re.compile(r"v[0-9]+")
REQUIRED_MANIFEST_FIELDS = (
    "kb_version",
    "model_name",
    "model_revision",
    "chunk_count",
    "index_sha256",
    "metadata_sha256",
)


@dataclass(frozen=True)
class Chunk:
    """One search result (spec 03, "Output")."""

    chunk_id: str
    article_id: str
    title: str
    text: str
    kb_version: str
    similarity_score: float


@dataclass(frozen=True)
class KBInfo:
    kb_version: str
    articles: list[tuple[str, str]]  # (article_id, title), sorted by article_id


class Retriever:
    """Search over one checked index. Create with open_retrieval()."""

    def __init__(self, kb_version: str, records: list[dict], vectors: np.ndarray, model):
        self._kb_version = kb_version
        self._records = records  # sorted by chunk_id, row i = vectors[i]
        self._vectors = vectors.astype(np.float64)
        self._model = model

    def search(self, query: str, k: int) -> list[Chunk]:
        """Top k chunks by cosine similarity; ties by chunk_id.

        The query is checked first, then embedded with QUERY_PREFIX in
        front (spec 03 v1.4). Otherwise it is used exactly as given.
        """
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be non-empty text")
        if isinstance(k, bool) or not isinstance(k, int) or not MIN_K <= k <= MAX_K:
            raise ValueError(f"k must be an integer from {MIN_K} to {MAX_K}, got {k!r}")

        query_vector = embed(self._model, [QUERY_PREFIX + query])[0].astype(np.float64)
        scores = np.clip(self._vectors @ query_vector, -1.0, 1.0)
        # Rows are in chunk_id order, so a stable sort on descending
        # score orders equal scores by chunk_id.
        order = np.argsort(-scores, kind="stable")[:k]
        return [
            Chunk(
                chunk_id=self._records[i]["chunk_id"],
                article_id=self._records[i]["article_id"],
                title=self._records[i]["title"],
                text=self._records[i]["text"],
                kb_version=self._kb_version,
                similarity_score=float(scores[i]),
            )
            for i in order
        ]

    def kb_info(self) -> KBInfo:
        titles = {r["article_id"]: r["title"] for r in self._records}
        return KBInfo(
            kb_version=self._kb_version,
            articles=sorted(titles.items()),
        )

    def article_chunks(self, article_id: str) -> list[Chunk]:
        """Every chunk of one article in chunk order c1, c2, ... (spec 03 v1.5).

        The chunks are read, not ranked, so similarity_score is 0.0.
        An unknown article_id raises ValueError.
        """
        if not isinstance(article_id, str):
            raise ValueError(f"article_id must be text, got {article_id!r}")
        records = [r for r in self._records if r["article_id"] == article_id]
        if not records:
            raise ValueError(f"unknown article_id {article_id!r} in kb_version {self._kb_version!r}")
        # Metadata is sorted by chunk_id as text ("#c10" before "#c2"),
        # so sort by the chunk number itself.
        records.sort(key=lambda r: int(r["chunk_id"].rsplit("#c", 1)[1]))
        return [
            Chunk(
                chunk_id=r["chunk_id"],
                article_id=r["article_id"],
                title=r["title"],
                text=r["text"],
                kb_version=self._kb_version,
                similarity_score=0.0,
            )
            for r in records
        ]


# --- Startup checks ---------------------------------------------------------


def _fail(folder: Path, reason: str):
    raise RetrievalError(f"cannot open retrieval index {folder}: {reason}")


def _read_manifest(folder: Path) -> dict:
    path = folder / MANIFEST_FILE
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        _fail(folder, f"{MANIFEST_FILE} cannot be read: {error}")
    if not isinstance(manifest, dict):
        _fail(folder, f"{MANIFEST_FILE} is not a JSON object")
    missing = [f for f in REQUIRED_MANIFEST_FIELDS if f not in manifest]
    if missing:
        _fail(folder, f"{MANIFEST_FILE} is missing {', '.join(missing)}")
    return manifest


def _check_hash(folder: Path, filename: str, expected: str) -> None:
    path = folder / filename
    if not path.is_file():
        _fail(folder, f"{filename} is missing")
    actual = sha256_file(path)
    if actual != expected:
        _fail(
            folder,
            f"SHA-256 of {filename} does not match the manifest "
            f"(manifest {expected}, file {actual})",
        )


def _load_records(folder: Path, kb_version: str) -> list[dict]:
    records = []
    lines = (folder / METADATA_FILE).read_text(encoding="utf-8").splitlines()
    for number, line in enumerate(lines, start=1):
        record = json.loads(line)
        if tuple(record) != METADATA_FIELDS:
            _fail(folder, f"{METADATA_FILE} line {number} has unexpected fields")
        if record["kb_version"] != kb_version:
            _fail(folder, f"{METADATA_FILE} line {number} is not kb_version {kb_version!r}")
        records.append(record)
    ids = [r["chunk_id"] for r in records]
    if ids != sorted(ids) or len(set(ids)) != len(ids):
        _fail(folder, f"{METADATA_FILE} is not sorted by unique chunk_id")
    return records


def open_retrieval(kb_version: str, *, index_root: Path | str | None = None) -> Retriever:
    """Open the index for kb_version after all startup checks.

    index_root is TEST-ONLY (spec 03 v1.1); the query side never
    passes it.
    """
    if not isinstance(kb_version, str) or not KB_VERSION_PATTERN.fullmatch(kb_version):
        raise RetrievalError(f"kb_version must look like 'v1', got {kb_version!r}")
    root = Path(index_root) if index_root is not None else DEFAULT_INDEX_ROOT
    folder = root / kb_version

    # 1. The index exists.
    if not (folder / MANIFEST_FILE).is_file():
        _fail(
            folder,
            f"no index for kb_version {kb_version!r}; build it with "
            f"'python -m ingestion.build data/kb_{kb_version}'",
        )
    manifest = _read_manifest(folder)

    # 2. The manifest is for the requested KB version.
    if manifest["kb_version"] != kb_version:
        _fail(
            folder,
            f"manifest kb_version is {manifest['kb_version']!r}, "
            f"requested {kb_version!r}",
        )

    # 3. The files are the ones the manifest describes.
    _check_hash(folder, VECTORS_FILE, manifest["index_sha256"])
    _check_hash(folder, METADATA_FILE, manifest["metadata_sha256"])

    # 4. The index was built with the model search uses.
    if (manifest["model_name"], manifest["model_revision"]) != (MODEL_NAME, MODEL_REVISION):
        _fail(
            folder,
            f"index was built with {manifest['model_name']}@"
            f"{manifest['model_revision']}, but search uses "
            f"{MODEL_NAME}@{MODEL_REVISION}; rebuild the index",
        )

    # Consistency of the (hash-verified) files with each other.
    records = _load_records(folder, kb_version)
    vectors = np.load(folder / VECTORS_FILE, allow_pickle=False)
    if vectors.ndim != 2 or vectors.shape[0] != len(records):
        _fail(folder, "vectors and metadata chunk counts differ")
    if len(records) != manifest["chunk_count"]:
        _fail(folder, "metadata and manifest chunk counts differ")

    model = load_model()
    if vectors.shape[1] != model.get_embedding_dimension():
        _fail(folder, "vector dimension does not match the embedding model")
    return Retriever(kb_version, records, vectors, model)
