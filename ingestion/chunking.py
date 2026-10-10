"""Split articles into chunks (spec 01, "Chunking strategy").

Each "##" section becomes one chunk, prefixed "<Title> — <Heading>".
A section over MAX_CHUNK_TOKENS is split at block boundaries
(paragraphs, list items, tables), never inside a block, and each later
piece starts with up to MAX_OVERLAP_TOKENS of overlap from the end of
the previous piece.

Token counts come from a counter with count(text, special_tokens=True),
normally ingestion.embedding.TokenCounter.
"""

import re
from dataclasses import dataclass

from ingestion.articles import Article
from ingestion.config import (
    MAX_CHUNK_TOKENS,
    MAX_OVERLAP_TOKENS,
    MODEL_TOKEN_LIMIT,
)
from ingestion.errors import IngestionError

PREFIX_SEPARATOR = " — "
PREFIX_BODY_SEPARATOR = "\n\n"
OVERVIEW_HEADING = "Overview"
CODE_FENCE = "```"

TITLE_LINE = re.compile(r"# ")
SECTION_LINE = re.compile(r"## ")
SUBHEADING_LINE = re.compile(r"#{3,6} ")
LIST_ITEM_LINE = re.compile(r"([-*+]|[0-9]+[.)]) ")
TABLE_LINE = re.compile(r"\s*\|")
# A sentence ends at . ! or ? followed by whitespace and a likely
# sentence start, so "e.g. the" and "10.0 s" are not split.
SENTENCE_START = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9`\"'*(\[])")

PARAGRAPH = "paragraph"
LIST_ITEM = "list_item"
TABLE = "table"
SUBHEADING = "subheading"

# Block kinds that may be repeated as overlap.
OVERLAP_KINDS = (PARAGRAPH, LIST_ITEM)


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    article_id: str
    title: str
    category: str
    kb_version: str
    text: str


@dataclass(frozen=True)
class Block:
    kind: str
    text: str
    separator: str  # original text before this block; "" for the first


@dataclass(frozen=True)
class Section:
    heading: str
    lines: list[str]


# --- Sections -------------------------------------------------------------


def split_sections(article: Article) -> list[Section]:
    """The "Overview" text (if any) and each "##" section, in order."""
    for number, line in enumerate(article.body.split("\n"), start=1):
        if CODE_FENCE in line:
            raise IngestionError(
                article.path,
                f"code fences (```) are not supported (body line {number})",
            )
    lines = article.body.split("\n")

    # Drop the "# Title" line if it is the first non-blank line.
    for index, line in enumerate(lines):
        if line.strip():
            if TITLE_LINE.match(line):
                lines = lines[index + 1 :]
            break

    sections: list[Section] = []
    heading = OVERVIEW_HEADING
    current: list[str] = []
    for line in lines:
        if SECTION_LINE.match(line):
            sections.append(Section(heading, current))
            heading = line[3:].strip()
            if not heading:
                raise IngestionError(article.path, "'##' heading has no text")
            current = []
        else:
            current.append(line)
    sections.append(Section(heading, current))

    overview, rest = sections[0], sections[1:]
    for section in rest:
        if not any(line.strip() for line in section.lines):
            raise IngestionError(
                article.path,
                f"'## {section.heading}' heading has no body text",
            )
    if any(line.strip() for line in overview.lines):
        return [overview, *rest]
    return rest


# --- Blocks ---------------------------------------------------------------


def _block_kind(line: str) -> str:
    if TABLE_LINE.match(line):
        return TABLE
    if SUBHEADING_LINE.match(line):
        return SUBHEADING
    if LIST_ITEM_LINE.match(line):
        return LIST_ITEM
    return PARAGRAPH


def _continues(kind: str, line: str) -> bool:
    """Whether a non-blank line continues the current block."""
    if kind == TABLE:
        return bool(TABLE_LINE.match(line))
    if kind == SUBHEADING:
        return False
    if kind == LIST_ITEM and line[:1].isspace():
        return True  # indented continuation or nested list
    return _block_kind(line) == PARAGRAPH


def split_blocks(lines: list[str]) -> list[Block]:
    """Paragraphs, top-level list items, tables and "###" lines.

    A "###" line is joined to the block after it, so a piece never
    ends with a lone heading. Separators keep the original spacing,
    so a section that is not split is reproduced exactly as written.
    """
    raw: list[Block] = []
    index = 0
    blank_lines = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            blank_lines += 1
            index += 1
            continue
        kind = _block_kind(line)
        block_lines = [line]
        index += 1
        while index < len(lines):
            line = lines[index]
            if line.strip():
                if not _continues(kind, line):
                    break
                block_lines.append(line)
                index += 1
                continue
            # Blank line(s): an indented line after them still belongs
            # to a list item (loose list item paragraph).
            look = index
            while look < len(lines) and not lines[look].strip():
                look += 1
            if kind == LIST_ITEM and look < len(lines) and lines[look][:1].isspace():
                block_lines.extend(lines[index : look + 1])
                index = look + 1
                continue
            break
        separator = "" if not raw else "\n" * (blank_lines + 1)
        raw.append(Block(kind, "\n".join(block_lines), separator))
        blank_lines = 0

    blocks: list[Block] = []
    pending: Block | None = None
    for block in raw:
        if pending is not None:
            block = Block(
                block.kind,
                pending.text + block.separator + block.text,
                pending.separator,
            )
            pending = None
        if block.kind == SUBHEADING:
            pending = block
        else:
            blocks.append(block)
    if pending is not None:
        blocks.append(Block(PARAGRAPH, pending.text, pending.separator))
    return blocks


