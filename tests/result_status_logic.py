#!/usr/bin/env python3
"""Regression checks for Notion race-status normalization."""
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("sync_notion", ROOT / "scripts" / "sync_notion.py")
sync_notion = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync_notion)
BUILD_SPEC = importlib.util.spec_from_file_location("build", ROOT / "build.py")
build = importlib.util.module_from_spec(BUILD_SPEC)
BUILD_SPEC.loader.exec_module(build)


def scoring_row(time_value=None, status_value=None):
    properties = {}
    if time_value is not None:
        properties["Time"] = {
            "type": "rich_text",
            "rich_text": [{"plain_text": time_value}],
        }
    if status_value is not None:
        properties["Status"] = {
            "type": "select",
            "select": {"name": status_value},
        }
    return {"properties": properties}


class ResultStatusTests(unittest.TestCase):
    def test_statuses_stored_in_time_are_canonical(self):
        expected = {
            "Finisher": "Finisher",
            "DNF": "DNF",
            "DNS": "DNS",
            "DSQ": "DSQ",
            "DQ": "DSQ",
        }
        for raw, canonical in expected.items():
            with self.subTest(raw=raw):
                self.assertEqual(sync_notion.scoring_status(scoring_row(raw)), canonical)

    def test_dedicated_status_property_is_supported(self):
        self.assertEqual(sync_notion.scoring_status(scoring_row(status_value="Disqualified")), "DSQ")

    def test_place_or_race_time_implies_finisher(self):
        self.assertEqual(sync_notion.scoring_status(scoring_row(), place=12), "Finisher")
        self.assertEqual(sync_notion.scoring_status(scoring_row("4:04.375")), "Finisher")

    def test_empty_roster_row_has_no_invented_status(self):
        self.assertIsNone(sync_notion.scoring_status(scoring_row()))

    def test_finisher_dnf_and_dsq_count_as_participation_in_every_phase(self):
        for phase in ("Qualifier", "Final"):
            for status in ("Finisher", "DNF", "DSQ"):
                with self.subTest(phase=phase, status=status):
                    self.assertTrue(sync_notion.scoring_counts_as_participation(phase, status))

    def test_dns_never_counts_as_participation(self):
        for phase in ("Qualifier", "Final"):
            with self.subTest(phase=phase):
                self.assertFalse(sync_notion.scoring_counts_as_participation(phase, "DNS"))

    def test_dns_is_visible_but_not_a_participation_or_ranking(self):
        dns = {"status": "DNS", "result": "DNS", "place": None,
               "points": None, "participated": False}
        self.assertEqual(build.result_status(dns), "DNS")
        self.assertFalse(build.result_counts_as_start(dns))
        self.assertFalse(build.result_is_rankable(dns))

    def test_dnf_and_dsq_count_as_starts(self):
        for status in ("DNF", "DSQ"):
            with self.subTest(status=status):
                result = {"status": status, "result": status, "place": None,
                          "points": None, "participated": True}
                self.assertTrue(build.result_counts_as_start(result))
                self.assertFalse(build.result_is_rankable(result))

    def test_placed_finisher_is_rankable_and_sorts_before_statuses(self):
        rider = {"display_name": "Finisher"}
        finisher = {"status": "Finisher", "place": 12, "points": 0,
                    "participated": True}
        dnf = {"status": "DNF", "place": None, "points": 0,
               "participated": True}
        self.assertTrue(build.result_is_rankable(finisher))
        self.assertLess(build.round_result_sort_key((rider, finisher)),
                        build.round_result_sort_key((rider, dnf)))

    def test_phase_result_preserves_individual_points(self):
        result = {
            "points": 225,
            "stages": {
                "Qualifier": {"place": 1, "points": 25, "result": "1st"},
                "Final": {"place": 1, "points": 200, "result": "1st"},
            },
        }
        self.assertEqual(build.result_stage(result, "Qualifier")["points"], 25)
        self.assertEqual(build.result_stage(result, "Final")["points"], 200)
        self.assertEqual(result["points"], 225)

    def test_legacy_combined_result_is_a_final_fallback(self):
        result = {"place": 2, "points": 160, "result": "2nd"}
        self.assertIs(build.result_stage(result, "Final"), result)
        self.assertIsNone(build.result_stage(result, "Qualifier"))

    def test_round_page_renders_qualifier_and_final_selectors(self):
        qualifier = {
            "place": 1, "points": 25, "result": "1st",
            "status": "Finisher", "participated": True,
        }
        final = {
            "place": 2, "points": 160, "result": "2nd",
            "status": "Finisher", "participated": True,
        }
        rider = {
            "display_name": "Test Rider",
            "slug": "test-rider",
            "gender_category": "Men Elite",
            "team": "Test Team",
            "country": "France",
            "competition_history": [{
                "year": 2026,
                "event": "Test Round",
                "category": "Test Series 2026",
                "place": 2,
                "points": 185,
                "result": "2nd",
                "status": "Finisher",
                "participated": True,
                "stages": {"Qualifier": qualifier, "Final": final},
            }],
        }
        competition = {
            "id": "test-series-2026",
            "name": "Test Series 2026",
            "season": 2026,
            "discipline": "Downhill",
            "events": [{"name": "Test Round", "date": "2026-06-01"}],
        }
        html = build.build_competition_round(
            [rider], competition, "Test Round", 1, ["Test Round"]
        )
        self.assertIn('data-standing-stage-filters', html)
        self.assertIn('data-standing-stage="Qualifier"', html)
        self.assertIn('data-standing-stage="Final"', html)
        self.assertIn('<td class="round-points">25</td>', html)
        self.assertIn('<td class="round-points">160</td>', html)


if __name__ == "__main__":
    unittest.main()
