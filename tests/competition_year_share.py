"""A season share payload includes only that year's dated competitions."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build

competitions = [
    {
        "name": "Downhill World Cup",
        "id": "downhill-world-cup-2027",
        "season": 2027,
        "discipline": "DH",
        "events": [{"name": "Leogang", "date": "2027-06-12", "location": "Austria"}],
    },
    {
        "name": "Hardline",
        "id": "hardline-2027",
        "season": 2027,
        "discipline": "Freeride",
        "events": [{"name": "Wales", "date": "2027-07-10", "end_date": "2027-07-11", "location": "Wales"}],
    },
    {
        "name": "Old Cup",
        "id": "old-cup-2026",
        "season": 2026,
        "events": [{"name": "Old round", "date": "2026-05-01"}],
    },
]

payload = build.competition_year_share_payload("2027", competitions)
assert payload["shareKind"] == "year"
assert payload["shareUrl"] == "#season-2027"
assert payload["competitionCard"]["eventsCount"] == 2
assert [item["name"] for item in payload["competitionCard"]["calendar"]] == [
    "Downhill World Cup · Leogang",
    "Hardline · Wales",
]
assert payload["competitionCard"]["calendar"][1]["endDate"] == "2027-07-10"
assert all("Old" not in item["name"] for item in payload["competitionCard"]["calendar"])

print("Competition year sharing: PASS")
