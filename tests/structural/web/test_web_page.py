"""GET / (spec 08 section 4.3)."""

import re
from html.parser import HTMLParser

import pytest

from web_testkit import CODE, secrets_in, response_text


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags: list[tuple[str, dict]] = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


@pytest.fixture
def page(make_bot):
    response = make_bot().client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    return response


def elements(html):
    parser = Elements()
    parser.feed(html)
    return parser.tags


def test_page_shows_the_demo_note(page, spec_08):
    assert spec_08.demo_note == "Demo bot for a fictional product (Voltrix VX-200). Synthetic data only."
    assert spec_08.demo_note in page.text


def test_page_has_code_field_question_box_button_and_result_area(page):
    tags = elements(page.text)
    inputs = [a for t, a in tags if t == "input"]
    assert any(a.get("id") == "access-code" and a.get("type") == "password" for a in inputs)
    assert any(t == "textarea" and a.get("id") == "question" for t, a in tags)
    assert any(t == "button" and a.get("id") == "ask" for t, a in tags)
    assert any(a.get("id") == "answer" for _, a in tags)
    assert any(a.get("id") == "citations" for _, a in tags)
    assert re.search(r">\s*Ask\s*<", page.text)


def test_page_loads_nothing_from_elsewhere(page):
    for tag, attrs in elements(page.text):
        assert tag != "link", "a <link> element"
        assert not (tag == "script" and "src" in attrs), "an external script"
        for name in ("src", "href", "action"):
            assert name not in attrs, f"<{tag} {name}=...>"
    assert not re.search(r"https?://", page.text)
    assert "@import" not in page.text and "url(" not in page.text


def test_browser_is_told_to_load_nothing_from_elsewhere(page):
    policy = page.headers["Content-Security-Policy"]
    assert "default-src 'none'" in policy and "connect-src 'self'" in policy
    assert "http" not in policy


@pytest.mark.parametrize(
    "storage", ["localStorage", "sessionStorage", "indexedDB", "document.cookie", "caches", "serviceWorker"]
)
def test_page_does_not_store_the_code(page, storage):
    assert storage not in page.text


def test_code_field_is_not_remembered(page):
    (attrs,) = [a for t, a in elements(page.text) if t == "input" and a.get("id") == "access-code"]
    assert attrs.get("autocomplete") == "off"
    assert "<form" not in page.text  # nothing is submitted as a form


def test_page_sends_code_in_the_spec_header(page):
    assert '"X-Access-Code"' in page.text and '"/ask"' in page.text


def test_page_shows_text_safely(page):
    # Model output is shown as text, never as HTML.
    assert "innerHTML" not in page.text and "outerHTML" not in page.text


def test_page_contains_no_secret(page):
    assert secrets_in(response_text(page)) == []
    assert CODE not in page.text
