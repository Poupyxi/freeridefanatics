#!/usr/bin/env python3
"""
RidersFanatics static site generator.

Reads data/riders.json and generates:
  - index.html               (rider directory, filterable grid)
  - riders/{slug}.html        (one detail page per rider)

Re-run this script any time data/riders.json is updated (new photos,
affiliate links, bios, results) — it fully regenerates the site.

Photos: drop a file named assets/img/riders/{slug}.jpg (or .png/.webp)
and it will automatically be picked up on next build, replacing the
placeholder initials avatar. No code changes needed.

Affiliate links: fill the "affiliate_link" field on any equipment item
in data/riders.json and rebuild — the "Shop" button will link there
instead of "#".
"""
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
import unicodedata

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(ROOT, "data", "riders.json")
RIDERS_DIR = os.path.join(ROOT, "riders")
EQUIPMENT_DIR = os.path.join(ROOT, "equipment")
COMPETITIONS_DIR = os.path.join(ROOT, "competitions")
IMG_DIR = os.path.join(ROOT, "assets", "img", "riders")
ACTION_IMG_DIR = os.path.join(ROOT, "assets", "img", "riders-action")
EQUIP_IMG_DIR = os.path.join(ROOT, "assets", "img", "equipment")
REVEAL_IMG_DIR = os.path.join(EQUIP_IMG_DIR, "reveal")

SITE_NAME = "RidersFanatics"
BUILD_ENV = os.environ.get("RF_BUILD_ENV", "production").strip().lower()
if BUILD_ENV not in {"production", "preprod"}:
    raise RuntimeError("RF_BUILD_ENV must be 'production' or 'preprod'")
IS_PREPROD = BUILD_ENV == "preprod"
SITE_URL = os.environ.get(
    "RF_SITE_URL",
    "https://preprod.ridersfanatics.com" if IS_PREPROD else "https://ridersfanatics.com",
).rstrip("/")
SITE_UPDATED = "2026-08-24"
SITE_UPDATED_LABEL = "24 Aug 2026"
SITE_UPDATED_LONG = "24 August 2026"
CONTACT_EMAIL = "contact@ridersfanatics.com"
DATA_LICENSE_URL = f"{SITE_URL}/data-license.html"
BUILD_VERSION = str(int(time.time()))  # cache-busting query string, changes every build

# Competitions are deliberately separate from the RidersFanatics brand.  The
# first release contains one series, but navigation and result filters consume
# this catalogue so future series can be added without renaming the whole site.
COMPETITIONS_PATH = os.path.join(ROOT, "data", "competitions.json")
ADS_PATH = os.path.join(ROOT, "data", "ads.json")
with open(COMPETITIONS_PATH, encoding="utf-8") as competition_source:
    COMPETITION_CATALOG = json.load(competition_source)

def visible_status(item):
    return item.get("status") == "published" or IS_PREPROD

COMPETITIONS = [item for item in COMPETITION_CATALOG.get("series", []) if visible_status(item)]
ORGANIZATIONS = [item for item in COMPETITION_CATALOG.get("organizations", []) if visible_status(item)]
CURRENT_COMPETITION = COMPETITIONS[0]
with open(ADS_PATH, encoding="utf-8") as ads_source:
    AD_CATALOG = json.load(ads_source)
with open(DATA_PATH, encoding="utf-8") as promo_source:
    PROMO_RIDERS = json.load(promo_source)
PROMO_EQUIPMENT = [
    item for rider in PROMO_RIDERS for item in (rider.get("equipment") or [])
    if item.get("category") and (item.get("brand") or item.get("model_detail"))
]

# Brevo-hosted subscription form. Brevo handles double opt-in, unsubscribe
# records and abuse protection; no API key is exposed in this static site.
NEWSLETTER_FORM_URL = (
    "https://10eaaef6.sibforms.com/v2/serve/"
    "MUIFAIsUlY8fObVL8vrzPGoBLdJ3a4LHKjjbIj6wiB9CecDkd2ERnrjCMrM3IwA9bJh7KPLV3s_b_iB0eKAQa9UnK0_0O7Bz53jlmVnqApR0vKBC9YR2YaZso54oK1CodhG7fcbQL89iGN4capGJoIrxGuEKH-4BQoeTkfEXmN2pG4Qh1K34nhC4x4LFylNox2vFvJnBJwGWfqPhsQ=="
)

# ---------------------------------------------------------------- equipment groups

EQUIP_GROUP_MAP = {
    "Frame": "Chassis", "Fork": "Chassis", "RearShock": "Chassis",
    "Handlebar": "Cockpit", "Saddle": "Cockpit", "DropperPost": "Cockpit", "GRIP": "Cockpit",
    "Crankset": "Drivetrain", "Derailleur": "Drivetrain", "BrakeLever": "Drivetrain",
    "Disk": "Drivetrain", "CHAIN": "Drivetrain",
    "Wheels": "Wheels & Tyres", "Tires": "Wheels & Tyres", "Pedals": "Wheels & Tyres",
    "Helmet": "Protection", "Protection": "Protection", "Goggles": "Protection", "Shoes": "Protection",
}
EQUIP_GROUP_ORDER = ["Chassis", "Cockpit", "Drivetrain", "Wheels & Tyres", "Protection"]

EQUIP_GROUP_ICONS = {
    "Chassis": '<svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M6 24 L16 8 L26 24 L16 20 Z"/><circle cx="6" cy="24" r="3"/><circle cx="26" cy="24" r="3"/></svg>',
    "Cockpit": '<svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M6 10 H26 M6 10 V15 M26 10 V15 M16 10 V26"/></svg>',
    "Drivetrain": '<svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="16" cy="16" r="10"/><circle cx="16" cy="16" r="3"/><path d="M16 6 V2 M16 30 V26 M6 16 H2 M30 16 H26"/></svg>',
    "Wheels & Tyres": '<svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="16" cy="16" r="12"/><circle cx="16" cy="16" r="2"/><path d="M16 16 L16 4 M16 16 L25 22 M16 16 L7 22"/></svg>',
    "Protection": '<svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M16 3 L27 7 V15 C27 22 22 27 16 30 C10 27 5 22 5 15 V7 Z"/></svg>',
}

# ---------------------------------------------------------------- points scales

# Position -> points, keyed by competition. Only a fallback: the sheet records
# the finishing position next to the points, and sync.py stores it as `place`.
# This ladder is the men's scale; the women's field is shorter and diverges from
# 7th place down, so deriving a position from points alone is only safe when the
# sheet left the position blank. Add an entry here when a new series is tracked;
# a competition with no scale simply shows no position.
POINTS_SCALES = {
    CURRENT_COMPETITION["name"]: [
        200, 160, 140, 125, 110, 95, 90, 85, 80, 75, 70, 65, 60, 55, 50, 45,
        44, 43, 42, 41, 40, 39, 38, 37, 36, 35, 34, 33, 32, 31, 30,
    ],
}

def placing_from_points(competition, points):
    """Finishing position implied by a points total, or None if not derivable."""
    scale = POINTS_SCALES.get(competition)
    if not scale or points is None:
        return None
    try:
        return scale.index(points) + 1
    except ValueError:
        return None

def history_place(h):
    """Finishing position for one result row — the sheet's own Classement when
    present, the points ladder only as a fallback."""
    place = h.get("place")
    if place is not None:
        return place
    if h.get("result"):
        return None  # DNS / DNF / DSQ — no position to show
    return placing_from_points(h.get("category") or "Other", h.get("points"))

def ordinal(n):
    if n is None:
        return None
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"

# ---------------------------------------------------------------- helpers

def prettify_category(cat):
    """RearShock -> Rear Shock, GRIP -> Grip, BrakeLever -> Brake Lever"""
    if not cat:
        return ""
    if cat == "Disk":
        return "Brake Rotor"
    if cat.isupper():
        return cat.capitalize()
    return re.sub(r'(?<!^)(?=[A-Z])', ' ', cat)

def norm_product_text(value):
    """Comparison key tolerant of accents, punctuation, casing and spacing."""
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    value = value.lower().replace("™", "").replace("®", "")
    return re.sub(r"[^a-z0-9]+", " ", value).strip()

# Explicit aliases only: automatic fuzzy merging can silently combine genuinely
# different race parts (for example SRAM X0 and X01). Add a row here when the
# Sheet uses two wordings for one real product.
EQUIPMENT_ALIASES = {
    ("Frame", "commencal", "supreme dh v5"): ("Commençal", "Supreme DH V5.2"),
    ("Frame", "commencal", "supreme dh v5 2"): ("Commençal", "Supreme DH V5.2"),
    ("Fork", "ohlins", "dh38 m2 coil"): ("Öhlins", "DH38"),
    ("RearShock", "fox", "factory"): ("Fox", "Float X2 Factory"),
    ("Handlebar", "burgtec", "ride wide alloy dh"): ("Burgtec", "Ride Wide DH"),
    ("Handlebar", "burgtec", "ride wide alloy downhill riser bar"): ("Burgtec", "Ride Wide DH"),
    ("Handlebar", "burgtec", "ride wide carbondh riser bar"): ("Burgtec", "Ride Wide DH Carbon"),
    ("Wheels", "dt swiss", "fr1500"): ("DT Swiss", "FR 1500"),
    ("Wheels", "dt swiss", "fr 1500"): ("DT Swiss", "FR 1500"),
    ("Wheels", "crankbrothers", "synthesis carbon dh"): ("Crankbrothers", "Synthesis DH Carbon"),
    ("Wheels", "crankbrothers", "synthesis dh carbon"): ("Crankbrothers", "Synthesis DH Carbon"),
    ("Tires", "maxxis", "assegai f dhr2 r"): ("Maxxis", "Assegai (F) + DHR II (R)"),
    ("Tires", "maxxis", "assegai f dhr ii r"): ("Maxxis", "Assegai (F) + DHR II (R)"),
    ("BrakeLever", "sram", "maven ultimate"): ("SRAM", "Maven"),
    ("BrakeLever", "sram", "maven silver"): ("SRAM", "Maven"),
    ("Crankset", "sram", "xo dh"): ("SRAM", "X0 DH"),
    ("Derailleur", "sram", "xo dh"): ("SRAM", "X0 DH"),
    ("Handlebar", "renthal", "fatbar 35mm"): ("Renthal", "Fatbar 35"),
    ("Handlebar", "renthal", "fatbar 35"): ("Renthal", "Fatbar 35"),
    ("Handlebar", "renthal", "fatbar"): ("Renthal", "Fatbar"),
}

BRAND_DISPLAY = {
    "5dev": "5DEV", "commencal": "Commençal", "enve": "ENVE",
    "north shore billet": "North Shore Billet", "northshorebillet": "North Shore Billet",
    "ohlins": "Öhlins", "rockshox": "RockShox", "sram": "SRAM",
}

def canonical_equipment_product(category, brand, main_model):
    """Return one stable display identity for loose Sheet/library wording."""
    brand_key = norm_product_text(brand)
    model_key = norm_product_text(main_model)
    alias = EQUIPMENT_ALIASES.get((category or "", brand_key, model_key))
    if alias:
        return alias
    return BRAND_DISPLAY.get(brand_key, (brand or "").strip()), (main_model or "").strip()

def is_rankable_equipment_product(main_model):
    """Rankings require a product reference, not a brand-only observation."""
    return bool((main_model or "").strip())

def bio_bullets(bio):
    if not bio:
        return []
    parts = [p.strip(" -") for p in bio.split(" - ") if p.strip(" -")]
    return parts

def has_photo(slug):
    for ext in ("jpg", "jpeg", "png", "webp"):
        if os.path.exists(os.path.join(IMG_DIR, f"{slug}.{ext}")):
            return f"{slug}.{ext}"
    return None

def equip_image_slug(category, brand, main_model):
    """Filename stem for an equipment photo, e.g. 'fork-fox-40-factory'.

    The category prefix is required, not decorative: 28 products in the source
    sheet share a brand+model across different categories (Shimano Saint is a
    brake lever, a crankset, a derailleur and a pedal), so brand+model alone
    would make them collide onto one photo."""
    brand, main_model = canonical_equipment_product(category, brand, main_model)
    s = f"{category} {brand} {main_model}".strip()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")

def has_equip_photo(category, brand, main_model):
    slug = equip_image_slug(category, brand, main_model)
    for ext in ("jpg", "jpeg", "png", "webp"):
        if os.path.exists(os.path.join(EQUIP_IMG_DIR, f"{slug}.{ext}")):
            return f"{slug}.{ext}"
    return None

def tire_component_photos(brand, main_model):
    """Resolve a front/rear tire combo to at most two individual product photos."""
    if "+" not in (main_model or ""):
        return []
    photos = []
    for raw_part in re.split(r"\s*\+\s*", main_model)[:2]:
        model = re.sub(r"\s*\((?:F|R|front|rear|avant|arriere)\)\s*", " ", raw_part,
                       flags=re.I)
        model = re.sub(r"\b(?:29|27[.,]5|26)(?:\s*[\"”]?\s*[x×]\s*[0-9.,]+)?", " ", model)
        model = re.sub(rf"^{re.escape(brand)}\b", "", model, flags=re.I)
        model = re.sub(r"\s+", " ", model).strip(" -/,")
        if norm_product_text(brand) == "maxxis" and norm_product_text(model) in {"dhr ii", "dhr2"}:
            model = "Minion DHR II"
        photo = has_equip_photo("Tires", brand, model)
        if photo:
            photos.append(photo)
    return photos if len(photos) == 2 else []

def equipment_photos(category, brand, main_model):
    combo = tire_component_photos(brand, main_model) if category == "Tires" else []
    if combo:
        return combo
    photo = has_equip_photo(category, brand, main_model)
    return [photo] if photo else []

def has_action_photo(slug):
    for ext in ("jpg", "jpeg", "png", "webp"):
        if os.path.exists(os.path.join(ACTION_IMG_DIR, f"{slug}.{ext}")):
            return f"{slug}.{ext}"
    return None

def initials(r):
    fn = (r.get("first_name") or "").strip()
    ln = (r.get("last_name") or "").strip()
    i = (fn[:1] + ln[:1]).upper()
    return i or "?"

def esc(s):
    if s is None:
        return ""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def esc_attr(s):
    """Escape a value placed inside a double-quoted HTML attribute."""
    return esc(s).replace('"', "&quot;").replace("'", "&#39;")

# ---------------------------------------------------------------- shared partials

def absolute_url(path):
    path = path or "/"
    return SITE_URL + (path if path.startswith("/") else "/" + path)

def json_ld(data):
    return f'<script type="application/ld+json">{json.dumps(data, ensure_ascii=False)}</script>'

def breadcrumb_schema(items):
    return {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i, "name": name, "item": absolute_url(path)}
            for i, (name, path) in enumerate(items, 1)
        ],
    }

def breadcrumb_html(items):
    return ""

def head(title, description, asset_prefix, body_class="", canonical_path="/",
         schemas=None, image_path=None, page_type="website"):
    body_attr = f' class="{esc(body_class)}"' if body_class else ""
    canonical = absolute_url(canonical_path)
    image = absolute_url(image_path) if image_path else absolute_url("/assets/img/og-default.png")
    image_dimensions = "" if image_path else '<meta property="og:image:width" content="1200">\n<meta property="og:image:height" content="630">'
    image_preload = f'<link rel="preload" as="image" href="{image}">' if image_path else ""
    schema_html = "\n".join(json_ld(s) for s in (schemas or []))
    adsense_script = "" if IS_PREPROD else '<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-6372404738608947" crossorigin="anonymous"></script>'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<meta name="robots" content="{'noindex,nofollow,noarchive' if IS_PREPROD else 'index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1'}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="{page_type}">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{image}">
{image_dimensions}
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(description)}">
<meta name="twitter:image" content="{image}">
<meta name="theme-color" content="#15161a">
<link rel="icon" href="{asset_prefix}assets/img/favicon.svg" type="image/svg+xml">
{image_preload}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Archivo+Black&family=Space+Mono:wght@400;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{asset_prefix}assets/css/style.css?v={BUILD_VERSION}">
{adsense_script}
{schema_html}
</head>
<body{body_attr}>
<a class="skip-link" href="#main-content">Skip to main content</a>
"""

def header_html(asset_prefix, active=""):
    def cls(name):
        return " class=\"active\"" if active == name else ""
    competition_cls = " class=\"active\"" if active in ("competitions", "standings") else ""
    home_href = asset_prefix or "./"
    competition_groups = []
    for organization in ORGANIZATIONS:
        items = []
        for competition in organization.get("competitions", []):
            if not visible_status(competition):
                continue
            href = competition.get("existing_path")
            if href:
                href = asset_prefix + href.lstrip("/")
            else:
                href = f"{asset_prefix}competitions/{organization['id']}/{competition['id']}/"
            items.append(f'<a href="{href}"><strong>{esc(competition.get("short_name", competition["name"]))}</strong><small>{esc(competition.get("discipline"))} · {competition.get("season", "")}</small></a>')
        if items:
            organization_href = f"{asset_prefix}competitions/{organization['id']}/"
            competition_groups.append(f'<div class="competition-menu-group"><a href="{organization_href}" class="competition-menu-title">{esc(organization["name"])}</a>{"".join(items)}</div>')
    if not competition_groups:
        competition_groups.append(f'<a href="{asset_prefix}competitions/{CURRENT_COMPETITION["id"]}.html"><strong>{CURRENT_COMPETITION["short_name"]}</strong><small>{CURRENT_COMPETITION["discipline"]} · {CURRENT_COMPETITION["season"]}</small></a>')
    return f"""<header>
  <div class="wrap nav-row">
    <a class="logo" href="{home_href}">
      <span class="mark">R</span>
      RIDERSFANATICS
    </a>
    <nav class="links" id="primary-navigation" aria-label="Primary navigation">
      <div class="nav-item has-dropdown competition-nav">
        <a href="{asset_prefix}competitions.html"{competition_cls}>Competitions <span class="caret">&#9662;</span></a>
        <div class="dropdown">
          <div class="dropdown-inner">
            {''.join(competition_groups)}
          </div>
        </div>
      </div>
      <div class="nav-item has-dropdown">
        <a href="{asset_prefix}riders.html#grid"{cls('riders')}>Riders <span class="caret">&#9662;</span></a>
        <div class="dropdown">
          <div class="dropdown-inner">
            <a href="{asset_prefix}riders.html#men">Men</a>
            <a href="{asset_prefix}riders.html#women">Women</a>
          </div>
        </div>
      </div>
      <a href="{asset_prefix}equipment.html"{cls('equipment')}>Equipment</a>
      <a href="{home_href}#faq">FAQ</a>
    </nav>
    <div class="nav-icons">
      <span class="icon-btn">64 Riders</span>
      <button class="nav-toggle" type="button" aria-label="Open navigation menu" aria-expanded="false" aria-controls="primary-navigation"><span></span><span></span><span></span></button>
    </div>
  </div>
</header>
"""

def footer_html(asset_prefix):
    home_href = asset_prefix or "./"
    return f"""{promo_strip_html(asset_prefix)}<footer>
  <div class="wrap footer-row">
    <a class="footer-logo" href="{home_href}"><span class="mark">R</span>RIDERSFANATICS</a>
    <nav class="footer-links" aria-label="Footer navigation">
      <a href="{asset_prefix}riders.html#grid">Riders</a>
      <a href="{asset_prefix}competitions.html">Competitions</a>
      <a href="{asset_prefix}equipment.html">Equipment</a>
      <a href="{asset_prefix}guides/en/">DH Guide</a>
      <a href="{home_href}#faq">FAQ</a>
      <a href="{asset_prefix}methodology.html">Methodology</a>
      <a href="{asset_prefix}data-license.html">Data license</a>
      <a href="{asset_prefix}about.html">About</a>
      <a href="{asset_prefix}contact.html">Contact</a>
      <a href="{asset_prefix}advertise.html">Advertise</a>
      <a href="{asset_prefix}affiliate-disclosure.html">Affiliates</a>
      <a href="{asset_prefix}privacy.html">Privacy</a>
    </nav>
    <span class="footer-copy">&copy; 2026 RidersFanatics</span>
  </div>
  <div class="wrap footer-updated">Last updated <time datetime="{SITE_UPDATED}">{SITE_UPDATED_LABEL}</time></div>
</footer>

