#!/usr/bin/env python3
"""Guard the production contract: Notion data, Google Drive images only."""
import inspect
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("sync_notion", ROOT / "scripts" / "sync_notion.py")
sync_notion = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync_notion)

parameters = list(inspect.signature(sync_notion.export).parameters)
if parameters != ["client"]:
    raise SystemExit(f"Notion exporter accepts a non-Notion fallback: {parameters}")

source = inspect.getsource(sync_notion.export)
for forbidden in ("baseline", "base.get", "data/riders.json", "photo_url"):
    if forbidden in source:
        raise SystemExit(f"Notion-only contract violated by {forbidden!r}")

if 'first_value(item, "country", "Country", "counrty")' not in source:
    raise SystemExit("The live Notion country relation is not mapped")

routes = sync_notion.ROUTE_SLUGS_BY_HANDLE
if not routes or not all(isinstance(key, str) and isinstance(value, str) for key, value in routes.items()):
    raise SystemExit("The URL compatibility registry must contain only handle-to-slug strings")
if routes.get("finniles") != "finn-iles":
    raise SystemExit("Established rider URLs are not protected")

print("Notion-only profile contract valid; portraits remain a build-time Drive concern.")
