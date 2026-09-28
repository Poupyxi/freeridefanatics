#!/usr/bin/env python3
"""Offline safety checks for the read-only Drive image synchronizer."""

import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("sync_drive_images", ROOT / "scripts" / "sync_drive_images.py")
sync_drive_images = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync_drive_images)


class DriveImageSyncTests(unittest.TestCase):
    def test_filename_separators_are_neutralized(self):
        self.assertEqual(sync_drive_images.safe_name("../rider.jpg"), ".._rider.jpg")
        self.assertEqual(sync_drive_images.safe_name("folder/image.webp"), "folder_image.webp")

    def test_empty_and_dot_names_are_rejected(self):
        for name in ("", ".", ".."):
            with self.subTest(name=name), self.assertRaises(ValueError):
                sync_drive_images.safe_name(name)

    def test_temporary_child_is_a_safe_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "drive-library"
            self.assertEqual(sync_drive_images.safe_output(target), target.resolve())

    def test_broad_targets_are_rejected(self):
        for target in (Path("/"), Path.home(), Path.cwd()):
            with self.subTest(target=target), self.assertRaises(ValueError):
                sync_drive_images.safe_output(target)


if __name__ == "__main__":
    unittest.main()
