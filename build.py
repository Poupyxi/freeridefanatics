#!/usr/bin/env python3
"""
FreerideFanatics static site generator.

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
import re
import sys
import time
import unicodedata

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(ROOT, "data", "riders.json")
RIDERS_DIR = os.path.join(ROOT, "riders")
IMG_DIR = os.path.join(ROOT, "assets", "img", "riders")
ACTION_IMG_DIR = os.path.join(ROOT, "assets", "img", "riders-action")
EQUIP_IMG_DIR = os.path.join(ROOT, "assets", "img", "equipment")
REVEAL_IMG_DIR = os.path.join(EQUIP_IMG_DIR, "reveal")

SITE_NAME = "FreerideFanatics"
BUILD_VERSION = str(int(time.time()))  # cache-busting query string, changes every build

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

# Position -> points, keyed by competition. The source sheet only records points,
# but the scale is a strict ladder, so the finishing position is recoverable
# without any extra data entry. Add an entry here when a new series is tracked;
# a competition with no scale simply shows no position.
POINTS_SCALES = {
    "UCI MTB World Cup DH 2026": [
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
    ("Handlebar", "burgtec", "ride wide alloy dh"): ("Burgtec", "Ride Wide DH"),
    ("Handlebar", "burgtec", "ride wide alloy downhill riser bar"): ("Burgtec", "Ride Wide DH"),
    ("Handlebar", "burgtec", "ride wide carbondh riser bar"): ("Burgtec", "Ride Wide DH Carbon"),
    ("Wheels", "dt swiss", "fr1500"): ("DT Swiss", "FR 1500"),
    ("Wheels", "dt swiss", "fr 1500"): ("DT Swiss", "FR 1500"),
    ("Wheels", "crankbrothers", "synthesis carbon dh"): ("Crankbrothers", "Synthesis DH Carbon"),
    ("Wheels", "crankbrothers", "synthesis dh carbon"): ("Crankbrothers", "Synthesis DH Carbon"),
    ("Tires", "maxxis", "assegai f dhr2 r"): ("Maxxis", "Assegai (F) + DHR II (R)"),
    ("Tires", "maxxis", "assegai f dhr ii r"): ("Maxxis", "Assegai (F) + DHR II (R)"),
    ("Crankset", "sram", "xo dh"): ("SRAM", "X0 DH"),
    ("Derailleur", "sram", "xo dh"): ("SRAM", "X0 DH"),
    ("Handlebar", "renthal", "fatbar 35mm"): ("Renthal", "Fatbar 35"),
    ("Handlebar", "renthal", "fatbar 35"): ("Renthal", "Fatbar 35"),
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

# ---------------------------------------------------------------- shared partials

def head(title, description, asset_prefix, body_class=""):
    body_attr = f' class="{esc(body_class)}"' if body_class else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Archivo+Black&family=Space+Mono:wght@400;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{asset_prefix}assets/css/style.css?v={BUILD_VERSION}">
</head>
<body{body_attr}>
"""

def header_html(asset_prefix, active=""):
    def cls(name):
        return " class=\"active\"" if active == name else ""
    return f"""<div class="announce">UCI MTB World Cup DH 2026 &nbsp;·&nbsp; <span>64 riders</span> tracked, every setup, every event</div>

<header>
  <div class="wrap nav-row">
    <a class="logo" href="{asset_prefix}index.html">
      <span class="mark">F</span>
      FREERIDEFANATICS
    </a>
    <nav class="links">
      <div class="nav-item has-dropdown">
        <a href="{asset_prefix}riders.html#grid"{cls('riders')}>Riders <span class="caret">&#9662;</span></a>
        <div class="dropdown">
          <div class="dropdown-inner">
            <a href="{asset_prefix}riders.html?filter=Men+Elite#grid">Men</a>
            <a href="{asset_prefix}riders.html?filter=Women+Elite#grid">Women</a>
          </div>
        </div>
      </div>
      <a href="{asset_prefix}standings.html"{cls('standings')}>Standings</a>
      <a href="{asset_prefix}index.html#faq">FAQ</a>
    </nav>
    <div class="nav-icons">
      <span class="icon-btn">64 Riders</span>
      <button class="nav-toggle" aria-label="Toggle menu"><span></span><span></span><span></span></button>
    </div>
  </div>
</header>
"""

