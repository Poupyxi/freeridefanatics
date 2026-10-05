#!/usr/bin/env python3
"""Keep the UCI mountain tour on the complete Notion-backed round pages."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOUR = (ROOT / "assets/js/uci-iconic-tour.js").read_text(encoding="utf-8")
BUILD = (ROOT / "build.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/deploy-preprod-ovh.yml").read_text(encoding="utf-8")

CANONICAL = {
    "Mona Yongpyong": "mona-yongpyong.html",
    "Loudenvielle": "loudenvielle.html",
    "Leogang": "leogang.html",
    "Lenzerheide": "lenzerheide.html",
    "La Thuile": "la-thuile.html",
    "Pal Arinsal": "pal-arinsal.html",
    "Les Gets": "les-gets.html",
    "Whistler": "whistler.html",
    "Lake Placid": "lake-placid.html",
}

LEGACY = {
    "mona-yongpyong-south-korea-may.html": "mona-yongpyong.html",
    "loudenvielle-france-may.html": "loudenvielle.html",
    "leogang-austria-june.html": "leogang.html",
    "switzerland-june.html": "lenzerheide.html",
    "la-thuile-italy-july.html": "la-thuile.html",
    "andorra-july.html": "pal-arinsal.html",
}

for event, filename in CANONICAL.items():
    expected = f"'{event}': '/competitions/uci-mtb-world-cup-dh-2026/rounds/{filename}'"
    if expected not in TOUR:
        raise SystemExit(f"UCI tour does not link {event} to {filename}")

for old_filename in LEGACY:
    if f"/rounds/{old_filename}'" in TOUR:
        raise SystemExit(f"UCI tour still links the incomplete legacy page {old_filename}")

for config in (ROOT / ".htaccess", ROOT / "deploy/preprod.htaccess"):
    source = config.read_text(encoding="utf-8")
    for old_filename, new_filename in LEGACY.items():
        if old_filename.replace(".", r"\.") not in source or f"/rounds/{new_filename}" not in source:
            raise SystemExit(f"Missing UCI redirect in {config.name}: {old_filename}")

if 'uci-iconic-tour.js?v=9' not in BUILD or 'uci-iconic-tour.js?v=9' not in WORKFLOW:
    raise SystemExit("UCI tour cache version and preproduction validation are not aligned")

print("UCI tour links all nine events to the complete Notion-backed round pages.")
