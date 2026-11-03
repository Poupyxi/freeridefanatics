#!/usr/bin/env python3
"""Protect the homepage's equipment-aware random rider selection."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from build import RANDOM_RIDER_EQUIPMENT_CHANCE, random_rider_button
RIDERS = [
    {"slug": "without-setup", "equipment": []},
    {
        "slug": "with-setup",
        "equipment": [{"category": "Frame", "brand": "Example", "model_detail": "DH"}],
    },
    {"slug": "empty-equipment-row", "equipment": [{}]},
]

markup = random_rider_button(RIDERS, solid=False)
assert 'data-random-rider="without-setup,with-setup,empty-equipment-row"' in markup
assert 'data-random-rider-priority="with-setup"' in markup
assert f'data-random-rider-priority-chance="{RANDOM_RIDER_EQUIPMENT_CHANCE}"' in markup
assert 0 < RANDOM_RIDER_EQUIPMENT_CHANCE < 1

baseline_equipment_probability = 1 / len(RIDERS)
weighted_equipment_probability = (
    RANDOM_RIDER_EQUIPMENT_CHANCE
    + (1 - RANDOM_RIDER_EQUIPMENT_CHANCE) * baseline_equipment_probability
)
assert weighted_equipment_probability > baseline_equipment_probability
assert weighted_equipment_probability >= RANDOM_RIDER_EQUIPMENT_CHANCE

script = (ROOT / "assets" / "js" / "site.js").read_text(encoding="utf-8")
assert "Math.random() < priorityChance" in script
assert "choices = slugs.filter" in script

print("equipment-aware random rider checks passed")
