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

    def test_notion_annotation_only_contains_audit_fields(self):
        payload = ANNOTATE.property_payload(
            {"status": "found", "match_type": "alias", "drive_url": "https://drive.google.com/open?id=x"},
            "2026-11-04T00:00:00+00:00",
        )
        self.assertEqual(set(payload), ANNOTATE.LINK_FIELDS)
        self.assertEqual(payload["Photo status"]["select"]["name"], "Alias")
        self.assertFalse(payload["Needs review"]["checkbox"])

    def test_annotation_targets_equipment_rows_and_aggregates_relations(self):
        build = ANNOTATE.load_build_module()
        self.assertIn("equipment", ANNOTATE.DATA_SOURCES)
        self.assertNotIn("equipment_links", ANNOTATE.DATA_SOURCES)
        rows = [
            {"category": "Frame", "brand": "Acme", "reference": "DH 1", "status": "found", "match_type": "exact", "drive_url": "https://drive.google.com/open?id=ok"},
            {"category": "Frame", "brand": "Acme", "reference": "DH 1", "status": "missing", "match_type": "none", "drive_url": ""},
        ]
        key, result = next(iter(ANNOTATE.aggregate_rows(build, rows).items()))
        self.assertEqual(key[0], "Frame")
        self.assertEqual(result["status"], "missing")
        self.assertEqual(result["missing_relations"], 1)
        self.assertEqual(result["drive_url"], "https://drive.google.com/open?id=ok")


if __name__ == "__main__":
    unittest.main()
