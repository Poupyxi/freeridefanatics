#!/usr/bin/env python3
"""Ensure the live Notion export actually includes linked Winter rider gear."""
import json
import os
from pathlib import Path


path = Path(os.environ.get("RF_DATA_PATH", "data/notion/riders.json"))
riders = json.loads(path.read_text(encoding="utf-8"))
winter_riders = [
    rider for rider in riders
    if any("ski" in name.casefold() or "snowboard" in name.casefold()
           for name in rider.get("disciplines") or [])
]
linked = [rider for rider in winter_riders if rider.get("winter_equipment")]
assert winter_riders, "No Ski/Snowboard riders in the Notion snapshot"
assert linked, "Notion has Winter riders but exported no linked Winter equipment"
assert all(
    item.get("category") and (item.get("brand") or item.get("model_detail"))
    for rider in linked for item in rider["winter_equipment"]
)
print(
    f"Winter equipment snapshot: {len(linked)}/{len(winter_riders)} riders linked, "
    f"{sum(len(rider['winter_equipment']) for rider in linked)} items."
)
