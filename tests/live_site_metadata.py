#!/usr/bin/env python3
"""Backtests for post-deployment rider count and freshness verification."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "verify_live_site_metadata", ROOT / "scripts" / "verify_live_site_metadata.py"
)
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class LiveSiteMetadataTests(unittest.TestCase):
    def fixture(self, directory: str):
        html = Path(directory) / "index.html"
        metadata = Path(directory) / "sync-metadata.json"
        html.write_text(
            '<span class="icon-btn">360 Riders</span>'
            '<time datetime="2026-10-07">7 Oct 2026</time>',
            encoding="utf-8",
        )
        metadata.write_text(json.dumps({
            "riders": 360,
            "generated_at": "2026-10-07T20:44:44.710488+00:00",
        }), encoding="utf-8")
        return html, metadata

    def test_matching_live_page_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            html, metadata = self.fixture(directory)
            verifier.verify_live_site(html, metadata)

    def test_wrong_count_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            html, metadata = self.fixture(directory)
            html.write_text(html.read_text().replace("360 Riders", "359 Riders"))
            with self.assertRaises(verifier.LiveMetadataError):
                verifier.verify_live_site(html, metadata)

    def test_wrong_date_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            html, metadata = self.fixture(directory)
            html.write_text(html.read_text().replace("7 Oct 2026", "6 Oct 2026"))
            with self.assertRaises(verifier.LiveMetadataError):
                verifier.verify_live_site(html, metadata)


if __name__ == "__main__":
    unittest.main()
