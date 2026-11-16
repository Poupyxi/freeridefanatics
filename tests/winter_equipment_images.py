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
    ],
}

with tempfile.TemporaryDirectory() as directory:
    library = Path(directory) / "Equipment"
    for season, folder, filename in (
        ("Summer", "Frame", "Bike Brand;DH One.jpg"),
        ("Winter", "Ski", "Ski Brand;Powder One.jpg"),
        ("Winter", "Ski Bindings", "Binding Brand;Tour One.jpg"),
        ("Winter", "Snowboard", "Board Brand;Freeride One.jpg"),
    ):
        destination = library / season / folder / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"fixture")
    with patch.object(import_images, "SRC_EQUIP", str(library)), \
         patch.object(import_images, "OUT_EQUIP", str(Path(directory) / "site-equipment")), \
         patch.object(import_images, "validate_library_image"):
        index, skipped = import_images.index_library_equipment([rider])
        assert not skipped
        assert len(index["Frame"]) == len(index["Skis"]) == len(index["Bindings"]) == len(index["Snowboard"]) == 1
        matched, missing = import_images.import_equipment([rider], force=True, dry=True)
        assert not missing, missing
        assert len(matched) == 4, matched

print("Summer and Winter Drive equipment folders resolve to rider products")
