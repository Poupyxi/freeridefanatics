#!/usr/bin/env python3
"""Redirect sources must stay out of the generated production sitemap."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITEMAP = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
GENERATOR = (ROOT / "build_seo_guides.py").read_text(encoding="utf-8")

REDIRECTS = {
    "andorra-july.html": "pal-arinsal.html",
    "la-thuile-italy-july.html": "la-thuile.html",
    "leogang-austria-june.html": "leogang.html",
    "loudenvielle-france-may.html": "loudenvielle.html",
    "mona-yongpyong-south-korea-may.html": "mona-yongpyong.html",
    "switzerland-june.html": "lenzerheide.html",
}

for legacy, canonical in REDIRECTS.items():
    assert legacy not in SITEMAP, f"Redirect source is still in sitemap: {legacy}"
    assert legacy in GENERATOR, f"Generator does not explicitly filter: {legacy}"

print("Sitemap redirect-source checks passed.")
