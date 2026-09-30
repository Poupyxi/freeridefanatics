#!/usr/bin/env python3
"""Build a content-addressed upload delta for a static deployment.

The remote manifest is treated as advisory and every path is validated. New or
changed files are copied to the delta directory. Files that existed in the
previous manifest but no longer exist locally are written as safe lftp removal
commands. The new manifest is uploaded last by the workflow so a partial upload
can never advertise files that did not reach the server.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path, PurePosixPath


MANIFEST_NAME = "deployment-manifest.json"
SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9._@+-]+$")


def safe_relative_path(value: str) -> bool:
    if not isinstance(value, str) or not value:
        return False
    path = PurePosixPath(value)
    return (
        not path.is_absolute()
        and value != MANIFEST_NAME
        and all(part not in {"", ".", ".."} and SAFE_SEGMENT.fullmatch(part) for part in path.parts)
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(public: Path) -> dict[str, dict[str, object]]:
    files: dict[str, dict[str, object]] = {}
    for path in sorted(public.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(public).as_posix()
        if relative == MANIFEST_NAME:
            continue
        if not safe_relative_path(relative):
            raise ValueError(f"Unsafe public path: {relative!r}")
        files[relative] = {"sha256": sha256(path), "size": path.stat().st_size}
    return files


def load_previous(path: Path) -> dict[str, dict[str, object]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw_files = payload["files"]
        if payload.get("version") != 1 or not isinstance(raw_files, dict):
            return {}
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return {}

    previous: dict[str, dict[str, object]] = {}
    for relative, metadata in raw_files.items():
        if not safe_relative_path(relative) or not isinstance(metadata, dict):
            continue
        digest = metadata.get("sha256")
        size = metadata.get("size")
        if isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest) and isinstance(size, int):
            previous[relative] = {"sha256": digest, "size": size}
    return previous


def ensure_safe_delta(path: Path, public: Path) -> None:
    resolved = path.resolve()
    if resolved == public.resolve() or resolved == Path("/") or resolved == Path.home():
        raise ValueError(f"Unsafe delta directory: {resolved}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--public", required=True, type=Path)
    parser.add_argument("--remote-manifest", required=True, type=Path)
    parser.add_argument("--delta", required=True, type=Path)
    parser.add_argument("--delete-script", required=True, type=Path)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()

    public = args.public.resolve()
    if not public.is_dir():
        raise SystemExit(f"Public directory not found: {public}")
    ensure_safe_delta(args.delta, public)
    if args.delta.exists():
        shutil.rmtree(args.delta)
    args.delta.mkdir(parents=True)

    current = inventory(public)
    previous = load_previous(args.remote_manifest)
    changed = sorted(
        relative for relative, metadata in current.items()
        if previous.get(relative) != metadata
    )
    removed = sorted(set(previous) - set(current))

    for relative in changed:
        destination = args.delta / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(public / relative, destination)

    manifest_path = public / MANIFEST_NAME
    manifest_path.write_text(
        json.dumps({"version": 1, "files": current}, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    args.delete_script.parent.mkdir(parents=True, exist_ok=True)
    args.delete_script.write_text(
        "".join(f'rm -f "{relative}"\n' for relative in removed),
        encoding="utf-8",
    )

    upload_bytes = sum(int(current[relative]["size"]) for relative in changed)
    report = (
        f"Differential deployment: {len(changed)} changed/new files "
        f"({upload_bytes} bytes), {len(removed)} removed, {len(current)} tracked."
    )
    print(report)
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as output:
            output.write(f"changed_count={len(changed)}\n")
            output.write(f"removed_count={len(removed)}\n")
            output.write(f"upload_bytes={upload_bytes}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
