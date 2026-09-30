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
    generated = health.create_metrics(riders_path, manifest_path)
    assert generated["counts"] == {"riders": 2, "results": 3, "images": 4}

minimums = {"riders": 300, "results": 750, "images": 1200}
limits = {"riders": 5.0, "results": 10.0, "images": 10.0}
baseline = {"riders": 355, "results": 1000, "images": 1400}
safe = {"riders": 350, "results": 950, "images": 1350}
assert health.validate_metrics(safe, baseline, minimums, limits) == []

unsafe = {"riders": 330, "results": 850, "images": 1200}
failures = health.validate_metrics(unsafe, baseline, minimums, limits)
assert any(message.startswith("riders:") for message in failures)
assert any(message.startswith("results:") for message in failures)
assert any(message.startswith("images:") for message in failures)

below_floor = {"riders": 299, "results": 749, "images": 1199}
assert len(health.validate_metrics(below_floor, None, minimums, limits)) == 3

print("deployment health guard: passed")
