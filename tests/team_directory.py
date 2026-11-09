#!/usr/bin/env python3
"""Team pages follow explicit Team–Rider–Season relations."""
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build


def rider(slug, name, team_history):
    return {
        "slug": slug,
        "display_name": name,
        "gender_category": "Men Elite",
        "country": "France",
        "team": team_history[-1]["team"],
        "team_history": team_history,
        "competition_history": [],
        "equipment": [],
    }


riders = [
    rider("alice", "Alice Rider", [
        {"team": "Team Alpha", "season": "UCI World Cup 2026"},
        {"team": "Team Beta", "season": "UCI World Cup 2027"},
    ]),
    rider("bob", "Bob Rider", [
        {"team": "Team Alpha", "season": "UCI World Cup 2026"},
    ]),
]

seasons = build.collect_team_seasons(riders)
assert sorted(seasons) == ["2026", "2027"]
assert sorted(seasons["2026"]) == ["Team Alpha"]
assert sorted(seasons["2027"]) == ["Team Beta"]
assert sorted(seasons["2026"]["Team Alpha"]["riders"]) == ["alice", "bob"]
assert sorted(seasons["2027"]["Team Beta"]["riders"]) == ["alice"]

directory = build.build_teams_directory(riders)
assert 'id="teams-2027"' in directory and 'id="teams-2026"' in directory
assert directory.index('id="teams-2027"') < directory.index('id="teams-2026"')
assert 'teams/2026/team-alpha.html' in directory
assert 'teams/2027/team-beta.html' in directory

assert os.environ.get("RF_BUILD_ENV") == "preprod"
print("Team directory keeps riders and teams separated by season.")