<script src="{asset_prefix}assets/js/promo-pool.js?v={BUILD_VERSION}"></script>
<script src="{asset_prefix}assets/js/site.js?v={BUILD_VERSION}"></script>
</body>
</html>
"""

def direct_ad_banner_html(asset_prefix):
    campaign = next((item for item in AD_CATALOG.get("campaigns", []) if item.get("status") == "active"), None)
    if not campaign:
        return ""
    destination = campaign.get("url") or "/advertise.html"
    is_external = destination.startswith(("http://", "https://"))
    href = destination if is_external else asset_prefix + destination.lstrip("/")
    link_attrs = ' target="_blank" rel="noopener sponsored"' if is_external or campaign.get("type") == "sponsor" else ""
    media = (f'<img src="{asset_prefix}{esc_attr(campaign["image"].lstrip("/"))}" alt="" loading="lazy" width="320" height="180">'
             if campaign.get("image") else '<span class="direct-ad-mark" aria-hidden="true">RF</span>')
    disclosure = "Advertisement" if campaign.get("type") == "sponsor" else "Partnership"
    return f'''<div class="direct-ad-shell" aria-label="{disclosure}"><div class="direct-ad-media">{media}</div><div class="direct-ad-copy"><span class="direct-ad-disclosure">{disclosure} · {esc(campaign.get('label'))}</span><strong>{esc(campaign.get('title'))}</strong><p>{esc(campaign.get('description'))}</p></div><a class="direct-ad-cta" href="{esc_attr(href)}"{link_attrs}>{esc(campaign.get('cta') or 'Learn more')} <span aria-hidden="true">→</span></a></div>'''

def promo_strip_html(asset_prefix):
    if not PROMO_RIDERS or not PROMO_EQUIPMENT:
        return ""
    competition_name = CURRENT_COMPETITION["name"]
    events = competition_events(PROMO_RIDERS, competition_name)
    last_event = events[-1] if events else "Latest recorded race"

    def last_race_winner(category):
        entries = []
        for rider in PROMO_RIDERS:
            if rider.get("gender_category") != category:
                continue
            result = next((item for item in rider.get("competition_history") or []
                           if item.get("category") == competition_name and item.get("event") == last_event), None)
            if result:
                entries.append((rider, result))
        entries.sort(key=lambda entry: (
            history_place(entry[1]) is None,
            history_place(entry[1]) or 9999,
            -(entry[1].get("points") or 0),
            entry[0].get("display_name") or "",
        ))
        return entries[0][0] if entries else None

    def rider_card(rider, label):
        if not rider:
            return ""
        photo = has_photo(rider["slug"])
        media = (f'<img src="{asset_prefix}assets/img/riders/{photo}" alt="" loading="lazy" width="180" height="180">'
                 if photo else f'<span class="promo-initials" aria-hidden="true">{esc(initials(rider))}</span>')
        role = "women" if rider.get("gender_category") == "Women Elite" else "men"
        return f'''<article class="promo-card" data-promo-role="{role}" data-current-slug="{esc_attr(rider['slug'])}"><div class="promo-card-media">{media}</div><div class="promo-card-copy"><span class="direct-ad-disclosure">{label} · Last race</span><strong>{esc(rider['display_name'])}</strong><p>{esc(last_event)}</p></div><a class="promo-card-link" href="{asset_prefix}riders/{rider['slug']}.html">View winner <span aria-hidden="true">→</span></a></article>'''

    women_winner = last_race_winner("Women Elite")
    men_winner = last_race_winner("Men Elite")

    def equipment_by_identity(rider):
        products = {}
        for item in (rider or {}).get("equipment") or []:
            category = item.get("category") or ""
            model = (item.get("model_detail") or "").split(";")[0].strip()
            brand, model = canonical_equipment_product(category, item.get("brand") or "", model)
            if category and model:
                products[(category, norm_product_text(brand), norm_product_text(model))] = (category, brand, model)
        return products

    women_equipment = equipment_by_identity(women_winner)
    men_equipment = equipment_by_identity(men_winner)
    common_keys = sorted(set(women_equipment) & set(men_equipment))
    if common_keys:
        category, brand, model = women_equipment[random.choice(common_keys)]
        equipment_note = "Used by both last-race winners."
    else:
        equipment = random.choice(PROMO_EQUIPMENT)
        category = equipment["category"]
        model = (equipment.get("model_detail") or "").split(";")[0].strip()
        brand, model = canonical_equipment_product(category, equipment.get("brand") or "", model)
        equipment_note = "Popular across tracked professional setups."
    equipment_title = " ".join(part for part in (brand, model) if part)
    category_slug = equip_image_slug(category, "", "")
    photo = has_equip_photo(category, brand, model)
    equipment_media = (f'<img src="{asset_prefix}assets/img/equipment/{photo}" alt="" loading="lazy" width="180" height="180">'
                       if photo else '<span class="promo-equipment-icon" aria-hidden="true">+</span>')
    equipment_card = f'''<article class="promo-card" data-promo-role="equipment"><div class="promo-card-media">{equipment_media}</div><div class="promo-card-copy"><span class="direct-ad-disclosure">Common equipment · {esc(category)}</span><strong>{esc(equipment_title)}</strong><p>{equipment_note}</p></div><a class="promo-card-link" href="{asset_prefix}equipment/{category_slug}.html">Explore category <span aria-hidden="true">→</span></a></article>'''
    return f'''<aside class="direct-ad promo-strip" data-promo-prefix="{esc_attr(asset_prefix)}" aria-label="Latest winners, equipment and advertising"><div class="wrap"><div class="promo-grid">{rider_card(women_winner, 'Top 1 Women')}{equipment_card}{rider_card(men_winner, 'Top 1 Men')}</div>{direct_ad_banner_html(asset_prefix)}</div></aside>'''

def hero_waves_svg():
    return """<svg class="hero-waves" viewBox="0 0 1240 500" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M-50,40 C120,0 260,70 420,35 C580,0 700,60 880,30 C1000,10 1150,40 1290,25" fill="none" stroke="#15161a" stroke-opacity="0.06" stroke-width="1.2"/>
    <path d="M-50,80 C130,45 270,110 430,80 C590,50 710,105 890,75 C1010,55 1160,80 1290,65" fill="none" stroke="#15161a" stroke-opacity="0.07" stroke-width="1.2"/>
    <path d="M0,150 C160,115 300,175 470,145 C630,120 760,165 930,140 C1060,120 1170,145 1240,135" fill="none" stroke="#15161a" stroke-opacity="0.06" stroke-width="1.3"/>
    <path d="M0,220 C170,190 310,240 480,210 C640,185 770,225 940,205 C1070,190 1170,210 1240,200" fill="none" stroke="#15161a" stroke-opacity="0.06" stroke-width="1.3"/>
    <path d="M0,300 C150,265 290,320 450,295 C610,270 730,310 900,290 C1030,275 1140,295 1240,285" fill="none" stroke="#15161a" stroke-opacity="0.08" stroke-width="1.4"/>
    <path d="M0,340 C155,305 305,355 465,330 C625,305 745,345 915,325 C1045,310 1150,330 1240,320" fill="none" stroke="#15161a" stroke-opacity="0.09" stroke-width="1.4"/>
    <path d="M0,380 C150,340 300,420 460,390 C620,360 720,300 900,330 C1050,355 1150,320 1240,340" fill="none" stroke="#15161a" stroke-opacity="0.10" stroke-width="1.5"/>
    <path d="M0,420 C160,390 320,460 480,430 C640,400 760,350 940,380 C1080,400 1160,370 1240,390" fill="none" stroke="#15161a" stroke-opacity="0.10" stroke-width="1.5"/>
    <path d="M0,460 C170,430 330,490 500,470 C660,450 780,410 960,430 C1100,445 1170,420 1240,435" fill="none" stroke="#15161a" stroke-opacity="0.08" stroke-width="1.5"/>
    <path d="M-50,500 C140,470 300,510 480,485 C650,460 780,495 950,475 C1080,460 1170,480 1240,470" fill="none" stroke="#15161a" stroke-opacity="0.06" stroke-width="1.3"/>
  </svg>"""

def newsletter_form_html(prefix=""):
    """Native-looking signup posted to Brevo without exposing an API key."""
    if IS_PREPROD:
        return f'''<form class="cta-form is-preview" aria-label="Newsletter preview">
      <label class="cta-field-label" for="newsletter-email-preview">Email address</label>
      <div class="cta-field-row">
        <input id="newsletter-email-preview" type="email" placeholder="you@example.com" disabled>
        <button type="button" disabled>Subscribe <span aria-hidden="true">→</span></button>
      </div>
    </form>
    <div class="fineprint"><strong>Preview only.</strong> Signup is disabled in preproduction. ·
      <a href="{prefix}privacy.html">Privacy</a></div>'''
    return f"""<form class="cta-form" action="{esc_attr(NEWSLETTER_FORM_URL)}" method="post"
          target="brevo-newsletter-response" accept-charset="UTF-8" data-brevo-newsletter>
      <label class="cta-field-label" for="newsletter-email">Email address</label>
      <div class="cta-field-row">
        <input id="newsletter-email" name="EMAIL" type="email" autocomplete="email"
               inputmode="email" placeholder="you@example.com" required>
        <button type="submit">Subscribe <span aria-hidden="true">→</span></button>
      </div>
      <span class="nl-trap" aria-hidden="true"><label>Leave this empty
        <input name="email_address_check" type="text" tabindex="-1" autocomplete="off">
      </label></span>
      <input name="locale" type="hidden" value="fr">
    </form>
    <p class="cta-status" data-brevo-newsletter-status aria-live="polite"></p>
    <iframe class="newsletter-response" name="brevo-newsletter-response"
            title="Newsletter subscription response" tabindex="-1" aria-hidden="true"></iframe>
    <div class="fineprint">Free · No spam · Unsubscribe anytime ·
      <a href="{prefix}privacy.html">Privacy</a></div>"""

def cta_waves_svg():
    return """<svg class="waves" viewBox="0 0 1240 420" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M-50,140 C130,105 280,165 450,135 C610,105 740,150 910,120 C1040,100 1160,125 1290,110" fill="none" stroke="#ffffff" stroke-opacity="0.06" stroke-width="1.2"/>
    <path d="M-50,190 C140,155 290,215 460,185 C620,155 750,200 920,170 C1050,150 1170,175 1290,160" fill="none" stroke="#ffffff" stroke-opacity="0.07" stroke-width="1.3"/>
    <path d="M0,240 C150,205 300,265 470,235 C630,205 760,250 930,220 C1060,200 1170,225 1240,215" fill="none" stroke="#ffffff" stroke-opacity="0.08" stroke-width="1.3"/>
    <path d="M0,300 C150,260 300,340 460,310 C620,280 720,220 900,250 C1050,275 1150,240 1240,260" fill="none" stroke="#ffffff" stroke-opacity="0.10" stroke-width="1.5"/>
    <path d="M0,340 C160,310 320,380 480,350 C640,320 760,270 940,300 C1080,320 1160,290 1240,310" fill="none" stroke="#ffffff" stroke-opacity="0.09" stroke-width="1.5"/>
    <path d="M0,380 C170,350 330,410 500,390 C660,370 780,330 960,350 C1100,365 1170,340 1240,355" fill="none" stroke="#ffffff" stroke-opacity="0.07" stroke-width="1.5"/>
    <path d="M-50,410 C160,385 310,420 490,400 C660,380 790,405 960,390 C1090,378 1180,395 1240,388" fill="none" stroke="#ffffff" stroke-opacity="0.06" stroke-width="1.3"/>
  </svg>"""

def build_editorial_page(slug, title, description, label, lead, sections):
    path = f"/{slug}.html"
    body = []
    for heading, paragraphs in sections:
        body.append(f'<section><h2>{esc(heading)}</h2>')
        body.extend(f'<p>{esc(paragraph)}</p>' for paragraph in paragraphs)
        body.append('</section>')
    html = head(
        f"{title} | {SITE_NAME}", description, "", body_class="guide-page",
        canonical_path=path, page_type="article",
        schemas=[
            {"@context": "https://schema.org", "@type": "Article", "headline": title,
             "description": description, "dateModified": SITE_UPDATED,
             "author": {"@type": "Organization", "name": SITE_NAME},
             "publisher": {"@type": "Organization", "name": SITE_NAME},
             "mainEntityOfPage": absolute_url(path)},
            breadcrumb_schema([("Home", "/"), (title, path)]),
        ],
    )
    html += header_html("")
    html += f'''<main><article>
<header class="guide-hero"><div class="wrap"><div class="label">{esc(label)}</div><h1>{esc(title)}</h1><p class="lead">{esc(lead)}</p><div class="guide-meta"><span>{SITE_NAME}</span><time datetime="{SITE_UPDATED}">Updated {SITE_UPDATED_LONG}</time></div></div></header>
<div class="wrap">{breadcrumb_html([("Home", "./"), (title, path.lstrip('/'))])}</div><div class="wrap guide-layout"><div class="guide-content">{"".join(body)}</div>
<aside class="guide-sidebar"><div class="guide-card"><h2>Explore</h2><a href="riders.html#grid">Rider directory</a><a href="equipment.html">Equipment database</a><a href="competitions/{CURRENT_COMPETITION['id']}/standings.html">2026 standings</a><a href="guides/en/">Downhill setup guide</a></div></aside></div>
</article></main>'''
    html += footer_html("")
    return html

def build_contact_page():
    path = "/contact.html"
    description = "Contact RidersFanatics to report a correction, share a reliable source, discuss equipment data or ask a partnership question."
    html = head(
        f"Contact {SITE_NAME} | Rider & Equipment Database", description, "",
        body_class="guide-page contact-page", canonical_path=path,
        schemas=[
            {"@context": "https://schema.org", "@type": "ContactPage",
             "name": f"Contact {SITE_NAME}", "description": description,
             "url": absolute_url(path), "dateModified": SITE_UPDATED,
             "mainEntity": {"@type": "Organization", "name": SITE_NAME,
                            "url": SITE_URL,
                            "email": f"mailto:{CONTACT_EMAIL}",
                            "contactPoint": {"@type": "ContactPoint",
                                             "contactType": "customer support",
                                             "email": CONTACT_EMAIL,
                                             "availableLanguage": ["English", "French"]}}},
            breadcrumb_schema([("Home", "/"), ("Contact", path)]),
        ],
    )
    html += header_html("")
    html += f'''<main><article>
<header class="guide-hero"><div class="wrap"><div class="label">Corrections · Sources · Partnerships</div><h1>Contact RidersFanatics</h1><p class="lead">Found an outdated result or a component we should recheck? Send the source and context that will help us verify it.</p><div class="guide-meta"><span>English or French</span><span>Direct email available</span></div></div></header>
<div class="wrap">{breadcrumb_html([("Home", "./"), ("Contact", "contact.html")])}</div>
<div class="wrap contact-layout">
  <section class="contact-intro" aria-labelledby="contact-intro-title">
    <div class="label">A useful message includes</div>
    <h2 id="contact-intro-title">Enough detail to verify.</h2>
    <ul class="contact-checklist">
      <li><strong>Correction</strong><span>The rider, result or component concerned.</span></li>
      <li><strong>Context</strong><span>The race, run, date or setup involved.</span></li>
      <li><strong>Evidence</strong><span>A public team, rider, brand or event source when possible.</span></li>
    </ul>
    <div class="contact-direct"><span>Prefer your email app?</span><a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a></div>
  </section>
  <section class="contact-panel" aria-labelledby="contact-form-title">
    <div class="label">Send a message</div>
    <h2 id="contact-form-title">What should we look at?</h2>
    <form class="contact-form" data-contact action="contact-submit.php" method="post">
      <div class="contact-field-row">
        <div class="contact-field"><label for="contact-name">Name <span aria-hidden="true">*</span></label><input id="contact-name" name="name" type="text" autocomplete="name" maxlength="100" required></div>
        <div class="contact-field"><label for="contact-email">Email <span aria-hidden="true">*</span></label><input id="contact-email" name="email" type="email" autocomplete="email" maxlength="254" required></div>
      </div>
      <div class="contact-field"><label for="contact-reason">Reason <span aria-hidden="true">*</span></label><select id="contact-reason" name="reason" required><option value="">Choose one</option><option value="correction">Data correction</option><option value="source">New source or equipment update</option><option value="partnership">Partnership or media</option><option value="technical">Website issue</option><option value="other">Other</option></select></div>
      <div class="contact-field"><label for="contact-page">Relevant page <span>optional</span></label><input id="contact-page" name="page_url" type="url" inputmode="url" maxlength="500" placeholder="https://ridersfanatics.com/..."></div>
      <div class="contact-field"><label for="contact-message">Message <span aria-hidden="true">*</span></label><textarea id="contact-message" name="message" rows="8" minlength="10" maxlength="5000" required></textarea><small>Do not include sensitive personal information.</small></div>
      <label class="contact-consent"><input name="consent" type="checkbox" value="yes" required><span>I agree that RidersFanatics uses these details to answer my request. See the <a href="privacy.html">privacy policy</a>. <span aria-hidden="true">*</span></span></label>
      <div class="contact-trap" aria-hidden="true"><label>Company<input type="text" name="company" tabindex="-1" autocomplete="off"></label></div>
      <input type="hidden" name="form_started" value="">
      <button class="btn btn-solid contact-submit" type="submit">Send message</button>
      <p class="contact-status" data-contact-status role="status" aria-live="polite"></p>
      <p class="contact-required"><span aria-hidden="true">*</span> Required fields</p>
    </form>
  </section>
</div></article></main>'''
    html += footer_html("")
    return html

def build_trust_pages():
    return {
        "about.html": build_editorial_page(
            "about", "About RidersFanatics",
            "Learn how RidersFanatics connects professional riders, competitions, equipment and results in one independent database.",
            "Independent rider and equipment database",
            "RidersFanatics documents professional riders, race equipment and results across competitions and disciplines.",
            [
                ("Our purpose", ["RidersFanatics was created to make professional downhill equipment easier to explore. Rider information, race results and identifiable bike components are connected in one structured database, so fans can move from a rider to a setup, from a component to the riders using it, and from equipment trends to sporting results.", "The site is designed for riders, fans, mechanics and journalists who want a clearer view of the equipment used at the highest level of downhill racing."]),
                ("Independent and unofficial", ["RidersFanatics is an independent editorial project. It is not an official UCI website and is not operated by, endorsed by or affiliated with the riders, teams, race organisers or manufacturers referenced on its pages.", "Brand names, rider names and product names remain the property of their respective owners and are used for identification and editorial reporting."]),
                ("What the database covers", ["The 2026 database currently connects 64 elite riders with teams, public career information, race results and identified equipment across frames, suspension, cockpit, drivetrain, wheels, tires and protection.", "The scope will grow when reliable information adds genuine value. RidersFanatics does not publish speculative specifications simply to fill an empty field."]),
                ("Transparency", ["Equipment can change between practice, qualifying and race runs. Prototypes can also differ from products sold to the public. Every setup should therefore be understood as a documented snapshot based on the best public information available at the time.", "The full collection and ranking principles are explained on the methodology page."]),
            ],
        ),
        "methodology.html": build_editorial_page(
            "methodology", "Data methodology",
            "How RidersFanatics collects, verifies, updates and ranks professional rider, competition, result and equipment data.",
            "Sources, verification and limitations",
            "A transparent explanation of how rider profiles, equipment records and season rankings are assembled and how uncertainty is handled.",
            [
                ("Sources used", ["The database is assembled from publicly available material including official event information, team and rider communications, manufacturer product pages, public sponsor listings, race photography and reputable event coverage.", "A manufacturer link identifies the product family but does not by itself prove every internal tune, prototype part or race-day setting."]),
                ("Equipment identification", ["A component is recorded when its brand or model can be identified with reasonable confidence. Model names are normalised so small differences in punctuation, accents or naming do not fragment the statistics.", "When only a brand is known, the database avoids inventing a model. When a component remains uncertain, it may be omitted until stronger evidence is available."]),
                ("Updates", ["Race results and standings are updated as new season data is imported. Equipment records are updated when a verifiable change is identified; the absence of a new entry does not mean that every component was physically rechecked after every run or every race.", "The global update date describes the most recent database publication, not a guarantee that all 64 setups were independently reconfirmed on that day."]),
                ("Equipment rankings", ["Equipment rankings combine the current season points of tracked riders associated with a product. They describe competitive presence within this dataset; they are not laboratory tests and do not prove that one product is objectively better than another.", "The number and performance of sponsored riders strongly influence these totals. Rankings should be read alongside rider count, category and season context."]),
                ("Corrections", ["Corrections should include the rider, component or result concerned, the proposed change, the relevant race or date and a public source that supports the correction.", f"Send a correction through the contact page or email {CONTACT_EMAIL}. Every proposed change is checked against a reliable public source before publication."]),
            ],
        ),
        "data-license.html": build_editorial_page(
            "data-license", "RidersFanatics Dataset License 1.0",
            "Terms for accessing, citing and reusing the RidersFanatics professional rider, competition and equipment datasets.",
            "Dataset access and reuse",
            "These terms explain which parts of the RidersFanatics datasets may be reused and how attribution must be provided.",
            [
                ("Permitted use", ["The public RidersFanatics datasets may be viewed, linked to and cited for personal, educational, journalistic and research purposes. Short extracts may be reproduced when they are necessary to support commentary or analysis.", "Any reuse must clearly credit RidersFanatics and include a direct link to the relevant dataset page. The data must not be presented as official information from a rider, team, organiser, governing body or manufacturer."]),
                ("Permission required", [f"Bulk republication, systematic redistribution, resale, commercial database use or the creation of a substantially similar competing dataset requires prior written permission from {CONTACT_EMAIL}.", "Automated access must respect the site's technical limits and must not interfere with availability, security or normal operation."]),
                ("Third-party rights", ["This license applies only to the original selection, organisation, normalisation and presentation produced by RidersFanatics. Rider names, brand names, trademarks, photographs, event information and source material may remain subject to rights held by their respective owners."]),
                ("Accuracy and changes", ["The datasets are provided for information without a guarantee of completeness or uninterrupted availability. Equipment can change between runs, and prototypes may differ from retail products.", "RidersFanatics may correct records and update these terms. Dataset pages identify their current publication date, and this page identifies version 1.0 of the reuse terms."]),
            ],
        ),
        "affiliate-disclosure.html": build_editorial_page(
            "affiliate-disclosure", "Affiliate disclosure",
            "How affiliate product links support RidersFanatics and how commercial links are separated from independent equipment data.",
            "Commercial transparency",
            "Some product links may generate a commission, but affiliate availability does not determine which riders, components or results appear in the database.",
            [
                ("How affiliate links work", ["Some external product links are affiliate links. If a visitor follows one of these links and completes a qualifying purchase, RidersFanatics may receive a commission without increasing the visitor's purchase price."]),
                ("Editorial independence", ["Equipment is recorded because it is publicly associated with a tracked rider, not because a retailer offers a commission. A product without an affiliate link can rank above a monetised product, and many tracked components have no commercial link at all."]),
                ("Buying decisions", ["Race equipment may be a prototype, a team-specific tune or a configuration that differs from a retail product. Visitors should verify compatibility, sizing, specification, warranty and local availability with the manufacturer or retailer before buying."]),
            ],
        ),
        "advertise.html": build_editorial_page(
            "advertise", "Advertise with RidersFanatics",
            "Direct advertising and partnership opportunities across RidersFanatics rider, competition and equipment pages.",
            "Direct partnerships",
            "Reach an audience actively exploring professional riders, race results and identifiable equipment through a clear, lightweight placement.",
            [
                ("Available placement", ["The primary partnership placement appears immediately before the footer across core RidersFanatics pages. It is designed for one clearly identified advertiser at a time, with a visual, short message and destination link.", "Campaigns can be scheduled and measured without adding third-party advertising scripts to the site."]),
                ("Suitable partners", ["Relevant campaigns may include mountain-bike equipment, protection, apparel, destinations, events, coaching and services that genuinely fit the RidersFanatics audience.", "Advertising availability never determines rider coverage, competition results or equipment rankings."]),
                ("Campaign requirements", ["Advertisers must provide the campaign name, destination URL, approved visual, start and end dates, target markets and confirmation that they hold the necessary rights to the supplied material.", "Every paid placement is clearly labelled as advertising and outbound commercial links are marked as sponsored."]),
                ("Request a proposal", [f"Contact {CONTACT_EMAIL} with the subject ‘Advertising’ and include your brand, campaign objective, preferred dates and destination markets.", "Audience figures and pricing will be shared from verified traffic data rather than estimated or invented reach."]),
            ],
        ),
        "privacy.html": build_editorial_page(
            "privacy", "Privacy policy",
            "Privacy information for visitors to RidersFanatics, including server logs, external links, affiliate links and future service changes.",
            "Visitor information",
            "RidersFanatics is primarily a static editorial website. It operates a contact form and an optional newsletter provided by Brevo; it has no user account system.",
            [
                ("Information processed", ["When you use the contact form, RidersFanatics receives your name, email address, chosen message category, message and any relevant page URL you provide. When you subscribe to the newsletter, Brevo processes your email address and the technical evidence needed to record your consent. Required fields are marked on each form. Standard hosting infrastructure may also process technical request information such as IP address, browser type, requested URL, timestamp and security events in server logs."]),
                ("Purpose and legal basis", ["Contact details are used to read, verify and answer your request. Newsletter details are used only to send RidersFanatics updates and an automatic welcome message after you submit the subscription form. Newsletter processing is based on consent, which you may withdraw at any time using the unsubscribe link in every message. Do not send sensitive personal information."]),
                ("Recipients and retention", [f"Contact messages are delivered to the RidersFanatics mailbox at {CONTACT_EMAIL}. Newsletter subscriptions are managed by Brevo as an email service provider. Details are not sold. Contact messages are kept only while the request is handled. Newsletter data is retained while the subscription remains active; limited suppression data may be retained after unsubscribe to ensure no further messages are sent, subject to legal obligations."]),
                ("Your rights", [f"You can ask to access, correct or delete your contact information, or withdraw your consent, by emailing {CONTACT_EMAIL}. You may also contact the data protection authority applicable to you, such as the CNIL in France."]),
                ("External services", ["The newsletter form and subscription emails are provided by Brevo. Pages may also link to manufacturers, retailers, Amazon and social platforms. Those services operate under their own privacy and cookie policies. Following an external link transfers the visitor to the third party's service."]),
                ("Affiliate links", ["Some outbound links are marked as sponsored affiliate links. The destination retailer may use its own identifiers or cookies to attribute a qualifying purchase. RidersFanatics does not receive the visitor's payment details from the retailer."]),
                ("Future changes", ["If analytics or user accounts are activated later, this policy will be updated before the new processing begins, with appropriate consent and retention information where required."]),
            ],
        ),
    }

# ---------------------------------------------------------------- index page

def rider_card(r):
    photo = has_photo(r["slug"])
    if photo:
        photo_html = (f'<img src="assets/img/riders/{photo}?v={BUILD_VERSION}" '
                      f'alt="{esc(r["display_name"])}" loading="lazy" decoding="async" width="400" height="400">')
    else:
        photo_html = f'<span class="initials">{esc(initials(r))}</span>'
    cat = esc(r.get("gender_category") or "")
    search_blob = " ".join([
        r.get("display_name",""), r.get("country") or "", r.get("team") or "", cat
    ]).lower()
    return f"""<a class="rider-card reveal" href="riders/{r['slug']}.html" data-category="{cat}" data-search="{esc(search_blob)}">
        <div class="photo">
          {photo_html}
          <span class="badge">{cat}</span>
        </div>
        <div class="info">
          <span class="country">{esc(r.get('country') or '—')}</span>
          <h3>{esc(r['display_name'])}</h3>
          <span class="team">{esc(r.get('team') or 'Privateer')}</span>
        </div>
      </a>"""

def random_rider_button(riders, asset_prefix="", solid=True):
    """CTA that opens a different rider each time.

    The href points at a real rider page so the button still works without
    JavaScript; site.js picks a random one on load and on every click. The
    fallback target is fixed rather than random so rebuilds stay reproducible."""
    slugs = [r["slug"] for r in riders]
    button_class = "btn btn-solid" if solid else "btn"
    if not slugs:
        return f'<a href="{asset_prefix}riders.html" class="{button_class}">Browse riders</a>'
    return (f'<a href="{asset_prefix}riders/{slugs[0]}.html" class="{button_class}" '
            f'data-random-rider="{",".join(slugs)}" '
            f'data-rider-prefix="{asset_prefix}riders/">Random rider</a>')

def build_index(riders, women_count, men_count):
    prefix = ""
    faq_schema = {
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": "Where does this data come from?", "acceptedAnswer": {"@type": "Answer", "text": "Setups and results are tracked from official competition information, team communications, manufacturer material and public sponsor listings."}},
            {"@type": "Question", "name": "Are the shop links affiliate links?", "acceptedAnswer": {"@type": "Answer", "text": "Some product links are affiliate links. RidersFanatics may earn a commission on qualifying purchases at no extra cost to the visitor."}},
            {"@type": "Question", "name": "How often is the equipment data updated?", "acceptedAnswer": {"@type": "Answer", "text": "Results are updated during the season and equipment is updated when a verifiable change is identified."}},
            {"@type": "Question", "name": "How are corrections handled?", "acceptedAnswer": {"@type": "Answer", "text": "Corrections are checked against a public source before publication. The methodology page explains the evidence required and current submission status."}},
            {"@type": "Question", "name": "Is Rider Fanatic the same as RidersFanatics?", "acceptedAnswer": {"@type": "Answer", "text": "Yes. Rider Fanatic, RiderFanatic and Riders Fanatics are common searches for RidersFanatics, the independent rider, equipment and race-results database at ridersfanatics.com."}},
        ],
    }
    html = head(
        f"{SITE_NAME} | Pro Riders, Equipment & Race Results",
        "RidersFanatics — also searched as Rider Fanatic or RiderFanatic — connects professional riders, competitions, equipment, setups and race results.",
        prefix,
        body_class="home-page",
        canonical_path="/",
        schemas=[
            {"@context": "https://schema.org", "@type": "WebSite", "name": SITE_NAME, "alternateName": ["RiderFanatic", "Rider Fanatic", "Riders Fanatics"], "url": SITE_URL + "/", "description": "Professional riders, competitions, equipment, setups and race results."},
            {"@context": "https://schema.org", "@type": "Organization", "name": SITE_NAME, "alternateName": ["RiderFanatic", "Rider Fanatic", "Riders Fanatics"], "url": SITE_URL + "/", "logo": absolute_url("/assets/img/favicon.svg")},
            faq_schema,
        ],
    )
    html += header_html(prefix, active="riders")
    html += f"""
