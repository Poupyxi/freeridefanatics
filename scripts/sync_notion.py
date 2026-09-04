#!/usr/bin/env python3
"""Export the read-only RidersFanatics Notion model to the site data contract.

The exporter never writes to Notion.  It queries the connected data sources,
keeps 2026 UCI downhill results with at least one point, combines final and
qualifying points for each event, and merges the result with the current Google
snapshot so profile fields and photos remain stable during the migration.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


API_ROOT = "https://api.notion.com/v1"
NOTION_VERSION = "2026-03-11"
ROOT = Path(__file__).resolve().parents[1]

DATA_SOURCES = {
    "seasons": "3c99cf6b-f148-80f4-a3ad-000b1635fee6",
    "riders": "3c89cf6b-f148-8044-9283-000b552443a8",
    "scoring": "3c99cf6b-f148-80cb-9bb7-000b0e98c714",
    "races": "3c99cf6b-f148-8025-8fd2-000b87843559",
    "events": "3c99cf6b-f148-80df-9d17-000b005efc59",
    "teams": "3c89cf6b-f148-800a-8bc8-000bebe8103a",
    "countries": "3ce9cf6b-f148-8067-98e3-000b66b51feb",
    "equipment": "3c99cf6b-f148-8010-a1c7-000b9ef9ef98",
    "brands": "3cb9cf6b-f148-8090-b481-000b49ff2d90",
    "equipment_links": "3ca9cf6b-f148-8018-9a11-000b4b610ef2",
}
PRIMARY_SEASON_PAGE_ID = "3c99cf6b-f148-8077-b23f-e87cec70ad46"

CATEGORY_MAP = {
    "Shox": "RearShock",
    "Frame": "Frame",
    "Fork": "Fork",
    "Wheels": "Wheels",
    "Seatposts": "DropperPost",
    "Dropper Post": "DropperPost",
    "Handlebar": "Handlebar",
    "Saddle": "Saddle",
    "Crankset": "Crankset",
    "Derailleur": "Derailleur",
    "Brake": "BrakeLever",
    "Grip": "GRIP",
    "Chain": "CHAIN",
    "Disk": "Disk",
    "Tires": "Tires",
    "Pedals": "Pedals",
    "Shoes": "Shoes",
    "Helmet": "Helmet",
    "Protection": "Protection",
    "Goggles": "Goggles",
}


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def page_id(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"([0-9a-f]{32})", value.replace("-", ""), re.I)
    if not match:
        return None
    raw = match.group(1).lower()
    return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"


class Notion:
    def __init__(self, token: str):
        self.token = token

    def request(self, method: str, path: str, body=None):
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{API_ROOT}{path}",
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
                "User-Agent": "RidersFanatics-Preprod-Sync/1.0",
            },
        )
        for attempt in range(5):
            try:
                with urllib.request.urlopen(req, timeout=45) as response:
                    return json.load(response)
            except urllib.error.HTTPError as exc:
                if exc.code == 429 or exc.code >= 500:
                    delay = int(exc.headers.get("Retry-After", "0") or 0) or 2 ** attempt
                    time.sleep(min(delay, 30))
                    continue
                detail = exc.read().decode("utf-8", "replace")
                raise RuntimeError(f"Notion API {exc.code} for {path}: {detail}") from exc
            except urllib.error.URLError as exc:
                if attempt == 4:
                    raise RuntimeError(f"Notion API unavailable for {path}: {exc}") from exc
                time.sleep(2 ** attempt)
        raise RuntimeError(f"Notion API failed for {path}")

    def query(self, source_id: str):
        results, cursor = [], None
        while True:
            body = {"page_size": 100, "result_type": "page"}
            if cursor:
                body["start_cursor"] = cursor
            payload = self.request("POST", f"/data_sources/{source_id}/query", body)
            results.extend(item for item in payload.get("results", []) if not item.get("in_trash") and not item.get("archived"))
            if not payload.get("has_more"):
                return results
            cursor = payload.get("next_cursor")

    def retrieve_page(self, identifier: str):
        return self.request("GET", f"/pages/{identifier}")


def prop(page, name):
    return (page.get("properties") or {}).get(name) or {}


def rich_text(items) -> str:
    return "".join(item.get("plain_text") or "" for item in (items or [])).strip()


def value(page, name):
    item = prop(page, name)
    kind = item.get("type")
    raw = item.get(kind) if kind else None
    if kind in {"title", "rich_text"}:
        return rich_text(raw)
    if kind in {"number", "url", "email", "phone_number", "checkbox"}:
        return raw
    if kind in {"select", "status"}:
        return (raw or {}).get("name")
    if kind == "multi_select":
        return [entry.get("name") for entry in (raw or []) if entry.get("name")]
    if kind == "date":
        return (raw or {}).get("start")
    if kind == "relation":
        return [page_id(entry.get("id")) for entry in (raw or []) if page_id(entry.get("id"))]
    if kind == "formula":
        formula = raw or {}
        return formula.get(formula.get("type"))
    if kind == "rollup":
        rollup = raw or {}
        return rollup.get(rollup.get("type"))
    return raw


def title_map(pages, title_property):
    return {page_id(item.get("id")): value(item, title_property) for item in pages}


def instagram_handle(url: str | None) -> str | None:
    if not url:
        return None
    candidate = url.strip().rstrip("/").split("/")[-1].split("?")[0]
    if candidate and candidate.lower() not in {"instagram.com", "www.instagram.com"}:
        return "@" + candidate.lstrip("@")
    return url if url.startswith("@") else None


def safe_int(value_):
    try:
        return int(float(value_))
    except (TypeError, ValueError):
        return None


def ordinal(number: int | None) -> str | None:
    if number is None:
        return None
    suffix = "th" if 10 <= number % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def age_from_birth(birth: str | None) -> int | None:
    if not birth:
        return None
    try:
        born = dt.date.fromisoformat(birth[:10])
    except ValueError:
        return None
    today = dt.date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def display_birth(birth: str | None) -> str | None:
    if not birth:
        return None
    try:
        return dt.date.fromisoformat(birth[:10]).strftime("%d %b %Y").lstrip("0")
    except ValueError:
        return birth


def competition_id(name: str) -> str:
    """Keep the established UCI URL stable while allowing new Notion seasons."""
    if slugify(name) == "uci-world-series-2026":
        return "uci-mtb-world-cup-dh-2026"
    return slugify(name)


def export(client: Notion, baseline_path: Path):
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline_by_slug = {item.get("slug"): item for item in baseline if item.get("slug")}
    baseline_by_handle = {
        (item.get("instagram") or "").lower().lstrip("@"): item
        for item in baseline if item.get("instagram")
    }

    pages = {name: client.query(source_id) for name, source_id in DATA_SOURCES.items()}
    seasons = {}
    event_seasons = {}
    for item in pages["seasons"]:
        identifier = page_id(item.get("id"))
        name = value(item, "Nom") or ""
        event_ids = value(item, "🏆 Event ") or []
        if not identifier or not name or not event_ids:
            continue
        seasons[identifier] = {"name": name, "event_ids": event_ids}
        for event_id in event_ids:
            event_seasons.setdefault(event_id, identifier)
    if not seasons:
        raise RuntimeError("No Notion season with visible Event relations was found")

    teams = title_map(pages["teams"], "Nom")
    countries = title_map(pages["countries"], "Name")
    brands = title_map(pages["brands"], "Name")
    events = {
        page_id(item.get("id")): {
            "name": value(item, "Name competition"),
            "date": value(item, "Date") or "9999-12-31",
        }
        for item in pages["events"] if page_id(item.get("id")) in event_seasons
    }

    competition_catalog = {"organizations": [], "series": []}
    ordered_seasons = sorted(
        seasons.items(),
        key=lambda entry: (not entry[1]["name"].lower().startswith("uci"), entry[1]["name"].lower()),
    )
    for identifier, season in ordered_seasons:
        event_records = [events[event_id] for event_id in season["event_ids"] if event_id in events]
        year_match = re.search(r"\b(20\d{2})\b", season["name"])
        competition_catalog["series"].append({
            "id": competition_id(season["name"]),
            "name": season["name"],
            "short_name": re.sub(r"\s+20\d{2}\s*$", "", season["name"]).strip(),
            "sport": "Mountain bike",
            "discipline": "Downhill",
            "season": int(year_match.group(1)) if year_match else 2026,
            "status": "published",
            "notion_page_id": identifier,
            "events": sorted(event_records, key=lambda event: (event["date"], event["name"])),
        })

    races = {}
    for item in pages["races"]:
        event_ids = value(item, "🏆 Event ") or []
        event_id = next((identifier for identifier in event_ids if identifier in events), None)
        season_id = event_seasons.get(event_id)
        phase = value(item, "Sélectionner")
        if season_id and phase in {"Final", "Qualifier"} and value(item, "Type") == "Downhill":
            races[page_id(item.get("id"))] = {
                "event": events[event_id]["name"],
                "date": events[event_id]["date"],
                "gender": value(item, "Sélectionner 1"),
                "phase": phase,
                "competition": seasons[season_id]["name"],
            }

    # Notion stores final and qualifying points on separate Scoring rows.  The
    # public site expects one row per rider and event, so combine both point
    # awards while keeping the final placing as the displayed race result.
    combined_results = {}
    for item in pages["scoring"]:
        rider_ids = value(item, "🚻 Riders") or []
        race_ids = value(item, "🏁 Race") or []
        rider_id = rider_ids[0] if rider_ids else None
        race_id = race_ids[0] if race_ids else None
        points = safe_int(value(item, "points"))
        place = safe_int(value(item, "Place"))
        if rider_id and race_id in races and points is not None and points >= 1:
            race = races[race_id]
            key = (rider_id, race["competition"], race["event"], race["gender"])
            year_match = re.search(r"\b(20\d{2})\b", race["competition"])
            result = combined_results.setdefault(key, {
                "year": int(year_match.group(1)) if year_match else 2026,
                "event": race["event"],
                "category": race["competition"],
                "result": None,
                "place": None,
                "points": 0,
                "_event_date": race["date"],
                "_has_final": False,
            })
            result["points"] += points
            if race["phase"] == "Final":
                result["place"] = place
                result["result"] = ordinal(place)
                result["_has_final"] = True
            elif not result["_has_final"]:
                result["place"] = place
                result["result"] = f"Q1 {ordinal(place)}" if place is not None else "Q1"

    result_rows = {}
    for (rider_id, _competition, _event, _gender), result in combined_results.items():
        result.pop("_has_final", None)
        result_rows.setdefault(rider_id, []).append(result)

    equipment = {}
    for item in pages["equipment"]:
        equipment[page_id(item.get("id"))] = {
            "category": CATEGORY_MAP.get(value(item, "Type")),
            "brand": next((brands.get(identifier) for identifier in (value(item, "Brand") or []) if brands.get(identifier)), ""),
            "model_detail": value(item, "Product") or "",
            "affiliate_link": value(item, "Link"),
            "amazon_link": None,
        }

    equipment_by_rider = {}
    primary_season_id = page_id(os.environ.get("NOTION_SEASON_PAGE_ID", PRIMARY_SEASON_PAGE_ID))
    for item in pages["equipment_links"]:
        if primary_season_id not in set(value(item, "☀️ Saison") or []):
            continue
        rider_ids = value(item, "🚻 Riders") or []
        product_ids = value(item, "Equipments") or []
        for rider_id in rider_ids:
            for product_id in product_ids:
                product = equipment.get(product_id)
                if product and product.get("category") and (product.get("brand") or product.get("model_detail")):
                    normalized = dict(product)
                    normalized["brand_model"] = ";".join(part for part in (normalized["brand"], normalized["model_detail"]) if part)
                    equipment_by_rider.setdefault(rider_id, []).append(normalized)

    riders = []
    for item in pages["riders"]:
        identifier = page_id(item.get("id"))
        if identifier not in result_rows:
            continue
        name = value(item, "First Name") or ""
        handle = instagram_handle(value(item, "Instagram"))
        base = baseline_by_handle.get((handle or "").lower().lstrip("@")) or baseline_by_slug.get(slugify(name)) or {}
        rider = dict(base)
        birth = value(item, "Date of Birth")
        team = next((teams.get(team_id) for team_id in (value(item, "Team") or []) if teams.get(team_id)), None)
        country = next((countries.get(country_id) for country_id in (value(item, "counrty") or []) if countries.get(country_id)), None)
        gender = value(item, "Gender")
        display_name = name.strip() or base.get("display_name") or base.get("name")
        history = sorted(result_rows[identifier], key=lambda row: (row["_event_date"], row["event"]))
        for result in history:
            result.pop("_event_date", None)
        rider.update({
            "name": display_name,
            "first_name": display_name.split()[0] if display_name else "",
            "last_name": " ".join(display_name.split()[1:]) if display_name else "",
            "display_name": display_name,
            "slug": base.get("slug") or slugify(display_name),
            "gender_category": "Women Elite" if gender == "Women" else "Men Elite",
            "discipline": "Professional Downhill (DH)",
            "country": country or base.get("country"),
            "hometown": value(item, "Hometown") or base.get("hometown"),
            "date_of_birth": display_birth(birth) or base.get("date_of_birth"),
            "age": age_from_birth(birth) if birth else base.get("age"),
            "instagram": handle or base.get("instagram"),
            "team": team or base.get("team"),
            "bio": value(item, "Biographie et principaux résultats") or base.get("bio") or "",
            "competition_history": history,
            "equipment": equipment_by_rider.get(identifier, base.get("equipment") or []),
            "season": 2026,
        })
        frame = next((part for part in rider["equipment"] if part.get("category") == "Frame"), None)
        if frame:
            rider["bike"] = {"brand": frame.get("brand") or "", "model": frame.get("model_detail") or ""}
        riders.append(rider)

    # Imports can leave two Notion rider pages for the same athlete (usually an
    # established profile plus a result-import profile sharing the same
    # Instagram handle).  Both resolve to the same public slug, so consolidate
    # their season history instead of either publishing a duplicate profile or
    # aborting the whole preproduction refresh.
    riders_by_slug = {}
    for rider in riders:
        slug = rider.get("slug")
        if slug not in riders_by_slug:
            riders_by_slug[slug] = rider
            continue
        current = riders_by_slug[slug]
        histories = {}
        for row in current.get("competition_history", []) + rider.get("competition_history", []):
            key = (row.get("year"), row.get("category"), row.get("event"))
            previous = histories.get(key)
            if previous is None or (row.get("points") or 0) > (previous.get("points") or 0):
                histories[key] = row
        current["competition_history"] = sorted(
            histories.values(), key=lambda row: (row.get("year") or 0, row.get("event") or "")
        )
        equipment_rows = {}
        for part in current.get("equipment", []) + rider.get("equipment", []):
            key = (part.get("category"), part.get("brand"), part.get("model_detail"))
            equipment_rows.setdefault(key, part)
        current["equipment"] = list(equipment_rows.values())
        for field in ("team", "country", "instagram", "hometown", "date_of_birth", "bio"):
            if not current.get(field) and rider.get(field):
                current[field] = rider[field]
    riders = list(riders_by_slug.values())

    if not riders:
        raise RuntimeError("No rider with a 2026 UCI downhill result of at least one point was exported")
    minimum_riders = int(os.environ.get("NOTION_MIN_RIDERS", "40"))
    if len(riders) < minimum_riders:
        raise RuntimeError(f"Only {len(riders)} riders were exported; safety minimum is {minimum_riders}")
    categories = {rider.get("gender_category") for rider in riders}
    if not {"Men Elite", "Women Elite"}.issubset(categories):
        raise RuntimeError("Both Men Elite and Women Elite must be present")
    slugs = [rider.get("slug") for rider in riders]
    if len(slugs) != len(set(slugs)):
        raise RuntimeError("Duplicate rider slugs were generated")
    riders.sort(key=lambda rider: (rider.get("gender_category") or "", -(sum(row["points"] for row in rider["competition_history"])), rider["display_name"]))
    return riders, competition_catalog, {name: len(items) for name, items in pages.items()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, default=ROOT / "data" / "riders.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "notion" / "riders.json")
    parser.add_argument("--competitions-output", type=Path, default=ROOT / "data" / "notion" / "competitions.json")
    parser.add_argument("--metadata", type=Path, default=ROOT / "data" / "notion" / "sync-metadata.json")
    args = parser.parse_args()
    token = os.environ.get("NOTION_TOKEN", "").strip()
    if not token:
        raise SystemExit("NOTION_TOKEN is required")

    riders, competitions, counts = export(Notion(token), args.baseline)
    serialized = json.dumps(riders, ensure_ascii=False, indent=2) + "\n"
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.competitions_output.parent.mkdir(parents=True, exist_ok=True)
    args.metadata.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(serialized, encoding="utf-8")
    args.competitions_output.write_text(
        json.dumps(competitions, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.metadata.write_text(json.dumps({
        "source": "notion-read-only",
        "notion_api_version": NOTION_VERSION,
        "season_data_source_id": DATA_SOURCES["seasons"],
        "seasons": len(competitions["series"]),
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "sha256": digest,
        "riders": len(riders),
        "queried_pages": counts,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Notion snapshot ready: {len(riders)} riders, {len(competitions['series'])} seasons, sha256={digest}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Notion export failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
