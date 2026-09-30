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
}
for source, category in expected_drive.items():
    assert import_images.FOLDER_TO_CATEGORY[source] == category

expected_notion = {
    "Crankseat": "Crankset",
    "Gearbox": "Derailleur",
    "Hub": "Hub",
    "Spacer": "Spacer",
    "Stems": "Stem",
}
for source, category in expected_notion.items():
    assert sync_notion.CATEGORY_MAP[source] == category

print("equipment category mapping: passed")
