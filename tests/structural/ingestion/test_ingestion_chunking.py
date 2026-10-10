"""Stage b: chunking (spec 01, "Chunking strategy").

Two kinds of test:
- Rule tests use a fake word-count tokenizer and small limits, so each
  split and overlap decision can be checked exactly.
- Fixture and real-KB tests use the pinned model's real tokenizer and
  the real 300 / 50 limits (acceptance criteria 2, 6, 8 and the
  per-chunk part of 1 and 3).
"""

import pytest
from conftest import DATA_DIR, FIXTURES_DIR, article_text

from ingestion import chunking
from ingestion.articles import load_articles
from ingestion.chunking import (
    LIST_ITEM,
    PARAGRAPH,
    TABLE,
    chunk_article,
    sentence_suffixes,
    split_blocks,
)
from ingestion.config import ARTICLE_ID_PATTERN
from ingestion.errors import IngestionError

PREFIX_END = "\n\n"


class WordCounter:
    """Fake tokenizer: one token per word, plus 2 special tokens."""

    def count(self, text: str, special_tokens: bool = True) -> int:
        return len(text.split()) + (2 if special_tokens else 0)


@pytest.fixture
def small_limits(monkeypatch):
    """Chunk limit 30 tokens, overlap limit 8 tokens (fake counter)."""
    monkeypatch.setattr(chunking, "MAX_CHUNK_TOKENS", 30)
    monkeypatch.setattr(chunking, "MAX_OVERLAP_TOKENS", 8)


def words(n: int, word: str = "w") -> str:
    return " ".join(f"{word}{i}" for i in range(n)) + "."


def chunks_for(make_kb, body: str, title: str = "T", counter=None):
    folder = make_kb({"a.md": article_text(title=title, body=body)})
    article = load_articles(folder)[0]
    return chunk_article(article, counter or WordCounter())


def bodies(chunks):
    return [c.text.split(PREFIX_END, 1)[1] for c in chunks]


# --- Sections, prefixes, numbering ----------------------------------------


def test_title_line_dropped_and_sections_prefixed(make_kb):
    body = "# My title\n\n## First\n\nAlpha.\n\n## Second\n\nBeta.\n"
    chunks = chunks_for(make_kb, body, title="My title")
    assert [c.text for c in chunks] == [
        "My title — First\n\nAlpha.",
        "My title — Second\n\nBeta.",
    ]


def test_text_before_first_section_is_overview_chunk(make_kb):
    body = "# T\n\nIntro text.\n\n## S\n\nBody.\n"
    chunks = chunks_for(make_kb, body)
    assert chunks[0].text == "T — Overview\n\nIntro text."
    assert chunks[1].text == "T — S\n\nBody."


def test_whitespace_only_overview_is_not_a_chunk(make_kb):
    body = "# T\n\n   \n\t\n\n## S\n\nBody.\n"
    assert [c.text for c in chunks_for(make_kb, body)] == ["T — S\n\nBody."]


def test_article_without_title_line_drops_nothing(make_kb):
    body = "Intro.\n\n## S\n\nBody.\n"
    assert chunks_for(make_kb, body)[0].text == "T — Overview\n\nIntro."


def test_subheadings_belong_to_parent_section(make_kb):
    body = "# T\n\n## S\n\nIntro.\n\n### Sub\n\nDetail.\n\n#### Deeper\n\nMore.\n"
    chunks = chunks_for(make_kb, body)
    assert len(chunks) == 1
    assert chunks[0].text == (
        "T — S\n\nIntro.\n\n### Sub\n\nDetail.\n\n#### Deeper\n\nMore."
    )


def test_markdown_kept_exactly_as_written(make_kb):
    section = (
        "Use `P-05` and **bold** text.\n"
        "Second line of the same paragraph.\n\n"
        "- tight item one\n- tight item two\n"
        "   - nested item\n\n"
        "| a | b |\n|---|---|\n| 1 | 2 |\n\n\n"
        "WARNING: after two blank lines."
    )
    chunks = chunks_for(make_kb, f"# T\n\n## S\n\n{section}\n")
    assert chunks[0].text == "T — S\n\n" + section


