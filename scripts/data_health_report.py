#!/usr/bin/env python3
"""Build a private, actionable health report for the reconciled site dataset."""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Callable


IMAGE_EXTENSIONS = {".avif", ".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"}
PARTICIPATION_STATUSES = {"FINISHER", "DNF", "DSQ", "DQ"}
ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_handle(value: object) -> str:
    raw = str(value or "").strip()
    path = Path(raw)
    if path.suffix.casefold() in IMAGE_EXTENSIONS:
        raw = path.stem
    return re.sub(r"[^a-z0-9]", "", raw.casefold().lstrip("@"))


def normalize_reference(value: object) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_value.casefold()).strip("-")


def image_exists(directory: Path, slug: str) -> bool:
    if not directory.is_dir():
        return False
    return any(
        path.is_file() and path.suffix.casefold() in IMAGE_EXTENSIONS
        for pattern in (f"{slug}.*", f"{slug}-drive.*")
        for path in directory.glob(pattern)
    )


def competition_inventory(catalog: dict) -> tuple[int, int, set[str]]:
    competitions = []
    competitions.extend(catalog.get("series") or [])
    for organization in catalog.get("organizations") or []:
        competitions.extend(organization.get("competitions") or [])
    references: set[str] = set()
    event_count = 0
    for competition in competitions:
        if not isinstance(competition, dict):
            continue
        for key in ("id", "name", "short_name"):
            value = normalize_reference(competition.get(key))
            if value:
                references.add(value)
        event_count += len(competition.get("events") or [])
    return len(competitions), event_count, references


def drive_inventory(manifest: dict) -> tuple[Counter, dict[str, list[str]]]:
    files = manifest.get("files")
    if not isinstance(files, list):
        raise ValueError("Drive manifest files must be an array")
    declared = manifest.get("image_count")
    if declared != len(files):
        raise ValueError(
            f"Drive manifest image_count mismatch: declared {declared}, found {len(files)}"
        )
    sections = Counter()
    portrait_paths = {"ppriders": [], "pictureriders": []}
    for row in files:
        if not isinstance(row, dict) or not row.get("path"):
            raise ValueError("each Drive manifest file needs a path")
        path = Path(str(row["path"]))
        section = path.parts[0].casefold() if path.parts else "root"
        sections[section] += 1
        if section in portrait_paths:
            portrait_paths[section].append(path.as_posix())
    return sections, portrait_paths


def compact_rider(rider: dict) -> dict[str, str]:
    return {
        "slug": str(rider.get("slug") or ""),
        "name": str(rider.get("display_name") or rider.get("name") or ""),
    }


def counts_as_participation(result: dict) -> bool:
    status = str(result.get("status") or result.get("result") or "").strip().upper()
    if status == "DNS":
        return False
    return bool(
        result.get("participated") is True
        or status in PARTICIPATION_STATUSES
        or result.get("place") is not None
    )


