#!/usr/bin/env python3
"""Protect the shared site logo and favicon contract."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOGO = ROOT / "assets" / "img" / "brand" / "freeride-fanatics-summer.jpg"
TOUCH_ICON = ROOT / "assets" / "img" / "brand" / "freeride-fanatics-summer-180.png"
FAVICON = ROOT / "assets" / "img" / "favicon.ico"


assert LOGO.is_file() and LOGO.stat().st_size > 1_000
assert TOUCH_ICON.is_file() and TOUCH_ICON.stat().st_size > 1_000
assert FAVICON.is_file() and FAVICON.stat().st_size > 1_000

for relative in ("index.html", "riders.html", "competitions.html", "guides/en/index.html"):
    html = (ROOT / relative).read_text(encoding="utf-8")
    prefix = "../../" if relative.startswith("guides/") else ""
    assert f'{prefix}assets/img/favicon.ico' in html, relative
    assert f'{prefix}assets/img/brand/freeride-fanatics-summer.jpg' in html, relative
    assert '<span class="mark">R</span>' not in html, relative

print("site branding contract: OK")