def test_chunk_fields_and_ids_numbered_through_article(make_kb, small_limits):
    body = "# T\n\n## A\n\nShort.\n\n## B\n\n" + "\n\n".join(
        words(10, f"p{i}") for i in range(5)
    ) + "\n\n## C\n\nShort.\n"
    chunks = chunks_for(make_kb, body)
    assert len(chunks) > 3
    assert [c.chunk_id for c in chunks] == [
        f"KB-001#c{n}" for n in range(1, len(chunks) + 1)
    ]
    for c in chunks:
        assert (c.article_id, c.title, c.category, c.kb_version) == (
            "KB-001", "T", "fault", "v1"
        )


def test_empty_section_fails_loudly(make_kb):
    body = "# T\n\n## Empty\n\n   \n\n## Full\n\nText.\n"
    with pytest.raises(IngestionError, match="'## Empty' heading has no body") as e:
        chunks_for(make_kb, body)
    assert e.value.path.name == "a.md"


def test_empty_last_section_fails_loudly(make_kb):
    with pytest.raises(IngestionError, match="no body text"):
        chunks_for(make_kb, "# T\n\n## Full\n\nText.\n\n## Empty\n")


def test_heading_without_text_fails_loudly(make_kb):
    with pytest.raises(IngestionError, match="heading has no text"):
        chunks_for(make_kb, "# T\n\n##   \n\nText.\n")


@pytest.mark.parametrize(
    "body",
    [
        "# T\n\n## S\n\nText.\n\n```\nP-05 = 10\n```\n",
        "# T\n\n## S\n\n```python\nx = 1\n```\n",
        "# T\n\nIntro.\n\n   ```\n   indented\n   ```\n\n## S\n\nText.\n",
        "# T\n\n## S\n\nInline ```code``` in a sentence.\n",
    ],
)
def test_code_fence_fails_loudly(make_kb, body):
    with pytest.raises(IngestionError, match="code fences") as excinfo:
        chunks_for(make_kb, body)
    assert excinfo.value.path.name == "a.md"


def test_single_backticks_are_allowed(make_kb):
    chunks = chunks_for(make_kb, "# T\n\n## S\n\nSet `P-05` and ``P-06``.\n")
    assert chunks[0].text == "T — S\n\nSet `P-05` and ``P-06``."


def test_article_with_no_text_fails_loudly(make_kb):
    with pytest.raises(IngestionError, match="no text to chunk"):
        chunks_for(make_kb, "# T\n\n")


# --- Blocks ---------------------------------------------------------------


def test_blocks_paragraphs_list_items_tables():
    lines = (
        "Para line one.\nPara line two.\n"
        "- item one\n  continued\n- item two\n"
        "1. step one\n   - nested a\n   - nested b\n"
        "2) step two\n\n"
        "| a |\n|---|\n\n"
        "After table."
    ).split("\n")
    blocks = split_blocks(lines)
    assert [(b.kind, b.text) for b in blocks] == [
        (PARAGRAPH, "Para line one.\nPara line two."),
        (LIST_ITEM, "- item one\n  continued"),
        (LIST_ITEM, "- item two"),
        (LIST_ITEM, "1. step one\n   - nested a\n   - nested b"),
        (LIST_ITEM, "2) step two"),
        (TABLE, "| a |\n|---|"),
        (PARAGRAPH, "After table."),
    ]
    assert [b.separator for b in blocks] == ["", "\n", "\n", "\n", "\n", "\n\n", "\n\n"]


def test_loose_list_item_keeps_indented_paragraph():
    blocks = split_blocks("- item\n\n  more about item\n\nNext.".split("\n"))
    assert [b.text for b in blocks] == ["- item\n\n  more about item", "Next."]


def test_subheading_joined_to_next_block():
    blocks = split_blocks("Intro.\n\n### Sub\n\n| a |\n|---|".split("\n"))
    assert [(b.kind, b.text) for b in blocks] == [
        (PARAGRAPH, "Intro."),
        (TABLE, "### Sub\n\n| a |\n|---|"),
    ]


