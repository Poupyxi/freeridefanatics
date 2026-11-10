import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import build


riders = [
    {
        "slug": "sample-skier",
        "display_name": "Sample Skier",
        "gender_category": "Women Elite",
        "disciplines": ["Ski Freeride"],
        "country": "France",
        "team": "Independent",
    },
    {
        "slug": "sample-snowboarder",
        "display_name": "Sample Snowboarder",
        "gender_category": "Men Elite",
        "disciplines": ["Snowboard Freeride"],
        "country": "Switzerland",
        "team": "Independent",
    },
]

html = build.build_riders_directory(riders, women_count=1, men_count=1, winter=True)

assert 'data-filter="ski">Ski (1)</button>' in html
assert 'data-filter="snowboard">Snowboard (1)</button>' in html
assert 'data-sports="ski"' in html
assert 'data-sports="snowboard"' in html
