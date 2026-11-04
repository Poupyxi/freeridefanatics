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


if __name__ == "__main__":
    unittest.main()
