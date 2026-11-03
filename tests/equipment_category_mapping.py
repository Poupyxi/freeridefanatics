#!/usr/bin/env python3
"""Keep Drive folder and Notion equipment category aliases aligned."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import import_images


spec = importlib.util.spec_from_file_location("sync_notion", ROOT / "scripts" / "sync_notion.py")
sync_notion = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(sync_notion)

expected_drive = {
    "Crankseat": "Crankset",
    "Gearbox": "Derailleur",
    "Hub": "Hub",
    "Spacer": "Spacer",
    "Stems": "Stem",
    "Seat Clamp": "SeatClamp",
}
for source, category in expected_drive.items():
    assert import_images.FOLDER_TO_CATEGORY[source] == category

expected_notion = {
    "Crankseat": "Crankset",
    "Gearbox": "Derailleur",
    "Hub": "Hub",
    "Spacer": "Spacer",
    "Stems": "Stem",
    "Seat Clamp": "SeatClamp",
}
for source, category in expected_notion.items():
    assert sync_notion.CATEGORY_MAP[source] == category

amaury_frame = import_images.pick_photo(
    [{
        "brand": "commencal",
        "model": "supreme dh v5 2 pure white 2027 amaury pierron",
        "full": "commencal supreme dh v5 2 pure white 2027 amaury pierron",
        "path": "/drive/frame.png",
        "name": "COMMENCAL_SUPREME DH V5.2 PURE WHITE 2027 AmauryPierron.png",
    }],
    "commencal",
    "cadre commencal supreme dh v5 2 pure white 2027 amaury pierron",
)
assert amaury_frame and amaury_frame["name"].endswith("AmauryPierron.png")

print("equipment category mapping: passed")
