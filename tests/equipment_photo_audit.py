#!/usr/bin/env python3
"""Contract checks for the manual, read-only equipment photo audit."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "audit-equipment-photos.yml"
SPEC = importlib.util.spec_from_file_location("equipment_photo_audit", ROOT / "scripts" / "audit_equipment_photos.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)
ANNOTATE_SPEC = importlib.util.spec_from_file_location(
    "annotate_notion_equipment_photos",
    ROOT / "scripts" / "annotate_notion_equipment_photos.py",
)
ANNOTATE = importlib.util.module_from_spec(ANNOTATE_SPEC)
assert ANNOTATE_SPEC.loader is not None
ANNOTATE_SPEC.loader.exec_module(ANNOTATE)


class EquipmentPhotoAuditTests(unittest.TestCase):
    def test_workflow_is_manual_only_and_read_only(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("schedule:", workflow)
        self.assertNotIn("push:", workflow)
        self.assertNotIn("notion.pages.update", workflow)
        self.assertIn("ref: preprod", workflow)
        self.assertIn("equipment-photo-audit", workflow)

    def test_report_has_explicit_statuses(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "riders.json"
            source.write_text(json.dumps([{"slug": "test-rider", "display_name": "Test Rider", "equipment": []}]), encoding="utf-8")
            self.assertEqual(MODULE.read_json(source)[0]["slug"], "test-rider")
        self.assertIn("ambiguous", MODULE.markdown([], Path("/tmp/library")))
        self.assertIn("missing", MODULE.markdown([], Path("/tmp/library")))

    def test_cli_runs_from_repository_root_and_lists_unreferenced_drive_images(self):
        import subprocess
        import sys
        from PIL import Image

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fork_folder = root / "library" / "Equipment" / "Summer" / "Fork"
            fork_folder.mkdir(parents=True)
            Image.new("RGB", (8, 8)).save(fork_folder / "Fox;40 Factory.jpg")
            Image.new("RGB", (8, 8)).save(fork_folder / "Nobrand;Unlisted 9000.jpg")
            riders = root / "riders.json"
            riders.write_text(json.dumps([{
                "slug": "test-rider",
                "display_name": "Test Rider",
                "equipment": [{"category": "Fork", "brand": "Fox", "model_detail": "40 Factory"}],
            }]), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable, "scripts/audit_equipment_photos.py",
                    "--riders", str(riders),
                    "--drive-library", str(root / "library"),
                    "--output-json", str(root / "audit.json"),
                    "--output-csv", str(root / "audit.csv"),
                    "--output-markdown", str(root / "audit.md"),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads((root / "audit.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["counts"], {"found": 1})
            unreferenced = payload["drive_images_without_notion_reference"]
            self.assertEqual([item["drive_file"] for item in unreferenced],
                             ["Equipment/Summer/Fork/Nobrand;Unlisted 9000.jpg"])
            self.assertIn("Drive images without a Notion reference", (root / "audit.md").read_text(encoding="utf-8"))

    def test_notion_annotation_only_contains_audit_fields(self):
        payload = ANNOTATE.property_payload(
            {"status": "found", "match_type": "alias", "drive_url": "https://drive.google.com/open?id=x"},
            "2026-11-04T00:00:00+00:00",
        )
        self.assertEqual(set(payload), ANNOTATE.LINK_FIELDS)
        self.assertEqual(payload["Photo status"]["select"]["name"], "Alias")
        self.assertFalse(payload["Needs review"]["checkbox"])


if __name__ == "__main__":
    unittest.main()