def join_blocks(blocks: list[Block]) -> str:
    return blocks[0].text + "".join(b.separator + b.text for b in blocks[1:])


# --- Overlap --------------------------------------------------------------


def sentence_suffixes(text: str) -> list[str]:
    """text, then text without its first sentence, and so on."""
    starts = [0] + [match.end() for match in SENTENCE_START.finditer(text)]
    return [text[start:] for start in starts]


def overlap_candidates(previous: list[Block], counter) -> list[str]:
    """Possible overlaps for the next piece, longest first, ending with "".

    Whole paragraphs or list items from the end of the previous piece,
    as many as fit within MAX_OVERLAP_TOKENS. If the last one alone is
    too long, its last whole sentences that fit. Tables and headings
    are never repeated. Overlap is measured without special tokens.
    """

    def fits(text: str) -> bool:
        return counter.count(text, special_tokens=False) <= MAX_OVERLAP_TOKENS

    whole: list[str] = []
    for start in range(len(previous) - 1, -1, -1):
        if previous[start].kind not in OVERLAP_KINDS:
            break
        text = join_blocks(previous[start:])
        if not fits(text):
            break
        whole.append(text)
    if whole:
        return [*reversed(whole), ""]

    last = previous[-1]
    if last.kind in OVERLAP_KINDS:
        sentences = [s for s in sentence_suffixes(last.text)[1:] if fits(s)]
        return [*sentences, ""]
    return [""]


# --- Sections to chunk texts ---------------------------------------------


def _assemble(prefix: str, overlap: str, blocks: list[Block]) -> str:
    body = join_blocks(blocks)
    if overlap:
        body = overlap + (blocks[0].separator or "\n\n") + body
    return prefix + PREFIX_BODY_SEPARATOR + body


def chunk_section(article: Article, section: Section, counter) -> list[str]:
    prefix = f"{article.title}{PREFIX_SEPARATOR}{section.heading}"
    blocks = split_blocks(section.lines)

    def fits(text: str) -> bool:
        return counter.count(text) <= MAX_CHUNK_TOKENS

    whole = _assemble(prefix, "", blocks)
    if fits(whole):
        return [whole]

    for block in blocks:
        alone = _assemble(prefix, "", [block])
        if not fits(alone):
            what = "table" if block.kind == TABLE else "paragraph or list item"
            raise IngestionError(
                article.path,
                f"a {what} in section '{section.heading}' is "
                f"{counter.count(alone)} tokens with its prefix; the "
                f"maximum is {MAX_CHUNK_TOKENS} and it cannot be split",
            )

    pieces: list[str] = []
    previous: list[Block] = []
    start = 0
    while start < len(blocks):
        candidates = overlap_candidates(previous, counter) if previous else [""]
        # Longest overlap that still leaves room for the next block.
        # "" always fits, because every block fits alone (checked above).
        overlap = next(
            o for o in candidates if fits(_assemble(prefix, o, blocks[start : start + 1]))
        )
        end = start + 1
        while end < len(blocks) and fits(_assemble(prefix, overlap, blocks[start : end + 1])):
            end += 1
        pieces.append(_assemble(prefix, overlap, blocks[start:end]))
        previous = blocks[start:end]
        start = end
    return pieces


def chunk_article(article: Article, counter) -> list[Chunk]:
    """All chunks of one article, numbered c1..cn in reading order."""
    texts: list[str] = []
    for section in split_sections(article):
        texts.extend(chunk_section(article, section, counter))
    if not texts:
        raise IngestionError(article.path, "article has no text to chunk")

    chunks = []
    for number, text in enumerate(texts, start=1):
        tokens = counter.count(text)
        if tokens > min(MAX_CHUNK_TOKENS, MODEL_TOKEN_LIMIT):
            raise IngestionError(  # safety net; chunk_section prevents it
                article.path, f"chunk c{number} is {tokens} tokens"
            )
        chunks.append(
            Chunk(
                chunk_id=f"{article.article_id}#c{number}",
                article_id=article.article_id,
                title=article.title,
                category=article.category,
                kb_version=article.kb_version,
                text=text,
            )
        )
    return chunks
