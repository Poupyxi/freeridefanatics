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
older_competition = {
    "id": "uci-test-2025",
    "name": "UCI Test 2025",
    "short_name": "UCI Test 2025",
    "season": 2025,
}
non_uci_competition = {
    "id": "redbull-test",
    "name": "Red Bull Test",
    "short_name": "Red Bull Test",
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
        {"category": older_competition["name"], "event": "Old Round", "place": 2, "points": 80},
        {"category": non_uci_competition["name"], "event": "Urban Round", "place": 1, "points": 999},
    ]),
]

with patch.object(build, "COMPETITIONS", [competition, older_competition, non_uci_competition]):
    html = build.build_rankings_section(riders)

assert "DH Rankings" in html
assert "General and completed events" not in html
assert "UCI Test ·" not in html
assert 'data-home-ranking-competition=' not in html
assert 'data-home-ranking-view="global"' in html
assert 'data-home-ranking-view="round-one"' in html
assert "Round One" in html
assert "Round Two" not in html  # qualifier only: the event is not finished
assert "Man One" in html and "Woman One" in html
assert "100 pts" in html
assert 'data-ranking-competition=' not in html
assert 'data-ranking-view="round-one"' in html
assert "home-event-slider" in html
assert "Men General Ranking" in html
assert "Women General Ranking" in html
assert "Team General Ranking" in html
global_panel = html.split('data-ranking-view="global"', 1)[1]
assert global_panel.index("Men General Ranking") < global_panel.index("Women General Ranking")
assert global_panel.index("Women General Ranking") < global_panel.index("Team General Ranking")
assert "999 pts" not in html
assert "Old Round" not in html
print("Homepage event rankings: finished-event slider passed.")
