#!/usr/bin/env python3
"""Write a completed equipment-photo audit into Notion audit properties.

This script changes only the audit fields on Equipment Rider Link pages. It
never changes rider, equipment, discipline, season, brand, or reference data.
Use ``--apply`` explicitly; without it the script only reports what it would
update.
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SYNC_PATH = ROOT / "scripts" / "sync_notion.py"

DATA_SOURCES = {
    "riders": "3c89cf6b-f148-8044-9283-000b552443a8",
    "equipment": "3c99cf6b-f148-8010-a1c7-000b9ef9ef98",
    "brands": "3cb9cf6b-f148-8090-b481-000b49ff2d90",
    "equipment_links": "3ca9cf6b-f148-8018-9a11-000b4b610ef2",
}
LINK_FIELDS = {
    "Photo status",
    "Photo file",
    "Match confidence",
    "Needs review",
    "Last photo audit",
}
STATUS_PRIORITY = {"Exact": 0, "Alias": 1, "Similar": 2, "Ambiguous": 3, "Missing": 4}


def load_sync_module():
    spec = importlib.util.spec_from_file_location("ridersfanatics_sync_notion", SYNC_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load sync_notion.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii").casefold()
    return "".join(char for char in text if char.isalnum())


def page_key(sync, value: object) -> str:
    return sync.page_id(str(value)) or ""


def model_from_row(row: dict) -> str:
    return str(row.get("reference") or "").strip()


def row_key(row: dict) -> tuple[str, str, str, str]:
    return (
        str(row.get("rider_slug") or ""),
        str(row.get("category") or ""),
        norm(row.get("brand")),
        norm(model_from_row(row)),
    )


def property_payload(row: dict, now: str) -> dict:
    match_type = str(row.get("match_type") or "")
    status = str(row.get("status") or "missing")
    if status == "found":
        notion_status = "Alias" if match_type == "alias" else "Exact"
        confidence = 0.95 if match_type == "alias" else 1.0
    elif status == "review":
        notion_status, confidence = "Similar", 0.75
    elif status == "ambiguous":
        notion_status, confidence = "Ambiguous", 0.5
    else:
        notion_status, confidence = "Missing", 0.0
    needs_review = notion_status in {"Similar", "Ambiguous", "Missing"}
    return {
        "Photo status": {"select": {"name": notion_status}},
        "Photo file": {"url": row.get("drive_url") or None},
        "Match confidence": {"number": confidence},
        "Needs review": {"checkbox": needs_review},
        "Last photo audit": {"date": {"start": now}},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-json", type=Path, required=True)
    parser.add_argument("--token", default="")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    token = args.token.strip()
    if not token:
        raise SystemExit("A Notion token is required")
    audit = json.loads(args.audit_json.read_text(encoding="utf-8"))
    rows = audit.get("rows") or []
    if not isinstance(rows, list):
        raise SystemExit("audit JSON rows must be an array")
    sync = load_sync_module()
    client = sync.Notion(token)

    rider_pages = client.query(DATA_SOURCES["riders"])
    rider_slugs = {}
    for page in rider_pages:
        identifier = page_key(sync, page.get("id"))
        if not identifier:
            continue
        raw_name = sync.scalar_value(page, "First Name") or sync.page_title(page, "Name", "Nom") or ""
        display_name = sync.display_rider_name(raw_name)
        if display_name:
            handle = (sync.instagram_handle(sync.scalar_value(page, "Instagram")) or "").lower().lstrip("@")
            rider_slugs[identifier] = sync.ROUTE_SLUGS_BY_HANDLE.get(handle, sync.slugify(display_name))

    brand_pages = client.query(DATA_SOURCES["brands"])
    brands = sync.title_map(brand_pages, "Name", "Nom", "Brand")
    equipment_pages = client.query(DATA_SOURCES["equipment"])
    equipment_keys = {}
    for page in equipment_pages:
        identifier = page_key(sync, page.get("id"))
        if not identifier:
            continue
        raw_category = sync.scalar_value(page, "Type") or ""
        category = sync.CATEGORY_MAP.get(raw_category, raw_category)
        brand = next((brands.get(item) for item in sync.list_value(page, "Brand") if brands.get(item)), "")
        model = sync.scalar_value(page, "Product") or ""
        model = next((part.strip() for part in str(model).split(";") if part.strip()), "")
        canonical_brand, canonical_model = sync.canonical_equipment_product(category, brand, model)
        equipment_keys[identifier] = (category, norm(canonical_brand), norm(canonical_model))

    relation_pages = client.query(DATA_SOURCES["equipment_links"])
    relation_map = defaultdict(list)
    for page in relation_pages:
        identifier = page_key(sync, page.get("id"))
        if not identifier:
            continue
        rider_ids = sync.list_value(page, "🚻 Riders")
        product_ids = sync.list_value(page, "Equipments")
        for rider_id in rider_ids:
            rider_slug = rider_slugs.get(rider_id)
            if not rider_slug:
                continue
            for product_id in product_ids:
                product_key = equipment_keys.get(product_id)
                if product_key:
                    relation_map[(rider_slug, *product_key)].append(identifier)

    by_key = {}
    for row in rows:
        key = row_key(row)
        current = by_key.get(key)
        if current is None or STATUS_PRIORITY.get(str(row.get("status")), 4) > STATUS_PRIORITY.get(str(current.get("status")), 4):
            by_key[key] = row

    now = dt.datetime.now(dt.timezone.utc).isoformat()
    updates = 0
    unmatched = []
    for key, row in by_key.items():
        page_ids = relation_map.get(key, [])
        if not page_ids:
            unmatched.append({"rider": row.get("rider"), "category": row.get("category"), "reference": row.get("reference")})
            continue
        payload = property_payload(row, now)
        for page_id in page_ids:
            if args.apply:
                client.request("PATCH", f"/pages/{page_id}", {"properties": payload})
            updates += 1

    mode = "updated" if args.apply else "would update"
    print(f"Notion photo audit: {mode} {updates} relation row(s); unmatched={len(unmatched)}")
    if unmatched:
        print(json.dumps({"unmatched": unmatched[:20]}, ensure_ascii=False))
    return 0 if not unmatched else 2


if __name__ == "__main__":
    raise SystemExit(main())
