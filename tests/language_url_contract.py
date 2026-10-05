#!/usr/bin/env python3
"""Prevent crawlable query-string translations from returning."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
site_js = (ROOT / "assets/js/site.js").read_text(encoding="utf-8")
htaccess = (ROOT / ".htaccess").read_text(encoding="utf-8")

assert "searchParams.set('lang'" not in site_js
assert "searchParams.get('lang'" not in site_js
assert "guides/' + language[0] + '/'" in site_js
assert 'hreflang="' in site_js
assert "lang=(?:en|fr|de|es|it|pt|nl|pl|ja|zh-cn)" in htaccess
assert "[R=301,L,NE,QSD]" in htaccess

print("Language URL crawl contract checks passed.")
