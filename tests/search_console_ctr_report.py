#!/usr/bin/env python3
"""Regression tests for the Search Console CTR opportunity report."""

import csv
import importlib.util
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/search_console_ctr_report.py"
spec = importlib.util.spec_from_file_location("ctr_report", SCRIPT)
report = importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules[spec.name] = report
spec.loader.exec_module(report)

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    source = root / "Queries.csv"
    source.write_text(
        "Requêtes,Clics,Impressions,CTR,Position\n"
        "amaury pierron bike,4,400,1%,5.2\n"
        "irrelevant query,20,25,80%,1.0\n",
        encoding="utf-8",
    )
    rows = report.read_export(source, min_impressions=30, max_position=20)
    assert len(rows) == 1
    assert rows[0].query == "amaury pierron bike"
    assert rows[0].priority == "High"
    assert rows[0].source == "query"
    assert report.suggested_title("", rows[0].query).endswith("| RidersFanatics")

    combined = root / "combined.csv"
    combined.write_text(
        "page,query,clicks,impressions,ctr,position\n"
        "https://ridersfanatics.com/riders/asa-vermette.html,asa vermette bike,2,200,0.01,4\n",
        encoding="utf-8",
    )
    rows = report.read_export(combined, min_impressions=30, max_position=20)
    assert rows[0].source == "page-query"
    title = report.suggested_title(rows[0].page, rows[0].query)
    assert "Profile & Bike Setup" in title
    assert len(title) <= 60

    output = root / "report.csv"
    report.write_csv(output, rows)
    with output.open(encoding="utf-8", newline="") as handle:
        written = list(csv.DictReader(handle))
    assert written[0]["Priority"] in {"High", "Medium", "Low"}
    assert written[0]["Source"] == "page-query"

print("Search Console CTR report tests passed.")
