"""Regression checks for competition and event logo fallback rules."""
from pathlib import Path
import base64
import json
import sys
import tempfile
from unittest.mock import patch


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
    "uci-mtb-world-cup-dh-2026": logo("uci-2026"),
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

# Notion's newer UCI World Series DH/CC identifiers reuse the nearest UCI
# series logo even though the older Drive filename says MTB World Cup DH.
assert build.competition_logo(logos, {"id": "uci-world-series-dh-2027"}) == logos["uci-mtb-world-cup-dh-2026"]
assert build.competition_logo(logos, {"id": "uci-world-series-cc-2027"}) == logos["uci-mtb-world-cup-dh-2026"]

# A Drive-managed logo must not be overwritten by the embedded fallback while
# pages are built and the next validated snapshot is prepared.
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "data").mkdir()
    image_dir = root / "assets" / "img" / "competitions"
    image_dir.mkdir(parents=True)
    embedded_path = root / "data" / "competition-logos.json"
    embedded_path.write_text(json.dumps({"logos": [{
        "key": "shared-event-2026", "name": "Embedded", "mime": "image/webp",
        "data": base64.b64encode(b"old-embedded-logo").decode("ascii"),
    }]}), encoding="utf-8")
    (root / "data" / "redbull-logos.json").write_text('{"logos": []}', encoding="utf-8")
    drive_path = image_dir / "shared-event-2026.webp"
    drive_path.write_bytes(b"current-drive-logo")
    drive_manifest = {
        "competitions": [{
            "key": "shared-event-2026",
            "name": "Drive",
            "src": "assets/img/competitions/shared-event-2026.webp",
        }],
        "brands": [],
        "teams": [],
    }
    with (
        patch.object(build, "ROOT", str(root)),
        patch.object(build, "COMPETITION_IMG_DIR", str(image_dir)),
        patch.object(build, "COMPETITION_LOGOS_PATH", str(embedded_path)),
        patch.object(build, "load_drive_logo_manifest", return_value=drive_manifest),
    ):
        loaded = build.load_competition_logos()
    assert loaded["shared-event-2026"]["name"] == "Drive"
    assert drive_path.read_bytes() == b"current-drive-logo"
