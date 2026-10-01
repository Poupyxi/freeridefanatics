#!/usr/bin/env python3
"""Create and validate deployment volume metrics before production publishing."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


METRICS = ("riders", "results", "images", "published_images")
IMAGE_EXTENSIONS = {".avif", ".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def count_public_images(paths: list[Path]) -> int:
    images = set()
    for root in paths:
        if root.is_dir():
            images.update(
                image.resolve() for image in root.rglob("*")
                if image.is_file() and image.suffix.casefold() in IMAGE_EXTENSIONS
            )
        elif root.is_file() and root.suffix.casefold() in IMAGE_EXTENSIONS:
            images.add(root.resolve())
    return len(images)


def create_metrics(
    riders_path: Path,
    drive_manifest_path: Path,
    public_image_paths: list[Path],
) -> dict[str, object]:
    riders = read_json(riders_path)
    drive_manifest = read_json(drive_manifest_path)
    if not isinstance(riders, list) or not riders:
        raise ValueError("riders must be a non-empty array")
    files = drive_manifest.get("files")
    if not isinstance(files, list):
        raise ValueError("Drive manifest files must be an array")
    declared_images = drive_manifest.get("image_count")
    if declared_images != len(files):
        raise ValueError(
            f"Drive manifest image_count mismatch: declared {declared_images}, found {len(files)}"
        )

    result_count = 0
    for index, rider in enumerate(riders, 1):
        if not isinstance(rider, dict):
            raise ValueError(f"rider {index} is not an object")
        history = rider.get("competition_history") or []
        if not isinstance(history, list):
            raise ValueError(f"rider {index} competition_history is not an array")
        result_count += len(history)

    return {
        "schema_version": 1,
        "counts": {
            "riders": len(riders),
            "results": result_count,
            "images": len(files),
            "published_images": count_public_images(public_image_paths),
        },
    }


def load_metrics(path: Path, *, required: bool) -> dict[str, int] | None:
    try:
        payload = read_json(path)
        counts = payload["counts"]
        parsed = {name: int(counts[name]) for name in METRICS}
        if payload.get("schema_version") != 1 or any(value < 0 for value in parsed.values()):
            raise ValueError("unsupported or negative metrics")
        return parsed
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        if required:
            raise ValueError(f"invalid candidate health file {path}: {exc}") from exc
        print(f"No usable production baseline at {path}; absolute safety floors still apply.")
        return None


def validate_metrics(
    candidate: dict[str, int],
    baseline: dict[str, int] | None,
    minimums: dict[str, int],
    maximum_drop: dict[str, float],
) -> list[str]:
    failures = []
    for name in METRICS:
        current = candidate[name]
        minimum = minimums[name]
        if current < minimum:
            failures.append(f"{name}: {current} is below the mandatory minimum {minimum}")
        if baseline and baseline[name] > 0:
            previous = baseline[name]
            drop = (previous - current) / previous * 100
            if drop > maximum_drop[name]:
                failures.append(
                    f"{name}: {current} vs {previous} in production "
                    f"({drop:.1f}% drop; maximum {maximum_drop[name]:.1f}%)"
                )
    return failures


def command_create(args) -> int:
    metrics = create_metrics(args.riders, args.drive_manifest, args.public_image_path)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(metrics, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    counts = metrics["counts"]
    print(
        f"Deployment health: {counts['riders']} riders, "
        f"{counts['results']} results, {counts['images']} Drive images, "
        f"{counts['published_images']} published images."
    )
    return 0


def command_validate(args) -> int:
    candidate = load_metrics(args.candidate, required=True)
    baseline = load_metrics(args.baseline, required=False) if args.baseline else None
    minimums = {
        "riders": args.min_riders,
        "results": args.min_results,
        "images": args.min_images,
        "published_images": args.min_published_images,
    }
    maximum_drop = {
        "riders": args.max_rider_drop,
        "results": args.max_result_drop,
        "images": args.max_image_drop,
        "published_images": args.max_published_image_drop,
    }
    failures = validate_metrics(candidate, baseline, minimums, maximum_drop)

    baseline_text = "none" if baseline is None else ", ".join(
        f"{name}={baseline[name]}" for name in METRICS
    )
    print("Candidate: " + ", ".join(f"{name}={candidate[name]}" for name in METRICS))
    print(f"Production baseline: {baseline_text}")
    if failures:
        print("Production deployment blocked:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("Production volume guard: passed")
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create")
    create.add_argument("--riders", type=Path, required=True)
    create.add_argument("--drive-manifest", type=Path, required=True)
    create.add_argument("--public-image-path", type=Path, action="append", required=True)
    create.add_argument("--output", type=Path, required=True)
    create.set_defaults(handler=command_create)

    validate = commands.add_parser("validate")
    validate.add_argument("--candidate", type=Path, required=True)
    validate.add_argument("--baseline", type=Path)
    validate.add_argument("--min-riders", type=int, default=300)
    validate.add_argument("--min-results", type=int, default=750)
    validate.add_argument("--min-images", type=int, default=1200)
    validate.add_argument("--min-published-images", type=int, default=1500)
    validate.add_argument("--max-rider-drop", type=float, default=5.0)
    validate.add_argument("--max-result-drop", type=float, default=10.0)
    validate.add_argument("--max-image-drop", type=float, default=10.0)
    validate.add_argument("--max-published-image-drop", type=float, default=10.0)
    validate.set_defaults(handler=command_validate)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        return args.handler(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Deployment health error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