def footer_html(asset_prefix):
    return f"""<footer>
  <div class="wrap footer-row">
    <a class="footer-logo" href="{asset_prefix}index.html"><span class="mark">F</span>FREERIDEFANATICS</a>
    <nav class="footer-links">
      <a href="{asset_prefix}riders.html#grid">Riders</a>
      <a href="{asset_prefix}index.html#faq">FAQ</a>
      <a href="#">About</a>
      <a href="#">Contact</a>
    </nav>
    <span class="footer-copy">&copy; 2026 FreerideFanatics</span>
  </div>
</footer>

<script src="{asset_prefix}assets/js/site.js?v={BUILD_VERSION}"></script>
</body>
</html>
"""

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

# ---------------------------------------------------------------- index page

def rider_card(r):
    photo = has_photo(r["slug"])
    if photo:
        photo_html = (f'<img src="assets/img/riders/{photo}?v={BUILD_VERSION}" '
                      f'alt="{esc(r["display_name"])}" loading="lazy">')
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
    html = head(
        f"{SITE_NAME} — Pro DH Kit, Every Setup",
        "Every UCI MTB World Cup Downhill rider's exact bike setup, gear and results — shop what they ride.",
        prefix,
        body_class="home-page"
    )
    html += header_html(prefix, active="riders")
    html += f"""
<section class="hero home-hero">
  {hero_waves_svg()}
  <div class="wrap hero-inner">
    <div class="label">UCI MTB World Cup · Downhill · Season 2026</div>
    <h1>Their <em>exact</em> setup. Your next upgrade.</h1>
    <p class="sub">Track {len(riders)} World Cup DH riders, explore their exact race setups and find the equipment they trust.</p>
    <div class="hero-ctas">
      <a href="riders.html#grid" class="btn btn-solid">Explore riders</a>
      {random_rider_button(riders, solid=False)}
      <a href="#faq" class="home-text-link">Read the FAQ <span aria-hidden="true">↓</span></a>
    </div>
    <div class="ticker-wrap">
      <div class="ticker-track">
        <a href="riders.html#grid"><b>Rider</b> Profiles</a><span class="dot">·</span><a href="#equipment"><b>Pro</b> Setups</a><span class="dot">·</span><a href="standings.html"><b>Follow</b> the Season</a><span class="dot">·</span><a href="standings.html"><b>Race</b> Results</a><span class="dot">·</span><a href="#rankings"><b>Check</b> Rankings</a><span class="dot">·</span><a href="#equipment"><b>Equipment</b> Details</a><span class="dot">·</span><a href="#equipment"><b>Shop</b> the Gear</a><span class="dot">·</span>
        <a href="riders.html#grid" aria-hidden="true" tabindex="-1"><b>Rider</b> Profiles</a><span class="dot" aria-hidden="true">·</span><a href="#equipment" aria-hidden="true" tabindex="-1"><b>Pro</b> Setups</a><span class="dot" aria-hidden="true">·</span><a href="standings.html" aria-hidden="true" tabindex="-1"><b>Follow</b> the Season</a><span class="dot" aria-hidden="true">·</span><a href="standings.html" aria-hidden="true" tabindex="-1"><b>Race</b> Results</a><span class="dot" aria-hidden="true">·</span><a href="#rankings" aria-hidden="true" tabindex="-1"><b>Check</b> Rankings</a><span class="dot" aria-hidden="true">·</span><a href="#equipment" aria-hidden="true" tabindex="-1"><b>Equipment</b> Details</a><span class="dot" aria-hidden="true">·</span><a href="#equipment" aria-hidden="true" tabindex="-1"><b>Shop</b> the Gear</a><span class="dot" aria-hidden="true">·</span>
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
        <div class="faq-q"><h3><span class="faq-num">Q1</span>Where does this data come from?</h3><span class="plus">+</span></div>
        <div class="faq-a"><p>Every setup is tracked from official UCI MTB World Cup entry lists, team press releases and public sponsor listings, updated across the 2026 season.</p></div>
      </div>
      <div class="faq-item">
        <div class="faq-q"><h3><span class="faq-num">Q2</span>Are the "Shop" links affiliate links?</h3><span class="plus">+</span></div>
        <div class="faq-a"><p>Yes — some product links on this site are affiliate links. We may earn a commission on qualifying purchases at no extra cost to you.</p></div>
      </div>
      <div class="faq-item">
        <div class="faq-q"><h3><span class="faq-num">Q3</span>How often is the kit list updated?</h3><span class="plus">+</span></div>
        <div class="faq-a"><p>Setups change race to race — we update frames, suspension tunes and component swaps as riders confirm them through the season.</p></div>
      </div>
      <div class="faq-item">
        <div class="faq-q"><h3><span class="faq-num">Q4</span>Can I suggest a correction?</h3><span class="plus">+</span></div>
        <div class="faq-a"><p>Absolutely — reach out via the Contact link and we'll verify and update the rider's page.</p></div>
      </div>
    </div>
  </div>
</section>
"""
    html += f"""
<section class="cta-dark">
  {cta_waves_svg()}
  <div class="wrap cta-inner">
    <div class="label">Stay up to speed</div>
    <h2>New kit drops every race weekend.</h2>
    <p class="sub">Get the setup sheet the morning after every World Cup round — straight to your inbox.</p>
    <!-- Newsletter form kept ready for future activation.
    <form class="cta-form" onsubmit="return false;">
      <input type="email" placeholder="you@example.com">
      <button type="submit">Subscribe</button>
    </form>
    <div class="fineprint">No spam · Unsubscribe anytime</div>
    -->
  </div>
</section>
"""
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

    def rider_rows(group, comp, events):
        entries = []
        for r in riders:
            if r.get("gender_category") != group:
                continue
            pts = points_map(r, comp)
            total = sum(v for v in pts.values() if v)
            if not total:
                continue
            entries.append((total, r, pts))
        entries.sort(key=lambda e: (-e[0], e[1]["display_name"]))

        rows = []
        for i, (total, r, pts) in enumerate(entries, start=1):
            cells = []
            for ev in events:
                p = pts.get(ev)
                place = placing_from_points(comp, p)
                title = f' title="{esc(ordinal(place))}"' if place else ""
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
            f'<th class="rd" title="{esc(ev)}"><abbr title="{esc(ev)}">{esc(short_event(ev))}</abbr></th>'
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
            <thead><tr><th>#</th><th>Rider</th><th>Nat</th>{head_cells}<th class="total">Pts</th></tr></thead>
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
            <thead><tr><th>#</th><th>Team</th><th class="total">Pts</th></tr></thead>
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
        ranked = [(sum(v or 0 for v in points_map(r, primary_comp).values()), r)
                  for r in riders if r.get("gender_category") == group]
        ranked = [entry for entry in ranked if entry[0]]
        return max(ranked, default=(0, {"display_name": "—"}), key=lambda entry: entry[0])
    men_lead_pts, men_lead = leader_for("Men Elite")
    women_lead_pts, women_lead = leader_for("Women Elite")
    latest_round = primary_events[-1] if primary_events else "Season start"

    html = head(f"Standings — {SITE_NAME}",
                "Full UCI MTB World Cup Downhill 2026 standings: every rider, every round, cumulative points.",
                prefix, body_class="standings-page")
    html += header_html(prefix, active="standings")
    html += f"""
<section class="hero standings-hero">
  <div class="wrap hero-inner">
    <div class="label">Season 2026 · Updated after round {len(primary_events)} · {esc(latest_round)}</div>
    <h1>Standings.</h1>
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
"""
    html += footer_html(prefix)
    return html