def analyze(
    riders: list,
    competitions: dict,
    drive_manifest: dict,
    *,
    portrait_dir: Path,
    action_dir: Path,
    equipment_resolver: Callable[[dict], str | None],
    generated_at: str,
    logo_manifest: dict | None = None,
) -> dict:
    if not isinstance(riders, list) or not riders:
        raise ValueError("riders must be a non-empty array")
    if not isinstance(competitions, dict):
        raise ValueError("competitions must be an object")

    competition_count, event_count, competition_references = competition_inventory(competitions)
    drive_sections, portrait_paths = drive_inventory(drive_manifest)
    issues: dict[str, list] = {
        "duplicate_slugs": [],
        "riders_without_country": [],
        "riders_without_team": [],
        "riders_without_instagram": [],
        "riders_without_results": [],
        "riders_without_equipment": [],
        "riders_without_profile_picture": [],
        "riders_without_action_picture": [],
        "incomplete_equipment_relations": [],
        "equipment_relations_without_image": [],
        "results_without_event": [],
        "results_without_competition": [],
        "results_without_outcome": [],
        "unmatched_competition_references": [],
        "unmatched_drive_portraits": [],
    }

    seen_slugs = set()
    handles = set()
    results = 0
    participations = 0
    qualifiers = 0
    finals = 0
    equipment_relations = 0
    equipment_with_image = 0
    unique_equipment = set()
    profile_pictures = 0
    action_pictures = 0
    women = 0
    men = 0

    for index, rider in enumerate(riders, 1):
        if not isinstance(rider, dict):
            raise ValueError(f"rider {index} is not an object")
        compact = compact_rider(rider)
        slug = compact["slug"]
        if not slug or not compact["name"]:
            raise ValueError(f"rider {index} needs slug and display_name")
        if slug in seen_slugs:
            issues["duplicate_slugs"].append(compact)
        seen_slugs.add(slug)

        category = str(rider.get("gender_category") or "")
        women += int("women" in category.casefold())
        men += int("men" in category.casefold() and "women" not in category.casefold())
        for field, issue in (
            ("country", "riders_without_country"),
            ("team", "riders_without_team"),
            ("instagram", "riders_without_instagram"),
        ):
            if not str(rider.get(field) or "").strip():
                issues[issue].append(compact)
        handle = normalize_handle(rider.get("instagram"))
        if handle:
            handles.add(handle)

        has_profile = image_exists(portrait_dir, slug)
        has_action = image_exists(action_dir, slug)
        profile_pictures += int(has_profile)
        action_pictures += int(has_action)
        if not has_profile:
            issues["riders_without_profile_picture"].append(compact)
        if not has_action:
            issues["riders_without_action_picture"].append(compact)

        history = rider.get("competition_history") or []
        if not isinstance(history, list):
            raise ValueError(f"{slug}: competition_history must be an array")
        if not history:
            issues["riders_without_results"].append(compact)
        for result in history:
            if not isinstance(result, dict):
                raise ValueError(f"{slug}: a competition result is not an object")
            results += 1
            participations += int(counts_as_participation(result))
            stages = result.get("stages") or {}
            if isinstance(stages, dict):
                qualifiers += int(bool(stages.get("Qualifier")))
                finals += int(bool(stages.get("Final")))
            detail = {**compact, "event": result.get("event"), "competition": result.get("category")}
            if not str(result.get("event") or "").strip():
                issues["results_without_event"].append(detail)
            competition = str(result.get("category") or "").strip()
            if not competition:
                issues["results_without_competition"].append(detail)
            elif competition_references and normalize_reference(competition) not in competition_references:
                issues["unmatched_competition_references"].append(detail)
            if not any(
                result.get(key) not in (None, "", {})
                for key in ("place", "points", "status", "result", "stages")
            ):
                issues["results_without_outcome"].append(detail)

        equipment = rider.get("equipment") or []
        if not isinstance(equipment, list):
            raise ValueError(f"{slug}: equipment must be an array")
        if not equipment:
            issues["riders_without_equipment"].append(compact)
        for item in equipment:
            if not isinstance(item, dict):
                raise ValueError(f"{slug}: an equipment relation is not an object")
            equipment_relations += 1
            category = str(item.get("category") or "").strip()
            brand = str(item.get("brand") or "").strip()
            model = str(item.get("model_detail") or "").split(";", 1)[0].strip()
            detail = {**compact, "category": category, "brand": brand, "model": model}
            if not category or not (brand or model):
                issues["incomplete_equipment_relations"].append(detail)
                continue
            unique_equipment.add((category.casefold(), brand.casefold(), model.casefold()))
            image = equipment_resolver(item)
            if image:
                equipment_with_image += 1
            else:
                issues["equipment_relations_without_image"].append(detail)

    for paths in portrait_paths.values():
        for path in paths:
            if normalize_handle(Path(path).name) not in handles:
                issues["unmatched_drive_portraits"].append(path)

    issue_counts = {name: len(rows) for name, rows in issues.items()}
    critical_count = issue_counts["duplicate_slugs"]
    logo_counts = {
        name: len(entries)
        for name, entries in ((logo_manifest or {}).get("logos") or {}).items()
        if isinstance(entries, list)
    }
    rider_count = len(riders)
    return {
        "schema_version": 1,
        "generated_at": generated_at,
        "status": "critical" if critical_count else ("attention" if any(issue_counts.values()) else "healthy"),
        "counts": {
            "riders": rider_count,
            "women": women,
            "men": men,
            "competitions": competition_count,
            "events": event_count,
            "results": results,
            "participations": participations,
            "qualifier_results": qualifiers,
            "final_results": finals,
            "equipment_relations": equipment_relations,
            "unique_equipment": len(unique_equipment),
            "drive_images": sum(drive_sections.values()),
            "profile_pictures": profile_pictures,
            "action_pictures": action_pictures,
            "equipment_relations_with_image": equipment_with_image,
        },
        "coverage": {
            "profile_picture_percent": round(profile_pictures / rider_count * 100, 1),
            "action_picture_percent": round(action_pictures / rider_count * 100, 1),
            "equipment_image_percent": round(
                equipment_with_image / equipment_relations * 100, 1
            ) if equipment_relations else 0.0,
        },
        "drive_sections": dict(sorted(drive_sections.items())),
        "logo_counts": logo_counts,
        "issue_counts": issue_counts,
        "issues": issues,
    }


