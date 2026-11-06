"""Share markup is restricted to preproduction and preserves source metadata."""
import json
import sys
from pathlib import Path
from unittest.mock import patch
from html import unescape
import re

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build

competition = {"name": "Demo Cup", "season": 2026, "id": "demo", "instagram": "demo.cup", "events": []}
riders = [{"slug": "sample", "country_code": "FRA"}]
with patch.object(build, "IS_PREPROD", False):
    assert build.ranking_share_assets(riders, competition, "../") == ""
with patch.object(build, "IS_PREPROD", True), patch.object(build, "load_competition_logos", return_value={}), patch.object(build, "competition_logo", return_value=None), patch.object(build, "has_photo", return_value="sample.webp"):
    markup = build.ranking_share_assets(riders, competition, "../")
    payload = json.loads(unescape(re.search('data-payload="([^"]+)"', markup)[1]))
    assert payload["instagram"] == "demo.cup"
    assert payload["riders"]["sample"]["country"] == "FRA"
    assert payload["riders"]["sample"]["photo"] == "../assets/img/riders/sample.webp"
    assert payload["eventCard"] is not None
    assert payload["shareKind"] == "competition"
    competition["events"] = [{"name": "Future race", "date": "2099-01-20", "location": "Test venue"}]
    with patch.object(build, "competition_event_logo", return_value=None):
        markup = build.ranking_share_assets([], competition, "../", "Future race")
        payload = json.loads(unescape(re.search('data-payload="([^"]+)"', markup)[1]))
        assert payload["eventCard"]["status"] == "Coming soon"
        assert payload["eventCard"]["location"] == "Test venue"
print("Ranking share environment and metadata: PASS")