<main id="main-content">
<section class="hero home-hero">
  {hero_waves_svg()}
  <div class="wrap hero-inner">
    <div class="label">Professional racing · Riders · Equipment · Results</div>
    <h1>Their <em>exact</em> setup. Your next upgrade.</h1>
    <p class="sub">Track {len(riders)} professional riders, explore their race setups and compare the equipment they trust across competitions.</p>
    <div class="hero-ctas">
      <a href="riders.html#grid" class="btn btn-solid">Explore riders</a>
      {random_rider_button(riders, solid=False)}
      <a href="compare.html" class="home-text-link">Compare equipment <span aria-hidden="true">→</span></a>
      <a href="#faq" class="home-text-link">Read the FAQ <span aria-hidden="true">↓</span></a>
    </div>
    <div class="ticker-wrap">
      <div class="ticker-track">
        <a href="riders.html#grid"><b>Rider</b> Profiles</a><span class="dot">·</span><a href="#equipment"><b>Pro</b> Setups</a><span class="dot">·</span><a href="competitions/{CURRENT_COMPETITION['id']}/standings.html"><b>Championship</b> Standings</a><span class="dot">·</span><a href="standings.html"><b>Round</b> Results</a><span class="dot">·</span><a href="#rankings"><b>Check</b> Rankings</a><span class="dot">·</span><a href="#equipment"><b>Equipment</b> Details</a><span class="dot">·</span><a href="#equipment"><b>Shop</b> the Gear</a><span class="dot">·</span>
        <a href="riders.html#grid" aria-hidden="true" tabindex="-1"><b>Rider</b> Profiles</a><span class="dot" aria-hidden="true">·</span><a href="#equipment" aria-hidden="true" tabindex="-1"><b>Pro</b> Setups</a><span class="dot" aria-hidden="true">·</span><a href="competitions/{CURRENT_COMPETITION['id']}/standings.html" aria-hidden="true" tabindex="-1"><b>Championship</b> Standings</a><span class="dot" aria-hidden="true">·</span><a href="standings.html" aria-hidden="true" tabindex="-1"><b>Round</b> Results</a><span class="dot" aria-hidden="true">·</span><a href="#rankings" aria-hidden="true" tabindex="-1"><b>Check</b> Rankings</a><span class="dot" aria-hidden="true">·</span><a href="#equipment" aria-hidden="true" tabindex="-1"><b>Equipment</b> Details</a><span class="dot" aria-hidden="true">·</span><a href="#equipment" aria-hidden="true" tabindex="-1"><b>Shop</b> the Gear</a><span class="dot" aria-hidden="true">·</span>
      </div>
    </div>
  </div>
</section>

{build_rankings_section(riders)}

{build_best_equipment_carousel(riders)}

<section class="section" id="faq">
  <div class="wrap">
    <div class="section-head">
      <div>
        <div class="label">Questions</div>
        <h2>FAQ</h2>
      </div>
    </div>
    <div class="faq">
      <div class="faq-item">
        <h3><button class="faq-q" type="button" id="faq-question-1" aria-expanded="false" aria-controls="faq-answer-1"><span><span class="faq-num">Q1</span>Where does this data come from?</span><span class="plus" aria-hidden="true">+</span></button></h3>
        <div class="faq-a" id="faq-answer-1" role="region" aria-labelledby="faq-question-1" hidden><p>Every setup is tracked from official competition information, team press releases, manufacturer material and public sponsor listings. Each result remains attached to its competition and season.</p></div>
      </div>
      <div class="faq-item">
        <h3><button class="faq-q" type="button" id="faq-question-2" aria-expanded="false" aria-controls="faq-answer-2"><span><span class="faq-num">Q2</span>Are the "Shop" links affiliate links?</span><span class="plus" aria-hidden="true">+</span></button></h3>
        <div class="faq-a" id="faq-answer-2" role="region" aria-labelledby="faq-question-2" hidden><p>Yes — some product links on this site are affiliate links. We may earn a commission on qualifying purchases at no extra cost to you.</p></div>
      </div>
      <div class="faq-item">
        <h3><button class="faq-q" type="button" id="faq-question-3" aria-expanded="false" aria-controls="faq-answer-3"><span><span class="faq-num">Q3</span>How often is the kit list updated?</span><span class="plus" aria-hidden="true">+</span></button></h3>
        <div class="faq-a" id="faq-answer-3" role="region" aria-labelledby="faq-question-3" hidden><p>Results are updated during the season. Equipment is updated when a verifiable change is identified; the global update date does not mean every setup was independently rescanned after every race.</p></div>
      </div>
      <div class="faq-item">
        <h3><button class="faq-q" type="button" id="faq-question-4" aria-expanded="false" aria-controls="faq-answer-4"><span><span class="faq-num">Q4</span>How are corrections handled?</span><span class="plus" aria-hidden="true">+</span></button></h3>
        <div class="faq-a" id="faq-answer-4" role="region" aria-labelledby="faq-question-4" hidden><p>Corrections are checked against a public source before publication. See our <a href="methodology.html">data methodology</a> for the evidence required and current submission status.</p></div>
      </div>
      <div class="faq-item">
        <h3><button class="faq-q" type="button" id="faq-question-5" aria-expanded="false" aria-controls="faq-answer-5"><span><span class="faq-num">Q5</span>Is Rider Fanatic the same as RidersFanatics?</span><span class="plus" aria-hidden="true">+</span></button></h3>
        <div class="faq-a" id="faq-answer-5" role="region" aria-labelledby="faq-question-5" hidden><p>Yes. Rider Fanatic, RiderFanatic and Riders Fanatics are common ways people search for <strong>RidersFanatics</strong>, our independent professional rider, equipment and race-results database.</p></div>
      </div>
    </div>
  </div>
</section>
"""
    html += f"""
<section class="cta-dark">
  {cta_waves_svg()}
  <div class="wrap cta-inner">
    <div class="cta-copy">
      <div class="label">RidersFanatics newsletter</div>
      <h2>Race updates. No noise.</h2>
      <p class="sub">The useful changes from the downhill paddock, sent only when there is something worth sharing.</p>
      <ul class="newsletter-benefits" aria-label="Newsletter content">
        <li>Race results</li><li>Pro setup updates</li><li>New equipment</li>
      </ul>
    </div>
    <div class="cta-signup">
      {newsletter_form_html()}
    </div>
  </div>
