#!/usr/bin/env python3
"""Backtest rollback artifact integrity and archive traversal defenses."""

import hashlib
import importlib.util
import io
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("restore_snapshot", ROOT / "scripts" / "restore_snapshot.py")
restore_snapshot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(restore_snapshot)


class RestoreSnapshotTests(unittest.TestCase):
    def artifact(self, root: Path, unsafe: bool = False, corrupt: bool = False) -> Path:
        artifact = root / "artifact"
        artifact.mkdir()
        archive = artifact / "public-site.tar"
        with tarfile.open(archive, "w") as bundle:
            for name in restore_snapshot.REQUIRED_FILES:
                payload = b"ok"
                info = tarfile.TarInfo(name=name)
                info.size = len(payload)
                bundle.addfile(info, io.BytesIO(payload))
            if unsafe:
                payload = b"escape"
                info = tarfile.TarInfo(name="../escape.txt")
                info.size = len(payload)
                bundle.addfile(info, io.BytesIO(payload))
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        if corrupt:
            digest = "0" * 64
        (artifact / "rollback-metadata.txt").write_text(
            f"run_id=123\narchive_sha256={digest}\n",
            encoding="utf-8",
        )
        return artifact

    def test_valid_snapshot_is_restored(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "restore"
            restore_snapshot.restore(self.artifact(root), "123", destination)
            for name in restore_snapshot.REQUIRED_FILES:
                self.assertTrue((destination / name).is_file())

    def test_checksum_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ValueError, "checksum"):
                restore_snapshot.restore(self.artifact(root, corrupt=True), "123", root / "restore")

    def test_path_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ValueError, "Unsafe archive path"):
                restore_snapshot.restore(self.artifact(root, unsafe=True), "123", root / "restore")


if __name__ == "__main__":
    unittest.main()
