#!/usr/bin/env python3
"""Validate a generated rider snapshot before it can become a site build source."""
import json
import sys
from pathlib import Path


def fail(message):
    raise SystemExit(f"Invalid rider snapshot: {message}")


path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/riders.json")
try:
    riders = json.loads(path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    fail(str(exc))

if not isinstance(riders, list) or not riders:
    fail("expected a non-empty JSON array")

slugs = set()
for index, rider in enumerate(riders, 1):
    if not isinstance(rider, dict):
        fail(f"row {index} is not an object")
    slug = str(rider.get("slug") or "").strip()
    name = str(rider.get("display_name") or "").strip()
    if not slug or not name:
        fail(f"row {index} needs slug and display_name")
    if slug in slugs:
        fail(f"duplicate slug: {slug}")
    slugs.add(slug)
    if not isinstance(rider.get("results") or [], list):
        fail(f"{slug}: results must be an array")
    if not isinstance(rider.get("equipment") or [], list):
        fail(f"{slug}: equipment must be an array")

print(f"Valid rider snapshot: {len(riders)} riders from {path}")
