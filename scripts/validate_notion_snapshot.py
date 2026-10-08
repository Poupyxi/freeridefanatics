#!/usr/bin/env python3
"""Reject incomplete, altered or stale Notion exports before deployment."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path


class SnapshotValidationError(RuntimeError):
    """Raised when a Notion snapshot is unsafe to deploy."""


def parse_timestamp(value: object) -> dt.datetime:
    if not isinstance(value, str) or not value.strip():
        raise SnapshotValidationError("sync metadata has no generated_at timestamp")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SnapshotValidationError("sync metadata generated_at is invalid") from exc
    if parsed.tzinfo is None:
        raise SnapshotValidationError("sync metadata generated_at must include a timezone")
    return parsed.astimezone(dt.timezone.utc)


def validate_snapshot(
    riders_path: Path,
    metadata_path: Path,
    *,
    max_age_hours: float = 48,
    now: dt.datetime | None = None,
) -> dict:
    try:
        riders_bytes = riders_path.read_bytes()
    except OSError as exc:
        raise SnapshotValidationError(f"Notion riders snapshot is missing: {riders_path}") from exc
    try:
        riders = json.loads(riders_bytes)
    except json.JSONDecodeError as exc:
        raise SnapshotValidationError("Notion riders snapshot is not valid JSON") from exc
    if not isinstance(riders, list) or not riders:
        raise SnapshotValidationError("Notion riders snapshot must be a non-empty list")

    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SnapshotValidationError(f"Notion sync metadata is missing: {metadata_path}") from exc
    except json.JSONDecodeError as exc:
        raise SnapshotValidationError("Notion sync metadata is not valid JSON") from exc
    if not isinstance(metadata, dict):
        raise SnapshotValidationError("Notion sync metadata must be a JSON object")

    expected_fields = {
        "source": "notion-read-only",
        "profile_data_source": "notion-only",
        "image_source": "google-drive-only",
    }
    for field, expected in expected_fields.items():
        if metadata.get(field) != expected:
            raise SnapshotValidationError(f"sync metadata {field} must equal {expected!r}")

    if metadata.get("riders") != len(riders):
        raise SnapshotValidationError(
            f"rider count mismatch: metadata={metadata.get('riders')!r}, file={len(riders)}"
        )
    digest = hashlib.sha256(riders_bytes).hexdigest()
    if metadata.get("sha256") != digest:
        raise SnapshotValidationError("riders snapshot SHA-256 does not match sync metadata")

    generated_at = parse_timestamp(metadata.get("generated_at"))
    current = now or dt.datetime.now(dt.timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=dt.timezone.utc)
    current = current.astimezone(dt.timezone.utc)
    age = current - generated_at
    if age < dt.timedelta(minutes=-5):
        raise SnapshotValidationError("Notion snapshot timestamp is more than five minutes in the future")
    if age > dt.timedelta(hours=max_age_hours):
        raise SnapshotValidationError(
            f"Notion snapshot is stale ({age.total_seconds() / 3600:.1f}h; limit {max_age_hours:g}h)"
        )
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--riders", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--max-age-hours", type=float, default=48)
    args = parser.parse_args()
    try:
        metadata = validate_snapshot(
            args.riders,
            args.metadata,
            max_age_hours=args.max_age_hours,
        )
    except SnapshotValidationError as exc:
        raise SystemExit(f"Notion snapshot validation failed: {exc}") from exc
    print(
        f"Notion snapshot valid: {metadata['riders']} riders, "
        f"generated {metadata['generated_at']}."
    )


if __name__ == "__main__":
    main()
