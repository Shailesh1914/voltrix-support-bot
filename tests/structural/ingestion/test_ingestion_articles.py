"""Stage a: reading and validating articles (spec 01, "Input").

Covers acceptance criterion 4 (README excluded, broken header fails
loudly, using tests/fixtures/), the article_id format and uniqueness
part of criterion 3, and the spec 01 v1.2 duplicate-id rule.
"""

import unicodedata

import pytest
from conftest import DATA_DIR, FIXTURES_DIR, article_text

from ingestion.articles import (
    kb_version_from_folder,
    list_article_files,
    load_articles,
)
from ingestion.errors import IngestionError


# --- Real knowledge base -------------------------------------------------


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_real_kb_loads_every_article_except_readme(version):
    folder = DATA_DIR / f"kb_{version}"
    expected = sorted(
        (p.name for p in folder.glob("*.md") if p.name != "README.md"),
        key=lambda name: name.encode("utf-8"),
    )
    articles = load_articles(folder)
    assert [a.path.name for a in articles] == expected
    assert all(a.kb_version == version for a in articles)
    assert "README.md" not in [a.path.name for a in articles]


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_real_kb_article_ids_valid_and_unique(version):
    articles = load_articles(DATA_DIR / f"kb_{version}")
    ids = [a.article_id for a in articles]
    assert len(ids) == len(set(ids))


# --- Fixture with a deliberately broken file (criterion 4) ---------------


def test_broken_header_fixture_fails_loudly_naming_the_file():
    folder = FIXTURES_DIR / "broken_header" / "kb_v1"
    with pytest.raises(IngestionError) as excinfo:
        load_articles(folder)
    assert excinfo.value.path.name == "broken-header.md"
    assert "broken-header.md" in str(excinfo.value)


def test_broken_header_fixture_readme_is_not_read():
    folder = FIXTURES_DIR / "broken_header" / "kb_v1"
    names = [p.name for p in list_article_files(folder)]
    assert names == ["broken-header.md", "good-article.md"]


# --- File selection -------------------------------------------------------


def test_readme_without_header_is_ignored(make_kb):
    folder = make_kb(
        {"README.md": "Not an article.\n", "a.md": article_text()}
    )
    assert [a.path.name for a in load_articles(folder)] == ["a.md"]


def test_subfolders_and_non_md_files_are_ignored(make_kb):
    folder = make_kb({"a.md": article_text(), "notes.txt": "x", "a.MD": "x"})
    sub = folder / "sub"
    sub.mkdir()
    (sub / "b.md").write_text("no header", encoding="utf-8")
    (folder / "dir.md").mkdir()
    assert [a.path.name for a in load_articles(folder)] == ["a.md"]


def test_files_processed_in_byte_order(make_kb):
    folder = make_kb(
        {
            "b.md": article_text(article_id="KB-002"),
            "B.md": article_text(article_id="KB-001"),
            "a.md": article_text(article_id="KB-003"),
            "é.md": article_text(article_id="KB-004"),
        }
    )
    names = [a.path.name for a in load_articles(folder)]
    assert names == ["B.md", "a.md", "b.md", "é.md"]


def test_empty_folder_fails(make_kb):
    folder = make_kb({"README.md": "only a readme"})
    with pytest.raises(IngestionError, match="no articles"):
        load_articles(folder)


def test_missing_folder_fails(tmp_path):
    with pytest.raises(IngestionError, match="does not exist"):
        load_articles(tmp_path / "kb_v1")


# --- Folder version -------------------------------------------------------


@pytest.mark.parametrize("name,version", [("kb_v1", "v1"), ("kb_v2", "v2")])
def test_kb_version_from_folder(tmp_path, name, version):
    assert kb_version_from_folder(tmp_path / name) == version


@pytest.mark.parametrize("name", ["kb", "kb_1", "v1", "kb_v1_old", "KB_v1"])
def test_bad_folder_name_fails(tmp_path, name):
    with pytest.raises(IngestionError, match="folder name"):
        kb_version_from_folder(tmp_path / name)


# --- Normalisation --------------------------------------------------------


