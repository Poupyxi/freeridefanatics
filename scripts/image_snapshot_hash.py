#!/usr/bin/env python3
"""Print a deterministic SHA-256 for generated public image folders."""

import argparse
import hashlib
from pathlib import Path


IMAGE_EXTENSIONS = {".avif", ".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    files = []
    for root in args.paths:
        if root.is_dir():
            files.extend(
                path for path in root.rglob("*")
                if path.is_file() and path.suffix.casefold() in IMAGE_EXTENSIONS
            )
        elif root.is_file() and root.suffix.casefold() in IMAGE_EXTENSIONS:
            files.append(root)
    files = sorted(set(files), key=lambda path: path.as_posix().casefold())
    if not files:
        raise SystemExit("No image was found for snapshot hashing")

    digest = hashlib.sha256()
    for path in files:
        encoded = path.as_posix().encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    print(digest.hexdigest())


if __name__ == "__main__":
    main()
