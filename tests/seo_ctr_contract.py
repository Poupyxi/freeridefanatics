#!/usr/bin/env python3
"""Validate the search-result metadata most likely to influence CTR."""

from html.parser import HTMLParser
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
PRIORITY_PAGES = [
    "competitions/uci-mtb-world-cup-dh-2026/standings.html",
    "riders/jackson-goldstone.html",
    "riders/max-alran.html",
    "riders/asa-vermette.html",
    "riders/lisa-bouladou.html",
]


class SearchMetadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.title = ""
        self.description = ""
        self.robots = ""
        self.canonical = ""
        self.properties = {}

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "title":
            self.in_title = True
        if tag == "meta" and values.get("name") == "description":
            self.description = values.get("content", "")
        if tag == "meta" and values.get("name") == "robots":
            self.robots = values.get("content", "")
        if tag == "meta" and values.get("property"):
            self.properties[values["property"]] = values.get("content", "")
        if tag == "link" and values.get("rel") == "canonical":
            self.canonical = values.get("href", "")

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data


titles = set()
descriptions = set()
canonicals = set()

for relative in PRIORITY_PAGES:
    path = ROOT / relative
    assert path.is_file(), f"Missing priority SEO page: {relative}"
    parser = SearchMetadata()
    parser.feed(path.read_text(encoding="utf-8"))

    title = " ".join(parser.title.split())
    description = " ".join(parser.description.split())
    assert title, f"Missing title: {relative}"
    assert description, f"Missing description: {relative}"
    assert len(description) <= 160, f"Description exceeds 160 characters: {relative}"
    assert description.endswith("."), f"Description is not a complete sentence: {relative}"
    assert "…" not in description, f"Description contains a generated ellipsis: {relative}"
    assert title not in titles, f"Duplicate priority title: {title}"
    assert description not in descriptions, f"Duplicate priority description: {relative}"
    assert parser.canonical.startswith("https://preprod.ridersfanatics.com/"), relative
    assert parser.canonical not in canonicals, f"Duplicate canonical: {parser.canonical}"
    assert parser.robots == "noindex,nofollow,noarchive", relative
    assert parser.properties.get("og:title") == title, relative
    assert parser.properties.get("og:description") == description, relative
    assert parser.properties.get("og:image"), relative
    assert parser.properties.get("og:image:alt") == title, relative
    assert parser.properties.get("og:updated_time"), relative

    titles.add(title)
    descriptions.add(description)
    canonicals.add(parser.canonical)

competitions = (ROOT / "competitions.html").read_text(encoding="utf-8")
assert ">Open competition<" not in competitions
assert re.search(
    r'href="competitions/uci-mtb-world-cup-dh-2026\.html">Explore [^<]+ results</a>',
    competitions,
), "The UCI competition link must use a descriptive results anchor"

print(f"CTR metadata contract passed for {len(PRIORITY_PAGES)} priority pages.")
