#!/usr/bin/env python3
"""Conservative, repeatable normalization for rider data.

Only explicit aliases and verified source-sheet mistakes live here.  This keeps
future syncs stable without relying on fuzzy matching or inventing missing data.
"""
import json
import os
import re


ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(ROOT, "data", "riders.json")

TEAM_ALIASES = {
    "commencal schwalbe by les orres": "Commençal Schwalbe by Les Orres",
    "commencal/muc-off by riding addiction": "Commençal/Muc-Off by Riding Addiction",
    "ms racing": "MS Racing",
    "ms-racing": "MS Racing",
    "norcoadidasracedivision": "Norco Race Division",
    "santa cruz / burgtec by goodman": "Santa Cruz / Burgtec by Goodman",
    "santa cruz burgtec by goodman": "Santa Cruz / Burgtec by Goodman",
    "yeti / fox factory race team": "Yeti / FOX Factory Race Team",
}

SPONSOR_ALIASES = {
    "100percentbike": "100%",
    "alpinestars": "Alpinestars",
    "aventon": "Aventon",
    "bike_center_cimone": "Bike Center Cimone",
    "canyon_mtb": "Canyon",
    "commencal": "Commençal",
    "crankbrothers": "Crankbrothers",
    "deitycomponents": "Deity",
    "ethirteencomponents": "e*thirteen",
    "foxmtb": "Fox Racing",
    "foxracingeurope": "Fox Racing",
    "framework": "Frameworks",
    "galferbike": "Galfer",
    "gopro": "GoPro",
    "lesorres": "Les Orres",
    "mondraker": "Mondraker",
    "monsterenergy": "Monster Energy",
    "mucoff": "Muc-Off",
    "netperformance": "Net Performance",
    "norco": "Norco",
    "redbull": "Red Bull",
    "redbullcanada": "Red Bull",
    "ridewill.it": "Ridewill",
    "santacruzsyndicate": "Santa Cruz Syndicate",
    "schable": "Schwalbe",
    "scottdhfactory": "Scott DH Factory Racing",
    "specializedgravity": "Specialized Gravity",
    "sram": "SRAM",
}

BRAND_ALIASES = {
    "commencal": "Commençal",
    "ohlins": "Öhlins",
    "rental": "Renthal",
    "rock shox": "RockShox",
    "sram": "SRAM",
}


def _key(value):
    return re.sub(r"\s+", " ", (value or "").strip()).lower()


def normalize_team(team):
    if not team:
        return None
    clean = re.sub(r"\s+", " ", team.strip())
    return TEAM_ALIASES.get(_key(clean), clean)


def normalize_sponsors(sponsors):
    expanded = []
    for sponsor in sponsors or []:
        # The source occasionally stores several Instagram handles in one cell.
        parts = (re.findall(r"@[A-Za-z0-9_.%*-]+", sponsor)
                 if sponsor.count("@") > 1 else [sponsor])
        expanded.extend(parts)
    result = []
    seen = set()
    for sponsor in expanded:
        clean = sponsor.strip().lstrip("@").strip()
        display = SPONSOR_ALIASES.get(_key(clean), clean)
        identity = _key(display)
        if display and identity not in seen:
            result.append(display)
            seen.add(identity)
    return result


def _refresh_item(item):
    item = dict(item)
    brand = re.sub(r"\s+", " ", (item.get("brand") or "").strip())
    model = re.sub(r"\s*;\s*", ";", (item.get("model_detail") or "").strip(" ;"))
    item["brand"] = BRAND_ALIASES.get(_key(brand), brand)
    item["model_detail"] = model
    item["brand_model"] = ";".join(filter(None, (item["brand"], model)))
    return item


def normalize_equipment(rider):
    items = [_refresh_item(item) for item in rider.get("equipment", [])]

    for item in items:
        category, brand, model = item.get("category"), item["brand"], item["model_detail"]
        if category == "RearShock" and _key(brand) == "float x2 factory" and not model:
            item["brand"], item["model_detail"] = "Fox", "Float X2 Factory"
        if category == "BrakeLever" and _key(brand) == "brembo lever" and not model:
            item["brand"] = "Brembo"
        if category == "Disk" and _key(brand) == "hope floating disc brake - hbsp330" and not model:
            item["brand"], item["model_detail"] = "Hope", "Floating Disc Brake HBSP330"
        if category == "Handlebar" and _key(model) == "fatbar":
            item["model_detail"] = "Fatbar"
        item.update(_refresh_item(item))

    # Verified against the source workbook: these values sit under incorrect
    # category headers.  Reassign only the affected products, never by guessing.
    slug = rider.get("slug")
    if slug == "marine-cabirou":
        repaired = []
        for item in items:
            category, brand, model = item.get("category"), _key(item["brand"]), _key(item["model_detail"])
            if category == "DropperPost" and brand == "ergon":
                item["category"] = "Saddle"
            elif category == "Saddle" and brand == "sram" and model == "x01 dh":
                item["category"] = "Derailleur"
            elif category == "Derailleur" and brand == "sram" and model == "maven":
                continue  # duplicate brake-family value in the wrong column
            elif category == "Wheels" and brand == "maxxis":
                item["category"] = "Tires"
            elif category == "Disk" and brand == "dt swiss":
                item["category"] = "Wheels"
            elif category == "Tires" and brand == "crankbrothers":
                item["category"] = "Pedals"
            repaired.append(_refresh_item(item))
        items = repaired
    elif slug == "aaron-gwin":
        for item in items:
            if item.get("category") == "Shoes" and _key(item["brand"]) == "bell" and not item["model_detail"]:
                item["category"] = "Helmet"

    order = {
        "Frame": 0, "Fork": 1, "RearShock": 2, "Handlebar": 3,
        "DropperPost": 4, "Saddle": 5, "Crankset": 6, "Derailleur": 7,
        "BrakeLever": 8, "GRIP": 9, "CHAIN": 10, "Disk": 11,
        "Wheels": 12, "Tires": 13, "Pedals": 14, "Shoes": 15,
        "Helmet": 16, "Protection": 17, "Goggles": 18,
    }
    return sorted((_refresh_item(item) for item in items), key=lambda item: order.get(item.get("category"), 99))


def normalize_riders(riders):
    for rider in riders:
        rider["team"] = normalize_team(rider.get("team"))
        rider["sponsors"] = normalize_sponsors(rider.get("sponsors"))
        rider["equipment"] = normalize_equipment(rider)
        frame = next((item for item in rider["equipment"] if item.get("category") == "Frame"), None)
        rider["bike"] = ({"brand": frame["brand"], "model": frame["model_detail"]}
                         if frame else None)
    return riders


def main():
    with open(DATA_PATH, encoding="utf-8") as source:
        riders = json.load(source)
    normalize_riders(riders)
    with open(DATA_PATH, "w", encoding="utf-8") as destination:
        json.dump(riders, destination, ensure_ascii=False, indent=1)
        destination.write("\n")
    print(f"Normalized {len(riders)} riders in {DATA_PATH}")


if __name__ == "__main__":
    main()
