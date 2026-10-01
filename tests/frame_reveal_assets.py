#!/usr/bin/env python3
"""Ensure every generated frame photo has fresh reveal animation assets."""

import os
from pathlib import Path
from xml.etree import ElementTree

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
EQUIPMENT = Path(os.environ.get(
    "RF_EQUIPMENT_IMAGE_DIR",
    ROOT / "assets" / "img" / "equipment",
)).resolve()
REVEAL = EQUIPMENT / "reveal"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".avif"}

frames = sorted(
    path for path in EQUIPMENT.iterdir()
    if path.is_file() and path.name.startswith("frame-") and path.suffix.lower() in IMAGE_EXTENSIONS
)
assert frames, "No generated frame image was found"

validated = set()
for frame in frames:
    stem = frame.stem
    if stem in validated:
        continue
    sketch = REVEAL / f"{stem}-sketch.png"
    drawing = REVEAL / f"{stem}-draw.svg"
    assert sketch.is_file() and sketch.stat().st_size > 0, f"Missing frame sketch: {sketch.name}"
    assert drawing.is_file() and drawing.stat().st_size > 0, f"Missing frame animation: {drawing.name}"
    assert sketch.stat().st_mtime_ns >= frame.stat().st_mtime_ns, f"Stale frame sketch: {sketch.name}"
    assert drawing.stat().st_mtime_ns >= frame.stat().st_mtime_ns, f"Stale frame animation: {drawing.name}"
    with Image.open(sketch) as image:
        image.verify()
    root = ElementTree.parse(drawing).getroot()
    paths = [element for element in root.iter() if element.tag.endswith("path")]
    assert paths, f"Frame animation has no drawing paths: {drawing.name}"
    svg_text = drawing.read_text(encoding="utf-8")
    assert "@keyframes draw" in svg_text and "stroke-dashoffset" in svg_text
    validated.add(stem)

print(f"Frame reveal validation passed for {len(validated)} frames")
