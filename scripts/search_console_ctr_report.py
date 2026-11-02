#!/usr/bin/env python3
"""Build a prioritized CTR opportunity report from Search Console CSV exports.

The Search Console UI exports queries and pages separately. This script accepts
either export, or an API export containing both ``page`` and ``query`` columns.
Raw Search Console data stays outside Git; only the generated report is written.
"""

from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


ALIASES = {
    "page": {"page", "pages", "url", "landing page"},
    "query": {"query", "queries", "requête", "requêtes", "top queries"},
    "clicks": {"clicks", "clics"},
    "impressions": {"impressions"},
    "ctr": {"ctr", "taux de clics"},
    "position": {"position", "average position", "position moyenne"},
}

# Conservative targets: opportunities, not promises.
TARGET_CTR = {
    1: 0.28,
    2: 0.16,
    3: 0.11,
    4: 0.08,
    5: 0.06,
    6: 0.045,
    7: 0.035,
    8: 0.028,
    9: 0.023,
    10: 0.020,
    11: 0.017,
    12: 0.015,
    13: 0.013,
    14: 0.012,
    15: 0.011,
    16: 0.010,
    17: 0.009,
    18: 0.008,
    19: 0.007,
    20: 0.006,
}


def normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def parse_number(value: str) -> float:
    value = value.strip().replace("\u202f", "").replace(" ", "")
    if not value:
        return 0.0
    if value.endswith("%"):
        return float(value[:-1].replace(",", ".")) / 100
    if "," in value and "." not in value:
        value = value.replace(",", ".")
    return float(value)


def column_map(fieldnames: list[str]) -> dict[str, str]:
    found = {}
    for original in fieldnames:
        key = normalized(original)
        for canonical, aliases in ALIASES.items():
            if key in aliases:
                found[canonical] = original
    missing = {"clicks", "impressions", "ctr", "position"} - found.keys()
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
    if "page" not in found and "query" not in found:
        raise ValueError("The export must contain a Page/URL or Query column")
    return found


def title_case_query(query: str) -> str:
    small = {"and", "of", "the", "de", "du", "des", "et"}
    words = []
    for index, word in enumerate(query.split()):
        words.append(word.lower() if index and word.lower() in small else word.capitalize())
    return " ".join(words)


def suggested_title(page: str, query: str) -> str:
    topic = title_case_query(query) if query else ""
    path = urlparse(page).path if page else ""
    slug = Path(path).stem.replace("-", " ") if path else ""
    if not topic:
        topic = title_case_query(slug)
    if "/riders/" in path:
        proposal = f"{topic} — Profile & Bike Setup"
    elif "/rounds/" in path:
        proposal = f"{topic} — Results & Ranking"
    elif "standings" in path:
        proposal = f"{topic} — Current Standings"
    elif "/competitions/" in path or "competition" in path:
        proposal = f"{topic} — Events, Results & Riders"
    else:
        proposal = topic or "RidersFanatics"
    suffix = " | RidersFanatics"
    limit = 60 - len(suffix)
    if len(proposal) > limit:
        proposal = proposal[:limit].rstrip(" -—|,&")
    return proposal + suffix


@dataclass
class Opportunity:
    page: str
    query: str
    clicks: int
    impressions: int
    ctr: float
    position: float
    target_ctr: float
    priority_score: float
    source: str

    @property
    def priority(self) -> str:
        if self.priority_score >= 20:
            return "High"
        if self.priority_score >= 5:
            return "Medium"
        return "Low"


def read_export(path: Path, min_impressions: int, max_position: float) -> list[Opportunity]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        reader = csv.DictReader(handle, dialect=dialect)
        mapping = column_map(reader.fieldnames or [])
        source = "page-query" if {"page", "query"} <= mapping.keys() else next(
            key for key in ("page", "query") if key in mapping
        )
        rows = []
        for row in reader:
            impressions = int(parse_number(row[mapping["impressions"]]))
            position = parse_number(row[mapping["position"]])
            ctr = parse_number(row[mapping["ctr"]])
            if impressions < min_impressions or position <= 0 or position > max_position:
                continue
            rank = max(1, min(20, round(position)))
            target = TARGET_CTR[rank]
            gap = max(0.0, target - ctr)
            if gap == 0:
                continue
            # Estimated additional clicks, weighted toward actionable positions 3–12.
            weight = 1.25 if 3 <= position <= 12 else 1.0
            rows.append(
                Opportunity(
                    page=row.get(mapping.get("page", ""), "").strip(),
                    query=row.get(mapping.get("query", ""), "").strip(),
                    clicks=int(parse_number(row[mapping["clicks"]])),
                    impressions=impressions,
                    ctr=ctr,
                    position=position,
                    target_ctr=target,
                    priority_score=impressions * gap * weight,
                    source=source,
                )
            )
    return rows


def write_csv(path: Path, rows: list[Opportunity]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "Page", "Query", "Clicks", "Impressions", "Position", "Current CTR",
            "Target CTR", "Priority", "Opportunity score", "Suggested title", "Source",
        ])
        for row in rows:
            writer.writerow([
                row.page, row.query, row.clicks, row.impressions, f"{row.position:.1f}",
                f"{row.ctr:.1%}", f"{row.target_ctr:.1%}", row.priority,
                f"{row.priority_score:.1f}", suggested_title(row.page, row.query), row.source,
            ])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exports", nargs="+", type=Path, help="Search Console CSV export(s)")
    parser.add_argument("--output", type=Path, default=Path("tmp/search-console/ctr-opportunities.csv"))
    parser.add_argument("--min-impressions", type=int, default=30)
    parser.add_argument("--max-position", type=float, default=20)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    rows = []
    for export in args.exports:
        rows.extend(read_export(export, args.min_impressions, args.max_position))
    rows.sort(key=lambda row: (-row.priority_score, row.position, -row.impressions))
    rows = rows[: args.limit]
    write_csv(args.output, rows)
    print(f"Wrote {len(rows)} CTR opportunities to {args.output}")


if __name__ == "__main__":
    main()