def markdown_report(report: dict, *, detail_limit: int = 20) -> str:
    counts = report["counts"]
    coverage = report["coverage"]
    lines = [
        "# RidersFanatics Data Health",
        "",
        f"Generated: `{report['generated_at']}`  ",
        f"Status: **{report['status'].upper()}**",
        "",
        "## Snapshot",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    labels = (
        ("Riders", "riders"), ("Women", "women"), ("Men", "men"),
        ("Competitions", "competitions"), ("Events", "events"),
        ("Results", "results"), ("Participations", "participations"),
        ("Qualifier results", "qualifier_results"), ("Final results", "final_results"),
        ("Equipment relations", "equipment_relations"),
        ("Unique equipment", "unique_equipment"), ("Drive images", "drive_images"),
    )
    lines.extend(f"| {label} | {counts[key]} |" for label, key in labels)
    lines.extend([
        "",
        "## Image coverage",
        "",
        "| Coverage | Matched | Percent |",
        "|---|---:|---:|",
        f"| Rider profile pictures | {counts['profile_pictures']}/{counts['riders']} | {coverage['profile_picture_percent']}% |",
        f"| Rider action pictures | {counts['action_pictures']}/{counts['riders']} | {coverage['action_picture_percent']}% |",
        f"| Equipment relations with an image | {counts['equipment_relations_with_image']}/{counts['equipment_relations']} | {coverage['equipment_image_percent']}% |",
        "",
        "## Attention points",
        "",
        "| Check | Count |",
        "|---|---:|",
    ])
    nonzero = [(name, value) for name, value in report["issue_counts"].items() if value]
    if nonzero:
        lines.extend(f"| `{name}` | {value} |" for name, value in nonzero)
    else:
        lines.append("| No issue detected | 0 |")

    for name, rows in report["issues"].items():
        if not rows:
            continue
        lines.extend(["", f"### {name} ({len(rows)})", ""])
        for row in rows[:detail_limit]:
            if isinstance(row, dict):
                value = " · ".join(str(item) for item in row.values() if item not in (None, ""))
            else:
                value = str(row)
            lines.append(f"- {value}")
        if len(rows) > detail_limit:
            lines.append(f"- … {len(rows) - detail_limit} more in the JSON report")
    return "\n".join(lines) + "\n"


def cli_equipment_resolver(equipment_dir: Path):
    spec = importlib.util.spec_from_file_location("ridersfanatics_build", ROOT / "build.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the site equipment resolver")
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)

    build.EQUIP_IMG_DIR = str(equipment_dir)
    cache: dict[tuple[str, str, str], str | None] = {}

    def resolve(item: dict) -> str | None:
        model = str(item.get("model_detail") or "").split(";", 1)[0].strip()
        key = (
            str(item.get("category") or ""),
            str(item.get("brand") or ""),
            model,
        )
        if key not in cache:
            cache[key] = build.has_equip_photo(*key)
        return cache[key]

    return resolve


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--riders", type=Path, required=True)
    parser.add_argument("--competitions", type=Path, required=True)
    parser.add_argument("--drive-manifest", type=Path, required=True)
    parser.add_argument("--logo-manifest", type=Path)
    parser.add_argument("--portrait-dir", type=Path, required=True)
    parser.add_argument("--action-dir", type=Path, required=True)
    parser.add_argument("--equipment-dir", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    parser.add_argument("--append-summary", type=Path)
    args = parser.parse_args()
    try:
        generated_at = dt.datetime.now(dt.timezone.utc).isoformat()
        report = analyze(
            read_json(args.riders),
            read_json(args.competitions),
            read_json(args.drive_manifest),
            portrait_dir=args.portrait_dir,
            action_dir=args.action_dir,
            equipment_resolver=cli_equipment_resolver(args.equipment_dir),
            generated_at=generated_at,
            logo_manifest=read_json(args.logo_manifest) if args.logo_manifest else None,
        )
        markdown = markdown_report(report)
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        args.output_markdown.write_text(markdown, encoding="utf-8")
        if args.append_summary:
            args.append_summary.parent.mkdir(parents=True, exist_ok=True)
            with args.append_summary.open("a", encoding="utf-8") as summary:
                summary.write(markdown)
        print(
            f"Data Health: {report['status']}; {report['counts']['riders']} riders, "
            f"{report['counts']['results']} results, "
            f"{report['counts']['drive_images']} Drive images."
        )
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Data Health report failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
