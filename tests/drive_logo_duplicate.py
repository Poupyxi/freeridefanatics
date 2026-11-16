#!/usr/bin/env python3
"""Regression checks for duplicate Drive logo filenames."""

import importlib.util
import tempfile
from pathlib import Path


script = Path(__file__).resolve().parents[1] / "scripts" / "sync_drive_logos.py"
spec = importlib.util.spec_from_file_location("sync_drive_logos", script)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

records = [
    {"name": "CAST.png", "id": "older", "modifiedTime": "2026-01-01T00:00:00Z"},
    {"name": "cast.webp", "id": "newer", "modifiedTime": "2026-11-15T00:00:00Z"},
]
selected = module.unique_logo_records("brands", records)
assert len(selected) == 1
assert selected[0][0] == "cast"
assert selected[0][2]["id"] == "newer"
assert module.unique_logo_records("brands", list(reversed(records))) == selected

aliases = [
    {"name": "Forbiden.png", "id": "older", "modifiedTime": "2026-01-01T00:00:00Z"},
    {"name": "Forbidden.png", "id": "newer", "modifiedTime": "2026-11-15T00:00:00Z"},
]
assert module.unique_logo_records("brands", aliases)[0][:2] == ("forbidden", "Forbidden")

# The mirrored Drive library may contain SVGs, but this converter only reads
# formats supported by Pillow. A raster alternative must still be selected.
with tempfile.TemporaryDirectory() as directory:
    brand_folder = Path(directory) / "Brand logo"
    brand_folder.mkdir()
    (brand_folder / "Leki.svg").write_text("<svg/>", encoding="utf-8")
    (brand_folder / "Leki.png").write_bytes(b"raster-test")
    section, _, mirrored = next(module.local_sections(Path(directory)))
    assert section == "brands"
    assert [record["name"] for record in mirrored] == ["Leki.png"]
print("Duplicate Drive logo selection is deterministic")
