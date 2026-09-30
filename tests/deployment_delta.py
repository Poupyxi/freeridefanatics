#!/usr/bin/env python3
"""Regression checks for content-addressed static deployment deltas."""

import json
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy" / "prepare-delta.py"


with tempfile.TemporaryDirectory() as temp:
    base = Path(temp)
    public = base / "public"
    delta = base / "delta"
    public.mkdir()
    (public / "assets").mkdir()
    (public / "index.html").write_text("new page", encoding="utf-8")
    (public / ".htaccess").write_text("Options -Indexes", encoding="utf-8")
    unchanged = public / "assets" / "photo.webp"
    unchanged.write_bytes(b"same image")

    import hashlib
    old_manifest = {
        "version": 1,
        "files": {
            "index.html": {"sha256": "0" * 64, "size": 8},
            "assets/photo.webp": {
                "sha256": hashlib.sha256(unchanged.read_bytes()).hexdigest(),
                "size": unchanged.stat().st_size,
            },
            "old.html": {"sha256": "1" * 64, "size": 3},
            "../unsafe": {"sha256": "2" * 64, "size": 3},
        },
    }
    remote = base / "remote.json"
    remote.write_text(json.dumps(old_manifest), encoding="utf-8")
    deletes = base / "delete.lftp"
    subprocess.run(
        [
            "python3", str(SCRIPT), "--public", str(public),
            "--remote-manifest", str(remote), "--delta", str(delta),
            "--delete-script", str(deletes),
        ],
        check=True,
    )

    assert (delta / "index.html").is_file()
    assert (delta / ".htaccess").is_file()
    assert not (delta / "assets" / "photo.webp").exists()
    assert deletes.read_text(encoding="utf-8") == 'rm -f "old.html"\n'
    generated = json.loads((public / "deployment-manifest.json").read_text(encoding="utf-8"))
    assert set(generated["files"]) == {".htaccess", "index.html", "assets/photo.webp"}

print("deployment delta: passed")