def test_trailing_subheading_is_its_own_block():
    blocks = split_blocks("Intro.\n\n### Sub".split("\n"))
    assert [b.text for b in blocks] == ["Intro.", "### Sub"]


# --- Sentences ------------------------------------------------------------


def test_sentence_suffixes():
    text = "One is here. Two uses e.g. this and 10.0 s! `P-05` third? (Four.)"
    assert sentence_suffixes(text) == [
        text,
        "Two uses e.g. this and 10.0 s! `P-05` third? (Four.)",
        "`P-05` third? (Four.)",
        "(Four.)",
    ]


# --- Splitting and overlap (fake counter, limits 30 / 8) ------------------


def test_section_within_limit_is_not_split(make_kb, small_limits):
    # prefix "T — S" = 3 words; 25 + 3 + 2 special = 30 tokens exactly.
    chunks = chunks_for(make_kb, f"# T\n\n## S\n\n{words(25)}\n")
    assert len(chunks) == 1


def test_split_at_paragraphs_with_whole_paragraph_overlap(make_kb, small_limits):
    paras = [words(6, "a"), words(6, "b"), words(6, "c"), words(6, "d"), words(6, "e")]
    chunks = chunks_for(make_kb, "# T\n\n## S\n\n" + "\n\n".join(paras) + "\n")
    # Each piece: 3 prefix + 2 special + up to 25 words.
    # Overlap: the last paragraph (6 words) fits in 8; two do not.
    assert bodies(chunks) == [
        "\n\n".join(paras[0:4]),
        "\n\n".join(paras[3:5]),
    ]
    assert all(c.text.startswith("T — S\n\n") for c in chunks)


def test_overlap_takes_as_many_whole_items_as_fit(make_kb, small_limits):
    items = [f"- {words(2, x)}" for x in "abcdefghij"]  # 3 words each
    chunks = chunks_for(make_kb, "# T\n\n## S\n\n" + "\n".join(items) + "\n")
    b = bodies(chunks)
    assert len(b) > 1
    for previous, current in zip(b, b[1:]):
        prev_items = previous.split("\n")
        # 2 items = 6 tokens fit within 8; 3 items = 9 do not.
        assert current.split("\n")[:2] == prev_items[-2:]
    assert all(WordCounter().count(c.text) <= 30 for c in chunks)


def test_sentence_overlap_when_last_paragraph_too_long(make_kb, small_limits):
    p1 = words(12, "a")
    p2 = "First sentence has five words. Second has four words. Tail ok."
    p3 = words(12, "c")
    chunks = chunks_for(make_kb, f"# T\n\n## S\n\n{p1}\n\n{p2}\n\n{p3}\n")
    # p2 is 11 words (> 8), so the overlap is its last sentences that
    # fit in 8 tokens: "Second has four words. Tail ok." (6 words).
    assert bodies(chunks) == [
        f"{p1}\n\n{p2}",
        f"Second has four words. Tail ok.\n\n{p3}",
    ]


def test_no_overlap_when_last_sentence_too_long(make_kb, small_limits):
    p1 = words(12, "a")
    p2 = words(10, "b")  # one sentence of 10 words > 8
    p3 = words(12, "c")
    chunks = chunks_for(make_kb, f"# T\n\n## S\n\n{p1}\n\n{p2}\n\n{p3}\n")
    assert bodies(chunks) == [f"{p1}\n\n{p2}", p3]


def test_no_overlap_after_table(make_kb, small_limits):
    p1 = words(10, "a")
    table = "| t0 t1 t2 t3 |\n|---|\n| t4 t5 t6 t7 |"
    p2 = words(20, "c")
    chunks = chunks_for(make_kb, f"# T\n\n## S\n\n{p1}\n\n{table}\n\n{p2}\n")
    assert bodies(chunks) == [f"{p1}\n\n{table}", p2]


