"""Read and validate knowledge base articles (spec 01, "Input").

Every problem raises IngestionError naming the file. Nothing is
skipped silently.
"""

import unicodedata
from dataclasses import dataclass
from pathlib import Path

import yaml

from ingestion.config import (
    ARTICLE_ID_PATTERN,
    CATEGORIES,
    EXCLUDED_FILENAMES,
    KB_FOLDER_PATTERN,
    REQUIRED_HEADER_FIELDS,
)
from ingestion.errors import IngestionError

HEADER_DELIMITER = "---"
BYTE_ORDER_MARK = "\ufeff"


class _StrictLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate keys instead of keeping the last."""

    def construct_mapping(self, node, deep=False):
        seen = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                raise yaml.constructor.ConstructorError(
                    None, None, f"duplicate key {key!r}", key_node.start_mark
                )
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


@dataclass(frozen=True)
class Article:
    path: Path
    article_id: str
    title: str
    category: str
    kb_version: str
    body: str  # normalised text after the header block


def kb_version_from_folder(folder: Path) -> str:
    """kb_v1 -> "v1". Any other folder name fails."""
    match = KB_FOLDER_PATTERN.fullmatch(folder.name)
    if match is None:
        raise IngestionError(
            folder, "folder name must look like kb_v<number>, e.g. kb_v1"
        )
    return match.group(1)


def list_article_files(folder: Path) -> list[Path]:
    """*.md files directly in folder, README.md excluded, byte-sorted."""
    if not folder.is_dir():
        raise IngestionError(folder, "knowledge base folder does not exist")
    files = [
        path
        for path in folder.iterdir()
        if path.is_file()
        and path.suffix == ".md"
        and path.name not in EXCLUDED_FILENAMES
    ]
    return sorted(files, key=lambda path: path.name.encode("utf-8"))


def normalise_text(text: str) -> str:
    """No byte-order mark, "\n" line endings, then Unicode NFC."""
    text = text.removeprefix(BYTE_ORDER_MARK)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return unicodedata.normalize("NFC", text)


def _split_header(path: Path, text: str) -> tuple[str, str]:
    lines = text.split("\n")
    if not lines or lines[0] != HEADER_DELIMITER:
        raise IngestionError(
            path, "no header block: file must start with a '---' line"
        )
    for index in range(1, len(lines)):
        if lines[index] == HEADER_DELIMITER:
            header = "\n".join(lines[1:index])
            body = "\n".join(lines[index + 1 :])
            return header, body
    raise IngestionError(path, "header block is not closed with a '---' line")


def _parse_header(path: Path, header_text: str) -> dict:
    try:
        header = yaml.load(header_text, Loader=_StrictLoader)
    except yaml.YAMLError as error:
        raise IngestionError(path, f"header block is not valid YAML: {error}")
    if not isinstance(header, dict):
        raise IngestionError(path, "header block must be a YAML mapping")
    return header


def _validate_header(path: Path, header: dict, folder_version: str) -> None:
    for field in REQUIRED_HEADER_FIELDS:
        if field not in header:
            raise IngestionError(path, f"header is missing required field '{field}'")
        value = header[field]
        if not isinstance(value, str) or not value.strip():
            raise IngestionError(
                path, f"header field '{field}' must be a non-empty string"
            )
    if not ARTICLE_ID_PATTERN.fullmatch(header["article_id"]):
        raise IngestionError(
            path,
            f"article_id {header['article_id']!r} does not match KB-<3 digits>",
        )
    if header["category"] not in CATEGORIES:
        raise IngestionError(
            path,
            f"category {header['category']!r} is not one of "
            f"{', '.join(sorted(CATEGORIES))}",
        )
    if header["kb_version"] != folder_version:
        raise IngestionError(
            path,
            f"kb_version {header['kb_version']!r} does not match folder "
            f"version {folder_version!r}",
        )


def read_article(path: Path, folder_version: str) -> Article:
    try:
        raw = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as error:
        raise IngestionError(path, f"file is not valid UTF-8: {error}")
    text = normalise_text(raw)
    header_text, body = _split_header(path, text)
    header = _parse_header(path, header_text)
    _validate_header(path, header, folder_version)
    return Article(
        path=path,
        article_id=header["article_id"],
        title=header["title"],
        category=header["category"],
        kb_version=header["kb_version"],
        body=body,
    )


def load_articles(folder: Path) -> list[Article]:
    """All valid articles in folder, in byte-sorted filename order.

    Fails on the first invalid file, on duplicate article_ids and on a
    folder with no articles.
    """
    folder = Path(folder)
    folder_version = kb_version_from_folder(folder)
    files = list_article_files(folder)
    if not files:
        raise IngestionError(folder, "folder contains no articles")

    articles: list[Article] = []
    seen: dict[str, Path] = {}
    for path in files:
        article = read_article(path, folder_version)
        if article.article_id in seen:
            raise IngestionError(
                path,
                f"duplicate article_id {article.article_id!r} "
                f"(already used by {seen[article.article_id].name})",
            )
        seen[article.article_id] = path
        articles.append(article)
    return articles
