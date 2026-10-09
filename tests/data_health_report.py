#!/usr/bin/env python3
"""Offline backtests for the private Data Health report."""

import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "data_health_report", ROOT / "scripts" / "data_health_report.py"
)
health = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(health)


class DataHealthReportTests(unittest.TestCase):
    def fixtures(self, root: Path):
        portraits = root / "portraits"
        actions = root / "actions"
        portraits.mkdir()
        actions.mkdir()
        (portraits / "complete-rider.jpg").write_bytes(b"image")
        riders = [
            {
                "slug": "complete-rider",
                "display_name": "Complete Rider",
                "gender_category": "Women Elite",
                "country": "France",
                "team": "Team One",
                "instagram": "@complete.rider",
                "competition_history": [{
                    "event": "Round One",
                    "category": "Test Series 2026",
                    "place": 1,
                    "status": "Finisher",
                    "participated": True,
                    "stages": {
                        "Qualifier": {"place": 2},
                        "Final": {"place": 1},
                    },
                }],
                "equipment": [{
                    "category": "Frame",
                    "brand": "Brand",
                    "model_detail": "Model;red",
                }],
            },
            {
                "slug": "incomplete-rider",
                "display_name": "Incomplete Rider",
                "gender_category": "Men Elite",
                "country": "",
                "team": None,
                "instagram": None,
                "competition_history": [],
                "equipment": [],
            },
        ]
        competitions = {
            "series": [{
                "id": "test-series-2026",
                "name": "Test Series 2026",
                "events": [{"name": "Round One"}],
            }],
        }
        drive = {
            "image_count": 3,
            "files": [
                {"path": "PPRiders/complete_rider.webp"},
                {"path": "PPRiders/orphan.webp"},
                {"path": "Equipment/Frame/Brand;Model.webp"},
            ],
        }
        return riders, competitions, drive, portraits, actions

    def test_report_counts_coverage_and_actionable_gaps(self):
        with tempfile.TemporaryDirectory() as directory:
            riders, competitions, drive, portraits, actions = self.fixtures(Path(directory))
            report = health.analyze(
                riders,
                competitions,
                drive,
                portrait_dir=portraits,
                action_dir=actions,
                equipment_resolver=lambda item: "frame-brand-model.jpg",
                generated_at="2026-10-09T08:00:00+00:00",
            )
            self.assertEqual(report["counts"]["riders"], 2)
            self.assertEqual(report["counts"]["results"], 1)
            self.assertEqual(report["counts"]["participations"], 1)
            self.assertEqual(report["counts"]["qualifier_results"], 1)
            self.assertEqual(report["counts"]["final_results"], 1)
            self.assertEqual(report["coverage"]["profile_picture_percent"], 50.0)
            self.assertEqual(report["coverage"]["equipment_image_percent"], 100.0)
            self.assertEqual(report["issue_counts"]["riders_without_country"], 1)
            self.assertEqual(report["issue_counts"]["riders_without_results"], 1)
            self.assertEqual(report["issue_counts"]["unmatched_drive_portraits"], 1)
            self.assertEqual(report["status"], "attention")
            markdown = health.markdown_report(report)
            self.assertIn("# RidersFanatics Data Health", markdown)
            self.assertIn("| Riders | 2 |", markdown)
            self.assertIn("Incomplete Rider", markdown)

    def test_dns_is_not_counted_but_dnf_and_dsq_are_participations(self):
        rows = [
            {"status": "DNS", "participated": False},
            {"status": "DNF", "participated": True},
            {"status": "DSQ", "participated": True},
        ]
        self.assertEqual([health.counts_as_participation(row) for row in rows], [False, True, True])

    def test_manifest_count_mismatch_is_rejected(self):
        with self.assertRaises(ValueError):
            health.drive_inventory({"image_count": 2, "files": [{"path": "PPRiders/a.jpg"}]})

    def test_cli_equipment_resolver_loads_build_from_the_repository_root(self):
        with tempfile.TemporaryDirectory() as directory:
            resolve = health.cli_equipment_resolver(Path(directory))
            self.assertIsNone(resolve({
                "category": "Frame",
                "brand": "Missing Brand",
                "model_detail": "Missing Model",
            }))

    def test_duplicate_slugs_are_critical(self):
        with tempfile.TemporaryDirectory() as directory:
            riders, competitions, drive, portraits, actions = self.fixtures(Path(directory))
            riders[1]["slug"] = riders[0]["slug"]
            report = health.analyze(
                riders,
                competitions,
                drive,
                portrait_dir=portraits,
                action_dir=actions,
                equipment_resolver=lambda item: None,
                generated_at="2026-10-09T08:00:00+00:00",
            )
            self.assertEqual(report["status"], "critical")
            self.assertEqual(report["issue_counts"]["duplicate_slugs"], 1)


if __name__ == "__main__":
    unittest.main()
