#!/usr/bin/env python3
"""Homepage DH rankings switch between completed events only."""
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build


competition = {
    "id": "uci-test",
    "name": "UCI Test 2026",
    "short_name": "UCI Test",
    "season": 2026,
}


def rider(slug, name, category, team, history):
    return {
        "slug": slug,
        "display_name": name,
        "gender_category": category,
        "team": team,
        "competition_history": history,
    }


riders = [
    rider("man-one", "Man One", "Men Elite", "Team A", [
        {"category": competition["name"], "event": "Round One", "place": 1, "points": 100},
        {"category": competition["name"], "event": "Round Two", "stages": {"Qualifier": {"place": 1}}},
    ]),
    rider("woman-one", "Woman One", "Women Elite", "Team B", [
        {"category": competition["name"], "event": "Round One", "place": 1, "points": 100},
    ]),
]

with patch.object(build, "CURRENT_COMPETITION", competition):
    html = build.build_rankings_section(riders)

assert "DH Event Rankings" in html
assert 'data-standings-comp="round-one"' in html
assert "Round One" in html
assert "Round Two" not in html  # qualifier only: the event is not finished
assert "Man One" in html and "Woman One" in html
assert "100 pts" in html
assert 'data-competition="round-one"' in html
assert "home-event-slider" in html
print("Homepage event rankings: finished-event slider passed.")
