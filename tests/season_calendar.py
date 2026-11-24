import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import build


competition = {
    "id": "sample-series-2027",
    "name": "Sample Series 2027",
    "short_name": "Sample Series",
    "season": 2027,
    "events": [
        {"name": "Alpine Round", "date": "2027-01-10", "location": "Alps"},
        {"name": "Undated Round", "date": "", "location": "TBC"},
    ],
}

calendar = build.build_competition_calendar(competition)

assert calendar.startswith("BEGIN:VCALENDAR\r\n")
assert calendar.count("BEGIN:VEVENT") == 1
assert "DTSTART;VALUE=DATE:20270110" in calendar
assert "DTEND;VALUE=DATE:20270111" in calendar
assert "SUMMARY:Alpine Round — Sample Series" in calendar
assert "LOCATION:Alps" in calendar
assert "/competitions/sample-series-2027/rounds/alpine-round.html" in calendar
assert "Undated Round" not in calendar
