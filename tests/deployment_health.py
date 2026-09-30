#!/usr/bin/env python3
"""Offline checks for the mandatory production volume guard."""

import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("deployment_health", ROOT / "scripts" / "deployment_health.py")
health = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(health)


with tempfile.TemporaryDirectory() as temp:
    base = Path(temp)
    riders = [
        {"competition_history": [{"event": "A"}, {"event": "B"}]},
        {"competition_history": [{"event": "A"}]},
    ]
    manifest = {"image_count": 4, "files": [{"path": str(i)} for i in range(4)]}
    riders_path = base / "riders.json"
    manifest_path = base / "manifest.json"
    riders_path.write_text(json.dumps(riders), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    public_images = base / "public-images"
    public_images.mkdir()
    (public_images / "rider one.webp").write_bytes(b"one")
    (public_images / "rider-two.jpg").write_bytes(b"two")
    generated = health.create_metrics(riders_path, manifest_path, [public_images])
    assert generated["counts"] == {
        "riders": 2, "results": 3, "images": 4, "published_images": 2,
    }

minimums = {"riders": 300, "results": 750, "images": 1200, "published_images": 1}
limits = {"riders": 5.0, "results": 10.0, "images": 10.0, "published_images": 10.0}
baseline = {"riders": 355, "results": 1000, "images": 1400, "published_images": 1800}
safe = {"riders": 350, "results": 950, "images": 1350, "published_images": 1750}
assert health.validate_metrics(safe, baseline, minimums, limits) == []

unsafe = {"riders": 330, "results": 850, "images": 1200, "published_images": 1500}
failures = health.validate_metrics(unsafe, baseline, minimums, limits)
assert any(message.startswith("riders:") for message in failures)
assert any(message.startswith("results:") for message in failures)
assert any(message.startswith("images:") for message in failures)
assert any(message.startswith("published_images:") for message in failures)

below_floor = {"riders": 299, "results": 749, "images": 1199, "published_images": 0}
assert len(health.validate_metrics(below_floor, None, minimums, limits)) == 4

print("deployment health guard: passed")
