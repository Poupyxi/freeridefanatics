#!/usr/bin/env python3
"""The protected preview exposes the agreed year-first competition tree."""
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
html = (ROOT / "competitions.html").read_text(encoding="utf-8")

assert os.environ.get("RF_BUILD_ENV") == "preprod"
assert html.index('id="season-2027"') < html.index('id="season-2026"')

expected_pages = (
    "uci-mtb-world-cup-dh-2027",
    "uci-enduro-world-cup-2027",
    "red-bull-hardline-2027",
    "red-bull-rampage-2027",
    "red-bull-cerro-abajo-2027",
    "uci-mtb-world-cup-dh-2026",
    "uci-enduro-world-cup-2026",
    "red-bull-hardline-2026",
    "red-bull-rampage-2026",
    "red-bull-cerro-abajo-2026",
    "other-events-2026",
)
for identifier in expected_pages:
    assert (ROOT / "competitions" / f"{identifier}.html").is_file(), identifier
    assert f'competitions/{identifier}.html' in html, identifier

header = html.split("</header>", 1)[0]
assert header.index(">2027<") < header.index(">2026<")

print("Preproduction competition navigation is grouped by 2027 and 2026.")
