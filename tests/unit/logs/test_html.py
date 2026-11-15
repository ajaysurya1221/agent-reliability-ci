"""Offline HTML, record-only visible values and deterministic strip charts."""

import re
from html.parser import HTMLParser

import pytest

from arci.logs.html import render_html
from arci.logs.report import render_text
from tests.unit.logs.test_report import SNAPSHOTS, cases, normalize_version


class Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.words: list[str] = []
        self.in_style = False
        self.dots = 0
        self.charts = 0
        self.splits = 0
        self.medians = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "style":
            self.in_style = True
        self.dots += tag == "circle"
        self.charts += tag == "svg"
        attributes = dict(attrs)
        self.splits += tag == "line" and attributes.get("class") == "split"
        self.medians += tag == "line" and attributes.get("class") == "median"
        assert "src" not in attributes
        assert "href" not in attributes or (attributes["href"] or "").startswith("#")

    def handle_endtag(self, tag: str) -> None:
        if tag == "style":
            self.in_style = False

    def handle_data(self, data: str) -> None:
        if not self.in_style:
            self.words.append(data)


@pytest.mark.parametrize("name", ["example", "too_few_days", "both_no_logs", "error_notices"])
def test_html_snapshot(name: str) -> None:
    decision = cases()[name]
    actual = render_html(decision)
    assert actual == render_html(decision)
    assert normalize_version(actual) == normalize_version((SNAPSHOTS / f"{name}.html").read_text())


@pytest.mark.parametrize("name", list(cases()))
def test_page_uses_only_record_numbers_and_has_no_external_reference(name: str) -> None:
    decision = cases()[name]
    actual = render_html(decision)
    for forbidden in ("<script", "http", "src="):
        assert forbidden not in actual.lower()
    page = Page()
    page.feed(actual)
    numbers = set(re.findall(r"\d+", render_text(decision) + decision.model_dump_json()))
    assert set(re.findall(r"\d+", " ".join(page.words))) <= numbers
    measures = [m for t in decision.tools for m in t.measures]
    assert page.charts == page.splits == sum(bool(m.before_days or m.after_days) for m in measures)
    assert page.dots == sum(len(m.before_days) + len(m.after_days) for m in measures)
    assert page.medians == sum(
        (m.median_before is not None) + (m.median_after is not None) for m in measures
    )


def test_names_cannot_inject_markup_or_controls() -> None:
    decision = cases()["no_drop"]
    unsafe = decision.tools[0].model_copy(update={"model": "x<&\x1b", "effort": "y<&\x07"})
    actual = render_html(decision.model_copy(update={"tools": (unsafe,)}))
    assert "x&lt;&amp;" in actual and "y&lt;&amp;" in actual
    assert "\x1b" not in actual and "\x07" not in actual
    assert "x<&" not in actual
