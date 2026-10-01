#!/usr/bin/env python3
"""Validate and extract a verified production rollback artifact safely."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import tarfile
from pathlib import Path, PurePosixPath


REQUIRED_FILES = {
    ".htaccess",
    "index.html",
    "deployment-health.json",
    "deployment-manifest.json",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_metadata(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key and value:
            values[key] = value
    return values


def safe_output(path: Path) -> Path:
    resolved = path.resolve()
    if resolved in {Path("/").resolve(), Path.home().resolve(), Path.cwd().resolve()}:
        raise ValueError(f"Unsafe restore directory: {resolved}")
    return resolved


def validate_members(archive: tarfile.TarFile) -> set[str]:
    names: set[str] = set()
    for member in archive.getmembers():
        path = PurePosixPath(member.name)
        if path.is_absolute() or any(part in {"", ".."} for part in path.parts):
            raise ValueError(f"Unsafe archive path: {member.name!r}")
        if not (member.isfile() or member.isdir()):
            raise ValueError(f"Unsupported archive entry: {member.name!r}")
        normalized = path.as_posix().removeprefix("./")
        if normalized:
            names.add(normalized)
    missing = REQUIRED_FILES - names
    if missing:
        raise ValueError(f"Rollback snapshot is incomplete: {sorted(missing)}")
    return names


def restore(artifact: Path, expected_run_id: str, output: Path) -> None:
    metadata_path = artifact / "rollback-metadata.txt"
    archive_path = artifact / "public-site.tar"
    if not metadata_path.is_file() or not archive_path.is_file():
        raise ValueError("Rollback artifact is missing its archive or metadata")
    metadata = read_metadata(metadata_path)
    if metadata.get("run_id") != expected_run_id:
        raise ValueError("Rollback run id does not match the requested artifact")
    if metadata.get("archive_sha256") != sha256(archive_path):
        raise ValueError("Rollback archive checksum mismatch")

    destination = safe_output(output)
    with tarfile.open(archive_path, "r") as archive:
        validate_members(archive)
        if destination.exists():
            shutil.rmtree(destination)
        destination.mkdir(parents=True)
        archive.extractall(destination, filter="data")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--expected-run-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    restore(args.artifact.resolve(), args.expected_run_id, args.output)
    print(f"Validated rollback snapshot from run {args.expected_run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
