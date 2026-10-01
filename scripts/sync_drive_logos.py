#!/usr/bin/env python3
"""Synchronize public logo assets from Google Drive without modifying Drive.

This is deliberately separate from the rider/equipment image synchronization.
It reads only the ``Brand logo``, ``Competition logo`` and ``Team logo``
folders, converts supported images to WebP, and writes a small deterministic
manifest consumed by ``build.py``.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import unicodedata
from pathlib import Path

from PIL import Image

try:
    import pillow_avif  # noqa: F401 - registers AVIF support with Pillow
except ImportError:
    pillow_avif = None


FOLDER_MIME = "application/vnd.google-apps.folder"
READ_ONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
SUPPORTED_MIME = {"image/jpeg", "image/png", "image/webp", "image/avif"}
SECTIONS = {
    "brand logo": ("brands", "brands"),
    "competition logo": ("competitions", "competitions"),
    "team logo": ("teams", "teams"),
}
REQUIRED_COMPETITION_KEYS = {
    "beyondgravity",
    "project-17",
    "red-bull-cerro-abajo-2026",
    "redbull-2026",
    "redbull-hardline-2026",
    "redbull-rampage-2026",
    "uci-mtb-world-cup-dh-2026",
}
COMPETITION_ALIASES = {
    "beyond-gravity-2027": "beyondgravity",
    "project17-2026": "project-17",
    "rebbull-2026": "redbull-2026",
    "redbull-2026": "redbull-2026",
    "redbullcerroabajo2026": "red-bull-cerro-abajo-2026",
    "redbull-rampage-2026": "redbull-rampage-2026",
    "red-bull-hardline-colombie-britannique-logo": "redbull-hardline-2026",
    "uci-mountain-bike-world-series-2026": "uci-mtb-world-cup-dh-2026",
}
COMPETITION_NAMES = {
    "beyondgravity": "Beyond Gravity",
    "project-17": "Project 17",
    "red-bull-cerro-abajo-2026": "Red Bull Cerro Abajo",
    "redbull-2026": "Red Bull",
    "redbull-hardline-2026": "Red Bull Hardline",
    "redbull-rampage-2026": "Red Bull Rampage",
    "uci-mtb-world-cup-dh-2026": "UCI Mountain Bike World Series",
}
BRAND_ALIASES = {
    # Preserve the official spelling even when the Drive filename has a typo.
    "forbiden": ("forbidden", "Forbidden"),
}


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")


def display_name(stem: str) -> str:
    return re.sub(r"[_-]+", " ", stem).strip()


def competition_key(stem: str) -> str:
    slug = slugify(stem)
    return COMPETITION_ALIASES.get(slug, slug)


def safe_relative_asset(value: str) -> bool:
    return bool(re.fullmatch(r"assets/img/(?:brands|competitions|teams)/[a-z0-9-]+\.webp", value))


def credentials_from_environment():
    from google.oauth2 import service_account

    raw = os.environ.get("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        raise RuntimeError("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON is required")
    try:
        info = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON is not valid JSON") from exc
    if info.get("type") != "service_account":
        raise RuntimeError("Google Drive credentials must describe a service account")
    return service_account.Credentials.from_service_account_info(info, scopes=[READ_ONLY_SCOPE])


def list_children(service, folder_id: str):
    token = None
    while True:
        response = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="nextPageToken,files(id,name,mimeType,modifiedTime,md5Checksum,size)",
            pageSize=1000,
            pageToken=token,
            orderBy="folder,name",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        yield from response.get("files", [])
        token = response.get("nextPageToken")
        if not token:
            return


def drive_bytes(service, file_id: str) -> bytes:
    from googleapiclient.http import MediaIoBaseDownload

    output = io.BytesIO()
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    downloader = MediaIoBaseDownload(output, request, chunksize=4 * 1024 * 1024)
    done = False
    while not done:
        _status, done = downloader.next_chunk(num_retries=3)
    return output.getvalue()


def local_sections(source: Path):
    for folder_name, (manifest_section, output_folder) in SECTIONS.items():
        folder = next(
            (item for item in source.iterdir() if item.is_dir() and item.name.casefold() == folder_name),
            None,
        )
        if folder:
            yield manifest_section, output_folder, [
                {
                    "id": None,
                    "name": item.name,
                    "mimeType": "",
                    "modifiedTime": None,
                    "bytes": item.read_bytes(),
                }
                for item in sorted(folder.iterdir(), key=lambda path: path.name.casefold())
                if item.is_file()
            ]


def drive_sections(service, root_id: str):
    folders = {
        item["name"].casefold(): item
        for item in list_children(service, root_id)
        if item.get("mimeType") == FOLDER_MIME
    }
    for folder_name, (manifest_section, output_folder) in SECTIONS.items():
        folder = folders.get(folder_name)
        if not folder:
            raise RuntimeError(f"Drive folder {folder_name!r} is missing from the configured root")
        records = []
        for item in list_children(service, folder["id"]):
            if item.get("mimeType") not in SUPPORTED_MIME:
                continue
            item = dict(item)
            item["bytes"] = drive_bytes(service, item["id"])
            records.append(item)
        yield manifest_section, output_folder, records


def to_webp(raw: bytes) -> bytes:
    with Image.open(io.BytesIO(raw)) as image:
        image.load()
        if image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGBA" if "transparency" in image.info else "RGB")
        output = io.BytesIO()
        image.save(output, "WEBP", quality=92, method=6, lossless=image.mode == "RGBA")
        return output.getvalue()


def previous_managed_assets(manifest_path: Path) -> set[str]:
    if not manifest_path.exists():
        return set()
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    return {
        entry.get("src")
        for entries in (payload.get("logos") or {}).values()
        for entry in entries
        if safe_relative_asset(entry.get("src") or "")
    }


def synchronize(sections, root: Path, manifest_path: Path, source_folder_id: str | None):
    manifest = {
        "source": "google-drive-read-only",
        "source_folder_id": source_folder_id,
        "access_scope": READ_ONLY_SCOPE,
        "logos": {"brands": [], "competitions": [], "teams": []},
    }
    seen = {section: set() for section in manifest["logos"]}
    generated_assets = set()

    for section, output_folder, records in sections:
        for record in sorted(records, key=lambda item: item["name"].casefold()):
            stem = Path(record["name"]).stem
            key = competition_key(stem) if section == "competitions" else slugify(stem)
            name = display_name(stem)
            if section == "competitions":
                name = COMPETITION_NAMES.get(key, name)
            elif section == "brands" and key in BRAND_ALIASES:
                key, name = BRAND_ALIASES[key]
            if not key:
                raise RuntimeError(f"Cannot generate a logo key from {record['name']!r}")
            if key in seen[section]:
                raise RuntimeError(f"Duplicate {section} logo key {key!r}")
            seen[section].add(key)
            converted = to_webp(record["bytes"])
            relative = f"assets/img/{output_folder}/{key}.webp"
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(converted)
            generated_assets.add(relative)
            manifest["logos"][section].append({
                "key": key,
                "name": name,
                "src": relative,
                "drive_id": record.get("id"),
                "modified_time": record.get("modifiedTime"),
                "sha256": hashlib.sha256(converted).hexdigest(),
            })

    missing_sections = [name for name, entries in manifest["logos"].items() if not entries]
    if missing_sections:
        raise RuntimeError(f"No logos were found for: {', '.join(missing_sections)}")
    competition_keys = {entry["key"] for entry in manifest["logos"]["competitions"]}
    missing_competitions = sorted(REQUIRED_COMPETITION_KEYS - competition_keys)
    if missing_competitions:
        raise RuntimeError(f"Required competition logos are missing: {', '.join(missing_competitions)}")

    for stale in previous_managed_assets(manifest_path) - generated_assets:
        stale_path = root / stale
        if stale_path.is_file():
            stale_path.unlink()

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = {name: len(entries) for name, entries in manifest["logos"].items()}
    print(f"Drive logos synchronized: {counts['brands']} brands, {counts['competitions']} competitions, {counts['teams']} teams")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder-id", default=os.environ.get("GOOGLE_DRIVE_IMAGE_FOLDER_ID", "").strip())
    parser.add_argument("--source-directory", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--manifest", type=Path, default=Path("data/drive-logo-manifest.json"))
    args = parser.parse_args()
    root = args.root.resolve()
    manifest_path = args.manifest if args.manifest.is_absolute() else root / args.manifest

    if args.source_directory:
        source = args.source_directory.resolve()
        synchronize(local_sections(source), root, manifest_path, None)
        return
    if not args.folder_id:
        raise SystemExit("GOOGLE_DRIVE_IMAGE_FOLDER_ID is required")
    from googleapiclient.discovery import build

    service = build("drive", "v3", credentials=credentials_from_environment(), cache_discovery=False)
    synchronize(drive_sections(service, args.folder_id), root, manifest_path, args.folder_id)


if __name__ == "__main__":
    main()
