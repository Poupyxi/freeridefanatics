#!/usr/bin/env python3
"""Regression checks for Notion team titles and renamed rider relations."""
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("sync_notion", ROOT / "scripts" / "sync_notion.py")
assert SPEC and SPEC.loader
SYNC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SYNC)


TEAM_ONE = "11111111-1111-1111-1111-111111111111"
TEAM_TWO = "22222222-2222-2222-2222-222222222222"
COUNTRY = "33333333-3333-3333-3333-333333333333"


def title_property(text):
    return {
        "type": "title",
        "title": [{"plain_text": text}],
    }


def relation_property(*identifiers):
    return {
        "type": "relation",
        "relation": [{"id": identifier} for identifier in identifiers],
    }


def main():
    team_pages = [
        {"id": TEAM_ONE, "properties": {"Name": title_property("Team One")}},
        {"id": TEAM_TWO, "properties": {"Official team": title_property("Team Two")}},
    ]
    teams = SYNC.title_map(team_pages, "Nom")
    assert teams == {TEAM_ONE: "Team One", TEAM_TWO: "Team Two"}

    rider = {
        "properties": {
            "country": relation_property(COUNTRY),
            "🚴 Current squad": relation_property(TEAM_ONE),
        }
    }
    assert SYNC.related_ids(rider, teams, "Team", "Teams") == [TEAM_ONE]

    # A relation to another database must never be mistaken for a team.
    unrelated = {"properties": {"Country": relation_property(COUNTRY)}}
    assert SYNC.related_ids(unrelated, teams, "Team", "Teams") == []

    # Preferred names remain supported when Notion uses the original schema.
    original = {"properties": {"Team": relation_property(TEAM_TWO)}}
    assert SYNC.related_ids(original, teams, "Team", "Teams") == [TEAM_TWO]
    assert SYNC.relation_schema_names([original], teams, "Team", "Teams") == ["Team"]
    assert SYNC.relation_schema_names([unrelated], teams, "Team", "Teams") == []

    seasons = {
        "44444444-4444-4444-4444-444444444444": {"name": "Season 2026"},
        "55555555-5555-5555-5555-555555555555": {"name": "Season 2027"},
    }
    rider_one = "66666666-6666-6666-6666-666666666666"
    rider_two = "77777777-7777-7777-7777-777777777777"
    complete_link = {"properties": {
        "👥 Team": relation_property(TEAM_ONE),
        "🚻 Riders": relation_property(rider_one, rider_two),
        "☀️ Saison": relation_property("44444444-4444-4444-4444-444444444444"),
    }}
    incomplete_link = {"properties": {
        "👥 Team": relation_property(TEAM_TWO),
        "🚻 Riders": relation_property(rider_one),
        "☀️ Saison": relation_property(),
    }}
    assignments, health = SYNC.team_season_assignments(
        [complete_link, incomplete_link], {rider_one, rider_two}, teams, seasons
    )
    assert assignments[rider_one] == [{"team": "Team One", "season": "Season 2026"}]
    assert assignments[rider_two] == [{"team": "Team One", "season": "Season 2026"}]
    assert health == {
        "assignment_rows": 2,
        "complete_rows": 1,
        "incomplete_rows": 1,
        "assignments": 2,
        "riders_with_team": 2,
        "conflicts": 0,
    }
    print("Notion team mapping: renamed titles and relations resolved safely")


if __name__ == "__main__":
    main()
