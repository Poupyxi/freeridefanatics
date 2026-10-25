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
    "competition_history": [],
}
snowboard = {
    "slug": "snowboard-rider", "display_name": "Snowboard Rider", "disciplines": ["Snowboard Freeride"],
    "gender_category": "Men Elite", "equipment": [], "competition_history": [],
}

bike_competition = {"id": "bike-dh", "name": "Bike DH", "sport": "Mountain bike", "discipline": "Downhill"}
ski_competition = {"id": "ski-tour", "name": "Ski Tour", "sport": "Ski", "discipline": "Freeride"}
snowboard_competition = {"id": "snow-tour", "name": "Snow Tour", "sport": "Snowboard", "discipline": "Freeride"}

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

with patch.object(build, "IS_PREPROD", True), patch.object(build, "RIDER_COUNT", 3):
    riders_html = build.build_winter_riders_directory([ski, snowboard])
    assert "Ski Rider" in riders_html and "Snowboard Rider" in riders_html
    assert "Bike Rider" not in riders_html
    assert 'href="riders/ski-rider.html"' in riders_html
    assert 'data-season-route="riders"' in riders_html
    assert "season-routing.js" in riders_html

    rider_html = build.build_winter_rider_page(ski, {"Ski Tour"})
    assert "Ski Rider" in rider_html
    assert "Ski Freeride" in rider_html
    assert "Bike Downhill" not in rider_html
    assert "equip-item" not in rider_html
    assert "Setup analysis" not in rider_html

    equipment_html = build.build_winter_equipment_directory([ski])
    assert "Winter Brand" in equipment_html
    assert "Powder 110" in equipment_html
    assert "Bike Brand" not in equipment_html
    assert "DH Frame" not in equipment_html

print("Seasonal data views: Bike Summer and Ski/Snowboard Winter scopes passed.")
