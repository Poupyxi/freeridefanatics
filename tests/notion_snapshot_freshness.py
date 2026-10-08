#!/usr/bin/env python3
"""Backtests for the strict Notion snapshot deployment guard."""

import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "validate_notion_snapshot", ROOT / "scripts" / "validate_notion_snapshot.py"
)
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class SnapshotFreshnessTests(unittest.TestCase):
    NOW = dt.datetime(2026, 10, 8, 12, tzinfo=dt.timezone.utc)

    def fixture(self, directory: str, *, generated_at=None):
        riders_path = Path(directory) / "riders.json"
        metadata_path = Path(directory) / "sync-metadata.json"
        riders_path.write_text('[{"slug":"one"}]\n', encoding="utf-8")
        metadata = {
            "source": "notion-read-only",
            "profile_data_source": "notion-only",
            "image_source": "google-drive-only",
            "generated_at": generated_at or "2026-10-08T11:45:00+00:00",
            "riders": 1,
            "sha256": hashlib.sha256(riders_path.read_bytes()).hexdigest(),
        }
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
        return riders_path, metadata_path

    def test_valid_recent_snapshot_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            riders, metadata = self.fixture(directory)
            result = validator.validate_snapshot(riders, metadata, now=self.NOW)
            self.assertEqual(result["riders"], 1)

    def test_missing_metadata_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            riders, metadata = self.fixture(directory)
            metadata.unlink()
            with self.assertRaises(validator.SnapshotValidationError):
                validator.validate_snapshot(riders, metadata, now=self.NOW)

    def test_invalid_metadata_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            riders, metadata = self.fixture(directory)
            metadata.write_text("{broken", encoding="utf-8")
            with self.assertRaises(validator.SnapshotValidationError):
                validator.validate_snapshot(riders, metadata, now=self.NOW)

    def test_count_and_hash_mismatches_are_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            riders, metadata = self.fixture(directory)
            document = json.loads(metadata.read_text(encoding="utf-8"))
            for key, value in (("riders", 2), ("sha256", "0" * 64)):
                changed = dict(document)
                changed[key] = value
                metadata.write_text(json.dumps(changed), encoding="utf-8")
                with self.subTest(key=key), self.assertRaises(validator.SnapshotValidationError):
                    validator.validate_snapshot(riders, metadata, now=self.NOW)

    def test_stale_and_future_snapshots_are_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            riders, metadata = self.fixture(directory, generated_at="2026-10-06T11:59:00+00:00")
            with self.assertRaises(validator.SnapshotValidationError):
                validator.validate_snapshot(riders, metadata, max_age_hours=48, now=self.NOW)
            riders, metadata = self.fixture(directory, generated_at="2026-10-08T12:06:00+00:00")
            with self.assertRaises(validator.SnapshotValidationError):
                validator.validate_snapshot(riders, metadata, now=self.NOW)


if __name__ == "__main__":
    unittest.main()
