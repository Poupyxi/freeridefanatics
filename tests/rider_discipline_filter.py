#!/usr/bin/env python3
"""Bike pages include Bike Downhill riders, including multisport athletes."""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import build


assert build.rider_has_discipline({"disciplines": ["Bike Downhill"]})
assert build.rider_has_discipline({
    "disciplines": ["Bike Downhill", "Ski Freeride"],
})
assert not build.rider_has_discipline({"disciplines": ["Ski Freeride"]})
assert not build.rider_has_discipline({"disciplines": ["Snowboard Freeride"]})
assert not build.rider_has_discipline({"disciplines": ["Bike Enduro"]})
assert not build.rider_has_discipline({"disciplines": []})

# The repository fixture predates the Notion relation. Keep PR validation
# functional without weakening the strict matching used by live snapshots.
assert build.rider_has_discipline({
    "discipline": "UCI MTB World Cup Downhill (DH)",
})

print("Bike Downhill rider filter checks passed.")
