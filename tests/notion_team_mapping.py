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
    print("Notion team mapping: renamed titles and relations resolved safely")


if __name__ == "__main__":
    main()
