#!/usr/bin/env python3
"""Regression coverage for announced competitions without Event relations."""

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "sync_notion", ROOT / "scripts" / "sync_notion.py"
)
sync_notion = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync_notion)


assert sync_notion.season_is_publishable(
    "4089cf6b-f148-8029-a261-c2fb02adb7ce", "Natural selection - 2027"
)
assert sync_notion.season_is_publishable(
    "4089cf6b-f148-80c7-af4d-fc8ef923164b",
    "Scandinavian Big Mountain Championships - 2027",
)
assert not sync_notion.season_is_publishable("", "Natural selection - 2027")
assert not sync_notion.season_is_publishable("page-id", "")

print("Notion competitions remain publishable before Event relations exist.")
