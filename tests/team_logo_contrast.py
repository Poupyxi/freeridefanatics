#!/usr/bin/env python3
"""Regression checks for automatic team-logo contrast classification."""

from __future__ import annotations

import importlib.util
import io
from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "sync_drive_logos", ROOT / "scripts" / "sync_drive_logos.py"
)
assert SPEC and SPEC.loader
SYNC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SYNC)


def logo_bytes(fill, accent=None):
    image = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 20, 70, 60), fill=fill)
    if accent:
        draw.rectangle((10, 20, 35, 60), fill=accent)
    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


class TeamLogoContrastTests(unittest.TestCase):
    def test_white_transparent_logo_requires_negative_filter(self):
        self.assertTrue(SYNC.needs_negative_filter(logo_bytes((255, 255, 255, 255))))

    def test_dark_logo_keeps_original_rendering(self):
        self.assertFalse(SYNC.needs_negative_filter(logo_bytes((20, 20, 20, 255))))

    def test_mixed_colour_logo_keeps_original_rendering(self):
        self.assertFalse(
            SYNC.needs_negative_filter(
                logo_bytes((255, 255, 255, 255), (184, 70, 28, 255))
            )
        )

    def test_local_sync_records_team_contrast_decision(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            for folder in ("Brand logo", "Competition logo", "Team logo"):
                (source / folder).mkdir(parents=True)
            (source / "Brand logo" / "Sample.png").write_bytes(
                logo_bytes((20, 20, 20, 255))
            )
            for key in SYNC.REQUIRED_COMPETITION_KEYS:
                (source / "Competition logo" / f"{key}.png").write_bytes(
                    logo_bytes((20, 20, 20, 255))
                )
            (source / "Team logo" / "White Factory.png").write_bytes(
                logo_bytes((255, 255, 255, 255))
            )
            manifest_path = root / "data" / "drive-logo-manifest.json"

            SYNC.synchronize(
                SYNC.local_sections(source), root, manifest_path, None
            )

            import json

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertTrue(manifest["logos"]["teams"][0]["negative_on_light"])


if __name__ == "__main__":
    unittest.main()