def short_event(ev):
    """'South Korea (May)' -> 'KOR MAY'.

    The month is part of the label on purpose: a season can visit the same
    country twice (France in May and again in August), and the place alone
    would give two identical column headers."""
    m = re.match(r"^(.*?)\s*\(([^)]*)\)\s*$", ev)
    place, month = (m.group(1), m.group(2)) if m else (ev, "")
    event_codes = {
        "South Korea": "KOR", "France": "FRA", "Austria": "AUT",
        "Switzerland": "SUI", "Italy": "ITA", "Andorra": "AND",
    }
    key = place.strip().split()[-1] if place.strip() else ev
    label = event_codes.get(place.strip(), key[:3].upper())
    return f"{label} {month[:3].upper()}".strip()

def build_riders_directory(riders, women_count, men_count):
    prefix = ""
    cards = "\n      ".join(rider_card(r) for r in riders)
    html = head(
        f"All Riders — {SITE_NAME}",
        "Browse every UCI MTB World Cup Downhill rider's bike setup, team and season results.",
        prefix
    )
    html += header_html(prefix, active="riders")
    html += f"""
<section class="hero" style="padding-bottom:0; border-bottom:none;">
  <div class="wrap hero-inner">
    <div class="label">Directory · Season 2026</div>
    <h1>All <em>{len(riders)}</em> riders.</h1>
    <p class="sub">Every UCI MTB World Cup DH athlete on the circuit this season — filter by category or search a name, team or country.</p>
  </div>
</section>

<section class="section" id="grid" style="padding-top:32px;">
  <div class="wrap">
    <div class="section-head reveal">
      <div>
        <div class="label">Directory</div>
        <h2>All Riders</h2>
      </div>
      <span class="see-all">{len(riders)} riders · {women_count} women · {men_count} men</span>
    </div>
    <div class="filters">
      <button class="filter-btn active" data-filter="all">All ({len(riders)})</button>
      <button class="filter-btn" data-filter="Men Elite">Men ({men_count})</button>
      <button class="filter-btn" data-filter="Women Elite">Women ({women_count})</button>
      <input class="search-input" type="text" placeholder="Search a rider, team, country..." data-search>
    </div>
    <div class="grid-riders" data-rider-grid>
      {cards}
    </div>
  </div>
</section>
"""
    html += footer_html(prefix)
    return html

