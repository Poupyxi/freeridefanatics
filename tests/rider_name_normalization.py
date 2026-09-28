#!/usr/bin/env python3
"""Checks public rider names exported from Notion."""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

from sync_notion import display_rider_name


cases = {
    "HÖLL Valentina": "Valentina Höll",
    "Hemstreet Gracey": "Hemstreet Gracey",
    "BOULADOU Lisa": "Lisa Bouladou",
    "VERMETTE Asa": "Asa Vermette",
    "PIERRON Amaury": "Amaury Pierron",
    "ALRAN Max": "Max Alran",
    "O' CONNOR Isla": "Isla O'Connor",
    "Luke Meier-Smith": "Luke Meier-Smith",
}

for source, expected in cases.items():
    actual = display_rider_name(source)
    assert actual == expected, f"{source!r}: expected {expected!r}, got {actual!r}"

print("Rider name normalization checks passed.")
