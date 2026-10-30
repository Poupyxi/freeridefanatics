"""Regression checks for competition and event logo fallback rules."""
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build


def logo(name):
    return {"src": f"assets/img/competitions/{name}.webp", "name": name}


logos = {
    "redbull-rampage-2024": logo("rampage-2024"),
    "redbull-rampage-2026": logo("rampage-2026"),
    "redbull-rampage-2028": logo("rampage-2028"),
    "redbull-hardline-2026": logo("hardline-2026"),
    "redbull-2026": logo("redbull-2026"),
}

# Exact matches always win.
assert build.resolve_logo(logos, "redbull-rampage-2026") == logos["redbull-rampage-2026"]

# A missing edition uses the closest preceding edition, never another event.
assert build.resolve_logo(logos, "redbull-rampage-2027") == logos["redbull-rampage-2026"]
assert build.resolve_logo(logos, "redbull-hardline-2027") == logos["redbull-hardline-2026"]

# If no preceding edition exists, the nearest future edition is allowed.
future_only = {"redbull-rampage-2028": logos["redbull-rampage-2028"]}
assert build.resolve_logo(future_only, "redbull-rampage-2027") == future_only["redbull-rampage-2028"]

# Event pages fall back to the parent competition when no event logo exists.
competition = {"id": "redbull-2026"}
assert build.competition_event_logo(logos, competition, "Unknown Event 2026") == logos["redbull-2026"]

# Missing competition editions follow the same year rule.
assert build.competition_logo(logos, {"id": "redbull-2027"}) == logos["redbull-2026"]
