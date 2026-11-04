#!/usr/bin/env python3
"""Rider-named Drive photos must win without leaking names into labels."""

import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import build
import import_images


riders = [
    {"slug": "jordan-williams", "display_name": "Jordan Williams"},
    {"slug": "finn-iles", "display_name": "Finn Iles"},
]

assert import_images.rider_slug_from_equipment_filename(
    "Ohlins_DH38 m.2 Air TTX18_Jordan Williams", riders
) == "jordan-williams"
assert import_images.rider_slug_from_equipment_filename(
    "Ohlins_DH38 m.2 Air TTX18_Jordna Williams", riders
) == "jordan-williams"

candidates = [
    {"brand": "ohlins", "model": "dh38 m 2 air ttx18", "full": "ohlins dh38 m 2 air ttx18",
     "path": "/generic.png", "name": "generic.png", "rider_slug": ""},
    {"brand": "ohlins", "model": "dh38 m 2 air ttx18", "full": "ohlins dh38 m 2 air ttx18",
     "path": "/jordan.png", "name": "jordan.png", "rider_slug": "jordan-williams"},
]
assert import_images.pick_photo(
    candidates, "ohlins", "dh38 m 2 air ttx18 jordan williams", "jordan-williams"
)["path"] == "/jordan.png"
assert import_images.pick_photo(
    candidates, "ohlins", "dh38 m 2 air ttx18", "finn-iles"
)["path"] == "/generic.png"

assert build.equipment_model_without_rider(
    "DH38 m.2 Air TTX18 Jordan Williams", "Jordan Williams"
) == "DH38 m.2 Air TTX18"
assert build.equipment_model_without_rider(
    "Demo 11 LTD Williams Jordan", "Jordan Williams"
) == "Demo 11 LTD"

with tempfile.TemporaryDirectory() as temporary:
    original = build.EQUIP_IMG_DIR
    build.EQUIP_IMG_DIR = temporary
    try:
        filename = "fork-ohlins-dh38-m-2-air-ttx18-jordan-williams--jordan-williams.jpg"
        Path(temporary, filename).touch()
        assert build.has_equip_photo(
            "Fork", "Öhlins", "DH38 m.2 Air TTX18 Jordan Williams",
            "jordan-williams", "Jordan Williams",
        ) == filename
    finally:
        build.EQUIP_IMG_DIR = original

print("rider-specific equipment images: passed")
