#!/usr/bin/env python3
"""Validate the generated read-only Google Drive logo manifest."""

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "drive-logo-manifest.json"
REQUIRED_SECTIONS = {"brands", "competitions", "teams"}
REQUIRED_COMPETITIONS = {
    "beyondgravity",
    "project-17",
    "red-bull-cerro-abajo-2026",
    "redbull-2026",
    "redbull-hardline-2026",
    "redbull-rampage-2026",
    "uci-mtb-world-cup-dh-2026",
}


payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
assert payload["source"] == "google-drive-read-only"
assert payload["access_scope"] == "https://www.googleapis.com/auth/drive.readonly"
assert set(payload["logos"]) == REQUIRED_SECTIONS

for section, entries in payload["logos"].items():
    assert entries, f"No {section} logo was generated"
    keys = [entry["key"] for entry in entries]
    assert len(keys) == len(set(keys)), f"Duplicate {section} keys"
    for entry in entries:
        assert re.fullmatch(r"[a-z0-9-]+", entry["key"])
        assert re.fullmatch(r"assets/img/(?:brands|competitions|teams)/[a-z0-9-]+\.webp", entry["src"])
        logo = ROOT / entry["src"]
        assert logo.is_file() and logo.stat().st_size > 0
        assert hashlib.sha256(logo.read_bytes()).hexdigest() == entry["sha256"]

competition_keys = {entry["key"] for entry in payload["logos"]["competitions"]}
assert REQUIRED_COMPETITIONS <= competition_keys
print("Google Drive logo manifest is valid")
