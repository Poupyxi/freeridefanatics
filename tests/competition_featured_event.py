#!/usr/bin/env python3
"""Regression checks for competitions containing multiple events on one date."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build


competition = {
    "events": [
        {"date": "2027-01-10", "name": "Zermatt", "location": "Zermatt"},
        {"date": "2027-01-10", "name": "Andermatt", "location": "Andermatt"},
    ]
}

previous_today = os.environ.get("RF_TODAY")
try:
    os.environ["RF_TODAY"] = "2027-01-01"
    featured = build.competition_featured_event(competition)
finally:
    if previous_today is None:
        os.environ.pop("RF_TODAY", None)
    else:
        os.environ["RF_TODAY"] = previous_today

assert featured is not None
assert featured["date"] == "2027-01-10"
assert featured["location"] == "Andermatt"
print("competition featured event: duplicate-date ordering passed")
