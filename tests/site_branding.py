#!/usr/bin/env python3
"""Protect the shared site logo and favicon contract."""

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
LOGO = ROOT / "assets" / "img" / "brand" / "freeride-fanatics-summer.png"
TOUCH_ICON = ROOT / "assets" / "img" / "brand" / "freeride-fanatics-summer-180.png"
FAVICON = ROOT / "assets" / "img" / "favicon.ico"


assert LOGO.is_file() and LOGO.stat().st_size > 1_000
assert TOUCH_ICON.is_file() and TOUCH_ICON.stat().st_size > 1_000
assert FAVICON.is_file() and FAVICON.stat().st_size > 1_000

with Image.open(LOGO) as image:
    assert "A" in image.getbands(), "site logo must preserve alpha transparency"
    rgba = image.convert("RGBA")
    assert rgba.getpixel((0, 0))[3] == 0, "site logo exterior must be transparent"
    assert rgba.getpixel((rgba.width // 2, rgba.height // 2))[3] > 0, "site logo artwork is empty"

for relative in ("index.html", "riders.html", "competitions.html", "guides/en/index.html"):
    html = (ROOT / relative).read_text(encoding="utf-8")
    prefix = "../../" if relative.startswith("guides/") else ""
    assert f'{prefix}assets/img/favicon.ico' in html, relative
    assert f'{prefix}assets/img/brand/freeride-fanatics-summer.png' in html, relative
    assert '<span class="mark">R</span>' not in html, relative

print("site branding contract: OK")
