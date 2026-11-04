#!/usr/bin/env python3
"""Write a completed equipment-photo audit into the canonical Equipments DB.

The audit itself is produced per rider/equipment relation, but its durable
annotation belongs to the product row in ``Equipments``.  This script therefore
aggregates relation results by canonical category/brand/model and only changes
the five audit fields on the matching equipment pages.  It never changes rider
links, seasons, brands, or product names.  Use ``--apply`` explicitly; without
it the script only reports what it would update.
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
BUILD_PATH = ROOT / "build.py"

DATA_SOURCES = {
    "equipment": "3c99cf6b-f148-8010-a1c7-000b9ef9ef98",
    "brands": "3cb9cf6b-f148-8090-b481-000b49ff2d90",
}
LINK_FIELDS = {
    "Photo status",
    "Photo file",
    "Match confidence",
    "Needs review",
    "Last photo audit",
}
# A product is only considered healthy when every checked rider relation found
# a safe image.  A missing relation therefore takes precedence over a match.
STATUS_PRIORITY = {"Exact": 0, "Alias": 1, "Similar": 2, "Ambiguous": 3, "Missing": 4}


def load_sync_module():
    spec = importlib.util.spec_from_file_location("ridersfanatics_sync_notion", SYNC_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load sync_notion.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_build_module():
    spec = importlib.util.spec_from_file_location("ridersfanatics_build", BUILD_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load build.py")
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


def equipment_key(build, category: object, brand: object, model: object) -> tuple[str, str, str]:
    """Return the same normalized product key used by the photo audit."""
    canonical_brand, canonical_model = build.canonical_equipment_product(
        str(category or "").strip(), str(brand or "").strip(), str(model or "").strip()
    )
    return (
        str(category or "").strip(),
        norm(canonical_brand),
        norm(canonical_model),
    )


def aggregate_rows(build, rows: list[dict]) -> dict[tuple[str, str, str], dict]:
    """Collapse relation-level rows to one conservative result per product."""
    grouped: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in rows:
        grouped[equipment_key(build, row.get("category"), row.get("brand"), row.get("reference"))].append(row)

    aggregate = {}
    for key, candidates in grouped.items():
        worst = max(
            candidates,
            key=lambda item: STATUS_PRIORITY.get(
                "Missing" if item.get("status") == "missing" else
                "Ambiguous" if item.get("status") == "ambiguous" else
                "Similar" if item.get("status") == "review" else
                "Alias" if item.get("match_type") == "alias" else "Exact",
                4,
            ),
        )
        # Prefer a usable Drive file even when another rider relation is the
        # one that triggered the conservative status.
        found = next((item for item in candidates if item.get("drive_url")), None)
        result = dict(worst)
        if found:
            result["drive_url"] = found.get("drive_url")
            result["drive_file"] = found.get("drive_file")
        result["relation_count"] = len(candidates)
        result["missing_relations"] = sum(item.get("status") == "missing" for item in candidates)
        result["ambiguous_relations"] = sum(item.get("status") == "ambiguous" for item in candidates)
        aggregate[key] = result
    return aggregate


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
    build = load_build_module()
    client = sync.Notion(token)

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
        equipment_keys[identifier] = equipment_key(build, category, brand, model)

    by_key = aggregate_rows(build, rows)

    now = dt.datetime.now(dt.timezone.utc).isoformat()
    updates = 0
    unmatched = []
    for key, row in by_key.items():
        page_ids = [page_id for page_id, product_key in equipment_keys.items() if product_key == key]
        if not page_ids:
            unmatched.append({"category": row.get("category"), "brand": row.get("brand"), "reference": row.get("reference")})
            continue
        payload = property_payload(row, now)
        for page_id in page_ids:
            if args.apply:
                client.request("PATCH", f"/pages/{page_id}", {"properties": payload})
            updates += 1

    mode = "updated" if args.apply else "would update"
    print(f"Notion photo audit: {mode} {updates} equipment row(s); unmatched={len(unmatched)}")
    if unmatched:
        print(json.dumps({"unmatched": unmatched[:20]}, ensure_ascii=False))
    return 0 if not unmatched else 2


if __name__ == "__main__":
    raise SystemExit(main())