</section>
"""
    html += "</main>"
    html += footer_html(prefix)
    return html

def build_standings(riders):
    """Full season standings: every rider ranked by points, plus a per-round
    breakdown, and a team table. Events come from the data so a new round on the
    sheet adds its column on the next build."""
    prefix = ""
    competitions = sorted({h.get("category") for r in riders
                           for h in r.get("competition_history") or [] if h.get("category")})

    def events_for(comp):
        """Rounds in season order.

        No rider has scored in every round, so no single history gives the full
        calendar — but each one is a subsequence of it. Topologically sorting the
        'this round came before that one' pairs recovers the true order."""
        succ, indeg, seen = {}, {}, []
        for r in riders:
            seq = [h["event"] for h in r.get("competition_history") or []
                   if h.get("category") == comp]
            for ev in seq:
                if ev not in indeg:
                    indeg[ev], succ[ev] = 0, set()
                    seen.append(ev)
            for a, b in zip(seq, seq[1:]):
                if b not in succ[a]:
                    succ[a].add(b)
                    indeg[b] += 1

        order, ready = [], [e for e in seen if indeg[e] == 0]
        while ready:
            ready.sort(key=seen.index)  # deterministic tie-break
            ev = ready.pop(0)
            order.append(ev)
            for nxt in succ[ev]:
                indeg[nxt] -= 1
                if indeg[nxt] == 0:
                    ready.append(nxt)
        # contradictory data would leave a cycle — fall back rather than drop rounds
        return order if len(order) == len(seen) else seen

    def points_map(r, comp):
        return {h["event"]: h.get("points")
                for h in r.get("competition_history") or [] if h.get("category") == comp}

    def result_map(r, comp):
        """event -> label shown in the cell tooltip ('3rd', 'DNF', …)."""
        out = {}
        for h in r.get("competition_history") or []:
            if h.get("category") != comp:
                continue
            out[h["event"]] = h.get("result") or ordinal(history_place(h))
        return out

    def rider_rows(group, comp, events):
        entries = []
        for r in riders:
            if r.get("gender_category") != group:
                continue
            pts = points_map(r, comp)
            total = sum(v for v in pts.values() if v)
            if not total:
                continue
            entries.append((total, r, pts, result_map(r, comp)))
        entries.sort(key=lambda e: season_rank_key(e[1]))

        rows = []
        for i, (total, r, pts, res) in enumerate(entries, start=1):
            cells = []
            for ev in events:
                p = pts.get(ev)
                label = res.get(ev)
                title = f' title="{esc(label)}"' if label else ""
                cls = " scored" if p else " blank"
                cells.append(f'<td class="rd{cls}"{title}>{p if p else "·"}</td>')
            medal = f" p{i}" if i <= 3 else ""
            search_blob = " ".join([r["display_name"], r.get("team") or "Privateer",
                                    r.get("country") or "", r.get("country_code") or ""]).lower()
            rows.append(f"""<tr data-standing-row data-search="{esc(search_blob)}">
            <td class="pos{medal}">{i}</td>
            <td class="who"><a href="riders/{r['slug']}.html">{esc(r['display_name'])}</a>
              <span class="sub">{esc(r.get('team') or 'Privateer')}</span>
              <span class="mobile-total">{total} pts</span></td>
            <td class="nat">{esc(r.get('country_code') or '')}</td>
            {"".join(cells)}
            <td class="total">{total}</td>
          </tr>""")
        return rows, len(entries)

    def team_rows(comp, events):
        totals, members = {}, {}
        for r in riders:
            team = r.get("team") or "Privateer"
            pts = points_map(r, comp)
            total = sum(v for v in pts.values() if v)
            if not total:
                continue
            totals[team] = totals.get(team, 0) + total
            members.setdefault(team, []).append(r["display_name"])
        order = sorted(totals.items(), key=lambda x: (-x[1], x[0]))
        rows = []
        for i, (team, total) in enumerate(order, start=1):
            who = ", ".join(sorted(members[team]))
            medal = f" p{i}" if i <= 3 else ""
            search_blob = f"{team} {who}".lower()
            rows.append(f"""<tr data-standing-row data-search="{esc(search_blob)}">
            <td class="pos{medal}">{i}</td>
            <td class="who">{esc(team)}<span class="sub">{esc(who)}</span>
              <span class="mobile-total">{total} pts</span></td>
            <td class="total">{total}</td>
          </tr>""")
        return rows, len(order)

    tables = []
    for comp in competitions:
        events = events_for(comp)
        head_cells = "".join(
            f'<th scope="col" class="rd" title="{esc(ev)}"><abbr title="{esc(ev)}">{esc(short_event(ev))}</abbr></th>'
            for ev in events)
        for group, label in (("Men Elite", "Men"), ("Women Elite", "Women")):
            rows, n = rider_rows(group, comp, events)
            if not rows:
                continue
            tables.append(f"""<div class="standings-block" id="standings-{group.lower().replace(' ', '-')}" data-standings="{esc(group)}" data-competition="{esc(comp)}">
        <div class="standings-swipe" aria-hidden="true"><span>Swipe to see every round</span><b>→</b></div>
        <div class="standings-scroll">
          <table class="standings-table">
            <caption>{esc(label)} Elite standings for {esc(comp)} after {len(events)} rounds</caption>
            <thead><tr><th scope="col">#</th><th scope="col">Rider</th><th scope="col">Nat</th>{head_cells}<th scope="col" class="total">Pts</th></tr></thead>
            <tbody>
            {"".join(rows)}
            </tbody>
          </table>
        </div>
        <div class="standings-empty" hidden>No matching rider or team.</div>
        <div class="standings-foot">{n} riders scored · {len(events)} rounds</div>
      </div>""")
        rows, n = team_rows(comp, events)
        if rows:
            tables.append(f"""<div class="standings-block" id="standings-teams" data-standings="Teams" data-competition="{esc(comp)}">
        <div class="standings-scroll">
          <table class="standings-table">
            <caption>Team standings for {esc(comp)}</caption>
            <thead><tr><th scope="col">#</th><th scope="col">Team</th><th scope="col" class="total">Pts</th></tr></thead>
            <tbody>
            {"".join(rows)}
            </tbody>
          </table>
        </div>
        <div class="standings-empty" hidden>No matching rider or team.</div>
        <div class="standings-foot">{n} teams scored</div>
      </div>""")

    group_chips = "".join(
        f'<button class="filter-btn{" active" if i == 0 else ""}" role="tab" '
        f'aria-selected="{"true" if i == 0 else "false"}" aria-controls="standings-{g.lower().replace(" ", "-")}" '
        f'data-standings-group="{g}">{lbl}</button>'
        for i, (g, lbl) in enumerate([("Men Elite", "Men"), ("Women Elite", "Women"), ("Teams", "Teams")]))
    comp_chips = (f'<span class="competition-badge">{esc(competitions[0])}</span>' if len(competitions) == 1 else "".join(
        f'<button class="filter-btn{" active" if i == 0 else ""}" data-standings-comp="{esc(c)}">{esc(c)}</button>'
        for i, c in enumerate(competitions)))

    primary_comp = competitions[0] if competitions else ""
    primary_events = events_for(primary_comp) if primary_comp else []
    scored_riders = [r for r in riders if sum(v or 0 for v in points_map(r, primary_comp).values())]
    def leader_for(group):
        """Same ordering as the table below — on equal points the alphabetical
        winner is not the leader."""
        ranked = [(sum(v or 0 for v in points_map(r, primary_comp).values()), r)
                  for r in riders if r.get("gender_category") == group]
        ranked = [entry for entry in ranked if entry[0]]
        if not ranked:
            return (0, {"display_name": "—"})
        return min(ranked, key=lambda entry: season_rank_key(entry[1]))
    men_lead_pts, men_lead = leader_for("Men Elite")
    women_lead_pts, women_lead = leader_for("Women Elite")
    latest_round = primary_events[-1] if primary_events else "Season start"

    html = head(f"2026 UCI Downhill Results by Round | {SITE_NAME}",
                "Round-by-round UCI MTB World Cup downhill results for 2026, with every tracked rider, finishing position and cumulative points across the season.",
                prefix, body_class="standings-page", canonical_path="/standings.html",
                schemas=[
                    {"@context": "https://schema.org", "@type": "CollectionPage", "name": "2026 UCI MTB World Cup downhill results by round", "url": absolute_url("/standings.html"), "description": "Round-by-round World Cup downhill results and cumulative points for men, women and teams.", "dateModified": SITE_UPDATED},
                    breadcrumb_schema([("Home", "/"), ("Standings", "/standings.html")]),
                ])
    html += header_html(prefix, active="standings")
    html += f"""
<main id="main-content">
<section class="hero standings-hero">
  <div class="wrap hero-inner">
    <div class="label">Season 2026 · Updated after round {len(primary_events)} · {esc(latest_round)}</div>
    <h1>Results by round.</h1>
  </div>
</section>

<section class="section standings-section" id="standings">
  <div class="wrap">
    <div class="standings-overview" aria-label="Season overview">
      <div><strong>{len(primary_events)}</strong><span>Rounds completed</span></div>
      <div><strong>{len(scored_riders)}</strong><span>Riders scored</span></div>
      <div><strong>{esc(men_lead['display_name'])}</strong><span>Men leader · {men_lead_pts} pts</span></div>
      <div><strong>{esc(women_lead['display_name'])}</strong><span>Women leader · {women_lead_pts} pts</span></div>
    </div>
    <div class="standings-toolbar">
      <div>
        <span class="toolbar-label">Competition</span>
    <div class="filters standings-comp" data-standings-comp-filters>
      {comp_chips}
    </div>
      </div>
      <div>
        <span class="toolbar-label">Category</span>
    <div class="filters" role="tablist" aria-label="Standings category" data-standings-filters>
      {group_chips}
    </div>
      </div>
      <label class="standings-search"><span>Search</span>
        <input class="search-input" type="search" placeholder="Rider, team or country…" data-standings-search>
      </label>
    </div>
    {"".join(tables)}
    <div class="standings-legend">
      <span><b>·</b> No points recorded</span>
      <span>Team totals combine every tracked rider's season points.</span>
    </div>
  </div>
</section>
</main>
"""
    html += footer_html(prefix)
    return html

def competition_events(riders, competition_name):
    """Recover round order from every rider's ordered history."""
    successors, indegree, seen = {}, {}, []
    for rider in riders:
        sequence = [h["event"] for h in rider.get("competition_history") or []
                    if h.get("category") == competition_name]
        for event in sequence:
            if event not in indegree:
                indegree[event], successors[event] = 0, set()
                seen.append(event)
        for before, after in zip(sequence, sequence[1:]):
            if after not in successors[before]:
                successors[before].add(after)
                indegree[after] += 1
    order, ready = [], [event for event in seen if indegree[event] == 0]
    while ready:
        ready.sort(key=seen.index)
        event = ready.pop(0)
        order.append(event)
        for following in successors[event]:
            indegree[following] -= 1
            if indegree[following] == 0:
                ready.append(following)
    return order if len(order) == len(seen) else seen

def competition_stats(riders, competition):
    name = competition["name"]
    scored = []
    for rider in riders:
        points = sum((h.get("points") or 0) for h in rider.get("competition_history") or []
                     if h.get("category") == name)
        if points:
            scored.append((rider, points))
    leaders = {}
    for category in ("Men Elite", "Women Elite"):
        category_riders = [rider for rider, _ in scored if rider.get("gender_category") == category]
        leaders[category] = min(category_riders, key=lambda rider: competition_rank_key(rider, name)) if category_riders else None
    return {
        "events": competition_events(riders, name),
        "scored": scored,
        "teams": {rider.get("team") or "Privateer" for rider, _ in scored},
        "leaders": leaders,
    }

def competition_rider_points(rider, competition_name):
    return sum((result.get("points") or 0) for result in rider.get("competition_history") or []
               if result.get("category") == competition_name)

def competition_rank_key(rider, competition_name):
    """Rank a rider using results from one competition only."""
    history = [result for result in rider.get("competition_history") or []
               if result.get("category") == competition_name]
    places = sorted(result["place"] for result in history if result.get("place"))
    last = next((result.get("points") or 0 for result in reversed(history)
                 if result.get("points")), 0)
    return (-competition_rider_points(rider, competition_name), places, -last,
            rider.get("display_name") or "")

