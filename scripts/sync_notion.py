#!/usr/bin/env python3
"""Export the read-only RidersFanatics Notion model to the site data contract.

The exporter never writes to Notion. It queries the connected data sources,
keeps recorded downhill results (including non-finish statuses), and combines
final and qualifying points for each event. Notion is the only structured-data
source; Google Drive portraits are matched later by ``build.py``.
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
ROUTE_SLUGS_PATH = ROOT / "data" / "rider-routes.json"
ROUTE_SLUGS_BY_HANDLE = json.loads(ROUTE_SLUGS_PATH.read_text(encoding="utf-8"))

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

RESULT_STATUS_ALIASES = {
    "FINISHER": "Finisher",
    "FINISHED": "Finisher",
    "FIN": "Finisher",
    "DNF": "DNF",
    "DNS": "DNS",
    "DSQ": "DSQ",
    "DQ": "DSQ",
    "DISQUALIFIED": "DSQ",
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


def first_value(page, *names):
    """Return the first populated property across current and legacy names."""
    for name in names:
        result = value(page, name)
        if result not in (None, "", []):
            return result
    return None


def title_map(pages, title_property):
    return {page_id(item.get("id")): value(item, title_property) for item in pages}


def instagram_handle(url: str | None) -> str | None:
    if not url:
        return None
    candidate = url.strip().rstrip("/").split("/")[-1].split("?")[0]
    if candidate and candidate.lower() not in {"instagram.com", "www.instagram.com"}:
        return "@" + candidate.lstrip("@")
    return url if url.startswith("@") else None


def season_edition_count(page) -> int | None:
    """Read an edition count regardless of the exact French/English label."""
    for name in (page.get("properties") or {}):
        normalized = slugify(name)
        if "edition" not in normalized:
            continue
        count = safe_int(value(page, name))
        if count is not None and count > 0:
            return count
    return None


def safe_int(value_):
    try:
        return int(float(value_))
    except (TypeError, ValueError):
        return None


def normalize_result_status(value_) -> str | None:
    """Return the canonical race status stored by the public data contract."""
    if value_ is None:
        return None
    normalized = re.sub(r"[^A-Z]+", "", str(value_).upper())
    return RESULT_STATUS_ALIASES.get(normalized)


def scoring_status(item, place: int | None = None) -> str | None:
    """Read an explicit status, or infer a finisher from a place/time value.

    The current Notion database stores statuses in ``Time``. Supporting common
    dedicated property names keeps the exporter compatible with a later schema
    cleanup without requiring a simultaneous site migration.
    """
    explicit = first_value(item, "Status", "Result", "Résultat")
    time_value = value(item, "Time")
    status = normalize_result_status(explicit) or normalize_result_status(time_value)
    if status:
        return status
    if place is not None:
        return "Finisher"
    if isinstance(time_value, str) and re.fullmatch(r"\d{1,2}:\d{2}(?:\.\d+)?", time_value.strip()):
        return "Finisher"
    return None


def scoring_counts_as_participation(phase: str | None, status: str | None) -> bool:
    """A qualifier entry counts as participation, including DNS/DNF/DSQ."""
    return phase == "Qualifier" or status != "DNS"


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
    """Keep established season URLs stable when Notion titles gain a year."""
    slug = slugify(name)
    return {
        "uci-world-series-2026": "uci-mtb-world-cup-dh-2026",
        "project-17-2026": "project-17",
        "beyondgravity-2026": "beyondgravity",
    }.get(slug, slug)


def competition_year(name: str, event_records: list[dict]) -> int:
    """Use the event year when a Notion season name does not include one."""
    event_years = sorted({
        int(event["date"][:4]) for event in event_records
        if re.fullmatch(r"20\d{2}-\d{2}-\d{2}", (event.get("date") or "")[:10])
    })
    # BeyondGravity's dated race is in 2027 even though its Notion title says
    # 2026. Keep the existing public season label aligned with the event date.
    if slugify(name) == "beyondgravity-2026" and len(event_years) == 1:
        return event_years[0]
    year_match = re.search(r"\b(20\d{2})\b", name)
    if year_match:
        return int(year_match.group(1))
    return event_years[0] if event_years else 2026


def export(client: Notion):
    pages = {name: client.query(source_id) for name, source_id in DATA_SOURCES.items()}
    seasons = {}
    event_seasons = {}
    for item in pages["seasons"]:
        identifier = page_id(item.get("id"))
        name = value(item, "Nom") or ""
        event_ids = value(item, "🏆 Event ") or []
        if not identifier or not name or not event_ids:
            continue
        seasons[identifier] = {
            "name": name,
            "event_ids": event_ids,
            "instagram": instagram_handle(value(item, "Instagram")),
            "edition_count": season_edition_count(item),
        }
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
        competition_catalog["series"].append({
            "id": competition_id(season["name"]),
            "name": season["name"],
            "short_name": re.sub(r"\s+20\d{2}\s*$", "", season["name"]).strip(),
            "sport": "Mountain bike",
            "discipline": "Downhill",
            "season": competition_year(season["name"], event_records),
            "status": "published",
            "notion_page_id": identifier,
            "instagram": season.get("instagram"),
            "edition_count": season.get("edition_count"),
            "events": sorted(event_records, key=lambda event: (event["date"], event["name"])),
        })

    races = {}
    for item in pages["races"]:
        event_ids = value(item, "🏆 Event ") or []
        event_id = next((identifier for identifier in event_ids if identifier in events), None)
        season_id = event_seasons.get(event_id)
        phase = value(item, "Sélectionner")
        if season_id and value(item, "Type") == "Downhill":
            races[page_id(item.get("id"))] = {
                "event": events[event_id]["name"],
                "date": events[event_id]["date"],
                "gender": value(item, "Sélectionner 1"),
                "phase": phase,
                "competition": seasons[season_id]["name"],
            }

    # Participation is independent from a timed/point-scoring result. This is
    # especially important for invitational seasons whose entry list can be
    # complete in Notion before timing and placings are published.
    participations_by_rider = {}
    for item in pages["scoring"]:
        rider_ids = value(item, "🚻 Riders") or []
        race_ids = value(item, "🏁 Race") or []
        race = races.get(race_ids[0]) if race_ids else None
        if race is None:
            continue
        place = safe_int(value(item, "Place"))
        # A qualifier entry always belongs to the participant field, including
        # DNS/DNF/DSQ. A final-only DNS does not count as a start.
        if not scoring_counts_as_participation(race["phase"], scoring_status(item, place)):
            continue
        for rider_id in rider_ids:
            participations_by_rider.setdefault(rider_id, set()).add(race["competition"])

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
        status = scoring_status(item, place)
        raw_time = value(item, "Time")
        race_time = (raw_time.strip() if isinstance(raw_time, str)
                     and normalize_result_status(raw_time) is None and raw_time.strip()
                     else None)
        race = races.get(race_id)
        has_points = points is not None and points >= 1
        # Invitational Red Bull races publish an official finishing order but
        # do not necessarily award championship points. Keep those placings so
        # their event result page is not empty. UCI remains points-gated.
        has_invitational_place = (
            place is not None
            and race is not None
            and not race["competition"].casefold().startswith("uci")
        )
        valid_phase = race is not None and race["phase"] in {"Final", "Qualifier"}
        has_recorded_result = status is not None or place is not None
        if rider_id and valid_phase and (has_points or has_invitational_place or has_recorded_result):
            key = (rider_id, race["competition"], race["event"], race["gender"])
            year_match = re.search(r"\b(20\d{2})\b", race["competition"])
            result = combined_results.setdefault(key, {
                "year": int(year_match.group(1)) if year_match else 2026,
                "event": race["event"],
                "category": race["competition"],
                "result": None,
                "status": None,
                "time": None,
                "participated": False,
                "place": None,
                "points": 0,
                "_event_date": race["date"],
                "_has_final": False,
                "_has_points": False,
            })
            if has_points:
                result["points"] += points
                result["_has_points"] = True
            if scoring_counts_as_participation(race["phase"], status):
                result["participated"] = True
            if race["phase"] == "Final":
                result["place"] = place
                result["status"] = status
                result["time"] = race_time
                result["result"] = ordinal(place) if place is not None else status
                result["_has_final"] = True
            elif not result["_has_final"]:
                result["place"] = place
                result["status"] = status
                result["time"] = race_time
                qualifier_result = ordinal(place) if place is not None else status
                result["result"] = f"Q1 {qualifier_result}" if qualifier_result else "Q1"

    result_rows = {}
    for (rider_id, _competition, _event, _gender), result in combined_results.items():
        result.pop("_has_final", None)
        if not result.pop("_has_points", False):
            result["points"] = None
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
        season_ids = set(value(item, "☀️ Saison") or [])
        # New equipment links are sometimes created before their season field
        # is filled in. Keep an explicitly different season isolated, but infer
        # the active season for an untagged link when the related rider already
        # participates in, or has a result for, that season. This prevents a
        # complete rider setup from disappearing because only the link's season
        # cell was left blank.
        if season_ids and primary_season_id not in season_ids:
            continue
        rider_ids = value(item, "🚻 Riders") or []
        if not season_ids:
            rider_ids = [
                rider_id for rider_id in rider_ids
                if rider_id in result_rows or rider_id in participations_by_rider
            ]
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
        name = value(item, "First Name") or ""
        handle = instagram_handle(value(item, "Instagram"))
        birth = value(item, "Date of Birth")
        team_ids = first_value(item, "Team", "team") or []
        team = next((teams.get(team_id) for team_id in team_ids if teams.get(team_id)), None)
        # The live Notion relation is named ``country``. Keep aliases only for
        # harmless schema renames; every value still comes from Notion.
        country_ids = first_value(item, "country", "Country", "counrty") or []
        country = next((countries.get(country_id) for country_id in country_ids if countries.get(country_id)), None)
        gender = value(item, "Gender")
        display_name = name.strip()
        if not display_name:
            continue
        route_handle = (handle or "").lower().lstrip("@")
        history = sorted(result_rows.get(identifier, []), key=lambda row: (row["_event_date"], row["event"]))
        for result in history:
            result.pop("_event_date", None)
        rider = {
            "name": display_name,
            "first_name": display_name.split()[0] if display_name else "",
            "last_name": " ".join(display_name.split()[1:]) if display_name else "",
            "display_name": display_name,
            # Preserve established public URLs without importing any profile
            # content from the former Google Sheet. New riders still receive a
            # deterministic slug generated exclusively from their Notion name.
            "slug": ROUTE_SLUGS_BY_HANDLE.get(route_handle) or slugify(display_name),
            "gender_category": "Women Elite" if gender == "Women" else "Men Elite",
            "discipline": value(item, "Disciplines") or "",
            "country": country,
            "hometown": value(item, "Hometown"),
            "date_of_birth": display_birth(birth),
            "age": age_from_birth(birth) if birth else None,
            "instagram": handle,
            "team": team,
            "bio": value(item, "Biographie et principaux résultats") or "",
            "competition_history": history,
            "competition_participation": sorted(participations_by_rider.get(identifier, set())),
            "equipment": equipment_by_rider.get(identifier, []),
            "season": 2026,
        }
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
        current["competition_participation"] = sorted(set(
            current.get("competition_participation", []) + rider.get("competition_participation", [])
        ))
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
        raise RuntimeError("No rider was exported from the Notion Riders database")
    minimum_riders = int(os.environ.get("NOTION_MIN_RIDERS", "40"))
    if len(riders) < minimum_riders:
        raise RuntimeError(f"Only {len(riders)} riders were exported; safety minimum is {minimum_riders}")
    categories = {rider.get("gender_category") for rider in riders}
    if not {"Men Elite", "Women Elite"}.issubset(categories):
        raise RuntimeError("Both Men Elite and Women Elite must be present")
    slugs = [rider.get("slug") for rider in riders]
    if len(slugs) != len(set(slugs)):
        raise RuntimeError("Duplicate rider slugs were generated")
    riders.sort(key=lambda rider: (
        rider.get("gender_category") or "",
        -sum((row.get("points") or 0) for row in rider["competition_history"]),
        rider["display_name"],
    ))
    return riders, competition_catalog, {name: len(items) for name, items in pages.items()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "notion" / "riders.json")
    parser.add_argument("--competitions-output", type=Path, default=ROOT / "data" / "notion" / "competitions.json")
    parser.add_argument("--metadata", type=Path, default=ROOT / "data" / "notion" / "sync-metadata.json")
    args = parser.parse_args()
    token = os.environ.get("NOTION_TOKEN", "").strip()
    if not token:
        raise SystemExit("NOTION_TOKEN is required")

    riders, competitions, counts = export(Notion(token))
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
        "profile_data_source": "notion-only",
        "image_source": "google-drive-only",
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
