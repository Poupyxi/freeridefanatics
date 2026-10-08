#!/usr/bin/env python3
"""Verify that a deployed homepage exposes its exact Notion snapshot metadata."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path


class LiveMetadataError(RuntimeError):
    """Raised when rendered site metadata differs from the deployed snapshot."""


def expected_date(metadata: dict) -> tuple[str, str]:
    value = metadata.get("generated_at")
    if not isinstance(value, str):
        raise LiveMetadataError("live sync metadata has no generated_at timestamp")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LiveMetadataError("live sync metadata generated_at is invalid") from exc
    months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    return parsed.date().isoformat(), f"{parsed.day} {months[parsed.month - 1]} {parsed.year}"


def verify_live_site(html_path: Path, metadata_path: Path) -> None:
    try:
        html = html_path.read_text(encoding="utf-8")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LiveMetadataError(f"cannot read live deployment evidence: {exc}") from exc
    rider_count = metadata.get("riders")
    if not isinstance(rider_count, int) or rider_count < 1:
        raise LiveMetadataError("live sync metadata has no valid rider count")
    count_marker = f'<span class="icon-btn">{rider_count} Riders</span>'
    if count_marker not in html:
        raise LiveMetadataError(f"homepage does not display the snapshot count ({rider_count} Riders)")
    iso_date, date_label = expected_date(metadata)
    date_marker = f'<time datetime="{iso_date}">{date_label}</time>'
    if date_marker not in html:
        raise LiveMetadataError(
            f"homepage update date does not match generated_at ({iso_date} / {date_label})"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    args = parser.parse_args()
    try:
        verify_live_site(args.html, args.metadata)
    except LiveMetadataError as exc:
        raise SystemExit(f"Live site metadata verification failed: {exc}") from exc
    print("Live rider count and Notion generation date match the deployed snapshot.")


if __name__ == "__main__":
    main()
