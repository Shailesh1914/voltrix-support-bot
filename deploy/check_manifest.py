"""Build-time check of the active KB index in the image (spec 08 section 6:
"its manifest is checked"; spec 01 "Output").

Usage (inside the image build, after python -m ingestion.build):
    python deploy/check_manifest.py data/kb_v2

Checks, independently of the ingestion code where possible:
- the folder is the active version in data/ACTIVE_KB_VERSION, and it is
  the only index in indexes/ (only the active version goes in the image);
- kb_version, model name and revision equal ingestion/config.py;
- library_versions equal the installed packages;
- index and metadata SHA-256 equal the files' own hashes;
- article_count equals the *.md files in the KB folder except README.md;
- chunk_count equals the lines of the metadata file;
then opens the index through the retrieval contract (open_retrieval),
which runs its own start-up checks.

Exit 0 if all pass, 1 with one line per problem otherwise.
"""

import hashlib
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INDEX_ROOT = REPO_ROOT / "indexes"
MANIFEST_FILE = "manifest.json"
EXCLUDED = "README.md"
KB_FOLDER = re.compile(r"kb_(v[0-9]+)")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def count_articles(kb_folder: Path) -> int:
    """Spec 01: *.md files directly in the folder, README.md excluded."""
    return sum(1 for p in kb_folder.glob("*.md") if p.is_file() and p.name != EXCLUDED)


def count_lines(path: Path) -> int:
    with path.open("rb") as handle:
        return sum(1 for line in handle if line.strip())


def manifest_problems(
    index_dir: Path,
    kb_folder: Path,
    active_version: str,
    model_name: str,
    model_revision: str,
    installed: Callable[[str], str | None],
) -> list[str]:
    problems: list[str] = []
    match = KB_FOLDER.fullmatch(kb_folder.name)
    if not match or match.group(1) != active_version:
        problems.append(f"KB folder {kb_folder.name} is not the active version {active_version}")
    if index_dir.name != active_version:
        problems.append(f"index folder {index_dir.name} is not the active version {active_version}")

    try:
        manifest = json.loads((index_dir / MANIFEST_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return problems + [f"{MANIFEST_FILE} cannot be read: {type(e).__name__}"]
    if not isinstance(manifest, dict):
        return problems + [f"{MANIFEST_FILE} is not a JSON object"]

    def expect(field: str, wanted) -> None:
        if manifest.get(field) != wanted:
            problems.append(f"manifest {field} is {manifest.get(field)!r}, expected {wanted!r}")

    expect("kb_version", active_version)
    expect("model_name", model_name)
    expect("model_revision", model_revision)

    libraries = manifest.get("library_versions")
    if not isinstance(libraries, dict) or not libraries:
        problems.append("manifest library_versions is missing or empty")
    else:
        for name, recorded in sorted(libraries.items()):
            got = installed(name)
            if got != recorded:
                problems.append(f"manifest library_versions {name} is {recorded!r}, installed {got!r}")

    for name_field, hash_field in (("index_file", "index_sha256"), ("metadata_file", "metadata_sha256")):
        name = manifest.get(name_field)
        if not isinstance(name, str) or "/" in name or not (index_dir / name).is_file():
            problems.append(f"manifest {name_field} {name!r} is not a file in {index_dir.name}/")
            continue
        expect(hash_field, sha256(index_dir / name))

    expect("article_count", count_articles(kb_folder))
    metadata = manifest.get("metadata_file")
    if isinstance(metadata, str) and (index_dir / metadata).is_file():
        expect("chunk_count", count_lines(index_dir / metadata))
    return problems


def other_indexes(index_root: Path, active_version: str) -> list[str]:
    return sorted(p.name for p in index_root.iterdir() if p.name != active_version)


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python deploy/check_manifest.py data/kb_<version>", file=sys.stderr)
        return 2
    sys.path.insert(0, str(REPO_ROOT))
    from importlib.metadata import PackageNotFoundError, version

    from ingestion import RetrievalError, open_retrieval
    from ingestion.config import MODEL_NAME, MODEL_REVISION
    from query.config import ConfigError, read_active_kb_version

    def installed(name: str) -> str | None:
        try:
            return version(name)
        except PackageNotFoundError:
            return None

    try:
        active = read_active_kb_version()
    except ConfigError as e:
        print(f"check_manifest: {e}", file=sys.stderr)
        return 1
    kb_folder = REPO_ROOT / argv[0]
    problems = manifest_problems(INDEX_ROOT / active, kb_folder, active, MODEL_NAME, MODEL_REVISION, installed)
    others = other_indexes(INDEX_ROOT, active)
    if others:
        problems.append(f"indexes/ holds more than the active version: {', '.join(others)}")
    if not problems:
        try:
            open_retrieval(active)
        except RetrievalError as e:
            problems.append(f"open_retrieval({active!r}) failed: {e}")
    if problems:
        for problem in problems:
            print(f"check_manifest: {problem}", file=sys.stderr)
        return 1
    print(f"check_manifest: indexes/{active} matches its manifest and opens through open_retrieval()")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