def test_overlap_shrinks_by_whole_items_to_fit_next_block(make_kb, small_limits):
    p1 = words(16, "a")
    items = "- one two\n- three four"  # 3 tokens each; both fit in 8
    p3 = words(20, "c")  # 5 + 6 + 20 > 30, but 5 + 3 + 20 fits
    chunks = chunks_for(make_kb, f"# T\n\n## S\n\n{p1}\n\n{items}\n\n{p3}\n")
    assert bodies(chunks) == [
        f"{p1}\n\n{items}",
        f"- three four\n\n{p3}",
    ]


def test_short_paragraph_overlap_is_dropped_not_cut_into_sentences(
    make_kb, small_limits
):
    p1 = words(18, "a")
    p2 = "One two three. Four five six seven."  # 7 tokens, fits in 8
    p3 = words(21, "c")  # does not fit with all of p2 as overlap
    chunks = chunks_for(make_kb, f"# T\n\n## S\n\n{p1}\n\n{p2}\n\n{p3}\n")
    assert bodies(chunks) == [f"{p1}\n\n{p2}", p3]


def test_table_split_from_its_neighbours_never_inside(make_kb, small_limits):
    table = "| a b c d e |\n|---|\n| f g h i j |\n| k l m n o |"
    body = f"# T\n\n## S\n\n{words(10)}\n\n{table}\n\n{words(10, 'z')}\n"
    for chunk_body in bodies(chunks_for(make_kb, body)):
        if "|" in chunk_body:
            assert table in chunk_body


@pytest.mark.parametrize(
    "block,what",
    [
        ("| " + " ".join(["x"] * 30) + " |\n|---|", "table"),
        (words(26), "paragraph or list item"),
        ("- " + words(25), "paragraph or list item"),
    ],
)
def test_oversized_block_fails_loudly(make_kb, small_limits, block, what):
    body = f"# T\n\n## Sec\n\nShort.\n\n{block}\n"
    with pytest.raises(IngestionError) as excinfo:
        chunks_for(make_kb, body)
    assert excinfo.value.path.name == "a.md"
    assert f"a {what} in section 'Sec'" in str(excinfo.value)


# --- Synthetic long article, real tokenizer (criterion 8) ----------------

LONG_DIR = FIXTURES_DIR / "long_article" / "kb_v1"


@pytest.fixture(scope="module")
def long_article():
    return load_articles(LONG_DIR)[0]


@pytest.fixture(scope="module")
def long_chunks(long_article, token_counter):
    return chunk_article(long_article, token_counter)


def _section_bodies(article):
    return {
        s.heading: chunking.join_blocks(chunking.split_blocks(s.lines))
        for s in chunking.split_sections(article)
    }


def _pieces_by_heading(chunks, title):
    grouped: dict[str, list[str]] = {}
    for c in chunks:
        prefix, body = c.text.split(PREFIX_END, 1)
        heading = prefix.removeprefix(f"{title} — ")
        grouped.setdefault(heading, []).append(body)
    return grouped


def _split_overlap(previous: str, current: str, section: str, pos: int):
    """Return (overlap, new_end_pos) for current, checked against section."""
    sep_end = pos
    while sep_end < len(section) and section[sep_end] == "\n":
        sep_end += 1
    separator = section[pos:sep_end]
    for length in range(len(current), 0, -1):
        new_text = current[-length:]
        if not section.startswith(new_text, sep_end):
            continue
        head = current[:-length]
        if head == "":
            return "", sep_end + length
        if head.endswith(separator):
            overlap = head[: -len(separator)]
            if previous.endswith(overlap):
                return overlap, sep_end + length
    raise AssertionError(f"piece does not continue the section: {current[:60]!r}")


def test_long_article_sections_are_split(long_article, long_chunks):
    pieces = _pieces_by_heading(long_chunks, long_article.title)
    for heading in ["Step-by-step procedure", "Background", "Long sentences", "Settings table"]:
        assert len(pieces[heading]) >= 2, heading
    assert len(pieces["Short section"]) == 1
    assert len(pieces["Overview"]) == 1


