#!/usr/bin/env python3
"""Audit Notion equipment relations against the read-only Drive image library.

The audit is deliberately non-destructive: it never edits Notion, Drive, or the
published site.  It reports one row per rider/equipment relation so a close
filename can be reviewed before it is turned into a permanent alias.
"""
from __future__ import annotations

import argparse
import csv
import difflib
import importlib.util
import json
import os
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# The workflow invokes this file as ``python3 scripts/audit_equipment_photos.py``
# from the repository root.  Keep the repository root importable so the
# dynamically loaded image importer can resolve the shared ``build`` module.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def norm_text(value: object) -> str:
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = value.encode("ascii", "ignore").decode("ascii").casefold()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def compact(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", norm_text(value))


def model_from_item(item: dict) -> str:
    return next(
        (part.strip() for part in str(item.get("model_detail") or "").split(";") if part.strip()),
        "",
    )


def load_importer(library: Path):
    # import_images reads RF_IMAGE_LIBRARY at import time.  Set it before the
    # module is loaded so the audit uses exactly the downloaded Drive snapshot.
    os.environ["RF_IMAGE_LIBRARY"] = str(library)
    spec = importlib.util.spec_from_file_location("ridersfanatics_import_images", ROOT / "import_images.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load import_images.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def brand_compatible(left: str, right: str) -> bool:
    left_key, right_key = compact(left), compact(right)
    if not left_key or not right_key:
        return False
    if left_key == right_key or left_key.startswith(right_key) or right_key.startswith(left_key):
        return min(len(left_key), len(right_key)) >= 4
    return difflib.SequenceMatcher(None, left_key, right_key).ratio() >= 0.86


def similarity(target_brand: str, target_model: str, candidate: dict) -> float:
    if not brand_compatible(target_brand, candidate.get("brand", "")):
        return 0.0
    target = compact(target_model)
    found = compact(candidate.get("model", ""))
    if not target or not found:
        return 0.0
    score = difflib.SequenceMatcher(None, target, found).ratio()
    if target.startswith(found) or found.startswith(target):
        score = max(score, 0.88)
    return score


def candidate_suggestions(candidates: list[dict], brand: str, model: str) -> list[dict]:
    ranked = []
    for candidate in candidates:
        score = similarity(brand, model, candidate)
        if score >= 0.72:
            ranked.append((score, candidate))
    ranked.sort(key=lambda item: (-item[0], item[1].get("name", "").casefold()))
    return [candidate for _score, candidate in ranked[:3]]


def relation_audit(importer, library_index: dict, drive_files: dict, rider: dict, item: dict) -> dict:
    category = str(item.get("category") or "").strip()
    brand = str(item.get("brand") or "").strip()
    model = model_from_item(item)
    canonical_brand, canonical_model = importer.build.canonical_equipment_product(category, brand, model)
    key = (category, importer.norm_text(canonical_brand), importer.norm_text(canonical_model))
    alias = importer.PHOTO_ALIASES.get(key)
    lookup_brand, lookup_model = alias or (importer.norm_text(canonical_brand), importer.norm_text(canonical_model))
    candidates = library_index.get(category, [])
    choice = importer.pick_photo(candidates, lookup_brand, lookup_model, rider.get("slug", ""))
    suggestions = candidate_suggestions(candidates, canonical_brand, canonical_model)

    row = {
        "rider": rider.get("display_name") or rider.get("name") or "",
        "rider_slug": rider.get("slug") or "",
        "category": category,
        "brand": brand,
        "reference": model,
        "status": "missing",
        "match_type": "none",
        "drive_file": "",
        "drive_file_id": "",
        "drive_url": "",
        "suggestion": "",
        "suggestion_count": len(suggestions),
    }
    if choice:
        row["drive_file"] = str(Path(choice["path"]).relative_to(Path(importer.LIBRARY)))
        drive_record = drive_files.get(row["drive_file"], {})
        row["drive_file_id"] = str(drive_record.get("drive_id") or "")
        if row["drive_file_id"]:
            row["drive_url"] = f"https://drive.google.com/open?id={row['drive_file_id']}"
        row["status"] = "found"
        row["match_type"] = "alias" if alias else "exact"
        if choice.get("rider_slug") == rider.get("slug"):
            row["match_type"] = "rider-specific"
        # A prefix match is useful, but should be explicitly reviewed rather
        # than silently treated as an exact product identity.
        target = compact(lookup_model)
        found = compact(choice.get("model", ""))
        if (
            target and found and target != found
            and (target.startswith(found) or found.startswith(target))
            and choice.get("rider_slug") != rider.get("slug")
        ):
            row["status"] = "review"
            row["match_type"] = "similar"
    elif suggestions:
        row["status"] = "review" if len(suggestions) == 1 else "ambiguous"
        row["match_type"] = "similar" if len(suggestions) == 1 else "ambiguous"
        row["suggestion"] = " | ".join(
            str(Path(candidate["path"]).relative_to(Path(importer.LIBRARY)))
            for candidate in suggestions
        )
    return row


def markdown(rows: list[dict], library: Path, skipped_folders: list[tuple[str, int]] | None = None) -> str:
    counts = Counter(row["status"] for row in rows)
    lines = [
        "# Equipment photo audit",
        "",
        "Read-only comparison of Notion equipment relations with the downloaded Google Drive library.",
        "",
        f"Drive snapshot: `{library}`  ",
        f"Relations checked: **{len(rows)}**  ",
        f"Found: **{counts['found']}** · Review: **{counts['review']}** · Ambiguous: **{counts['ambiguous']}** · Missing: **{counts['missing']}**",
        "",
        "## Relations requiring attention",
        "",
        "| Rider | Category | Brand | Reference | Status | Drive file / suggestion |",
        "|---|---|---|---|---|---|",
    ]
    attention = [row for row in rows if row["status"] != "found"]
    if not attention:
        lines.append("| None |  |  |  |  |  |")
    else:
        for row in attention:
            location = row["drive_file"] or row["suggestion"] or "—"
            lines.append(
                f"| {row['rider']} | {row['category']} | {row['brand']} | {row['reference']} | {row['status']} | {location} |"
            )
    lines.extend([
        "",
        "## Interpretation",
        "",
        "- `found / exact`: the product matched the Drive filename rules.",
        "- `found / alias`: an existing validated alias matched the product.",
        "- `found / rider-specific`: a product photo containing that rider's name matched.",
        "- `review / similar`: one close candidate exists; validate it before adding an alias.",
        "- `ambiguous`: several close candidates exist; no automatic selection is made.",
        "- `missing`: no safe candidate was found.",
    ])
    if skipped_folders:
        lines.extend([
            "",
            "## Drive folders not mapped to a site category",
            "",
        ])
        lines.extend(f"- `{name}` ({count} image(s))" for name, count in skipped_folders)
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--riders", type=Path, required=True)
    parser.add_argument("--drive-library", type=Path, required=True)
    parser.add_argument("--drive-manifest", type=Path)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    args = parser.parse_args()
    riders = read_json(args.riders)
    if not isinstance(riders, list) or not riders:
        raise SystemExit("riders snapshot must contain a non-empty array")
    library = args.drive_library.resolve()
    if not library.is_dir():
        raise SystemExit(f"Drive library does not exist: {library}")
    importer = load_importer(library)
    library_index, skipped_folders = importer.index_library_equipment(riders)
    drive_files = {}
    if args.drive_manifest:
        manifest = read_json(args.drive_manifest)
        for record in manifest.get("files") or []:
            if isinstance(record, dict) and record.get("path"):
                drive_files[str(record["path"])] = record
    rows = []
    for rider in riders:
        for item in rider.get("equipment") or []:
            rows.append(relation_audit(importer, library_index, drive_files, rider, item))
    counts = Counter(row["status"] for row in rows)
    payload = {
        "schema_version": 1,
        "read_only": True,
        "riders": len(riders),
        "relations": len(rows),
        "counts": dict(sorted(counts.items())),
        "rows": rows,
        "unmapped_drive_folders": [
            {"name": name, "images": count} for name, count in skipped_folders
        ],
    }
    for path in (args.output_json, args.output_csv, args.output_markdown):
        path.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with args.output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else ["status"])
        writer.writeheader()
        writer.writerows(rows)
    args.output_markdown.write_text(markdown(rows, library, skipped_folders), encoding="utf-8")
    print(
        f"Equipment photo audit: {len(rows)} relations; "
        f"found={counts['found']} review={counts['review']} "
        f"ambiguous={counts['ambiguous']} missing={counts['missing']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
