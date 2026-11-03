#!/usr/bin/env python3
"""Winter pages contain only Ski/Snowboard records; Summer remains bike-only."""
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build
from scripts import sync_notion


bike = {
    "slug": "bike-rider", "display_name": "Bike Rider", "disciplines": ["Bike Downhill"],
    "gender_category": "Men Elite", "equipment": [], "competition_history": [],
}
ski = {
    "slug": "ski-rider", "display_name": "Ski Rider", "disciplines": ["Ski Freeride"],
    "gender_category": "Women Elite",
    "equipment": [
        {"category": "Skis", "brand": "Winter Brand", "model_detail": "Powder 110"},
        {"category": "Frame", "brand": "Bike Brand", "model_detail": "DH Frame"},
    ],
    "competition_history": [], "competition_memberships": ["Ski Tour - 2026"],
}
snowboard = {
    "slug": "snowboard-rider", "display_name": "Snowboard Rider", "disciplines": ["Snowboard Freeride"],
    "gender_category": "Men Elite", "equipment": [], "competition_history": [],
}

bike_competition = {"id": "bike-dh", "name": "Bike DH", "short_name": "Bike DH", "sport": "Mountain bike", "discipline": "Downhill", "season": 2026, "events": []}
ski_competition = {"id": "ski-tour", "name": "Ski Tour - 2026", "short_name": "Ski Tour -", "sport": "Ski", "discipline": "Freeride", "season": 2026, "events": [{"name": "Snow Test - 2026", "date": "2026-12-10", "location": "Alps"}]}
snowboard_competition = {"id": "snow-tour", "name": "Snow Tour", "short_name": "Snow Tour", "sport": "Snowboard", "discipline": "Freeride", "season": 2026, "events": []}

assert build.rider_has_discipline(bike)
assert not build.rider_has_discipline(ski)
assert build.rider_has_winter_discipline(ski, "ski")
assert build.rider_has_winter_discipline(snowboard, "snowboard")
assert build.competition_is_bike(bike_competition)
assert not build.competition_is_winter(bike_competition)
assert build.competition_is_winter(ski_competition)
assert build.competition_is_winter(snowboard_competition)
assert sync_notion.season_sport_and_discipline(["Ski Freeride"]) == ("Ski", "Ski Freeride")
assert sync_notion.season_sport_and_discipline(["Snowboard Freeride"]) == ("Snowboard", "Snowboard Freeride")
assert sync_notion.season_sport_and_discipline(["Bike Downhill"]) == ("Mountain bike", "Bike Downhill")
assert sync_notion.season_short_name("FreeRideWorldTour - 2027") == "FreeRideWorldTour"
assert sync_notion.instagram_handle("https://instagram.com/valid.handle") == "@valid.handle"
assert sync_notion.instagram_handle("@www.freerideworldtour.com") is None
assert sync_notion.instagram_handle("@kings-queens-corbets") is None
season_id = "4089cf6b-f148-8051-9dc5-d685f4e935ce"
season_relation = {"properties": {"☀️ Saison": {
    "type": "relation", "relation": [{"id": season_id}],
}}}
assert sync_notion.related_ids(
    season_relation, {season_id: {"name": "Winter Tour"}}, "☀️ Saison", "Season"
) == [season_id]

with patch.object(build, "IS_PREPROD", True), patch.object(build, "RIDER_COUNT", 3):
    riders_html = build.build_winter_riders_directory([ski, snowboard])
    assert "Ski Rider" in riders_html and "Snowboard Rider" in riders_html
    assert "Bike Rider" not in riders_html
    assert 'href="riders/ski-rider.html"' in riders_html
    assert 'data-season-route="riders"' in riders_html
    assert "season-routing.js" in riders_html
    summer_riders_html = build.build_riders_directory([bike], 0, 1)
    for shared_marker in ('class="directory-intro"', 'class="filters"', 'class="grid-riders" data-rider-grid'):
        assert shared_marker in riders_html and shared_marker in summer_riders_html

    rider_html = build.build_winter_rider_page(ski, {"Ski Tour"})
    assert "Ski Rider" in rider_html
    # The shared header intentionally contains a hidden Summer menu. Validate
    # the Winter page body rather than rejecting that navigation fallback.
    rider_main = rider_html.split("<main", 1)[1]
    assert "Bike Downhill" not in rider_main
    assert "Setup analysis" not in rider_html
    assert "Winter Brand" in rider_html
    assert "Bike Brand" not in rider_html

    equipment_html = build.build_winter_equipment_directory([ski])
    summer_equipment_html = build.build_equipment_directory([bike])
    assert "Winter Brand" in equipment_html
    assert "Powder 110" in equipment_html
    assert "Bike Brand" not in equipment_html
    assert "DH Frame" not in equipment_html
    for shared_marker in ('class="equipment-hero"', 'class="equipment-hero-stats"', 'class="section equipment-catalogue"'):
        assert shared_marker in equipment_html and shared_marker in summer_equipment_html

    competitions_html = build.build_winter_competitions_hub([ski], [ski_competition])
    summer_competitions_html = build.build_competitions_hub([bike], [bike_competition])
    for shared_marker in ('class="section competitions-list"', 'class="competition-grid"', 'class="competition-card'):
        assert shared_marker in competitions_html and shared_marker in summer_competitions_html
    assert "Ski Tour -</strong>" not in competitions_html
    assert "<strong>1</strong> rider" in competitions_html

    competition_html = build.build_winter_competition_page([ski], ski_competition)
    assert 'href="ski-tour/rounds/snow-test-2026.html"' in competition_html
    assert "View event" in competition_html
    assert 'href="ski-tour/riders.html"' in competition_html
    competition_riders_html = build.build_competition_riders([ski], ski_competition, winter=True)
    assert 'href="../../../winter/riders/ski-rider.html"' in competition_riders_html
    assert '/winter/competitions/ski-tour/riders.html' in competition_riders_html
    competition_round_html = build.build_competition_round(
        [ski], ski_competition, "Snow Test - 2026", 1, ["Snow Test - 2026"], winter=True
    )
    assert "Coming soon" in competition_round_html
    assert '/winter/competitions/ski-tour/rounds/snow-test-2026.html' in competition_round_html
    assert build.season_ranking_selector([ski], ski_competition) == ""

    with patch.object(build, "COMPETITIONS", [bike_competition, ski_competition, snowboard_competition]), \
         patch.object(build, "ORGANIZATIONS", []):
        seasonal_header = build.header_html("../", seasonal=True)
        summer_menu = seasonal_header.split('class="dropdown" data-season-scope="summer"', 1)[1].split('</div>\n        </div>', 1)[0]
        winter_menu = seasonal_header.split('class="dropdown" data-season-scope="winter" hidden', 1)[1].split('</div>\n        </div>', 1)[0]
        assert "Bike DH" in summer_menu
        assert "Ski Tour" not in summer_menu and "Snow Tour" not in summer_menu
        assert "Bike DH" not in winter_menu
        assert "Ski Tour" in winter_menu and "Snow Tour" in winter_menu
        assert '../winter/competitions/ski-tour.html' in winter_menu

print("Seasonal data views: Bike Summer and Ski/Snowboard Winter scopes passed.")
