#!/usr/bin/env python3
"""Regression checks for priority competition and rider SEO output."""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import build

# Keep the regression test independent from Drive-backed image synchronization.
build.load_competition_logos = lambda: {}


def sample_rider(event, competition_name):
    return {
        "display_name": "Sample Rider",
        "slug": "sample-rider",
        "gender_category": "Men Elite",
        "country": "Canada",
        "country_code": "CAN",
        "team": "Sample Factory Team",
        "competition_history": [{
            "category": competition_name,
            "event": event,
            "year": 2026,
            "place": 1,
            "points": 200,
        }],
        "equipment": [],
    }


def assert_round(competition, event, expected_title, expected_heading):
    rider = sample_rider(event, competition["name"])
    html = build.build_competition_round([rider], competition, event, 1, [event])
    assert f"<title>{expected_title}</title>" in html
    assert expected_heading in html
    assert "round-seo-context" in html
    return html


uci = {
    "id": "uci-mtb-world-cup-dh-2026",
    "name": "UCI World Series 2026",
    "sport": "Mountain bike",
    "discipline": "Downhill",
    "season": 2026,
    "events": [],
}
assert_round(
    uci,
    "Whistler",
    "UCI Downhill Whistler 2026 Results | Riders &amp; Rankings",
    "Whistler UCI Downhill World Cup 2026",
)

build.IS_PREPROD = True
uci["events"] = [{
    "name": "Lake Placid",
    "date": "2026-10-03",
    "location": "Lake Placid, New York, USA",
}]
assert build.competition_page_events([], uci) == ["Lake Placid"]
lake_placid_html = build.build_competition_round([], uci, "Lake Placid", 1, ["Lake Placid"])
assert "<title>Lake Placid 2026 | Upcoming UCI Downhill Event</title>" in lake_placid_html
assert "Coming soon" in lake_placid_html
assert '"@type": "SportsEvent"' in lake_placid_html
assert "No verified rider results are recorded yet" in lake_placid_html

red_bull = {
    "id": "redbull-2026",
    "name": "RedBull 2026",
    "sport": "Mountain bike",
    "discipline": "Freeride",
    "season": 2026,
    "events": [
        {"name": "Rampage 2026", "date": "2026-10-08", "location": "Utah, USA"},
        {"name": "Hardline 2026", "date": "2026-10-17", "location": "British Columbia, Canada"},
    ],
}
rampage_html = assert_round(
    red_bull,
    "Rampage 2026",
    "Red Bull Rampage 2026 | Riders, Results &amp; Rankings",
    "Red Bull Rampage 2026 riders and results",
)
hardline_html = assert_round(
    red_bull,
    "Hardline 2026",
    "Red Bull Hardline 2026 | Riders, Results &amp; Rankings",
    "Red Bull Hardline 2026 riders and results",
)
assert '"@type": "SportsEvent"' in rampage_html
assert '"@type": "SportsEvent"' in hardline_html

priority_riders = {
    "valentina-holl": "Valentina Höll Bike Check 2026 | UCI DH Results",
    "gracey-hemstreet": "Gracey Hemstreet Bike Check 2026 | Results & Setup",
    "lisa-bouladou": "Lisa Bouladou 2026 | DH Results & Bike Check",
    "asa-vermette": "Asa Vermette Bike Check 2026 | Results & Equipment",
    "amaury-pierron": "Amaury Pierron Bike Check 2026 | UCI DH Results",
    "max-alran": "Max Alran Bike Check 2026 | UCI DH Results",
}
for slug, expected in priority_riders.items():
    rider = {
        "display_name": expected.split(" Bike")[0].split(" 2026")[0],
        "slug": slug,
        "team": "Factory Team",
        "competition_history": [{"points": 100}],
    }
    title, description = build.rider_seo_metadata(
        rider, [{"category": "Frame"}], rider["competition_history"], 1, ["Bike Frame"],
    )
    assert title == expected
    assert rider["display_name"] in description

print("Priority competition and rider SEO checks passed.")