def competition_round_slug(event):
    value = unicodedata.normalize("NFKD", event or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "round"

def build_competition_round(riders, competition, event, round_number, events):
    """One crawlable result page per recorded round, generated from rider history."""
    name = competition["name"]
    cid = competition["id"]
    slug = competition_round_slug(event)
    path = f"/competitions/{cid}/rounds/{slug}.html"

    categories = {}
    all_entries = []
    for category in ("Men Elite", "Women Elite"):
        entries = []
        for rider in riders:
            if rider.get("gender_category") != category:
                continue
            result = next((item for item in rider.get("competition_history") or []
                           if item.get("category") == name and item.get("event") == event), None)
            if result:
                entries.append((rider, result))
        entries.sort(key=lambda pair: (
            history_place(pair[1]) is None,
            history_place(pair[1]) or 9999,
            -(pair[1].get("points") or 0),
            pair[0].get("display_name") or "",
        ))
        categories[category] = entries
        all_entries.extend(entries)

    def result_table(category, label):
        rows = []
        entries = categories[category]
        for rider, result in entries:
            place = history_place(result)
            result_label = result.get("result") or ordinal(place) or "—"
            team = rider.get("team") or "Privateer"
            nation = rider.get("country_code") or rider.get("country") or "—"
            search = esc_attr(f"{rider['display_name']} {team} {nation}".lower())
            rows.append(f'''<tr data-standing-row data-search="{search}"><td class="round-place">{esc(result_label)}</td><th scope="row"><a href="../../../riders/{rider['slug']}.html">{esc(rider['display_name'])}</a><small>{esc(team)}</small></th><td>{esc(nation)}</td><td class="round-points">{esc(result.get('points')) if result.get('points') is not None else '—'}</td></tr>''')
        if not rows:
            return f'<section class="round-category"><h2>{label}</h2><p class="round-empty">No {label.lower()} results are recorded for this round yet.</p></section>'
        return f'''<section class="round-category standings-block" data-standings="{category}" data-competition="{esc_attr(name)}"><div class="round-table-scroll standings-scroll" tabindex="0" role="region" aria-label="{label} results, horizontally scrollable"><table class="round-results"><caption>{label} results for {esc(event)}</caption><thead><tr><th scope="col">Result</th><th scope="col">Rider</th><th scope="col">Nation</th><th scope="col">Points</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div><p class="standings-empty" hidden>No {label.lower()} results are recorded for this event.</p></section>'''

    event_team_points, event_team_riders = {}, {}
    for rider, result in all_entries:
        team = rider.get("team") or "Privateer"
        event_team_points[team] = event_team_points.get(team, 0) + (result.get("points") or 0)
        event_team_riders.setdefault(team, []).append(rider["display_name"])
    event_teams = sorted(event_team_points, key=lambda team: (-event_team_points[team], team.lower()))
    team_rows = []
    for rank, team in enumerate(event_teams, 1):
        names = ", ".join(event_team_riders[team])
        search = esc_attr(f"{team} {names}".lower())
        team_rows.append(f'''<tr data-standing-row data-search="{search}"><td class="round-place">{rank:02d}</td><th scope="row">{esc(team)}<small>{esc(names)}</small></th><td>{len(event_team_riders[team])} riders</td><td class="round-points">{event_team_points[team]}</td></tr>''')
    team_table = f'''<section class="round-category standings-block" data-standings="Teams" data-competition="{esc_attr(name)}"><div class="round-table-scroll standings-scroll" tabindex="0" role="region" aria-label="Team results, horizontally scrollable"><table class="round-results"><caption>Team results for {esc(event)}</caption><thead><tr><th scope="col">Rank</th><th scope="col">Team</th><th scope="col">Riders</th><th scope="col">Points</th></tr></thead><tbody>{''.join(team_rows)}</tbody></table></div><p class="standings-empty" hidden>No team result is recorded for this event.</p></section>'''

    hero_leaders = []
    for category, label in (("Men Elite", "Men winner"), ("Women Elite", "Women winner")):
        if categories[category]:
            rider, result = categories[category][0]
            result_label = result.get("result") or ordinal(history_place(result)) or "1st"
            hero_leaders.append(f'''<a href="../../../riders/{rider['slug']}.html"><span>{label}</span><strong>{esc(rider['display_name'])}</strong><small>{esc(result_label)}</small></a>''')
    if event_teams:
        winning_team = event_teams[0]
        hero_leaders.append(f'''<div><span>Team winner</span><strong>{esc(winning_team)}</strong><small>{event_team_points[winning_team]} pts</small></div>''')

    previous_link = ""
    next_link = ""
    if round_number > 1:
        previous = events[round_number - 2]
        previous_link = f'<a href="{competition_round_slug(previous)}.html"><span>Previous round</span><strong>{esc(previous)}</strong></a>'
    if round_number < len(events):
        following = events[round_number]
        next_link = f'<a href="{competition_round_slug(following)}.html"><span>Next round</span><strong>{esc(following)}</strong></a>'

    item_list = [
        {"@type": "ListItem", "position": position, "name": rider["display_name"],
         "url": absolute_url(f"/riders/{rider['slug']}.html")}
        for position, (rider, _) in enumerate(all_entries, 1)
    ]
    description = f"{event} downhill results from the {name}: Elite Men and Women placings, points, teams and linked rider profiles."
    html = head(
        f"{event} Downhill Results | {competition['season']} {SITE_NAME}", description, "../../../",
        body_class="competition-round-page", canonical_path=path,
        schemas=[
            {"@context": "https://schema.org", "@type": "CollectionPage", "name": f"{event} downhill results",
             "description": description, "url": absolute_url(path), "dateModified": SITE_UPDATED,
             "mainEntity": {"@type": "ItemList", "numberOfItems": len(item_list), "itemListElement": item_list}},
            breadcrumb_schema([("Home", "/"), ("Competitions", "/competitions.html"),
                               (name, f"/competitions/{cid}.html"), (event, path)]),
        ],
    )
    html += header_html("../../../", active="competitions")
    html += f'''<main><section class="round-hero"><div class="wrap"><div class="label">Round {round_number:02d} · {esc(competition['discipline'])} · {competition['season']}</div><h1>{esc(event)}</h1><div class="round-hero-leaders">{''.join(hero_leaders)}</div></div></section>
<section class="section round-results-section"><div class="wrap"><div class="standings-toolbar clean-standings-toolbar"><div><span class="toolbar-label">Ranking</span><div class="filters" role="tablist" aria-label="Event ranking category" data-standings-filters><button class="filter-btn active" data-standings-group="Men Elite" aria-selected="true">Men</button><button class="filter-btn" data-standings-group="Women Elite" aria-selected="false">Women</button><button class="filter-btn" data-standings-group="Teams" aria-selected="false">Teams</button></div></div></div>{result_table('Men Elite', 'Men')}{result_table('Women Elite', 'Women')}{team_table}</div></section>
<nav class="wrap round-pagination" aria-label="Round pagination">{previous_link}{next_link}</nav>
</main>'''
    html += footer_html("../../../")
    return html

def competition_subnav(competition, active):
    return ""

def build_competition_standings(riders, competition):
    name = competition["name"]
    cid = competition["id"]
    stats = competition_stats(riders, competition)
    path = f"/competitions/{cid}/standings.html"
    categories = {}
    for category in ("Men Elite", "Women Elite"):
        categories[category] = sorted(
            [rider for rider in riders
             if rider.get("gender_category") == category
             and competition_rider_points(rider, name) > 0],
            key=lambda rider: competition_rank_key(rider, name),
        )

    team_points, team_riders = {}, {}
    for rider in categories["Men Elite"] + categories["Women Elite"]:
        team = rider.get("team") or "Privateer"
        team_points[team] = team_points.get(team, 0) + competition_rider_points(rider, name)
        team_riders.setdefault(team, []).append(rider)
    teams = sorted(team_points, key=lambda team: (-team_points[team], team.lower()))

    def podium_card(rank, rider):
        points = competition_rider_points(rider, name)
        return f'''<a class="clean-podium-card podium-{rank}" href="../../riders/{rider['slug']}.html">
          <span class="clean-podium-rank">{rank:02d}</span><div><strong>{esc(rider['display_name'])}</strong><small>{esc(rider.get('team') or 'Privateer')} · {esc(rider.get('nationality') or '')}</small></div><b>{points}<small>pts</small></b>
        </a>'''

    def rider_panel(category, label):
        ranked = categories[category]
        podium = "".join(podium_card(rank, rider) for rank, rider in enumerate(ranked[:3], 1))
        rows = []
        for rank, rider in enumerate(ranked, 1):
            team = rider.get("team") or "Privateer"
            nation = rider.get("country_code") or rider.get("country") or "—"
            points = competition_rider_points(rider, name)
            search = esc_attr(f"{rider['display_name']} {team} {nation}".lower())
            rows.append(f'''<a class="clean-standing-row" href="../../riders/{rider['slug']}.html" data-standing-row data-search="{search}">
              <span class="clean-standing-rank">{rank:02d}</span><span class="clean-standing-name"><strong>{esc(rider['display_name'])}</strong><small>{esc(team)} · {esc(nation)}</small></span><span class="clean-standing-team">{esc(team)}</span><span class="clean-standing-nation">{esc(nation)}</span><b>{points}<small>pts</small></b>
            </a>''')
        return f'''<section class="standings-block clean-standings-panel" data-standings="{category}" data-competition="{esc_attr(name)}">
          <div class="clean-podium">{podium}</div>
          <div class="standings-scroll clean-standing-list"><div class="clean-standing-head"><span>Rank</span><span>Rider</span><span>Team</span><span>Nation</span><span>Points</span></div>{"".join(rows)}</div>
          <p class="standings-empty" hidden>No {label.lower()} rider matches your search.</p>
        </section>'''

    team_podium = "".join(
        f'''<div class="clean-podium-card podium-{rank}"><span class="clean-podium-rank">{rank:02d}</span><div><strong>{esc(team)}</strong><small>{len(team_riders[team])} tracked riders</small></div><b>{team_points[team]}<small>pts</small></b></div>'''
        for rank, team in enumerate(teams[:3], 1)
    )
    team_rows = []
    for rank, team in enumerate(teams, 1):
        names = ", ".join(rider["display_name"] for rider in team_riders[team])
        search = esc_attr(f"{team} {names}".lower())
        team_rows.append(f'''<div class="clean-standing-row team-standing-row" data-standing-row data-search="{search}">
          <span class="clean-standing-rank">{rank:02d}</span><span class="clean-standing-name"><strong>{esc(team)}</strong><small>{esc(names)}</small></span><span class="clean-standing-team">{len(team_riders[team])} riders</span><span class="clean-standing-nation">—</span><b>{team_points[team]}<small>pts</small></b>
        </div>''')
    team_panel = f'''<section class="standings-block clean-standings-panel" data-standings="Teams" data-competition="{esc_attr(name)}">
      <div class="clean-podium">{team_podium}</div><div class="standings-scroll clean-standing-list"><div class="clean-standing-head"><span>Rank</span><span>Team</span><span>Riders</span><span>Nation</span><span>Points</span></div>{"".join(team_rows)}</div><p class="standings-empty" hidden>No team matches your search.</p>
    </section>'''

    leaders = categories["Men Elite"][:1] + categories["Women Elite"][:1]
    leader_summary = " · ".join(rider["display_name"] for rider in leaders)
    item_list = [
        {"@type": "ListItem", "position": position,
         "name": rider["display_name"], "url": absolute_url(f"/riders/{rider['slug']}.html")}
        for position, rider in enumerate(categories["Men Elite"] + categories["Women Elite"], 1)
    ]
    description = "UCI downhill standings 2026 for Elite Men, Elite Women and teams: current World Cup points, championship leaders and linked rider profiles."
    latest_round = stats["events"][-1] if stats["events"] else "Season start"
    latest_round_href = (f"rounds/{competition_round_slug(latest_round)}.html"
                         if stats["events"] else "../../competitions.html")
    html = head(
        f"UCI Downhill Standings 2026 | Men, Women & Teams", description, "../../",
        body_class="competition-standings-page", canonical_path=path,
        schemas=[
            {"@context": "https://schema.org", "@type": "CollectionPage",
             "name": f"{name} standings", "description": description,
             "url": absolute_url(path), "dateModified": SITE_UPDATED,
             "mainEntity": {"@type": "ItemList", "numberOfItems": len(item_list),
                            "itemListElement": item_list}},
            {"@context": "https://schema.org", "@type": "Dataset",
             "name": f"{name} standings dataset", "description": description,
             "url": absolute_url(path), "dateModified": SITE_UPDATED,
             "creator": {"@type": "Organization", "name": SITE_NAME, "url": SITE_URL},
             "license": DATA_LICENSE_URL, "isAccessibleForFree": True},
            breadcrumb_schema([("Home", "/"), ("Competitions", "/competitions.html"),
                               (name, f"/competitions/{cid}.html"), ("Standings", path)]),
        ],
    )
    html += header_html("../../", active="competitions")
    html += f'''<main>
<section class="competition-standings-hero"><div class="wrap"><div class="label">{esc(competition['sport'])} · {esc(competition['discipline'])} · Updated {SITE_UPDATED_LABEL}</div><h1>2026 UCI Downhill standings.</h1><p>{esc(name)} — the current championship order for Elite Men, Elite Women and teams, updated after {esc(latest_round)}.</p><div class="standings-hero-meta"><span><strong>{len(stats['events'])}</strong> rounds</span><span><strong>{len(stats['scored'])}</strong> riders scored</span><span><strong>{esc(leader_summary)}</strong> category leaders</span></div><div class="hero-ctas"><a class="btn btn-solid" href="{latest_round_href}">Latest round results</a><a class="btn" href="../{cid}.html">Season overview</a></div></div></section>
{competition_subnav(competition, "standings")}
<div class="wrap">{breadcrumb_html([("Home", "../../"), ("Competitions", "../../competitions.html"), (name, f"../{cid}.html"), ("Standings", "standings.html")])}</div>
<section class="section clean-standings-section"><div class="wrap"><div class="clean-standings-heading"><div><div class="label">Championship order</div><h2>Current ranking.</h2></div><a class="see-all" href="../../standings.html">Round-by-round detail →</a></div>
<div class="standings-toolbar clean-standings-toolbar"><div><span class="toolbar-label">Category</span><div class="filters" role="tablist" aria-label="Standings category" data-standings-filters><button class="filter-btn active" data-standings-group="Men Elite" aria-selected="true">Men</button><button class="filter-btn" data-standings-group="Women Elite" aria-selected="false">Women</button><button class="filter-btn" data-standings-group="Teams" aria-selected="false">Teams</button></div></div><label class="standings-search"><span>Search</span><input class="search-input" type="search" placeholder="Rider, team or country…" data-standings-search></label></div>
{rider_panel('Men Elite', 'Men')}{rider_panel('Women Elite', 'Women')}{team_panel}
<div class="clean-standings-note"><strong>How to read this ranking</strong><p>Points are attached to this competition only. The detailed view keeps every recorded round visible, while this page focuses on the championship order. Dataset updated {SITE_UPDATED_LONG}.</p><div><a href="../../methodology.html">Methodology →</a><br><a href="../../data-license.html">Data license →</a></div></div>
</div></section></main>'''
    html += footer_html("../../")
    return html

def build_competitions_hub(riders):
    cards = []
    item_list = []
    for position, competition in enumerate(COMPETITIONS, 1):
        stats = competition_stats(riders, competition)
        detail_path = f"/competitions/{competition['id']}.html"
        cards.append(f'''<article class="competition-card">
          <div class="competition-card-top"><span class="competition-status">Tracking now</span><span>{competition['season']}</span></div>
          <div class="competition-sport">{esc(competition['sport'])} · {esc(competition['discipline'])}</div>
          <h2>{esc(competition['name'])}</h2>
          <p>Explore the season context, completed rounds, tracked riders and links to the live standings and equipment database.</p>
          <div class="competition-card-stats"><span><strong>{len(stats['events'])}</strong> rounds</span><span><strong>{len(stats['scored'])}</strong> riders scored</span><span><strong>{len(stats['teams'])}</strong> teams</span></div>
          <a class="btn btn-solid" href="competitions/{competition['id']}.html">Open competition</a>
        </article>''')
        item_list.append({"@type": "ListItem", "position": position,
                          "name": competition["name"], "url": absolute_url(detail_path)})
    hub_organizations = [organization for organization in ORGANIZATIONS if organization.get("show_in_hub", True)]
    for organization in hub_organizations:
        children = [item for item in organization.get("competitions", []) if visible_status(item)]
        status_label = "Draft preview" if organization.get("status") == "draft" else "Published"
        cards.append(f'''<article class="competition-card">
          <div class="competition-card-top"><span class="competition-status">{status_label}</span><span>Organisation</span></div>
          <div class="competition-sport">Action sports · Event family</div>
          <h2>{esc(organization['name'])}</h2><p>{esc(organization.get('description'))}</p>
          <div class="competition-card-stats"><span><strong>{len(children)}</strong> competitions</span><span><strong>Draft</strong> workspace</span></div>
          <a class="btn btn-solid" href="competitions/{organization['id']}/">Open organisation</a>
        </article>''')
    description = "Choose a competition tracked by RidersFanatics and explore its riders, standings, results and race equipment."
    html = head(
        f"Competitions | Riders, Standings & Equipment | {SITE_NAME}", description, "",
        body_class="competitions-page", canonical_path="/competitions.html",
        schemas=[
            {"@context": "https://schema.org", "@type": "CollectionPage",
             "name": "Competitions tracked by RidersFanatics", "description": description,
             "url": absolute_url("/competitions.html"), "dateModified": SITE_UPDATED,
             "mainEntity": {"@type": "ItemList", "numberOfItems": len(item_list),
                            "itemListElement": item_list}},
            breadcrumb_schema([("Home", "/"), ("Competitions", "/competitions.html")]),
        ],
    )
    html += header_html("", active="competitions")
    html += f'''<main>
<section class="competition-hero"><div class="wrap"><div class="label">Series · Seasons · Disciplines</div><h1>Choose a competition.</h1><p>RidersFanatics is built to follow more than one championship. Select the series you want, then move between riders, results and equipment without mixing seasons.</p></div></section>
<div class="wrap">{breadcrumb_html([("Home", "./"), ("Competitions", "competitions.html")])}</div>
<section class="section competitions-list"><div class="wrap"><div class="section-head"><div><div class="label">Currently tracked</div><h2>Competition database</h2></div><span class="see-all">{len(COMPETITIONS) + len(hub_organizations)} active series</span></div><div class="competition-grid">{"".join(cards)}</div>
<div class="competition-note"><strong>Built for expansion</strong><p>New winter, bike and action-sport competitions can be added as separate datasets. The RidersFanatics brand, rider directory and equipment catalogue remain shared.</p></div></div></section>
</main>'''
    html += footer_html("")
    return html

def build_organization_page(organization):
    organization_id = organization["id"]
    children = [item for item in organization.get("competitions", []) if visible_status(item)]
    cards = []
    for item in children:
        item_href = item.get("existing_path") or f"{item['id']}/"
        if item_href.startswith("/"):
            item_href = "../.." + item_href
        status_label = "Published" if item.get("status") == "published" else "Draft preview"
        cards.append(f'''<article class="competition-card"><div class="competition-card-top"><span class="competition-status">{status_label}</span><span>{esc(item.get('discipline'))}</span></div><div class="competition-sport">{esc(item.get('sport'))}</div><h2>{esc(item['name'])}</h2><p>Explore the 2026 competition workspace, verified information and connected RidersFanatics data.</p><a class="btn btn-solid" href="{item_href}">Open competition</a></article>''')
    is_draft = organization.get("status") == "draft"
    page_label = "Protected draft · Independent coverage" if is_draft else "Competition organisation · Independent coverage"
    list_label = "Draft competitions" if is_draft else "Tracked competitions"
    title_suffix = " — Draft" if is_draft else " Competitions 2026"
    description = organization.get("description", "Competition organisation overview.")
    html = head(f"{organization['name']}{title_suffix} | {SITE_NAME}", description, "../../", body_class="competitions-page", canonical_path=f"/competitions/{organization_id}/",
                schemas=[{"@context": "https://schema.org", "@type": "CollectionPage", "name": f"{organization['name']} competitions", "description": description, "url": absolute_url(f"/competitions/{organization_id}/"), "dateModified": SITE_UPDATED}])
    html += header_html("../../", active="competitions")
    html += f'''<main><section class="competition-hero"><div class="wrap"><div class="label">{page_label}</div><h1>{esc(organization['name'])}</h1><p>{esc(description)}</p></div></section><div class="wrap">{breadcrumb_html([("Home", "../../"), ("Competitions", "../../competitions.html"), (organization['name'], "./")])}</div><section class="section competitions-list"><div class="wrap"><div class="section-head"><div><div class="label">{list_label}</div><h2>Choose an event.</h2></div><span class="see-all">{len(children)} competition{'s' if len(children) != 1 else ''}</span></div><div class="competition-grid">{"".join(cards)}</div><div class="competition-note"><strong>Independent database</strong><p>Open a competition to explore its 2026 standings, round results, rider profiles and documented equipment. RidersFanatics is not affiliated with the organiser.</p></div></div></section></main>'''
    return html + footer_html("../../")

def build_organization_competition_page(organization, competition):
    event_cards = []
    for event in competition.get("events", []):
        winners = ""
        if event.get("winners"):
            winners = '<div class="competition-card-stats">' + "".join(
                f'<span><strong>{esc(winner)}</strong></span>' for winner in event["winners"]
            ) + "</div>"
        source = ""
        if event.get("source_url"):
            source = f'<a class="see-all" href="{esc_attr(event["source_url"])}" rel="nofollow noopener" target="_blank">{esc(event.get("source_label", "Official source"))} ↗</a>'
        event_cards.append(f'''<article class="competition-card"><div class="competition-card-top"><span class="competition-status">{esc(event.get('status', 'draft'))}</span><span>{competition.get('season', 2026)}</span></div><div class="competition-sport">{esc(event.get('location'))}</div><h2>{esc(event['name'])}</h2><p><strong>{esc(event.get('dates'))}</strong></p><p>{esc(event.get('format'))}</p><p>{esc(event.get('note'))}</p>{winners}{source}</article>''')
    html = head(f"{competition['name']} — Draft | {SITE_NAME}", f"Protected editorial draft for {competition['name']} on RidersFanatics.", "../../../", body_class="competition-detail-page", canonical_path=f"/competitions/{organization['id']}/{competition['id']}/")
    html += header_html("../../../", active="competitions")
    html += f'''<main><section class="competition-detail-hero"><div class="wrap"><div class="label">Draft · {competition.get('season', 2026)} · {esc(competition.get('sport'))} · {esc(competition.get('discipline'))}</div><h1>{esc(competition['name'])}</h1><p>Protected 2026 editorial workspace. No official affiliation is claimed and no protected brand artwork is used.</p><div class="hero-ctas"><a class="btn" href="../">Back to {esc(organization['name'])}</a></div></div></section><div class="wrap">{breadcrumb_html([("Home", "../../../"), ("Competitions", "../../../competitions.html"), (organization['name'], "../"), (competition['name'], "./")])}</div><section class="section competitions-list"><div class="wrap"><div class="section-head"><div><div class="label">2026 only</div><h2>Events and verified status.</h2></div><span class="see-all">{len(event_cards)} event{'s' if len(event_cards) != 1 else ''}</span></div><div class="competition-grid">{"".join(event_cards)}</div><div class="competition-note"><strong>Draft dataset</strong><p>Dates, results and participants are included only when an official source is available. Unannounced details remain explicitly marked as to be confirmed.</p></div></div></section></main>'''
    return html + footer_html("../../../")

def season_ranking_selector(riders, competition):
    name = competition["name"]
    categories = {}
    for category in ("Men Elite", "Women Elite"):
        categories[category] = sorted(
            [rider for rider in riders
             if rider.get("gender_category") == category
             and competition_rider_points(rider, name) > 0],
            key=lambda rider: competition_rank_key(rider, name),
        )

    def rider_panel(category, label):
        rows = []
        for rank, rider in enumerate(categories[category], 1):
            team = rider.get("team") or "Privateer"
            nation = rider.get("country_code") or rider.get("country") or "—"
            points = competition_rider_points(rider, name)
            search = esc_attr(f"{rider['display_name']} {team} {nation}".lower())
            rows.append(f'''<a class="clean-standing-row" href="../riders/{rider['slug']}.html" data-standing-row data-search="{search}"><span class="clean-standing-rank">{rank:02d}</span><span class="clean-standing-name"><strong>{esc(rider['display_name'])}</strong><small>{esc(team)} · {esc(nation)}</small></span><span class="clean-standing-team">{esc(team)}</span><span class="clean-standing-nation">{esc(nation)}</span><b>{points}<small>pts</small></b></a>''')
        return f'''<section class="standings-block clean-standings-panel" data-standings="{category}" data-competition="{esc_attr(name)}"><div class="standings-scroll clean-standing-list"><div class="clean-standing-head"><span>Rank</span><span>Rider</span><span>Team</span><span>Nation</span><span>Points</span></div>{''.join(rows)}</div><p class="standings-empty" hidden>No {label.lower()} ranking is available.</p></section>'''

    team_points, team_riders = {}, {}
    for rider in categories["Men Elite"] + categories["Women Elite"]:
        team = rider.get("team") or "Privateer"
        team_points[team] = team_points.get(team, 0) + competition_rider_points(rider, name)
        team_riders.setdefault(team, []).append(rider["display_name"])
    teams = sorted(team_points, key=lambda team: (-team_points[team], team.lower()))
    team_rows = []
    for rank, team in enumerate(teams, 1):
        names = ", ".join(team_riders[team])
        search = esc_attr(f"{team} {names}".lower())
        team_rows.append(f'''<div class="clean-standing-row team-standing-row" data-standing-row data-search="{search}"><span class="clean-standing-rank">{rank:02d}</span><span class="clean-standing-name"><strong>{esc(team)}</strong><small>{esc(names)}</small></span><span class="clean-standing-team">{len(team_riders[team])} riders</span><span class="clean-standing-nation">—</span><b>{team_points[team]}<small>pts</small></b></div>''')
    team_panel = f'''<section class="standings-block clean-standings-panel" data-standings="Teams" data-competition="{esc_attr(name)}"><div class="standings-scroll clean-standing-list"><div class="clean-standing-head"><span>Rank</span><span>Team</span><span>Riders</span><span>Nation</span><span>Points</span></div>{''.join(team_rows)}</div><p class="standings-empty" hidden>No team ranking is available.</p></section>'''
    return f'''<section class="section clean-standings-section season-ranking-section" id="season-ranking"><div class="wrap"><div class="clean-standings-heading"><div><h2>Season ranking.</h2></div></div><div class="standings-toolbar clean-standings-toolbar"><div><span class="toolbar-label">Ranking</span><div class="filters" role="tablist" aria-label="Season ranking category" data-standings-filters><button class="filter-btn active" data-standings-group="Men Elite" aria-selected="true">Men</button><button class="filter-btn" data-standings-group="Women Elite" aria-selected="false">Women</button><button class="filter-btn" data-standings-group="Teams" aria-selected="false">Teams</button></div></div></div>{rider_panel('Men Elite', 'Men')}{rider_panel('Women Elite', 'Women')}{team_panel}</div></section>'''

def build_competition_detail(riders, competition):
    stats = competition_stats(riders, competition)
    events = stats["events"]
    name = competition["name"]
    path = f"/competitions/{competition['id']}.html"
    description = f"{name} season overview: completed events, current leaders, rider profiles and links to overall standings and professional downhill equipment."
    html = head(
        f"{name} | Riders & Events", description, "../",
        body_class="competition-detail-page", canonical_path=path,
        schemas=[
            {"@context": "https://schema.org", "@type": "CollectionPage", "name": name,
             "description": description, "url": absolute_url(path), "dateModified": SITE_UPDATED,
             "mainEntity": {"@type": "ItemList", "numberOfItems": len(events),
                            "itemListElement": [{"@type": "ListItem", "position": i,
                                                 "name": event}
                                                for i, event in enumerate(events, 1)]}},
            breadcrumb_schema([("Home", "/"), ("Competitions", "/competitions.html"), (name, path)]),
        ],
    )
    html = html.replace('</head>', '<link rel="stylesheet" href="../assets/css/uci-tour.css?v=4">\n</head>')
    html += header_html("../", active="competitions")
    html += f'''<main>
<section class="competition-detail-hero"><div class="wrap"><div class="label">{esc(competition['sport'])} · {esc(competition['discipline'])} · {competition['season']}</div><h1>{esc(name)}</h1></div></section>
<section class="uci-events-banner uci-tour-in-header" id="events" aria-label="2026 UCI Downhill World Cup events"><uci-iconic-tour></uci-iconic-tour></section>
{season_ranking_selector(riders, competition)}
</main>'''
    html += footer_html("../").replace(
        '<script src="../assets/js/site.js',
        '<script src="../assets/js/uci-iconic-tour.js?v=4"></script>\n<script src="../assets/js/site.js',
    )
    return html

def short_event(ev):
    """'South Korea (May)' -> 'KOR MAY'.

    The month is part of the label on purpose: a season can visit the same
    country twice (France in May and again in August), and the place alone
    would give two identical column headers."""
    m = re.match(r"^(.*?)\s*\(([^)]*)\)\s*$", ev)
    place, month = (m.group(1), m.group(2)) if m else (ev, "")
    place = place.strip()
    # Events read 'Venue, Country'; the country carries the code. A round the
    # sheet lists by country alone has no comma and is its own key.
    country = place.rsplit(",", 1)[-1].strip() if "," in place else place
    event_codes = {
        "South Korea": "KOR", "France": "FRA", "Austria": "AUT",
        "Switzerland": "SUI", "Italy": "ITA", "Andorra": "AND",
    }
    fallback = (country.split()[-1] if country.split() else ev)[:3].upper()
    label = event_codes.get(country, fallback)
    return f"{label} {month[:3].upper()}".strip()

def build_riders_directory(riders, women_count, men_count):
    prefix = ""
    cards = "\n      ".join(rider_card(r) for r in riders)
    html = head(
        f"All Riders — {SITE_NAME}",
        "Browse professional riders, bike setups, teams and season results across every competition tracked by RidersFanatics.",
        prefix, canonical_path="/riders.html",
        schemas=[
            {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Professional riders and race setups", "url": absolute_url("/riders.html"), "dateModified": SITE_UPDATED,
             "mainEntity": {"@type": "ItemList", "numberOfItems": len(riders), "itemListElement": [
                 {"@type": "ListItem", "position": i, "url": absolute_url(f"/riders/{r['slug']}.html"), "name": r["display_name"]}
                 for i, r in enumerate(riders, 1)
             ]}},
            breadcrumb_schema([("Home", "/"), ("Riders", "/riders.html")]),
        ]
    )
    html += header_html(prefix, active="riders")
    html += f"""
<main id="main-content">
<section class="section" id="grid" style="padding-top:32px;">
  <div class="wrap">
    <div class="filters" aria-label="Filter rider directory">
      <button class="filter-btn active" type="button" aria-pressed="true" data-filter="all">All ({len(riders)})</button>
      <button class="filter-btn" type="button" aria-pressed="false" data-filter="Men Elite">Men ({men_count})</button>
      <button class="filter-btn" type="button" aria-pressed="false" data-filter="Women Elite">Women ({women_count})</button>
      <label class="search-label"><span class="visually-hidden">Search riders</span><input class="search-input" type="search" placeholder="Search a rider, team, country..." data-search></label>
    </div>
    <div class="grid-riders" data-rider-grid>
      {cards}
    </div>
  </div>
</section>
</main>
"""
    html += footer_html(prefix)
    return html

# ---------------------------------------------------------------- rider page

def equip_item_html(item):
    raw_cat = item.get("category")
    cat = prettify_category(raw_cat)
    brand = item.get("brand") or ""
    detail_parts = [p.strip() for p in (item.get("model_detail") or "").split(";") if p.strip()]
    main_model = detail_parts[0] if detail_parts else ""
    extra = " · ".join(detail_parts[1:]) if len(detail_parts) > 1 else ""
    title = " ".join([brand, main_model]).strip() or "—"
    link = item.get("affiliate_link")
    amazon_link = item.get("amazon_link")
    photo = has_equip_photo(item.get("category"), brand, main_model)
    photo_html = f'<span class="equip-thumb"><img src="../assets/img/equipment/{photo}" alt="{esc(title)}" loading="lazy"></span>' if photo else ""
    detail_line = f'          <div class="detail">{esc(extra)}</div>\n' if extra else ""
    actions = []
    if link:
        actions.append(f'<a class="shop-btn" href="{esc(link)}" target="_blank" rel="noopener">Details</a>')
    if amazon_link:
        actions.append(f'<a class="shop-btn amazon-btn" href="{esc(amazon_link)}" target="_blank" rel="noopener sponsored">Amazon</a>')
    actions_html = f'<div class="equip-actions">{"".join(actions)}</div>' if actions else ""
    actions_line = f"        {actions_html}\n" if actions_html else ""
    return f"""<div class="equip-item reveal">
        {photo_html}
        <div>
          <a class="cat" href="../equipment/{equip_image_slug(raw_cat, '', '')}.html">{esc(cat)}</a>
          <h4>{esc(title)}</h4>
{detail_line}        </div>
{actions_line}      </div>"""

def find_equip(equipment, category):
    """First item of a category, with its photo resolved (or None)."""
    for item in equipment or []:
        if item.get("category") != category:
            continue
        brand = item.get("brand") or ""
        detail = [p.strip() for p in (item.get("model_detail") or "").split(";") if p.strip()]
        main_model = detail[0] if detail else ""
        photo = has_equip_photo(category, brand, main_model)
        if photo:
            return {
                "photo": photo,
                "title": " ".join([brand, main_model]).strip() or "—",
                "link": item.get("affiliate_link"),
                "item": item,
            }
    return None

def bike_build_parts(equipment):
    """The frame/fork/shock actually shown in the banner, so the kit list below
    can drop exactly those and keep anything the banner couldn't display."""
    frame = find_equip(equipment, "Frame")
    if not frame:
        return None
    fork = find_equip(equipment, "Fork")
    shock = find_equip(equipment, "RearShock")
    return {"frame": frame, "fork": fork, "shock": shock}

def bike_build_html(equipment):
    """Hero composition for the rider's chassis: the frame large in the middle,
    the fork laid over the front and the rear shock sitting behind.

    Deliberately an editorial layout, not a photo-realistic assembly: the source
    product shots have inconsistent viewpoints (frames in profile, forks head-on),
    so they can never line up into an actual bike. Rendered only when the frame
    photo exists — with no centrepiece the composition has nothing to hold it."""
    parts = bike_build_parts(equipment)
    if not parts:
        return ""
    frame, fork, shock = parts["frame"], parts["fork"], parts["shock"]

    def visual(slot, data):
        """The frame gets the three-layer reveal (self-drawing outline → pencil
        sketch → photo) when its derived layers exist; everything else is a
        plain image."""
        img = (f'<img class="bb-photo" src="../assets/img/equipment/{data["photo"]}" '
               f'alt="{esc(data["title"])}" loading="lazy">')
        if slot != "frame":
            return img
        stem = os.path.splitext(data["photo"])[0]
        sketch = os.path.join(REVEAL_IMG_DIR, f"{stem}-sketch.png")
        draw = os.path.join(REVEAL_IMG_DIR, f"{stem}-draw.svg")
        if not (os.path.exists(sketch) and os.path.exists(draw)):
            return img
        return f"""<span class="bb-reveal" data-frame-reveal>
            {img}
            <img class="bb-sketch" src="../assets/img/equipment/reveal/{stem}-sketch.png" alt="" aria-hidden="true" loading="lazy">
            <img class="bb-draw" src="../assets/img/equipment/reveal/{stem}-draw.svg" alt="" aria-hidden="true" loading="lazy">
          </span>"""

    def part(slot, data, label):
        if not data:
            return ""
        inner = f"""{visual(slot, data)}
          <figcaption>
            <span class="bb-cat">{esc(label)}</span>
            <span class="bb-name">{esc(data['title'])}</span>
          </figcaption>"""
        if data["link"]:
            return f"""<figure class="bb-part bb-{slot}">
          <a href="{esc(data['link'])}" target="_blank" rel="noopener">{inner}</a>
        </figure>"""
        return f'<figure class="bb-part bb-{slot}">{inner}</figure>'

    parts_html = "\n        ".join(filter(None, [
        part("shock", shock, "Rear shock"),
        part("frame", frame, "Frame"),
        part("fork", fork, "Fork"),
    ]))
    return f"""<div class="bike-build reveal">
      <div class="bb-stage">
        {parts_html}
      </div>
    </div>"""

def equipment_groups_html(equipment, hide_items=()):
    """Group equipment items into Chassis/Cockpit/Drivetrain/Wheels & Tyres/Protection
    sections, each with an icon + index number, matching the rest unsorted at the end."""
    # Parts already shown in the banner above are dropped so the page doesn't
    # list them twice. Filtering per item rather than per group matters: when
    # the banner can't show one of them (no photo), it stays in the list.
    hidden = {id(i) for i in hide_items}
    buckets = {g: [] for g in EQUIP_GROUP_ORDER}
    other = []
    for item in equipment:
        if id(item) in hidden:
            continue
        group = EQUIP_GROUP_MAP.get(item.get("category"))
        if group:
            buckets[group].append(item)
        else:
            other.append(item)

    shown = [g for g in EQUIP_GROUP_ORDER if buckets[g]]

    sections = []
    for idx, group in enumerate(shown, start=1):
        icon = EQUIP_GROUP_ICONS.get(group, "")
        items_html = "\n        ".join(equip_item_html(i) for i in buckets[group])
        sections.append(f"""<div class="equip-group reveal">
      <div class="equip-group-head">
        <span class="icon">{icon}</span>
        <div>
          <div class="idx">{idx:02d} / {len(shown):02d}</div>
          <h3>{esc(group)}</h3>
        </div>
      </div>
      <div class="equip-grid">
        {items_html}
      </div>
    </div>""")

    if other:
        items_html = "\n        ".join(equip_item_html(i) for i in other)
        sections.append(f"""<div class="equip-group reveal">
      <div class="equip-group-head">
        <div>
          <div class="idx">Other</div>
          <h3>Additional Kit</h3>
        </div>
      </div>
      <div class="equip-grid">
        {items_html}
      </div>
    </div>""")

    return "\n    ".join(sections)

# ---------------------------------------------------------------- rankings

def rider_total_points(r):
    return sum((h.get("points") or 0) for h in (r.get("competition_history") or []))

def season_rank_key(r):
    """Sort key for a season standing: points first, then the UCI tie-break —
    countback on best finishing positions, then the most recent round. Without
    it two riders on equal points are separated alphabetically, which puts the
    wrong name in the 'leader' slot."""
    history = r.get("competition_history") or []
    places = sorted(h["place"] for h in history if h.get("place"))
    last = next((h.get("points") or 0 for h in reversed(history) if h.get("points")), 0)
    return (-rider_total_points(r), places, -last, r.get("display_name") or "")

def build_rankings_section(riders):
    men = sorted([r for r in riders if r.get("gender_category") == "Men Elite"],
                 key=season_rank_key)[:5]
    women = sorted([r for r in riders if r.get("gender_category") == "Women Elite"],
                    key=season_rank_key)[:5]

    team_points = {}
    team_riders = {}
    for r in riders:
        team = r.get("team") or "Privateer"
        team_points[team] = team_points.get(team, 0) + rider_total_points(r)
        team_riders.setdefault(team, []).append(r)
    teams_sorted = sorted(team_points.items(), key=lambda x: x[1], reverse=True)[:5]

    def rider_row(rank, r):
        return f"""<a class="ranking-row" href="riders/{r['slug']}.html">
          <span class="ranking-rank">{rank:02d}</span>
          <div class="id-block">
            <div class="name">{esc(r['display_name'])}</div>
            <div class="sub">{esc(r.get('team') or 'Privateer')}</div>
          </div>
          <span class="pts">{rider_total_points(r)} pts</span>
        </a>"""

    def team_row(rank, team, pts):
        riders_on_team = team_riders[team]
        sub = ", ".join(r['display_name'] for r in riders_on_team[:3])
        if len(riders_on_team) > 3:
            sub += f" +{len(riders_on_team) - 3}"
        return f"""<div class="ranking-row">
          <span class="ranking-rank">{rank:02d}</span>
          <div class="id-block">
            <div class="name">{esc(team)}</div>
            <div class="sub">{esc(sub)}</div>
          </div>
          <span class="pts">{pts} pts</span>
        </div>"""

    team_rows = "\n        ".join(team_row(i + 1, t, p) for i, (t, p) in enumerate(teams_sorted))
    men_rows = "\n        ".join(rider_row(i + 1, r) for i, r in enumerate(men))
    women_rows = "\n        ".join(rider_row(i + 1, r) for i, r in enumerate(women))

    return f"""<section class="section home-rankings" id="rankings">
  <div class="wrap">
    <div class="section-head">
      <div>
        <div class="label">Current competition · Season {CURRENT_COMPETITION['season']}</div>
        <h2>DH Rankings</h2>
      </div>
      <a class="see-all" href="competitions/{CURRENT_COMPETITION['id']}/standings.html">View overall standings →</a>
    </div>
    <div class="rankings-grid">
      <div class="ranking-col">
        <div class="ranking-col-head"><h3>Team Ranking</h3><span class="tag">Top 5</span></div>
        {team_rows}
      </div>
      <div class="ranking-col">
        <div class="ranking-col-head"><h3>Men Ranking</h3><span class="tag">Top 5</span></div>
        {men_rows}
      </div>
      <div class="ranking-col">
        <div class="ranking-col-head"><h3>Women Ranking</h3><span class="tag">Top 5</span></div>
        {women_rows}
      </div>
    </div>
  </div>
</section>"""

def collect_equipment(riders):
    """Category/product facts used by SEO equipment pages."""
    by_cat = {}
    for rider in riders:
        seen = set()
        for item in rider.get("equipment") or []:
            cat = item.get("category")
            parts = [p.strip() for p in (item.get("model_detail") or "").split(";") if p.strip()]
            brand, model = canonical_equipment_product(cat, item.get("brand") or "", parts[0] if parts else "")
            # Keep brand-only observations on rider profiles, but never present
            # them as products in category rankings or their statistics.
            if not cat or not is_rankable_equipment_product(model):
                continue
            key = (cat, norm_product_text(brand), norm_product_text(model))
            if key in seen:
                continue
            seen.add(key)
            product = by_cat.setdefault(cat, {}).setdefault((brand, model), {
                "brand": brand, "model": model, "riders": [], "points": 0,
                "link": None, "amazon_link": None,
            })
            product["riders"].append(rider)
            product["points"] += rider_total_points(rider)
            product["link"] = product["link"] or item.get("affiliate_link")
            product["amazon_link"] = product["amazon_link"] or item.get("amazon_link")
    return by_cat

def equipment_category_path(category):
    return f"/equipment/{equip_image_slug(category, '', '')}.html"

EQUIPMENT_CATEGORY_PLURALS = {
    "Frame": "Frames", "Fork": "Forks", "RearShock": "Rear Shocks",
    "Handlebar": "Handlebars", "Wheels": "Wheels", "Tires": "Tires",
    "BrakeLever": "Brake Levers", "Crankset": "Cranksets",
    "Derailleur": "Derailleurs", "Pedals": "Pedals", "Saddle": "Saddles",
    "DropperPost": "Dropper Posts", "Helmet": "Helmets", "Goggles": "Goggles",
    "Protection": "Body Protection", "Shoes": "Shoes", "CHAIN": "Chains",
    "Disk": "Brake Rotors", "GRIP": "Grips", "Stem": "Stems",
    "Shifter": "Shifters", "BrakeCaliper": "Brake Calipers",
}

DIRECTORY_GROUP_MAP = {
    "Frame": "Frame & suspension", "Fork": "Frame & suspension", "RearShock": "Frame & suspension",
    "Handlebar": "Cockpit", "DropperPost": "Cockpit", "GRIP": "Cockpit", "Stem": "Cockpit",
    "BrakeLever": "Cockpit", "BrakeCaliper": "Cockpit", "Disk": "Cockpit",
    "Crankset": "Drivetrain", "Derailleur": "Drivetrain", "CHAIN": "Drivetrain", "Shifter": "Drivetrain",
    "Wheels": "Wheels", "Tires": "Wheels",
    "Saddle": "Extention", "Pedals": "Extention",
    "Helmet": "Protection", "Protection": "Protection", "Goggles": "Protection", "Shoes": "Protection",
}
DIRECTORY_GROUP_ORDER = ["Frame & suspension", "Cockpit", "Drivetrain", "Wheels", "Extention", "Protection"]

DIRECTORY_GROUP_ICONS = {
    "Frame & suspension": EQUIP_GROUP_ICONS["Chassis"],
    "Cockpit": EQUIP_GROUP_ICONS["Cockpit"],
    "Drivetrain": EQUIP_GROUP_ICONS["Drivetrain"],
    "Wheels": EQUIP_GROUP_ICONS["Wheels & Tyres"],
    "Extention": '<svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M8 9 H24 M16 9 V23 M11 23 H21"/><circle cx="16" cy="9" r="3"/></svg>',
    "Protection": EQUIP_GROUP_ICONS["Protection"],
}

DIRECTORY_GROUP_CONTENT = {
    "Frame & suspension": ("Frame & suspension", "Frames and suspension platforms that define the bike's geometry, travel and control."),
    "Cockpit": ("Cockpit", "Handlebars, grips, stems, dropper posts and braking controls used by the tracked riders."),
    "Drivetrain": ("Drivetrain", "Cranksets, derailleurs, chains and shifters that transfer power and manage gear changes."),
    "Wheels": ("Wheels", "Wheels and tires connecting each race setup to the track."),
    "Extention": ("Extention", "Saddles and pedals completing the rider's contact points."),
    "Protection": ("Protection", "Helmets, goggles, body protection and shoes used across the tracked field."),
}

def equipment_category_plural(category):
    return EQUIPMENT_CATEGORY_PLURALS.get(category, prettify_category(category) + "s")

def equipment_category_card(category, products, index):
    label = equipment_category_plural(category)
    ranked = sorted(products.values(), key=lambda p: (-p["points"], -len(p["riders"]), p["brand"], p["model"]))
    riders = {r["slug"] for p in ranked for r in p["riders"]}
    leader = ranked[0] if ranked else {"brand": "", "model": "", "points": 0}
    leader_name = " ".join([leader["brand"], leader["model"]]).strip()
    photo = has_equip_photo(category, leader["brand"], leader["model"]) if leader_name else None
    group = DIRECTORY_GROUP_MAP.get(category, "Frame & suspension")
    media = (f'<img src="assets/img/equipment/{photo}" alt="{esc_attr(leader_name)}" loading="lazy">'
             if photo else f'<span class="equipment-category-icon" aria-hidden="true">{DIRECTORY_GROUP_ICONS[group]}</span>')
    return f'''<a class="equipment-category-card" href="equipment/{equip_image_slug(category, '', '')}.html">
      <div class="equipment-category-media">{media}<span class="equipment-category-number">{index:02d}</span><span class="equipment-category-arrow" aria-hidden="true">↗</span></div>
      <div class="equipment-category-body"><span class="label">{esc(label)}</span><h3>{esc(leader_name)}</h3>
      <p>Most represented · {leader['points']} competition points</p>
      <div class="equipment-category-stats"><span><strong>{len(ranked)}</strong> products</span><span><strong>{len(riders)}</strong> riders</span></div></div>
    </a>'''

def equipment_hero_visual(by_cat):
    preferred = ["Frame", "Fork", "RearShock"]
    cards = []
    for slot, category in enumerate(preferred, 1):
        products = by_cat.get(category) or {}
        ranked = sorted(products.values(), key=lambda p: (-p["points"], -len(p["riders"]), p["brand"], p["model"]))
        if not ranked:
            continue
        leader = ranked[0]
        title = " ".join([leader["brand"], leader["model"]]).strip()
        photo = has_equip_photo(category, leader["brand"], leader["model"])
        image = (f'<img src="assets/img/equipment/{photo}" alt="{esc_attr(title)}">' if photo else
                 f'<span class="equipment-hero-icon">{DIRECTORY_GROUP_ICONS[DIRECTORY_GROUP_MAP.get(category, "Frame & suspension")]}</span>')
        cards.append(f'''<figure class="equipment-hero-product hero-product-{slot}">{image}<figcaption><span>{esc(equipment_category_plural(category))}</span><strong>{esc(title)}</strong></figcaption></figure>''')
    return "".join(cards)

def build_equipment_directory(riders):
    by_cat = collect_equipment(riders)
    categories = [c for c in CAROUSEL_CATEGORY_ORDER if c in by_cat]
    categories += sorted(c for c in by_cat if c not in categories)
    grouped_sections = []
    running_index = 1
    for group in DIRECTORY_GROUP_ORDER:
        group_categories = [c for c in categories if DIRECTORY_GROUP_MAP.get(c) == group]
        if not group_categories:
            continue
        group_title, group_description = DIRECTORY_GROUP_CONTENT[group]
        cards = []
        for category in group_categories:
            cards.append(equipment_category_card(category, by_cat[category], running_index))
            running_index += 1
        group_id = re.sub(r"[^a-z0-9]+", "-", group.lower()).strip("-")
        grouped_sections.append(f'''<section class="equipment-group" id="{group_id}"><div class="equipment-group-head"><div class="equipment-group-icon">{DIRECTORY_GROUP_ICONS[group]}</div><div><span class="label">{len(group_categories)} categories</span><h2>{esc(group_title)}</h2><p>{esc(group_description)}</p></div></div><div class="equipment-category-grid">{"".join(cards)}</div></section>''')
    path = "/equipment.html"
    product_count = sum(len(by_cat[c]) for c in categories)
    group_nav = "".join(
        f'<a href="#{re.sub(r"[^a-z0-9]+", "-", group.lower()).strip("-")}">{esc(DIRECTORY_GROUP_CONTENT[group][0])}</a>'
        for group in DIRECTORY_GROUP_ORDER if any(DIRECTORY_GROUP_MAP.get(c) == group for c in categories)
    )
    schema_items = [
        {"@type": "ListItem", "position": i, "name": equipment_category_plural(cat), "url": absolute_url(equipment_category_path(cat))}
        for i, cat in enumerate(categories, 1)
    ]
    html = head(
        f"Professional Downhill Equipment Database | {SITE_NAME}",
        "Explore the frames, forks, shocks, brakes, wheels, tires and protection used by 64 tracked professional downhill riders.",
        "", body_class="equipment-page", canonical_path=path,
        schemas=[
            {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Professional downhill equipment database", "url": absolute_url(path), "dateModified": SITE_UPDATED, "mainEntity": {"@type": "ItemList", "itemListElement": schema_items}},
            breadcrumb_schema([("Home", "/"), ("Equipment", path)]),
        ],
    )
    html += header_html("", active="equipment")
    html += f'''<main><section class="equipment-hero"><div class="wrap equipment-hero-layout"><div class="equipment-hero-copy"><div class="label">Professional race equipment · Verified setups</div><h1>Race equipment, <em>decoded.</em></h1><p>Explore what professional riders actually use. Every category connects products to riders, teams and results within the selected competition.</p><div class="hero-ctas"><a class="btn btn-solid" href="#equipment-catalogue">Browse categories</a><a class="btn equipment-compare-cta" href="compare.html">Open comparator</a></div><div class="equipment-hero-stats"><div><strong>{len(categories)}</strong><span>Categories</span></div><div><strong>{product_count}</strong><span>Products</span></div><div><strong>{len(riders)}</strong><span>Riders</span></div></div></div><div class="equipment-hero-visual" aria-label="Leading tracked equipment">{equipment_hero_visual(by_cat)}</div></div></section>
<div class="wrap">{breadcrumb_html([("Home", "./"), ("Equipment", "equipment.html")])}</div>
<section class="section equipment-catalogue" id="equipment-catalogue"><div class="wrap"><div class="equipment-catalogue-head"><div><div class="label">Equipment catalogue</div><h2>Explore the paddock.</h2><p>Choose a family, then open a category to see every tracked product and the riders using it.</p></div><a class="see-all" href="methodology.html">How rankings work →</a></div><nav class="equipment-group-nav" aria-label="Equipment families">{group_nav}</nav>{"".join(grouped_sections)}
<div class="equipment-compare-banner"><div><span class="label">Product comparator</span><h2>Build a side-by-side shortlist.</h2><p>Select two to four products from the same category and compare their tracked riders, teams and competition presence.</p></div><a class="btn btn-solid" href="compare.html">Start comparing</a></div>
<div class="guide-callout"><strong>How to read these rankings</strong><p>Combined rider points describe competitive presence in the tracked field. They are not a laboratory comparison: sponsorship, rider count and team selection influence every total.</p></div></div></section></main>'''
    html += footer_html("")
    return html

EQUIPMENT_EDITORIAL = {
    "Frame": ("Frames define the chassis platform around which the rest of a downhill build is assembled.", "Compare the number of tracked riders, team representation and the suspension platform before using points as a measure of visibility."),
    "Fork": ("Downhill forks manage front-wheel impacts and help riders maintain control through braking zones and rough terrain.", "Look at rider adoption and team use alongside the model name; race tunes and internal settings are not captured by this table."),
    "RearShock": ("Rear shocks control the frame's rear suspension and are normally tuned to the rider, frame and course.", "Treat each model as a platform rather than an identical setup because springs, damping and prototype internals can vary."),
    "Tires": ("Tires are a direct contact point with the course, and teams may change casing, compound or tread as conditions evolve.", "This ranking records the named product family. It should not be read as a fixed choice for every round or weather condition."),
    "Wheels": ("Wheel systems influence durability, handling and serviceability across a downhill race weekend.", "Compare adoption across riders and teams, while remembering that rims, hubs and spokes can be combined in different builds."),
    "BrakeLever": ("Brake controls are part of a complete braking system designed for repeatable modulation on steep tracks.", "Use the linked rider profiles to see the wider build; lever names alone do not document pads, rotors or individual setup."),
    "Handlebar": ("Handlebars shape a rider's cockpit position and steering interface.", "Model usage shows paddock presence, but width, rise and trimming are rider-specific details that may not be public."),
    "Stem": ("Stems connect the handlebar to the fork and contribute to cockpit fit.", "Compare named platforms and rider adoption without assuming that every rider uses the same length or position."),
    "GRIP": ("Grips are a small but highly personal contact point between rider and bike.", "Usage totals show which products appear in the tracked field, not which diameter, compound or wear strategy suits every rider."),
    "Crankset": ("Cranksets transfer rider input through the downhill drivetrain and must tolerate repeated impacts.", "Read points as competitive exposure and open the rider profiles for the surrounding drivetrain context."),
    "CHAIN": ("Chains connect the drivetrain components and are selected as part of a complete transmission system.", "The table identifies recorded product families; compatibility, gearing and replacement schedules remain build-specific."),
    "Derailleur": ("Rear derailleurs manage shifting and chain control on downhill race bikes.", "Compare rider and team presence, while recognising that gearing and electronic or mechanical configuration can differ."),
    "Pedals": ("Pedals are a critical rider-to-bike contact point, with choice shaped by feel, retention and confidence.", "Adoption is useful evidence of paddock presence, but it is not a universal recommendation for every riding style."),
    "Saddle": ("Saddles contribute to bike control and rider movement even though downhill riders spend limited time seated.", "The database records named models, not individual position, angle or customisation."),
    "DropperPost": ("Seatposts and dropper posts help define clearance and saddle position on a race bike.", "Use the ranking to compare documented use; travel and setup dimensions may vary by rider and frame size."),
    "Helmet": ("Full-face helmets are central protective equipment for professional downhill racing.", "Product presence does not replace fit checks, current certification guidance or manufacturer replacement advice."),
    "Goggles": ("Goggles protect vision and help riders manage changing light, dust and mud.", "The recorded brand or model may cover several lens choices used across different race conditions."),
    "Protection": ("Body protection is selected around coverage, mobility and the demands of the course.", "This list documents visible or published equipment only and should not be treated as a complete safety prescription."),
    "Shoes": ("Shoes complete the rider's connection to the pedals and influence fit and feel.", "Compare tracked usage as paddock evidence, then check pedal compatibility and manufacturer sizing independently."),
    "Disk": ("Brake rotors turn lever input into braking force at the wheel and must manage repeated heat cycles on long downhill tracks.", "Compare recorded diameters and product families in the rider profiles; rotor choice remains part of a complete brake setup."),
}

def build_equipment_category_page(category, products):
    label = equipment_category_plural(category)
    ranked = sorted(products.values(), key=lambda p: (-p["points"], -len(p["riders"]), p["brand"], p["model"]))
    tracked_riders = {r["slug"] for p in ranked for r in p["riders"]}
    path = equipment_category_path(category)
    rows = []
    schema_items = []
    for position, p in enumerate(ranked, 1):
        title = " ".join([p["brand"], p["model"]]).strip()
        rider_links = "".join(f'<a href="../riders/{r["slug"]}.html">{esc(r["display_name"])}</a>' for r in sorted(p["riders"], key=lambda x: season_rank_key(x)))
        photos = equipment_photos(category, p["brand"], p["model"])
        photo = photos[0] if photos else None
        photo_html = (f'<span class="equipment-photo-pair">' + "".join(
            f'<img src="../assets/img/equipment/{item}" alt="{esc_attr(title)}" loading="lazy" width="80" height="120">'
            for item in photos) + '</span>') if len(photos) == 2 else (f'<img src="../assets/img/equipment/{photo}" alt="{esc_attr(title)}" loading="lazy" width="160" height="120">' if photo else '<span class="equipment-placeholder" aria-hidden="true">FF</span>')
        external = ""
        if p["link"]:
            external += f'<a class="shop-btn" href="{esc(p["link"])}" rel="noopener" target="_blank">Product details</a>'
        if p["amazon_link"]:
            external += f'<a class="shop-btn amazon-btn" href="{esc(p["amazon_link"])}" rel="noopener sponsored" target="_blank">Amazon</a>'
        compare_payload = {
            "id": equip_image_slug(category, p["brand"], p["model"]),
            "category": category,
            "categoryLabel": label,
            "brand": p["brand"],
            "model": p["model"],
            "title": title,
            "points": p["points"],
            "riderCount": len(p["riders"]),
            "riders": [
                {"name": r["display_name"], "url": f"/riders/{r['slug']}.html"}
                for r in sorted(p["riders"], key=lambda x: season_rank_key(x))
            ],
            "teams": sorted({r.get("team") or "Privateer" for r in p["riders"]}),
            "image": f"/assets/img/equipment/{photo}" if photo else "",
            "productUrl": p["link"] or p["amazon_link"] or "",
            "competition": CURRENT_COMPETITION["name"],
        }
        compare_json = esc_attr(json.dumps(compare_payload, ensure_ascii=False, separators=(",", ":")))
        compare_button = f'<button class="compare-toggle" type="button" data-compare-product="{compare_json}" aria-pressed="false">Compare</button>'
        rows.append(f'''<article class="equipment-rank-card"><span class="equipment-rank">{position:02d}</span>{photo_html}<div class="equipment-rank-main"><div class="label">{esc(label)}</div><h2>{esc(title)}</h2><p><strong>{p['points']} pts</strong> · {len(p['riders'])} tracked rider{'s' if len(p['riders']) != 1 else ''}</p><div class="equipment-riders">{rider_links}</div><div class="equip-actions">{compare_button}{external}</div></div></article>''')
        schema_items.append({"@type": "ListItem", "position": position, "name": title})
    leader = " ".join([ranked[0]["brand"], ranked[0]["model"]]).strip() if ranked else "—"
    brand_count = len({p["brand"] for p in ranked if p["brand"]})
    total_points = sum(p["points"] for p in ranked)
    leader_share = round((ranked[0]["points"] / total_points) * 100) if ranked and total_points else 0
    context, compare_note = EQUIPMENT_EDITORIAL.get(category, (
        f"{label} form part of a complete professional downhill race setup.",
        "Compare documented rider and team adoption, and use points only as a measure of presence in the tracked field.",
    ))
    description = f"Compare {len(ranked)} {label.lower()} used by {len(tracked_riders)} tracked professional downhill riders. See rider count, competition points and associated profiles."
    html = head(
        f"Pro Downhill {label} | {SITE_NAME}", description,
        "../", body_class="equipment-page", canonical_path=path,
        schemas=[
            {"@context": "https://schema.org", "@type": "Dataset", "name": f"Professional downhill {label.lower()} usage", "description": description, "url": absolute_url(path), "dateModified": SITE_UPDATED, "creator": {"@type": "Organization", "name": SITE_NAME, "url": SITE_URL}, "license": DATA_LICENSE_URL, "isAccessibleForFree": True, "mainEntity": {"@type": "ItemList", "itemListElement": schema_items}},
            breadcrumb_schema([("Home", "/"), ("Equipment", "/equipment.html"), (label, path)]),
        ],
    )
    html += header_html("../", active="equipment")
    html += f'''<main><section class="hero equipment-hero"><div class="wrap hero-inner"><div class="label">Professional downhill · Competition-based data</div><h1>{esc(label)} used by professional downhill riders.</h1><p class="sub">{esc(description)} The current points leader in this category is {esc(leader)}.</p></div></section>
<div class="wrap">{breadcrumb_html([("Home", "../"), ("Equipment", "../equipment.html"), (label, equip_image_slug(category, '', '') + ".html")])}</div>
<section class="section"><div class="wrap"><div class="section-head"><div><div class="label">Ranked by combined rider points</div><h2>{esc(label)} leaderboard</h2></div><a class="see-all" href="../methodology.html">Read the methodology →</a></div><div class="equipment-ranking-list">{"".join(rows)}</div>
<section class="equipment-editorial reveal"><div><div class="label">How to read this category</div><h2>What the {esc(label.lower())} data tells us.</h2><p>{esc(context)} {esc(compare_note)}</p><p>The current RidersFanatics dataset connects {len(ranked)} products from {brand_count} brands to {len(tracked_riders)} rider profiles. {esc(leader)} leads by combined rider points and represents {leader_share}% of the points attached to this category. That figure measures competitive exposure, not technical superiority.</p></div><dl class="content-stats"><div><dt>{len(ranked)}</dt><dd>Products</dd></div><div><dt>{brand_count}</dt><dd>Brands</dd></div><div><dt>{len(tracked_riders)}</dt><dd>Riders</dd></div><div><dt>{leader_share}%</dt><dd>Leader share</dd></div></dl></section>
<div class="guide-callout"><strong>Editorial and data status</strong><p>This table records competitive usage within the RidersFanatics dataset. It does not claim that the first product is universally better, and race prototypes may differ from retail specifications. Counts are recalculated from the rider records at build time, so every category stays connected to its supporting profiles. Page generated from data updated {esc(SITE_UPDATED)}; see the <a href="../methodology.html">methodology</a> or <a href="../contact.html">report a correction</a>.</p></div></div></section></main>'''
    html += footer_html("../")
    return html

def build_compare_page():
    path = "/compare.html"
    html = head(
        f"Compare Professional Downhill Equipment | {SITE_NAME}",
        "Compare up to four professional downhill products by tracked riders, teams and competition points on RidersFanatics.",
        "", body_class="compare-page", canonical_path=path,
        schemas=[
            {"@context": "https://schema.org", "@type": "WebPage", "name": "Professional downhill equipment comparison", "url": absolute_url(path), "dateModified": SITE_UPDATED},
            breadcrumb_schema([("Home", "/"), ("Equipment", "/equipment.html"), ("Compare", path)]),
        ],
    )
    html += header_html("", active="equipment")
    html += f'''<main>
<section class="hero compare-hero"><div class="wrap hero-inner"><div class="label">Simple comparison · Up to 4 products</div><h1>Compare race equipment.</h1><p class="sub">Place products from the same category side by side using verified RidersFanatics data: tracked riders, teams and points in the current competition.</p></div></section>
<div class="wrap">{breadcrumb_html([("Home", "./"), ("Equipment", "equipment.html"), ("Compare", "compare.html")])}</div>
<section class="section"><div class="wrap">
  <div class="compare-notice"><strong>How to read this comparison</strong><p>Competition points describe sporting presence among tracked riders. They are not a laboratory score and do not prove that one product is technically better.</p></div>
  <div data-compare-page aria-live="polite">
    <div class="compare-empty"><h2>No products selected yet.</h2><p>Open an equipment category and select between two and four products marked “Compare”.</p><a class="btn btn-solid" href="equipment.html">Browse equipment</a></div>
  </div>
  <section class="compare-guide" aria-labelledby="compare-guide-title"><div><div class="label">Start with comparable products</div><h2 id="compare-guide-title">Build a useful downhill equipment comparison.</h2><p>Select products from the same component category, then compare the professional riders, teams and 2026 competition points connected to each product. Rider points measure visibility in the tracked field; they do not replace geometry, weight, price or laboratory testing.</p></div><div class="compare-guide-links"><a href="equipment/frame.html">Compare frames</a><a href="equipment/fork.html">Compare forks</a><a href="equipment/rearshock.html">Compare rear shocks</a><a href="equipment/tires.html">Compare tires</a></div></section>
</div></section>
</main>'''
    html += footer_html("")
    return html

# ---------------------------------------------------------------- best equipment carousel

CAROUSEL_CATEGORY_ORDER = [
    "Frame", "Fork", "RearShock", "Handlebar", "Wheels", "Tires",
    "BrakeLever", "Crankset", "Derailleur", "Pedals", "Saddle",
    "DropperPost", "Helmet", "Goggles", "Protection", "Shoes",
]

def build_best_equipment_carousel(riders):
    """Full-bleed carousel: one slide per equipment category, each showing the
    top 3 models of that category ranked by the combined season points of
    every rider running them."""
    # aggregate (category, brand, model) -> combined points + rider count
    by_cat = {}
    for r in riders:
        pts = rider_total_points(r)
        for item in r.get("equipment") or []:
            cat = item.get("category")
            brand = item.get("brand") or ""
            detail_parts = [p.strip() for p in (item.get("model_detail") or "").split(";") if p.strip()]
            main_model = detail_parts[0] if detail_parts else ""
            brand, main_model = canonical_equipment_product(cat, brand, main_model)
            if not is_rankable_equipment_product(main_model):
                continue
            key = (brand, main_model)
            g = by_cat.setdefault(cat, {}).setdefault(key, {
                "brand": brand, "model": main_model,
                "points": 0, "rider_count": 0, "link": None, "amazon_link": None,
            })
            g["points"] += pts
            g["rider_count"] += 1
            if not g["link"] and item.get("affiliate_link"):
                g["link"] = item["affiliate_link"]
            if not g["amazon_link"] and item.get("amazon_link"):
                g["amazon_link"] = item["amazon_link"]

    # keep categories in preferred order; skip those without enough data for a
    # meaningful podium (needs 3+ distinct models and 8+ riders tracked)
    def has_enough_data(cat):
        models = by_cat.get(cat, {})
        return len(models) >= 3 and sum(g["rider_count"] for g in models.values()) >= 8

    cats = [c for c in CAROUSEL_CATEGORY_ORDER if has_enough_data(c)]
    cats += [c for c in by_cat if c not in cats and has_enough_data(c)]
    if not cats:
        return ""

    total = len(cats)

    def slide_html(idx, cat, hidden=False):
        cat_label = prettify_category(cat)
        hidden_tab = ' tabindex="-1"' if hidden else ""
        top3 = sorted(by_cat[cat].values(), key=lambda g: g["points"], reverse=True)[:3]
        max_pts = top3[0]["points"] or 1

        rows = []
        for rank, g in enumerate(top3, start=1):
            title = " ".join([g["brand"], g["model"]]).strip() or "—"
            amazon_link = g["amazon_link"]
            width = max(6, round(g["points"] / max_pts * 100))
            photos = equipment_photos(cat, g["brand"], g["model"])
            pair_class = " p-thumb-pair" if len(photos) == 2 else ""
            thumb = (f'<span class="p-thumb{pair_class}">' + "".join(
                f'<img src="assets/img/equipment/{photo}" alt="{esc(title)}" loading="lazy">'
                for photo in photos) + '</span>') if photos else ""
            thumb_line = f'\n              {thumb}' if thumb else ""
            shop = (f'<a class="p-shop" href="{esc(amazon_link)}" target="_blank" '
                    f'rel="noopener sponsored">Amazon</a>' if amazon_link
                    else '<span class="p-shop is-muted">Tracked</span>')
            rows.append(f"""<div class="podium-item rank-{rank}">
              <span class="p-rank">{rank}</span>{thumb_line}
              <div class="p-main">
                <h4 title="{esc(title)}">{esc(title)}</h4>
                <div class="p-bar"><span style="width:{width}%"></span></div>
                <div class="p-foot">
                  <span class="p-meta">{g['points']} pts · {g['rider_count']} rider{'s' if g['rider_count'] != 1 else ''}</span>
                  {shop}
                </div>
              </div>
            </div>""")

        aria = ' aria-hidden="true"' if hidden else ""
        return f"""<div class="carousel-slide"{aria}>
          <div class="slide-head">
            <span class="idx">{idx + 1:02d} / {total:02d}</span>
            <h3><a href="equipment/{equip_image_slug(cat, '', '')}.html"{hidden_tab}>{esc(cat_label)}</a></h3>
            <span class="cat-sub">Top 3 · competition points</span>
          </div>
          <div class="podium">
            {"".join(rows)}
          </div>
        </div>"""

    slides = "".join(slide_html(i, c) for i, c in enumerate(cats))
    # duplicated set so the marquee can loop seamlessly
    slides_dup = "".join(slide_html(i, c, hidden=True) for i, c in enumerate(cats))

    return f"""<section class="section eq-carousel-section" id="equipment">
  <div class="wrap">
    <div class="section-head">
      <div>
        <div class="label">Race-proven · Season 2026</div>
        <h2>Best Equipment</h2>
      </div>
      <a class="see-all" href="equipment.html">Explore all {total} categories →</a>
    </div>
  </div>
  <div class="carousel" data-marquee aria-label="Best equipment by category">
    <div class="carousel-track">
      {slides}{slides_dup}
    </div>
  </div>
</section>"""

def results_rows(history):
    rows = []
    for h in history or []:
        points = h.get("points")
        comp = h.get("category") or "Other"
        place = history_place(h)
        result = h.get("result") or ordinal(place) or "—"
        podium = f" podium p{place}" if place and place <= 3 else ""
        competition = next((item for item in COMPETITIONS if item.get("name") == comp), None)
        event_label = esc(h.get('event'))
        if competition and h.get("event"):
            event_label = (f'<a href="../competitions/{competition["id"]}/rounds/'
                           f'{competition_round_slug(h["event"])}.html">{event_label}</a>')
        rows.append(f"""<tr data-competition="{esc(comp)}">
          <td>{esc(h.get('year'))}</td>
          <td>{event_label}</td>
          <td class="result{podium}">{esc(result)}</td>
          <td class="points">{esc(points) if points is not None else '—'}</td>
        </tr>""")
    return "\n        ".join(rows)

def competition_filters(history):
    """Chips to narrow the results table by competition. Built from the data, so
    adding a second series to the sheet makes its chip appear on its own."""
    counts = {}
    for h in history or []:
        comp = h.get("category") or "Other"
        counts[comp] = counts.get(comp, 0) + 1
    if not counts:
        return ""
    # No "all" chip: the first competition is selected on load and the table is
    # filtered to it, so the chips always reflect what the table is showing.
    chips = []
    for i, comp in enumerate(sorted(counts)):
        active = " active" if i == 0 else ""
        chips.append(f'<button class="filter-btn{active}" data-competition-filter="{esc(comp)}">'
                     f'{esc(comp)} ({counts[comp]})</button>')
    return f'<div class="filters results-filters" data-competition-filters>{"".join(chips)}</div>'

def rider_editorial(r, riders):
    history = r.get("competition_history") or []
    equipment = r.get("equipment") or []
    category = r.get("gender_category") or "tracked category"
    field = sorted([x for x in riders if (x.get("gender_category") or "") == (r.get("gender_category") or "")], key=season_rank_key)
    rank = next((i for i, x in enumerate(field, 1) if x.get("slug") == r.get("slug")), None)
    places = [(history_place(h), h) for h in history if history_place(h)]
    best_place, best_event = min(places, key=lambda x: x[0]) if places else (None, None)
    podiums = sum(1 for place, _ in places if place <= 3)
    top_tens = sum(1 for place, _ in places if place <= 10)
    points = rider_total_points(r)
    rank_text = f"ranked {ordinal(rank)} of {len(field)} riders in the tracked {category} field" if rank else f"listed in the tracked {category} field"
    season = f"{r['display_name']} is currently {rank_text}, with {points} points across {len(history)} recorded start{'s' if len(history) != 1 else ''}."
    if best_event:
        season += f" The strongest recorded finish is {ordinal(best_place)} at {best_event.get('event')}."
    if places:
        season += f" The season sample contains {podiums} podium{'s' if podiums != 1 else ''} and {top_tens} top-ten result{'s' if top_tens != 1 else ''}."
    else:
        season += " No classified finish is currently recorded, so the profile remains a data-monitoring page rather than a performance assessment."

    def product(cat):
        item = next((e for e in equipment if e.get("category") == cat), None)
        if not item:
            return ""
        model = next((p.strip() for p in (item.get("model_detail") or "").split(";") if p.strip()), "")
        return " ".join(filter(None, [item.get("brand"), model])).strip()

    frame, fork, shock = product("Frame"), product("Fork"), product("RearShock")
    tires, wheels, brakes = product("Tires"), product("Wheels"), product("BrakeLever")
    setup_bits = []
    if frame: setup_bits.append(f"a {frame} frame")
    if fork: setup_bits.append(f"a {fork} fork")
    if shock: setup_bits.append(f"a {shock} rear shock")
    setup = f"The recorded 2026 build contains {len(equipment)} identified equipment items."
    if setup_bits:
        setup += " Its documented chassis combines " + ", ".join(setup_bits) + "."
    contact_bits = [x for x in (wheels, tires, brakes) if x]
    if contact_bits:
        setup += " Other published components include " + ", ".join(contact_bits) + "."
    setup += " These entries describe the documented race platform; settings, compounds and prototype internals can change by event."
    return rank, season, setup, best_place

def build_rider_page(r, riders):
    prefix = "../"
    # The rider page hero prefers the portrait action shot; the square avatar
    # (used on the grid cards) is the fallback, then the initials placeholder.
    action = has_action_photo(r["slug"])
    photo = has_photo(r["slug"])
    if action:
        photo_html = f'<img src="../assets/img/riders-action/{action}" alt="{esc(r["display_name"])}" fetchpriority="high">'
    elif photo:
        photo_html = f'<img src="../assets/img/riders/{photo}" alt="{esc(r["display_name"])}" width="400" height="400" fetchpriority="high">'
    else:
        photo_html = f'<span class="initials">{esc(initials(r))}</span>'

    bullets = bio_bullets(r.get("bio"))
    bio_html = ""
    if bullets:
        items = "".join(f"<li>{esc(b)}</li>" for b in bullets)
        bio_html = f'<ul class="rider-bio" style="list-style:disc; padding-left:18px;">{items}</ul>'
    else:
        bio_html = '<p class="rider-bio">No public palmarès on file yet.</p>'

    sponsors = r.get("sponsors") or []
    sponsor_html = ""
    if sponsors:
        chips = "".join(f"<span>{esc(s)}</span>" for s in sponsors)
        sponsor_html = f'<div class="sponsor-row">{chips}</div>'

    equipment = r.get("equipment") or []
    build_html = bike_build_html(equipment)
    setup_head = ""
    banner = bike_build_parts(equipment) or {}
    shown_in_banner = [p["item"] for p in banner.values() if p]
    if equipment:
        equip_html = equipment_groups_html(equipment, hide_items=shown_in_banner)
    else:
        equip_html = '<p style="color:var(--muted); font-size:14px;">No public equipment spec on file yet for this rider.</p>'

    history = r.get("competition_history") or []
    category_rank, season_analysis, setup_analysis, best_place = rider_editorial(r, riders)
    highlight_parts = []
    for wanted in ("Frame", "Fork", "RearShock"):
        item = next((e for e in equipment if e.get("category") == wanted), None)
        if not item:
            continue
        details = [p.strip() for p in (item.get("model_detail") or "").split(";") if p.strip()]
        product = " ".join([item.get("brand") or "", details[0] if details else ""]).strip()
        if product:
            highlight_parts.append(product)
    identity = f"a {r.get('country')} downhill rider" if r.get("country") else "a professional downhill rider"
    if r.get("team"):
        identity += f" competing for {r['team']}"
    rider_summary = f"{r['display_name']} is {identity}. RidersFanatics currently tracks {len(equipment)} equipment items for this 2026 race setup"
    if highlight_parts:
        rider_summary += ", including " + ", ".join(highlight_parts)
    rider_summary += f". The season record below contains {len(history)} tracked result{'s' if len(history) != 1 else ''} and {rider_total_points(r)} cumulative points."
    meta_description = f"{r['display_name']}: 2026 downhill results, {rider_total_points(r)} tracked points"
    if category_rank:
        meta_description += f", {ordinal(category_rank)} in {r.get('gender_category') or 'the category'}"
    meta_description += f", plus the documented bike setup and equipment."
    keyword_pages = {
        "jackson-goldstone": (
            "Jackson Goldstone Bike Setup 2026 | Results & Kit",
            "Jackson Goldstone bike setup for 2026: frame, suspension, wheels and components, plus UCI downhill results, ranking and tracked points.",
        ),
        "jordan-williams": (
            "Jordan Williams Bike Check 2026 | Setup & Results",
            "Jordan Williams bike check and 2026 downhill setup: documented frame, suspension and components with UCI results, ranking and points.",
        ),
        "asa-vermette": (
            "Asa Vermette Bike Setup 2026 | Results & Equipment",
            "Asa Vermette bike setup and equipment for 2026, with documented race components, UCI downhill results, championship ranking and points.",
        ),
        "anna-newkirk": (
            "Anna Newkirk — Downhill Rider, Results & Bike 2026",
            "Anna Newkirk’s 2026 profile: 4th in the tracked UCI DH Women Elite standings with 565 points, plus results and her Frameworks race bike setup.",
        ),
        "gloria-scarsi": (
            "Gloria Scarsi — Downhill Rider, Results & Bike 2026",
            "Gloria Scarsi’s 2026 profile: 5th in the tracked UCI DH Women Elite standings with 550 points, plus results and her Zerode G3 race bike setup.",
        ),
        "sacha-earnest": (
            "Sacha Earnest — Downhill Rider, Results & Bike 2026",
            "Sacha Earnest’s 2026 profile: 7th in the tracked UCI DH Women Elite standings with 520 points, plus results, podiums and her Trek Session setup.",
        ),
    }
    page_title, meta_description = keyword_pages.get(
        r.get("slug"),
        (f"{r['display_name']} — Bike Setup & Kit | {SITE_NAME}", meta_description),
    )
    if history:
        results_html = f"""{competition_filters(history)}
      <div class="results-scroll" tabindex="0" role="region" aria-label="Race results table, horizontally scrollable on small screens"><table class="results-table" data-results-table>
        <caption>{esc(r['display_name'])} 2026 race results</caption>
        <thead><tr><th scope="col">Year</th><th scope="col">Event</th><th scope="col">Result</th><th scope="col">Points</th></tr></thead>
        <tbody>
        {results_rows(history)}
        </tbody>
      </table></div>"""
    else:
        results_html = '<p style="color:var(--muted); font-size:14px;">No 2026 results recorded yet.</p>'

    # (label, value_html) — value is already-escaped markup so Instagram can be a link
    meta_items = []
    if r.get("country"):
        meta_items.append(("Country", esc(r["country"])))
    if r.get("hometown"):
        meta_items.append(("Hometown", esc(r["hometown"])))
    if r.get("age"):
        meta_items.append(("Age", esc(str(r["age"]))))
    if r.get("date_of_birth"):
        meta_items.append(("Born", esc(r["date_of_birth"])))
    if r.get("instagram"):
        handle = r["instagram"].strip().lstrip("@")
        meta_items.append((
            "Instagram",
            f'<a class="ig-link" href="https://instagram.com/{esc(handle)}" '
            f'target="_blank" rel="noopener">@{esc(handle)}</a>',
        ))
    if r.get("team"):
        meta_items.append(("Team", esc(r["team"])))
    meta_html = "\n      ".join(
        f'<div class="item"><span>{k}</span>{v}</div>' for k, v in meta_items
    )

    rider_url = f"/riders/{r['slug']}.html"
    rider_image = f"/assets/img/riders-action/{action}" if action else (f"/assets/img/riders/{photo}" if photo else None)
    person_schema = {
        "@context": "https://schema.org", "@type": "Person", "name": r["display_name"],
        "url": absolute_url(rider_url), "nationality": r.get("country") or None,
        "description": rider_summary,
    }
    if rider_image:
        person_schema["image"] = absolute_url(rider_image)
    if r.get("team"):
        person_schema["affiliation"] = {"@type": "SportsTeam", "name": r["team"]}
    if r.get("instagram"):
        person_schema["sameAs"] = [f"https://instagram.com/{r['instagram'].strip().lstrip('@')}"]
    html = head(
        page_title,
        meta_description,
        prefix, canonical_path=rider_url, page_type="article", image_path=rider_image,
        schemas=[
            {"@context": "https://schema.org", "@type": "WebPage", "name": f"{r['display_name']} bike setup and results", "url": absolute_url(rider_url), "dateModified": SITE_UPDATED, "mainEntity": {"@id": absolute_url(rider_url) + "#rider"}},
            {**person_schema, "@id": absolute_url(rider_url) + "#rider"},
            breadcrumb_schema([("Home", "/"), ("Riders", "/riders.html"), (r["display_name"], rider_url)]),
        ]
    )
    html += header_html(prefix, active="riders")

    related = [candidate for candidate in sorted(
        riders, key=season_rank_key
    ) if candidate.get("slug") != r.get("slug")
        and candidate.get("gender_category") == r.get("gender_category")][:4]
    related_html = "".join(
        f'<a href="{candidate["slug"]}.html"><strong>{esc(candidate["display_name"])}</strong>'
        f'<span>{esc(candidate.get("team") or "Privateer")} · {rider_total_points(candidate)} pts</span></a>'
        for candidate in related
    )
    html += f"""
<main class="section" style="padding-top:18px;">
  <div class="wrap">
    <div class="rider-hero">
      <div class="photo">{photo_html}</div>
      <div>
        <h1>{esc(r['display_name'])}</h1>
        <div class="rider-meta">
          {meta_html}
        </div>
        {bio_html}
        {sponsor_html}
      </div>
    </div>

    {setup_head}{build_html}
    {equip_html}

    <section class="rider-editorial rider-setup-analysis reveal"><div><div class="label">Build context</div><h2>Setup analysis</h2><p>{esc(setup_analysis)}</p><p class="data-note">Page generated from the dataset updated {esc(SITE_UPDATED)}. Equipment is revised when a verifiable change is identified. <a href="../methodology.html">Read the methodology</a> or <a href="../contact.html">report a correction</a>.</p></div></section>

    <div class="section-head reveal" style="border-bottom:none; margin:48px 0 24px;">
      <div>
        <div class="label">Season 2026</div>
        <h2>Results</h2>
      </div>
    </div>
    {results_html}
    <section class="rider-related" aria-labelledby="related-riders-title">
      <div class="section-head"><div><div class="label">Continue exploring</div><h2 id="related-riders-title">Related 2026 downhill riders</h2></div><a class="see-all" href="../riders.html#grid">All riders →</a></div>
      <div class="rider-related-grid">{related_html}</div>
    </section>
  </div>
</main>
"""
    html += footer_html(prefix)
    return html

# ---------------------------------------------------------------- main

def list_missing_images(riders):
    """Print the exact filenames the build is looking for and doesn't have yet."""
    missing_riders = [r["slug"] for r in riders if not has_photo(r["slug"])]
    seen = set()
    missing_equip = []
    for r in riders:
        for item in r.get("equipment") or []:
            brand = item.get("brand") or ""
            detail_parts = [p.strip() for p in (item.get("model_detail") or "").split(";") if p.strip()]
            main_model = detail_parts[0] if detail_parts else ""
            if not brand and not main_model:
                continue
            slug = equip_image_slug(item.get("category"), brand, main_model)
            if slug in seen:
                continue
            seen.add(slug)
            if not has_equip_photo(item.get("category"), brand, main_model):
                missing_equip.append(slug)

    print(f"— Rider photos missing ({len(missing_riders)}) → assets/img/riders/<name>.jpg")
    for s in missing_riders:
        print(f"  {s}.jpg")
    print(f"\n— Equipment photos missing ({len(missing_equip)}) → assets/img/equipment/<name>.jpg")
    for s in sorted(missing_equip):
        print(f"  {s}.jpg")

def run_image_optimizer():
    if os.environ.get("RF_SKIP_IMAGE_OPTIMIZER") == "1":
        return
    image_optimizer = os.path.join(ROOT, "optimize_images.py")
    if os.path.exists(image_optimizer):
        subprocess.run([sys.executable, image_optimizer], check=True)

def ensure_accessibility_landmarks():
    """Keep the skip link target in the static HTML, including generated pages."""
    for directory, _, filenames in os.walk(ROOT):
        if ".git" in directory.split(os.sep):
            continue
        for filename in filenames:
            if not filename.endswith(".html"):
                continue
            path = os.path.join(directory, filename)
            with open(path, encoding="utf-8") as source:
                markup = source.read()
            if 'id="main-content"' not in markup and "<main" in markup:
                markup = markup.replace("<main", '<main id="main-content"', 1)
                with open(path, "w", encoding="utf-8") as target:
                    target.write(markup)

def write_promo_pool(riders):
    """Small public dataset used to rotate footer discoveries after the daily first visit."""
    public_riders = []
    for rider in riders:
        equipment = []
        seen = set()
        for item in rider.get("equipment") or []:
            category = item.get("category") or ""
            raw_model = (item.get("model_detail") or "").split(";")[0].strip()
            brand, model = canonical_equipment_product(category, item.get("brand") or "", raw_model)
            if not category or not model:
                continue
            key = "|".join((category, norm_product_text(brand), norm_product_text(model)))
            if key in seen:
                continue
            seen.add(key)
            photo = has_equip_photo(category, brand, model)
            equipment.append({
                "key": key,
                "category": category,
                "brand": brand,
                "model": model,
                "photo": f"/assets/img/equipment/{photo}" if photo else "",
                "href": equipment_category_path(category),
            })
        photo = has_photo(rider["slug"])
        public_riders.append({
            "name": rider["display_name"],
            "slug": rider["slug"],
            "gender": rider.get("gender_category") or "",
            "team": rider.get("team") or "Independent rider",
            "photo": f"/assets/img/riders/{photo}" if photo else "",
            "href": f"/riders/{rider['slug']}.html",
            "equipment": equipment,
        })
    promo_path = os.path.join(ROOT, "assets", "js", "promo-pool.js")
    with open(promo_path, "w", encoding="utf-8") as target:
        payload = json.dumps({"riders": public_riders}, ensure_ascii=False, separators=(",", ":"))
        target.write(f"window.RF_PROMO_POOL={payload};\n")


def main():
    with open(DATA_PATH, encoding="utf-8") as f:
        riders = json.load(f)

    os.makedirs(RIDERS_DIR, exist_ok=True)
    os.makedirs(EQUIPMENT_DIR, exist_ok=True)
    os.makedirs(COMPETITIONS_DIR, exist_ok=True)
    os.makedirs(IMG_DIR, exist_ok=True)
    os.makedirs(EQUIP_IMG_DIR, exist_ok=True)

    # Remove generated organization drafts that are not visible in this build.
    # This makes a production build safe even after a previous preprod build.
    visible_organization_ids = {item["id"] for item in ORGANIZATIONS}
    for item in COMPETITION_CATALOG.get("organizations", []):
        if item["id"] not in visible_organization_ids:
            shutil.rmtree(os.path.join(COMPETITIONS_DIR, item["id"]), ignore_errors=True)
            continue
        organization_dir = os.path.join(COMPETITIONS_DIR, item["id"])
        for competition in item.get("competitions", []):
            if not visible_status(competition) or competition.get("existing_path"):
                shutil.rmtree(os.path.join(organization_dir, competition["id"]), ignore_errors=True)

    if "--missing-images" in sys.argv:
        list_missing_images(riders)
        return

    women = [r for r in riders if r.get("gender_category") == "Women Elite"]
    men = [r for r in riders if r.get("gender_category") == "Men Elite"]
    write_promo_pool(riders)

    if "--standings-only" in sys.argv:
        with open(os.path.join(ROOT, "standings.html"), "w", encoding="utf-8") as f:
            f.write(build_standings(riders))
        run_image_optimizer()
        print("Built standings.html.")
        return

    index_html = build_index(riders, len(women), len(men))
    with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)

    if "--index-only" in sys.argv:
        run_image_optimizer()
        print("Built index.html.")
        return

    riders_html = build_riders_directory(riders, len(women), len(men))
    with open(os.path.join(ROOT, "riders.html"), "w", encoding="utf-8") as f:
        f.write(riders_html)

    with open(os.path.join(ROOT, "standings.html"), "w", encoding="utf-8") as f:
        f.write(build_standings(riders))

    with open(os.path.join(ROOT, "equipment.html"), "w", encoding="utf-8") as f:
        f.write(build_equipment_directory(riders))

    with open(os.path.join(ROOT, "compare.html"), "w", encoding="utf-8") as f:
        f.write(build_compare_page())

    with open(os.path.join(ROOT, "contact.html"), "w", encoding="utf-8") as f:
        f.write(build_contact_page())

    with open(os.path.join(ROOT, "competitions.html"), "w", encoding="utf-8") as f:
        f.write(build_competitions_hub(riders))
    for competition in COMPETITIONS:
        with open(os.path.join(COMPETITIONS_DIR, f"{competition['id']}.html"), "w", encoding="utf-8") as f:
            f.write(build_competition_detail(riders, competition))
        standings_dir = os.path.join(COMPETITIONS_DIR, competition["id"])
        os.makedirs(standings_dir, exist_ok=True)
        with open(os.path.join(standings_dir, "standings.html"), "w", encoding="utf-8") as f:
            f.write(build_competition_standings(riders, competition))
        events = competition_events(riders, competition["name"])
        rounds_dir = os.path.join(standings_dir, "rounds")
        os.makedirs(rounds_dir, exist_ok=True)
        for round_number, event in enumerate(events, 1):
            round_file = os.path.join(rounds_dir, f"{competition_round_slug(event)}.html")
            with open(round_file, "w", encoding="utf-8") as f:
                f.write(build_competition_round(riders, competition, event, round_number, events))
    for organization in ORGANIZATIONS:
        organization_dir = os.path.join(COMPETITIONS_DIR, organization["id"])
        os.makedirs(organization_dir, exist_ok=True)
        with open(os.path.join(organization_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(build_organization_page(organization))
        for competition in organization.get("competitions", []):
            if not visible_status(competition):
                continue
            if competition.get("existing_path"):
                continue
            competition_dir = os.path.join(organization_dir, competition["id"])
            os.makedirs(competition_dir, exist_ok=True)
            with open(os.path.join(competition_dir, "index.html"), "w", encoding="utf-8") as f:
                f.write(build_organization_competition_page(organization, competition))

    equipment_data = collect_equipment(riders)
    for category, products in equipment_data.items():
        filename = f"{equip_image_slug(category, '', '')}.html"
        with open(os.path.join(EQUIPMENT_DIR, filename), "w", encoding="utf-8") as f:
            f.write(build_equipment_category_page(category, products))

    for filename, content in build_trust_pages().items():
        with open(os.path.join(ROOT, filename), "w", encoding="utf-8") as f:
            f.write(content)

    for r in riders:
        page = build_rider_page(r, riders)
        with open(os.path.join(RIDERS_DIR, f"{r['slug']}.html"), "w", encoding="utf-8") as f:
            f.write(page)

    seo_builder = os.path.join(ROOT, "build_seo_guides.py")
    if os.path.exists(seo_builder):
        subprocess.run([sys.executable, seo_builder], check=True)

    ensure_accessibility_landmarks()
    run_image_optimizer()

    print(f"Built core pages + {len(riders)} rider pages + {len(equipment_data)} equipment category pages ({len(women)} women, {len(men)} men).")
    print("newsletter:  Brevo single-opt-in form embedded.")

if __name__ == "__main__":
    main()
