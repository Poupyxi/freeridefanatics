#!/usr/bin/env python3
"""Regression checks for season-scoped team standings."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build", ROOT / "build.py")
assert SPEC and SPEC.loader
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)

COMPETITION = "Test Series 2026"


def rider(name, points, team=None, *, gender="Men Elite", status="Finisher"):
    team_history = ([{"team": team, "season": COMPETITION}] if team else [])
    return {
        "display_name": name,
        "slug": BUILD.competition_round_slug(name),
        "gender_category": gender,
        "country": "France",
        "country_code": "FRA",
        "team": None,
        "team_history": team_history,
        "competition_history": [{
            "category": COMPETITION,
            "event": "Round One",
            "place": max(1, 201 - points) if status == "Finisher" else None,
            "points": points,
            "result": status,
            "status": status,
            "participated": True,
        }],
    }


class TeamStandingsTests(unittest.TestCase):
    def test_team_is_resolved_for_the_requested_season_only(self):
        athlete = rider("Season Rider", 100, "Test Factory")
        athlete["team_history"].append({
            "team": "Other Factory",
            "season": "Other Series 2027",
        })
        self.assertEqual(
            BUILD.rider_team_for_competition(athlete, COMPETITION),
            "Test Factory",
        )
        self.assertEqual(
            BUILD.rider_team_for_competition(athlete, "Other Series 2027"),
            "Other Factory",
        )
        self.assertIsNone(
            BUILD.rider_team_for_competition(athlete, "Unknown Series"),
        )

    def test_team_tab_does_not_require_fifty_percent_coverage(self):
        riders = [
            rider("Alpha One", 100, "Alpha Factory"),
            rider("Alpha Two", 60, "Alpha Factory", gender="Women Elite"),
            rider("Alpha DNF", 0, "Alpha Factory", status="DNF"),
            rider("Private One", 50),
            rider("Private Two", 40),
            rider("Private Three", 30),
            rider("Private Four", 20),
        ]
        html = BUILD.season_ranking_selector(riders, {
            "id": "test-series-2026",
            "name": COMPETITION,
        })
        self.assertIn('data-standings-group="Teams"', html)
        self.assertIn("Alpha Factory", html)
        self.assertIn("Alpha One, Alpha Two, Alpha DNF", html)
        self.assertIn("3 riders", html)
        self.assertIn("160<small>pts</small>", html)
        self.assertNotIn(">Privateer</strong>", html)
        self.assertIn("Every team-linked rider", html)


if __name__ == "__main__":
    unittest.main()
