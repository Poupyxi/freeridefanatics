#!/usr/bin/env python3
"""Regression checks for crawl quality and AdSense delivery prerequisites."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

htaccess = (ROOT / ".htaccess").read_text(encoding="utf-8")
assert "pagead2.googlesyndication.com" in htaccess
assert "googleads.g.doubleclick.net" in htaccess
assert "tpc.googlesyndication.com" in htaccess

sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
assert "favorites.html" not in sitemap
assert "<lastmod>" not in sitemap, "Do not publish a fabricated common modification date"

for name in ("riders.html", "competitions.html", "brands.html"):
    source = (ROOT / name).read_text(encoding="utf-8")
    assert re.search(r"<h1(?:\s|>)", source), f"{name} needs a crawlable H1"
    words = re.sub(r"<[^>]+>", " ", source).split()
    assert len(words) >= 250, f"{name} remains too thin ({len(words)} words)"

for rider_page in (ROOT / "riders").glob("*.html"):
    source = rider_page.read_text(encoding="utf-8")
    empty = (
        "No public palmarès on file yet." in source
        and "No public equipment spec on file yet" in source
        and "No 2026 results recorded yet." in source
    )
    if empty:
        assert re.search(r'content="noindex,(?:follow|nofollow),noarchive"', source)
        assert rider_page.name not in sitemap

print("AdSense and SEO readiness checks passed.")
