#!/usr/bin/env python3
"""Drive's seasonal Equipment folders still resolve to Notion rider products."""

import tempfile
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import import_images


rider = {
    "slug": "winter-fixture", "display_name": "Winter Fixture",
    "equipment": [{"category": "Frame", "brand": "Bike Brand", "model_detail": "DH One"}],
    "winter_equipment": [
        {"category": "Skis", "brand": "Ski Brand", "model_detail": "Powder One"},
        {"category": "Bindings", "brand": "Binding Brand", "model_detail": "Tour One"},
        {"category": "Snowboard", "brand": "Board Brand", "model_detail": "Freeride One"},
        {"category": "Avalanche Safety", "brand": "Safety Brand", "model_detail": "Airbag One"},
        {"category": "Skis", "brand": "Majesty", "model_detail": "Vanguard 108 CTi Special Edition Zuza Witych"},
        {"category": "Skis", "brand": "Volkl", "model_detail": "Revolte 114_2025"},
        {"category": "Skis", "brand": "Volkl", "model_detail": "Revolte 114"},
        {"category": "Skis", "brand": "Headski", "model_detail": "KORE 112 Ti"},
        {"category": "Bindings", "brand": "Look", "model_detail": "PIVOT 2.0 15 GW B115 ORANGE METAL"},
        {"category": "Snowboard", "brand": "Headsnowboard", "model_detail": "E.B.I LYT_2027"},
    ],
}

with tempfile.TemporaryDirectory() as directory:
    library = Path(directory) / "Equipment"
    for season, folder, filename in (
        ("Summer", "Frame", "Bike Brand;DH One.jpg"),
        ("Winter", "Ski", "Ski Brand;Powder One.jpg"),
        ("Winter", "Ski Bindings", "Binding Brand;Tour One.jpg"),
        ("Winter", "Snowboard", "Board Brand;Freeride One.jpg"),
        ("Winter", "Avalanche Airbags", "Safety Brand;Airbag One.jpg"),
        ("Winter", "Ski", "MAJESTY_Vanguard 108 CTI Zuza Witych_2027_front.webp"),
        ("Winter", "Ski", "Volkl_Revolt 114_2025_front.webp"),
        ("Winter", "Ski", "Volkl_Revolt 114_front.webp"),
        ("Winter", "Ski", "Head_KORE 112 ti_2027_front.webp"),
        ("Winter", "Ski Bindings", "LOOK_PIVOT 2.0 15 GW ORANGE METAL.png"),
        ("Winter", "Snowboard", "HEAD_E.B.I LYT_front.png"),
    ):
        destination = library / season / folder / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"fixture")
    with patch.object(import_images, "SRC_EQUIP", str(library)), \
         patch.object(import_images, "OUT_EQUIP", str(Path(directory) / "site-equipment")), \
         patch.object(import_images, "validate_library_image"):
        index, skipped = import_images.index_library_equipment([rider])
        assert not skipped
        assert {category: len(index[category]) for category in (
            "Frame", "Skis", "Bindings", "Snowboard", "Avalanche Safety"
        )} == {"Frame": 1, "Skis": 5, "Bindings": 2, "Snowboard": 2, "Avalanche Safety": 1}
        matched, missing = import_images.import_equipment([rider], force=True, dry=True)
        assert not missing, missing
        assert len(matched) == 11, matched

print("Summer and Winter Drive equipment folders resolve to rider products")
