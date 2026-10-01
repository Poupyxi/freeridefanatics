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

    def test_public_mirror_requires_the_exact_generated_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            accepted = root / "assets" / "img" / "drive-library"
            self.assertEqual(sync_drive_images.safe_public_mirror(accepted), accepted.resolve())
            for rejected in (root / "assets", root / "assets" / "img", root / "drive-library"):
                with self.subTest(rejected=rejected), self.assertRaises(ValueError):
                    sync_drive_images.safe_public_mirror(rejected)

    def test_source_version_is_stable_and_changes_with_drive_metadata(self):
        first = {
            "path": "PPRiders/rider.webp",
            "drive_id": "drive-1",
            "mime_type": "image/webp",
            "modified_time": "2026-10-01T00:00:00Z",
            "drive_md5": "abc",
            "size": 42,
        }
        second = {**first, "path": "Equipment/Frame/frame.webp", "drive_id": "drive-2"}
        baseline = sync_drive_images.source_version([first, second])
        self.assertEqual(baseline, sync_drive_images.source_version([second, first]))
        self.assertNotEqual(
            baseline,
            sync_drive_images.source_version([first, {**second, "drive_md5": "changed"}]),
        )

    def test_inventory_reads_metadata_without_downloading_files(self):
        original = sync_drive_images.list_children
        tree = {
            "root": [
                {"id": "folder-1", "name": "PPRiders", "mimeType": sync_drive_images.FOLDER_MIME},
                {"id": "ignored", "name": "notes.txt", "mimeType": "text/plain"},
            ],
            "folder-1": [{
                "id": "image-1",
                "name": "Rider.webp",
                "mimeType": "image/webp",
                "modifiedTime": "2026-10-01T00:00:00Z",
                "md5Checksum": "abc",
                "size": "123",
            }],
        }
        try:
            sync_drive_images.list_children = lambda _service, folder_id: iter(tree[folder_id])
            records = sync_drive_images.inventory_folder(object(), "root")
        finally:
            sync_drive_images.list_children = original
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["path"], "PPRiders/Rider.webp")
        self.assertEqual(records[0]["size"], 123)


if __name__ == "__main__":
    unittest.main()