def test_crlf_and_cr_become_lf(make_kb):
    text = article_text(body="# T\n\n## S\n\nline one\nline two\n")
    crlf = text.replace("\n", "\r\n").encode("utf-8")
    folder = make_kb({"a.md": crlf, "b.md": text.replace("\n", "\r").replace(
        "KB-001", "KB-002").encode("utf-8")})
    for article in load_articles(folder):
        assert "\r" not in article.body
        assert "line one\nline two" in article.body


def test_text_is_nfc_normalised(make_kb):
    decomposed = unicodedata.normalize("NFD", "Café")
    folder = make_kb(
        {"a.md": article_text(title=decomposed, body=f"## S\n\n{decomposed}\n")}
    )
    article = load_articles(folder)[0]
    assert article.title == "Café"
    assert unicodedata.is_normalized("NFC", article.body)
    assert "Café" in article.body


def test_body_keeps_markdown_after_header(make_kb):
    body = "# T\n\n## S\n\nUse `P-05` and **bold**.\n"
    folder = make_kb({"a.md": article_text(body=body)})
    assert load_articles(folder)[0].body == "\n" + body


def test_quoted_yaml_title_is_parsed(make_kb):
    folder = make_kb(
        {"a.md": article_text(title='"Quick-start: motor data"')}
    )
    assert load_articles(folder)[0].title == "Quick-start: motor data"


# --- Invalid headers fail loudly, naming the file ------------------------

INVALID_FILES = {
    "no_header": "# Title\n\n## S\n\ntext\n",
    "header_not_first_line": "\n" + article_text(),
    "unclosed_header": "---\narticle_id: KB-001\ntitle: T\ncategory: fault\n"
    "kb_version: v1\n\n## S\n",
    "invalid_yaml": "---\narticle_id: [KB-001\n---\n\n## S\n",
    "header_is_list": "---\n- a\n- b\n---\n\n## S\n",
    "empty_header": "---\n---\n\n## S\n",
    "missing_article_id": "---\ntitle: T\ncategory: fault\nkb_version: v1\n---\n",
    "missing_title": "---\narticle_id: KB-001\ncategory: fault\nkb_version: v1\n---\n",
    "missing_category": "---\narticle_id: KB-001\ntitle: T\nkb_version: v1\n---\n",
    "missing_kb_version": "---\narticle_id: KB-001\ntitle: T\ncategory: fault\n---\n",
    "empty_title": article_text(title='""'),
    "non_string_title": article_text(title="123"),
    "bad_category": article_text(category="pricing"),
    "category_wrong_case": article_text(category="Fault"),
    "kb_version_mismatch": article_text(kb_version="v2"),
    "article_id_two_digits": article_text(article_id="KB-01"),
    "article_id_four_digits": article_text(article_id="KB-0001"),
    "article_id_lowercase": article_text(article_id="kb-001"),
    "article_id_non_ascii_digits": article_text(article_id="KB-١٢٣"),
    "article_id_number": article_text(article_id="1"),
}


@pytest.mark.parametrize("case", sorted(INVALID_FILES))
def test_invalid_header_fails_loudly(make_kb, case):
    folder = make_kb(
        {"a-good.md": article_text(article_id="KB-100"),
         "z-bad.md": INVALID_FILES[case]}
    )
    with pytest.raises(IngestionError) as excinfo:
        load_articles(folder)
    assert excinfo.value.path.name == "z-bad.md"
    assert "z-bad.md" in str(excinfo.value)


def test_non_utf8_file_fails_loudly(make_kb):
    folder = make_kb({"a.md": article_text().encode("utf-8") + b"\xff\xfe"})
    with pytest.raises(IngestionError, match="UTF-8") as excinfo:
        load_articles(folder)
    assert excinfo.value.path.name == "a.md"


def test_duplicate_article_id_fails_loudly(make_kb):
    folder = make_kb(
        {"a.md": article_text(article_id="KB-007"),
         "b.md": article_text(article_id="KB-007")}
    )
    with pytest.raises(IngestionError, match="duplicate") as excinfo:
        load_articles(folder)
    assert excinfo.value.path.name == "b.md"
    assert "a.md" in str(excinfo.value)
