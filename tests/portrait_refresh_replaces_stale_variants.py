#!/usr/bin/env python3
"""A forced Drive refresh must not leave an older preferred WebP behind."""

import tempfile
from pathlib import Path
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import import_images


with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    source = root / "PictureFaceRiders"
    output = root / "riders-action"
    source.mkdir()
    output.mkdir()

    Image.new("RGB", (80, 120), "blue").save(source / "@lisabaumann.jpg")
    Image.new("RGB", (20, 20), "red").save(output / "lisa-baumann.webp")

    imported, missing = import_images.import_riders(
        [{
            "slug": "lisa-baumann",
            "display_name": "Lisa Baumann",
            "instagram": "@lisabaumann",
        }],
        str(source),
        str(output),
        "page portraits",
        False,
        True,
        False,
        prune=True,
    )

    assert imported == ["lisa-baumann"]
    assert missing == []
    assert (output / "lisa-baumann.jpg").is_file()
    assert not (output / "lisa-baumann.webp").exists()

print("Forced portrait refresh removes stale preferred variants.")
