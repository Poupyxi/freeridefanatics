#!/usr/bin/env python3
"""Competition directories expose an automatic season-year selector."""
from pathlib import Path
import sys
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build


def competition(identifier, name, season):
    return {
        "id": identifier,
        "name": name,
        "short_name": name,
        "sport": "Mountain bike",
        "discipline": "Bike Downhill",
        "season": season,
        "events": [],
    }


events_2026 = competition("event-2026", "Event 2026", 2026)
events_2027 = competition("event-2027", "Event 2027", "Season 2027")
cross_year = competition("winter-tour", "Winter Tour 2026 2027", "2026/2027")

assert build.competition_season_years(events_2026) == ("2026",)
assert build.competition_season_years(events_2027) == ("2027",)
assert build.competition_season_years(cross_year) == ("2026", "2027")
assert build.competition_display_name(events_2026) == "Event"
assert build.competition_display_name(events_2027) == "Event"
assert build.competition_display_name(cross_year) == "Winter Tour"
assert build.competition_display_name(competition("project-17", "Project 17", 2026)) == "Project 17"

with patch.object(build, "load_competition_logos", return_value={}), \
     patch.object(build, "ORGANIZATIONS", []):
    html = build.build_competitions_hub([], [events_2026, events_2027, cross_year])

assert 'data-competition-year-filter' in html
assert '<option value="all">All seasons</option>' in html
assert '<option value="2027">2027</option>' in html
assert '<option value="2026">2026</option>' in html
assert 'data-competition-year="2026"' in html
assert 'data-competition-year="2027"' in html
assert 'data-competition-year="2026 2027"' in html
assert html.index('<option value="2027">') < html.index('<option value="2026">')
assert html.index('data-competition-year="2027"') < html.index('data-competition-year="2026"')
assert "Event 2026</h2>" not in html and "Event 2027</h2>" not in html
assert "Winter Tour 2026 2027</h2>" not in html

script = (ROOT / "assets" / "js" / "site.js").read_text(encoding="utf-8")
assert "safe('competition-year-filter'" in script
assert "years.indexOf(year) !== -1" in script

print("Competition year filter supports current, future and cross-year seasons.")