# ---------------------------------------------------------------- rider page

def equip_item_html(item):
    cat = prettify_category(item.get("category"))
    brand = item.get("brand") or ""
    detail_parts = [p.strip() for p in (item.get("model_detail") or "").split(";") if p.strip()]
    main_model = detail_parts[0] if detail_parts else ""
    extra = " · ".join(detail_parts[1:]) if len(detail_parts) > 1 else ""
    title = " ".join([brand, main_model]).strip() or "—"
    link = item.get("affiliate_link") or "#"
    photo = has_equip_photo(item.get("category"), brand, main_model)
    photo_html = f'<span class="equip-thumb"><img src="../assets/img/equipment/{photo}" alt="{esc(title)}" loading="lazy"></span>' if photo else ""
    return f"""<div class="equip-item reveal">
        {photo_html}
        <div>
          <span class="cat">{esc(cat)}</span>
          <h4>{esc(title)}</h4>
          {f'<div class="detail">{esc(extra)}</div>' if extra else ''}
        </div>
        <a class="shop-btn" href="{esc(link)}" target="_blank" rel="noopener sponsored">Details</a>
      </div>"""

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
          <a href="{esc(data['link'])}" target="_blank" rel="noopener sponsored">{inner}</a>
        </figure>"""
        return f'<figure class="bb-part bb-{slot}">{inner}</figure>'

    parts_html = "\n        ".join(filter(None, [
        part("shock", shock, "Rear shock"),
        part("frame", frame, "Frame"),
        part("fork", fork, "Fork"),
    ]))
    return f"""<div class="bike-build reveal">
      <div class="bb-label">Race Setup</div>
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