def test_long_article_chunks_within_token_limits(long_chunks, token_counter):
    for c in long_chunks:
        tokens = token_counter.count(c.text)
        assert tokens <= 300 and tokens <= 512, (c.chunk_id, tokens)


def test_long_article_every_piece_repeats_prefix(long_article, long_chunks):
    sections = _section_bodies(long_article)
    for c in long_chunks:
        heading = c.text.split(PREFIX_END, 1)[0].removeprefix(f"{long_article.title} — ")
        assert heading in sections
        assert c.text.startswith(f"{long_article.title} — {heading}\n\n")


def test_long_article_pieces_cover_section_at_block_boundaries(
    long_article, long_chunks, token_counter
):
    """Overlap is a suffix of the previous piece (<= 50 tokens), the new
    text continues the section exactly, and every piece ends at a block
    boundary (end of a paragraph, list item or table)."""
    sections = _section_bodies(long_article)
    pieces = _pieces_by_heading(long_chunks, long_article.title)
    for heading, section in sections.items():
        parts = pieces[heading]
        assert section.startswith(parts[0])
        pos = len(parts[0])
        for previous, current in zip(parts, parts[1:]):
            assert section[pos] == "\n", "piece must end at a block boundary"
            overlap, pos = _split_overlap(previous, current, section, pos)
            assert token_counter.count(overlap, special_tokens=False) <= 50
        assert pos == len(section), f"section {heading!r} not fully covered"


def test_long_article_overlap_kinds(long_article, long_chunks):
    pieces = _pieces_by_heading(long_chunks, long_article.title)
    steps = pieces["Step-by-step procedure"]
    # Whole list items repeated: the second piece starts with the last
    # list item(s) of the first.
    first_line = steps[1].split("\n")[0]
    assert first_line[0].isdigit() and first_line in steps[0].split("\n")

    background = pieces["Background"]
    # Last paragraph > 50 tokens: overlap is its last whole sentences,
    # so the second piece starts mid-paragraph, at a sentence start.
    overlap_start = background[1].split("\n\n")[0]
    last_paragraph = background[0].split("\n\n")[-1]
    assert last_paragraph.endswith(overlap_start)
    assert overlap_start != last_paragraph

    long_sentences = pieces["Long sentences"]
    # Every sentence > 50 tokens: no overlap.
    assert long_sentences[1].split("\n\n")[0] not in long_sentences[0]

    table_section = pieces["Settings table"]
    # Previous piece ends with a table: no overlap.
    assert table_section[0].endswith("|")
    assert table_section[1].split("\n\n")[0] not in table_section[0]


def test_long_article_chunk_ids(long_chunks):
    assert [c.chunk_id for c in long_chunks] == [
        f"KB-950#c{n}" for n in range(1, len(long_chunks) + 1)
    ]


def test_big_table_fixture_fails_loudly(token_counter):
    article = load_articles(FIXTURES_DIR / "big_table" / "kb_v1")[0]
    with pytest.raises(IngestionError) as excinfo:
        chunk_article(article, token_counter)
    assert excinfo.value.path.name == "big-table.md"
    assert "a table in section 'Parameter list'" in str(excinfo.value)


# --- Real knowledge base (criteria 1, 2, 3, 6 at chunk level) ------------


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_real_kb_chunks(version, token_counter):
    for article in load_articles(DATA_DIR / f"kb_{version}"):
        chunks = chunk_article(article, token_counter)
        assert chunks, article.path.name  # criterion 1
        assert [c.chunk_id for c in chunks] == [  # criterion 6
            f"{article.article_id}#c{n}" for n in range(1, len(chunks) + 1)
        ]
        for c in chunks:
            assert c.article_id == article.article_id  # criterion 3
            assert ARTICLE_ID_PATTERN.fullmatch(c.article_id)
            assert c.kb_version == version
            assert token_counter.count(c.text) <= 300  # criterion 2
            assert c.text.startswith(f"{article.title} — ")
