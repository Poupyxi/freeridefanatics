#!/usr/bin/env python3
"""Replace snapshot-specific rider totals with reusable translation templates."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG_DIR = ROOT / "assets" / "i18n"
DATA_PATH = Path(os.environ.get("RF_DATA_PATH", ROOT / "data" / "riders.json"))
if not DATA_PATH.is_absolute():
    DATA_PATH = ROOT / DATA_PATH
DATASET_RIDER_COUNT = int(os.environ.get(
    "RF_RIDER_COUNT",
    len(json.loads(DATA_PATH.read_text(encoding="utf-8"))),
))
COUNT_TEXT = re.compile(
    rf"\b(?P<count>{DATASET_RIDER_COUNT})(?P<space>\s+)riders?\b",
    re.IGNORECASE,
)
SPLIT_TEXT = re.compile(
    rf"^(?P<count>{DATASET_RIDER_COUNT}) riders · (?P<women>\d+) women · (?P<men>\d+) men$",
    re.IGNORECASE,
)
ALL_TEXT = re.compile(rf"^All \((?P<count>{DATASET_RIDER_COUNT})\)$")
TRANSLATIONS = {
    "fr": ("{count} pilotes", "{count} pilotes · {women} femmes · {men} hommes"),
    "de": ("{count} Fahrer", "{count} Fahrer · {women} Frauen · {men} Männer"),
    "es": ("{count} ciclistas", "{count} ciclistas · {women} mujeres · {men} hombres"),
    "it": ("{count} rider", "{count} rider · {women} donne · {men} uomini"),
    "pt": ("{count} atletas", "{count} atletas · {women} mulheres · {men} homens"),
    "nl": ("{count} renners", "{count} renners · {women} vrouwen · {men} mannen"),
    "pl": ("{count} zawodników", "{count} zawodników · {women} kobiet · {men} mężczyzn"),
    "ja": ("{count}人のライダー", "{count}人のライダー · 女子{women}人 · 男子{men}人"),
    "zh-cn": ("{count} 位车手", "{count} 位车手 · {women} 位女子 · {men} 位男子"),
}


def normalize_catalog(path: Path, language: str) -> int:
    catalog = json.loads(path.read_text(encoding="utf-8"))
    normalized = {}
    changed = 0
    for key, value in catalog.items():
        new_key = key
        new_value = value
        split_match = SPLIT_TEXT.match(key)
        count_match = COUNT_TEXT.search(key)
        all_match = ALL_TEXT.match(key)
        if split_match:
            new_key = "{count} riders · {women} women · {men} men"
            for placeholder in ("count", "women", "men"):
                number = split_match.group(placeholder)
                new_value = new_value.replace(number, "{" + placeholder + "}", 1)
            changed += 1
        elif count_match:
            number = count_match.group("count")
            start, end = count_match.span("count")
            new_key = key[:start] + "{count}" + key[end:]
            new_value = new_value.replace(number, "{count}", 1)
            changed += 1
        elif all_match:
            number = all_match.group("count")
            new_key = "All ({count})"
            new_value = new_value.replace(number, "{count}", 1)
            changed += 1
        normalized[new_key] = new_value
    catalog = normalized
    count_text, split_text = TRANSLATIONS[language]
    catalog["{count} Riders"] = count_text
    catalog["{count} riders · {women} women · {men} men"] = split_text
    pretty = path.name == "fr-overrides.json"
    path.write_text(
        json.dumps(
            catalog,
            ensure_ascii=False,
            indent=2 if pretty else None,
            separators=None if pretty else (",", ":"),
        ) + "\n",
        encoding="utf-8",
    )
    return changed


def main() -> None:
    total = 0
    for path in sorted(CATALOG_DIR.glob("*.json")):
        language = "fr" if path.name == "fr-overrides.json" else path.stem
        if language not in TRANSLATIONS:
            continue
        total += normalize_catalog(path, language)
    print(f"Normalized {total} snapshot-specific rider-count translations.")


if __name__ == "__main__":
    main()