def build_rankings_section(riders):
    men = sorted([r for r in riders if r.get("gender_category") == "Men Elite"],
                 key=rider_total_points, reverse=True)[:5]
    women = sorted([r for r in riders if r.get("gender_category") == "Women Elite"],
                    key=rider_total_points, reverse=True)[:5]

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
        <div class="label">UCI DH Season 2026 · Cumulative points</div>
        <h2>DH Rankings</h2>
      </div>
      <a class="see-all" href="standings.html">View full standings →</a>
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
            if not brand and not main_model:
                continue
            key = (brand, main_model)
            g = by_cat.setdefault(cat, {}).setdefault(key, {
                "brand": brand, "model": main_model,
                "points": 0, "rider_count": 0, "link": None,
            })
            g["points"] += pts
            g["rider_count"] += 1
            if not g["link"] and item.get("affiliate_link"):
                g["link"] = item["affiliate_link"]

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
        top3 = sorted(by_cat[cat].values(), key=lambda g: g["points"], reverse=True)[:3]
        max_pts = top3[0]["points"] or 1

        rows = []
        for rank, g in enumerate(top3, start=1):
            title = " ".join([g["brand"], g["model"]]).strip() or "—"
            link = g["link"]
            width = max(6, round(g["points"] / max_pts * 100))
            photo = has_equip_photo(cat, g["brand"], g["model"])
            thumb = f'<span class="p-thumb"><img src="assets/img/equipment/{photo}" alt="{esc(title)}" loading="lazy"></span>' if photo else ""
            thumb_line = f'\n              {thumb}' if thumb else ""
            shop = (f'<a class="p-shop" href="{esc(link)}" target="_blank" '
                    f'rel="noopener sponsored">Shop</a>' if link
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
            <h3>{esc(cat_label)}</h3>
            <span class="cat-sub">Top 3 · combined UCI points</span>
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
      <span class="see-all">{total} categories · Ranked by combined rider points</span>
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
        place = placing_from_points(comp, points)
        result = h.get("result") or ordinal(place) or "—"
        podium = f" podium p{place}" if place and place <= 3 else ""
        rows.append(f"""<tr data-competition="{esc(comp)}">
          <td>{esc(h.get('year'))}</td>
          <td>{esc(h.get('event'))}</td>
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

def build_rider_page(r):
    prefix = "../"
    # The rider page hero prefers the portrait action shot; the square avatar
    # (used on the grid cards) is the fallback, then the initials placeholder.
    action = has_action_photo(r["slug"])
    photo = has_photo(r["slug"])
    if action:
        photo_html = f'<img src="../assets/img/riders-action/{action}" alt="{esc(r["display_name"])}">'
    elif photo:
        photo_html = f'<img src="../assets/img/riders/{photo}" alt="{esc(r["display_name"])}">'
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
    # The label lives inside the banner; without a banner it still needs a home
    setup_head = "" if build_html else """<div class="section-head reveal" style="border-bottom:none; padding-bottom:8px; margin-bottom:0;">
      <div>
        <div class="label">Race Setup</div>
      </div>
    </div>
    """
    banner = bike_build_parts(equipment) or {}
    shown_in_banner = [p["item"] for p in banner.values() if p]
    if equipment:
        equip_html = equipment_groups_html(equipment, hide_items=shown_in_banner)
    else:
        equip_html = '<p style="color:var(--muted); font-size:14px;">No public equipment spec on file yet for this rider.</p>'

    history = r.get("competition_history") or []
    if history:
        results_html = f"""{competition_filters(history)}
      <table class="results-table" data-results-table>
        <thead><tr><th>Year</th><th>Event</th><th>Result</th><th>Points</th></tr></thead>
        <tbody>
        {results_rows(history)}
        </tbody>
      </table>"""
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

    html = head(
        f"{r['display_name']} — Bike Setup & Kit | {SITE_NAME}",
        f"{r['display_name']}'s full {r.get('team') or 'World Cup'} DH bike setup, sponsors and 2026 season results.",
        prefix
    )
    html += header_html(prefix, active="riders")
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

    <div class="section-head reveal" style="border-bottom:none; margin:48px 0 24px;">
      <div>
        <div class="label">Season 2026</div>
        <h2>Results</h2>
      </div>
    </div>
    {results_html}
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

def main():
    with open(DATA_PATH, encoding="utf-8") as f:
        riders = json.load(f)

    os.makedirs(RIDERS_DIR, exist_ok=True)
    os.makedirs(IMG_DIR, exist_ok=True)
    os.makedirs(EQUIP_IMG_DIR, exist_ok=True)

    if "--missing-images" in sys.argv:
        list_missing_images(riders)
        return

    women = [r for r in riders if r.get("gender_category") == "Women Elite"]
    men = [r for r in riders if r.get("gender_category") == "Men Elite"]

    if "--standings-only" in sys.argv:
        with open(os.path.join(ROOT, "standings.html"), "w", encoding="utf-8") as f:
            f.write(build_standings(riders))
        print("Built standings.html.")
        return

    index_html = build_index(riders, len(women), len(men))
    with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)

    if "--index-only" in sys.argv:
        print("Built index.html.")
        return

    riders_html = build_riders_directory(riders, len(women), len(men))
    with open(os.path.join(ROOT, "riders.html"), "w", encoding="utf-8") as f:
        f.write(riders_html)

    with open(os.path.join(ROOT, "standings.html"), "w", encoding="utf-8") as f:
        f.write(build_standings(riders))

    for r in riders:
        page = build_rider_page(r)
        with open(os.path.join(RIDERS_DIR, f"{r['slug']}.html"), "w", encoding="utf-8") as f:
            f.write(page)

    print(f"Built index.html + riders.html + {len(riders)} rider pages ({len(women)} women, {len(men)} men).")

if __name__ == "__main__":
    main()
