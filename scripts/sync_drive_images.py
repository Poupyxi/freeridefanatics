#!/usr/bin/env python3
"""Download a shared Google Drive image library without modifying Drive."""

import argparse
import hashlib
import json
import os
import re
import shutil
from pathlib import Path

FOLDER_MIME = "application/vnd.google-apps.folder"
READ_ONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
SAFE_SEGMENT = re.compile(r"[\\/\x00]")
LIBRARY_SECTION_NAMES = {"ppriders", "pictureriders", "equipment"}


def safe_name(name: str) -> str:
    candidate = SAFE_SEGMENT.sub("_", (name or "").strip())
    if candidate in {"", ".", ".."}:
        raise ValueError(f"Unsafe or empty Drive filename: {name!r}")
    return candidate


def safe_output(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    forbidden = {Path("/").resolve(), Path.home().resolve(), Path.cwd().resolve()}
    if resolved in forbidden or len(resolved.parts) < 3:
        raise ValueError(f"Unsafe synchronization target: {resolved}")
    return resolved


def safe_public_mirror(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if tuple(part.casefold() for part in resolved.parts[-3:]) != (
        "assets", "img", "drive-library"
    ):
        raise ValueError(f"Drive mirror must end with assets/img/drive-library: {resolved}")
    return resolved


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
    return service_account.Credentials.from_service_account_info(
        info,
        scopes=[READ_ONLY_SCOPE],
    )


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


def download_file(service, file_id: str, destination: Path):
    from googleapiclient.http import MediaIoBaseDownload

    destination.parent.mkdir(parents=True, exist_ok=True)
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    with destination.open("wb") as handle:
        downloader = MediaIoBaseDownload(handle, request, chunksize=8 * 1024 * 1024)
        done = False
        while not done:
            _status, done = downloader.next_chunk(num_retries=3)


def sync_folder(service, folder_id: str, destination: Path, relative=Path(".")):
    records = []
    seen_names = set()
    for item in list_children(service, folder_id):
        name = safe_name(item.get("name"))
        folded = name.casefold()
        if folded in seen_names:
            path = Path(name)
            suffix = f"--{item['id'][:8]}"
            name = f"{path.stem}{suffix}{path.suffix}"
            folded = name.casefold()
            counter = 2
            while folded in seen_names:
                name = f"{path.stem}{suffix}-{counter}{path.suffix}"
                folded = name.casefold()
                counter += 1
        seen_names.add(folded)
        child_relative = relative / name
        child_path = destination / child_relative
        mime = item.get("mimeType")
        if mime == FOLDER_MIME:
            child_path.mkdir(parents=True, exist_ok=True)
            records.extend(sync_folder(service, item["id"], destination, child_relative))
        elif isinstance(mime, str) and mime.startswith("image/"):
            download_file(service, item["id"], child_path)
            digest = hashlib.sha256(child_path.read_bytes()).hexdigest()
            records.append({
                "path": child_relative.as_posix(),
                "drive_id": item["id"],
                "mime_type": mime,
                "modified_time": item.get("modifiedTime"),
                "drive_md5": item.get("md5Checksum"),
                "sha256": digest,
                "size": child_path.stat().st_size,
            })
    return records


def main():
    from googleapiclient.discovery import build

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--folder-id",
        default=os.environ.get("GOOGLE_DRIVE_IMAGE_FOLDER_ID", "").strip(),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--public-mirror", type=Path)
    args = parser.parse_args()
    if not args.folder_id:
        raise SystemExit("GOOGLE_DRIVE_IMAGE_FOLDER_ID is required")

    output = safe_output(args.output)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    service = build("drive", "v3", credentials=credentials_from_environment(), cache_discovery=False)
    metadata = service.files().get(
        fileId=args.folder_id,
        fields="id,name,mimeType,modifiedTime",
        supportsAllDrives=True,
    ).execute()
    if metadata.get("mimeType") != FOLDER_MIME:
        raise SystemExit("GOOGLE_DRIVE_IMAGE_FOLDER_ID must identify a folder")

    root_name = safe_name(metadata.get("name"))
    if root_name.casefold() in LIBRARY_SECTION_NAMES:
        (output / root_name).mkdir()
        relative_root = Path(root_name)
    else:
        relative_root = Path(".")
    records = sync_folder(service, args.folder_id, output, relative_root)
    if not records:
        raise SystemExit("No supported images were found in the Google Drive folder")

    if args.public_mirror:
        public_mirror = safe_public_mirror(args.public_mirror)
        if public_mirror.exists():
            shutil.rmtree(public_mirror)
        shutil.copytree(output, public_mirror)

    manifest = {
        "source_folder_id": args.folder_id,
        "source_folder_name": metadata.get("name"),
        "access_scope": READ_ONLY_SCOPE,
        "image_count": len(records),
        "files": sorted(records, key=lambda row: row["path"].casefold()),
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Downloaded {len(records)} Drive images from {metadata.get('name')!r} into {output}")
    if args.public_mirror:
        print(f"Mirrored every downloaded Drive image into {public_mirror}")


if __name__ == "__main__":
    main()
