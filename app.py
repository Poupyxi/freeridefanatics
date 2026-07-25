#!/usr/bin/env python3
"""
Freeride Fanatics — Web App
============================
Lance : python3 app.py
Ouvre  : http://localhost:5000  (ou http://ton-vps-ip:5000)

Dépendances : pip install flask
"""

import io
import sys
import importlib
import os
from pathlib import Path
from flask import Flask, jsonify, request, send_file, send_from_directory, Response, session, redirect as flask_redirect

# ── Import du moteur de génération ───────────────────────────────────────────
BASE_DIR = Path(__file__).parent
ASSETS_DIR = BASE_DIR / "assets"
APP_VERSION = "V0.8"
sys.path.insert(0, str(BASE_DIR))
import generate_cards as gc

app = Flask(__name__)

# ── Secrets locaux ────────────────────────────────────────────────────────────
# Les clés sensibles restent dans config.py (fichier ignoré par Git).
try:
    import config as _local_config
except Exception:
    _local_config = None

def _secret_config(name, default=""):
    value = getattr(_local_config, name, None) if _local_config else None
    return str(value if value not in (None, "") else os.environ.get(name, default)).strip()

META_APP_ID = _secret_config("META_APP_ID")
META_APP_SECRET = _secret_config("META_APP_SECRET")
META_ACCESS_TOKEN = _secret_config("META_ACCESS_TOKEN")
INSTAGRAM_BUSINESS_ACCOUNT_ID = _secret_config("INSTAGRAM_BUSINESS_ACCOUNT_ID")

# ── OAuth / Session ───────────────────────────────────────────────────────────
import secrets as _secrets, json as _json
_OAUTH_DIR = Path.home() / '.config' / 'freeridefanatics'
_OAUTH_DIR.mkdir(parents=True, exist_ok=True)

_SK_FILE = _OAUTH_DIR / 'flask_secret.key'
if _SK_FILE.exists():
    app.secret_key = _SK_FILE.read_bytes()
else:
    _sk = _secrets.token_bytes(32)
    _SK_FILE.write_bytes(_sk)
    app.secret_key = _sk

_GOOGLE_SECRET_FILE = _OAUTH_DIR / 'google_client_secret.json'
_GOOGLE_TOKEN_FILE  = _OAUTH_DIR / 'google_token.json'
_GOOGLE_SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/spreadsheets',
]

_DEFAULT_GSHEET_ID = getattr(gc, "GSHEET_ID", "")
_SETTINGS_FILE = _OAUTH_DIR / 'app_settings.json'

def _load_app_settings():
    try:
        return _json.loads(_SETTINGS_FILE.read_text()) if _SETTINGS_FILE.exists() else {}
    except Exception:
        return {}

def _save_app_settings(data):
    _SETTINGS_FILE.write_text(_json.dumps(data or {}, indent=2))

def _extract_gsheet_id(value):
    import re
    text = str(value or "").strip()
    if not text:
        return ""
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", text)
    if match:
        return match.group(1)
    if re.fullmatch(r"[a-zA-Z0-9_-]{20,}", text):
        return text
    return ""

def _active_gsheet_id():
    settings = _load_app_settings()
    return settings.get("gsheet_id") or _DEFAULT_GSHEET_ID

def _active_gsheet_url():
    gsheet_id = _active_gsheet_id()
    return f"https://docs.google.com/spreadsheets/d/{gsheet_id}/edit" if gsheet_id else ""

def _apply_gsheet_settings():
    gc.GSHEET_ID = _active_gsheet_id()

_apply_gsheet_settings()

def _fetch_gsheet_rows_for_id(gsheet_id, sheet_name=None, gid=None):
    import csv as _csv
    import io as _io
    import urllib.parse as _urlparse
    import urllib.request as _urlrequest
    if gid is not None:
      url = f"https://docs.google.com/spreadsheets/d/{gsheet_id}/gviz/tq?tqx=out:csv&gid={gid}"
    else:
      encoded = _urlparse.quote(str(sheet_name or ""))
      url = f"https://docs.google.com/spreadsheets/d/{gsheet_id}/gviz/tq?tqx=out:csv&sheet={encoded}"
    try:
        req = _urlrequest.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with _urlrequest.urlopen(req, timeout=10, context=getattr(gc, "_ssl_ctx", None)) as r:
            content = r.read().decode("utf-8")
        rows = list(_csv.reader(_io.StringIO(content)))
        if rows and rows[0]:
            return rows
    except Exception:
        return None
    return None

def _sheet_header_index(rows):
    if not rows:
        return 0
    header_markers = {
        "firstname", "lastname", "instagram", "frame", "fork", "tires", "tyres",
        "brand", "instagramhandle", "tagtype", "defaulthashtag", "team",
    }
    scored = []
    for i, row in enumerate(rows[:8]):
        values = [str(c or "").strip() for c in row]
        filled = sum(1 for c in values if c)
        if filled:
            keys = {_sheet_header_key(c) for c in values if c}
            marker_hits = len(keys & header_markers)
            scored.append((marker_hits * 50 + filled, -i, i))
    if not scored:
        return 0
    scored.sort(reverse=True)
    return scored[0][2]

def _sheet_non_empty_rows(rows):
    if not rows:
        return 0
    header_idx = _sheet_header_index(rows)
    count = 0
    for row in rows[header_idx + 1:]:
        if any(str(c or "").strip() for c in row):
            count += 1
    return count

def _sheet_header_values(rows):
    if not rows:
        return []
    row = rows[_sheet_header_index(rows)] if rows else []
    return [str(c or "").strip().lower() for c in row]

def _sheet_header_key(value):
    import re as _re
    import unicodedata as _unicodedata
    text = _unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not _unicodedata.combining(ch))
    return _re.sub(r"[^a-z0-9]+", "", text.lower())

def _test_sheet_candidate(gsheet_id, candidates, required_headers=()):
    for candidate in candidates:
        rows = _fetch_gsheet_rows_for_id(
            gsheet_id,
            sheet_name=candidate.get("name"),
            gid=candidate.get("gid"),
        )
        if not rows:
            continue
        headers = _sheet_header_values(rows)
        header_keys = {_sheet_header_key(h) for h in headers if h}
        missing_headers = []
        for group in required_headers:
            if isinstance(group, (list, tuple, set)):
                label = str(next(iter(group), "")).strip()
                aliases = group
            else:
                label = str(group).strip()
                aliases = (group,)
            alias_keys = {_sheet_header_key(alias) for alias in aliases if str(alias or "").strip()}
            if alias_keys and not (header_keys & alias_keys):
                missing_headers.append(label)
        if missing_headers:
            return {
                "ok": False,
                "row_count": _sheet_non_empty_rows(rows),
                "matched": candidate.get("label") or candidate.get("name") or f"gid {candidate.get('gid')}",
                "detail": "Colonnes manquantes : " + ", ".join(missing_headers),
            }
        return {
            "ok": True,
            "row_count": _sheet_non_empty_rows(rows),
            "matched": candidate.get("label") or candidate.get("name") or f"gid {candidate.get('gid')}",
            "detail": "Onglet détecté.",
        }
    return {"ok": False, "row_count": 0, "matched": "", "detail": "Onglet introuvable ou inaccessible."}

# Cache global (rechargé au premier appel)
_cache = {}

def get_engine():
    if "ready" not in _cache:
        bg = gc.Image.open(gc.BACKGROUND).convert("RGB").resize((gc.W, gc.H), gc.Image.LANCZOS) if gc.BACKGROUND else gc.make_fallback_bg()
        _cache["bg"]       = bg
        _cache["fonts"]    = gc.load_fonts()
        profiles = None
        if gc.GSHEET_ID:
            profiles = gc.load_profiles_from_gsheet()
        _cache["profiles"] = profiles or gc.load_profiles()
        _cache["ready"]    = True
    return _cache["bg"], _cache["fonts"], _cache["profiles"]

def reload_engine():
    _apply_gsheet_settings()
    _cache.clear()
    get_engine()

def get_equipment():
    if "equipment" not in _cache:
        _cache["equipment"] = gc.load_equipment_from_gsheet() or {}
    return _cache["equipment"]

def _norm_match_name(value):
    import re
    import unicodedata
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", value.lower())

def get_results_2026():
    if "results_2026" in _cache:
        return _cache["results_2026"]

    rows = gc._fetch_gsheet_csv_by_gid(581226329) or gc._fetch_gsheet_csv("📊 Résultats 2026") or []
    if not rows:
        _cache["results_2026"] = {"events": [], "riders": []}
        return _cache["results_2026"]

    _, _, profiles = get_engine()
    by_name = {}
    for p in profiles:
        key = _norm_match_name(f"{p.get('prenom', '')}{p.get('nom', '')}")
        if key:
            by_name[key] = p

    header = rows[0] if rows else []
    events = []
    for idx, name in enumerate(header[5:], start=5):
        clean = " ".join(str(name or "").split())
        if clean:
            events.append({"index": idx, "name": clean})

    parsed = []
    for row in rows[1:]:
        row = list(row) + [""] * max(0, len(header) - len(row))
        genre = (row[0] or "").strip().upper()
        if genre in ("W", "F", "WOMEN", "FEMME"):
            genre = "F"
        elif genre in ("M", "MEN", "HOMME"):
            genre = "M"
        else:
            continue

        first = (row[1] or "").strip()
        last = (row[2] or "").strip()
        if not first or not last:
            continue

        event_points = []
        total = 0.0
        for ev in events:
            raw = str(row[ev["index"]] if ev["index"] < len(row) else "").strip().replace(",", ".")
            if not raw:
                continue
            try:
                pts = float(raw)
            except ValueError:
                continue
            if pts <= 0:
                continue
            total += pts
            event_points.append({"event": ev["name"], "points": pts})

        profile = by_name.get(_norm_match_name(first + last))
        parsed.append({
            "genre": genre,
            "first_name": first,
            "last_name": last,
            "name": f"{first} {last}".strip(),
            "nationality": (row[3] or "").strip(),
            "flag": (row[4] or "").strip(),
            "instagram": (profile.get("instagram", "") if profile else "").lstrip("@").lower(),
            "total_points": int(total) if total.is_integer() else total,
            "event_count": len(event_points),
            "events": event_points,
        })

    for genre in ("F", "M"):
        ranked = sorted([r for r in parsed if r["genre"] == genre], key=lambda r: (-float(r["total_points"]), r["name"].lower()))
        for i, rider in enumerate(ranked, start=1):
            rider["rank"] = i

    parsed.sort(key=lambda r: (r["genre"], int(r.get("rank") or 999), r["name"].lower()))
    _cache["results_2026"] = {"events": [e["name"] for e in events], "riders": parsed}
    return _cache["results_2026"]

def _sheet_rows_as_dicts(rows):
    if not rows:
        return []
    header_idx = 0
    for i, row in enumerate(rows[:6]):
        lowered = [str(c or "").strip().lower() for c in row]
        if any(c in lowered for c in ("brand", "name", "tag_type", "instagram_handle")):
            header_idx = i
            break
    headers = [str(c or "").strip() for c in rows[header_idx]]
    out = []
    for row in rows[header_idx + 1:]:
        row = list(row) + [""] * max(0, len(headers) - len(row))
        item = {headers[i]: str(row[i] or "").strip() for i in range(len(headers)) if headers[i]}
        if any(item.values()):
            out.append(item)
    return out

def _clean_social_handle(value):
    value = str(value or "").strip()
    if not value:
        return ""
    value = value.replace("https://www.instagram.com/", "").replace("https://instagram.com/", "")
    value = value.replace("http://www.instagram.com/", "").replace("http://instagram.com/", "")
    value = value.lstrip("@").split("?")[0].split("#")[0].strip("/")
    return f"@{value}" if value else ""

def get_brand_tags():
    if "brand_tags" in _cache:
        return _cache["brand_tags"]

    rows = gc._fetch_gsheet_csv_by_gid(1345104699) or gc._fetch_gsheet_csv("Brand") or []
    brands = []
    for row in _sheet_rows_as_dicts(rows):
        name = row.get("brand") or row.get("Brand") or row.get("name") or row.get("Name") or ""
        handle = row.get("instagram_handle") or row.get("Instagram") or row.get("handle") or ""
        status = row.get("status") or row.get("Status") or ""
        if not name:
            continue
        brands.append({
            "brand": name.strip(),
            "instagram_handle": _clean_social_handle(handle),
            "website": row.get("website") or row.get("Website") or "",
            "status": status,
            "notes": row.get("notes") or row.get("Notes") or "",
        })
    _cache["brand_tags"] = brands
    return brands

def get_context_tags():
    if "context_tags" in _cache:
        return _cache["context_tags"]

    rows = gc._fetch_gsheet_csv_by_gid(755371970) or gc._fetch_gsheet_csv("Tags") or []
    tags = []
    for row in _sheet_rows_as_dicts(rows):
        name = row.get("name") or row.get("Name") or ""
        handle = row.get("instagram_handle") or row.get("Instagram") or ""
        hashtag = row.get("default_hashtag") or row.get("hashtag") or ""
        if not name and not handle and not hashtag:
            continue
        tags.append({
            "tag_type": row.get("tag_type") or row.get("type") or "",
            "name": name,
            "instagram_handle": _clean_social_handle(handle),
            "default_hashtag": hashtag.strip(),
            "context": row.get("context") or "",
            "status": row.get("status") or "",
            "notes": row.get("notes") or "",
        })
    _cache["context_tags"] = tags
    return tags

# ── HTML ──────────────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Freeride Fanatics V0.8 — Card Generator</title>
<link rel="icon" type="image/x-icon" href="/favicon.ico?v=20260721-2">
<link rel="apple-touch-icon" href="/assets/brand/freeride-fanatics-summer.jpg?v=20260721">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html { min-width: 320px; overflow-x: hidden; }
  body { font-family: 'Segoe UI', sans-serif; background: #1a1a1a; color: #eee; min-height: 100vh; overflow-x: hidden; }
  img, video, canvas { max-width: 100%; }
  button, input, select, textarea { min-width: 0; }

  header {
    background: #111;
    border-bottom: 3px solid #C8D400;
    padding: 12px 24px;
    display: flex;
    align-items: center;
    gap: 16px;
  }
  header h1 { font-size: 1.3rem; color: #C8D400; letter-spacing: 2px; text-transform: uppercase; flex-shrink: 0; }
  header span { color: #888; font-size: 0.85rem; }
  .brand-mark {
    width: 34px;
    height: 34px;
    border-radius: 8px;
    object-fit: cover;
    border: 1px solid rgba(200,212,0,.45);
    box-shadow: 0 0 0 1px rgba(0,0,0,.7);
    flex-shrink: 0;
  }
  .brand-title {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: max-content;
  }
  .brand-title span {
    color: #C8D400;
    font-size: inherit;
  }
  .brand-title .version-badge {
    color: #111;
    background: #C8D400;
    border-radius: 999px;
    padding: 2px 8px;
    font-size: 0.68rem;
    font-weight: 900;
    letter-spacing: .06em;
    line-height: 1.25;
  }
  .loading-brand-mark {
    width: 72px;
    height: 72px;
    border-radius: 16px;
    object-fit: cover;
    border: 1px solid rgba(200,212,0,.55);
    box-shadow: 0 12px 34px rgba(0,0,0,.45);
  }

  /* ── Tab nav ── */
  .tab-nav {
    display: flex;
    gap: 3px;
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    padding: 3px;
    border-radius: 8px;
    margin-left: 8px;
    flex: 1 1 auto;
    min-width: 0;
    max-width: 100%;
    overflow-x: auto;
    scrollbar-width: none;
  }
  .tab-nav::-webkit-scrollbar { display: none; }
  .tab-btn {
    padding: 6px 18px;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: #555;
    font-size: 0.82rem;
    font-weight: 700;
    cursor: pointer;
    letter-spacing: 0.5px;
    transition: all .15s;
    white-space: nowrap;
  }
  .tab-btn:hover { color: #aaa; }
  .tab-btn.active { background: #252800; color: #C8D400; }

  /* ── Header right zone ── */
  .header-right {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-left: auto;
    flex-shrink: 0;
    min-width: 0;
  }

  /* ── Dashboard dropdown ── */
  .dashboard-dropdown { position: relative; }
  .dashboard-btn {
    padding: 6px 14px;
    border: 1px solid #2a2a2a;
    border-radius: 8px;
    background: #1a1a1a;
    color: #888;
    font-size: 0.82rem;
    font-weight: 700;
    cursor: pointer;
    letter-spacing: 0.5px;
    white-space: nowrap;
    transition: all .15s;
  }
  .dashboard-btn:hover,
  .dashboard-dropdown.open .dashboard-btn { color: #C8D400; border-color: #C8D400; }
  .dashboard-btn.active { color: #C8D400; border-color: #C8D400; background: #252800; }
  .dashboard-btn.has-active { color: #C8D400; border-color: #444; background: #252800; }

  .dashboard-menu {
    display: none;
    position: absolute;
    right: 0;
    top: calc(100% + 8px);
    background: #111;
    border: 1px solid #2a2a2a;
    border-radius: 10px;
    min-width: 200px;
    padding: 8px 0 10px;
    z-index: 500;
    box-shadow: 0 8px 32px rgba(0,0,0,.6);
  }
  .dashboard-dropdown.open .dashboard-menu { display: block; }
  .dashboard-section-label {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: .12em;
    color: #444;
    padding: 6px 16px 4px;
    text-transform: uppercase;
  }
  .dashboard-menu-btn {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 9px 16px;
    background: transparent;
    border: none;
    color: #999;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    text-align: left;
    transition: background .12s, color .12s;
  }
  .dashboard-menu-btn:hover { background: #1a1a1a; color: #eee; }
  .dashboard-menu-btn.active { color: #C8D400; }

  /* ── Burger ── */
  .burger-btn {
    display: none;
    background: none;
    border: 1px solid #2a2a2a;
    color: #888;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 1.1rem;
    cursor: pointer;
    line-height: 1;
  }
  .burger-btn:hover { color: #C8D400; border-color: #C8D400; }

  .burger-drawer {
    display: none;
    position: fixed;
    inset: 0;
    z-index: 400;
  }
  .burger-drawer.open { display: block; }
  .burger-overlay {
    position: absolute;
    inset: 0;
    background: rgba(0,0,0,.6);
  }
  .burger-panel {
    position: absolute;
    top: 0; right: 0;
    width: min(280px, calc(100vw - 40px));
    height: 100%;
    background: #111;
    border-left: 1px solid #2a2a2a;
    padding: 20px 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
    overflow-y: auto;
  }
  .burger-item {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 11px 20px;
    background: transparent;
    border: none;
    color: #888;
    font-size: 0.9rem;
    font-weight: 600;
    cursor: pointer;
    text-align: left;
    transition: background .12s, color .12s;
  }
  .burger-item:hover { background: #1a1a1a; color: #eee; }
  .burger-item.active { color: #C8D400; }
  .burger-divider {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: .12em;
    color: #333;
    padding: 14px 20px 4px;
    text-transform: uppercase;
    border-top: 1px solid #1e1e1e;
    margin-top: 6px;
  }

  /* ── Reel page ── */
  #page-reel { display:none; height:calc(100vh - 65px); }
  #page-reel .layout { height:100%; }
  .reel-item {
    display:flex; align-items:center; gap:10px;
    background:#1a1a1a; border:1px solid #2a2a2a; border-radius:8px;
    padding:8px; margin-bottom:8px; cursor:grab;
    user-select:none;
  }
  .reel-item:hover { border-color:#444; }
  .reel-item.is-selection { border-color:#C8D400; }
  .reel-item.drag-over { border-color:#C8D400; border-style:dashed; background:#1e2200; }
  .reel-item.dragging  { opacity:0.4; }
  .reel-thumb {
    width:60px; height:74px; border-radius:5px; object-fit:cover;
    background:#111; flex-shrink:0;
  }
  .reel-info { flex:1; min-width:0; }
  .reel-label { font-size:0.78rem; color:#eee; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .reel-sub   { font-size:0.68rem; color:#666; margin-top:2px; }
  .reel-star  { font-size:1.1rem; cursor:pointer; color:#444; transition:color .15s; flex-shrink:0; }
  .reel-star.active { color:#C8D400; }
  .reel-remove { font-size:1rem; cursor:pointer; color:#555; transition:color .15s; flex-shrink:0; }
  .reel-remove:hover { color:#e55; }
  .reel-empty { text-align:center; color:#444; font-size:0.82rem; padding:30px 0; }
  .reel-library-header {
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:8px;
    margin-bottom:8px;
  }
  .reel-library-title {
    color:#C8D400;
    font-size:.74rem;
    font-weight:900;
    text-transform:uppercase;
    letter-spacing:.08em;
  }
  .reel-library-grid {
    display:grid;
    grid-template-columns:repeat(2, minmax(0, 1fr));
    gap:8px;
    margin-bottom:12px;
  }
  .reel-library-card {
    background:#111;
    border:1px solid #2a2a2a;
    border-radius:8px;
    overflow:hidden;
  }
  .reel-library-thumb {
    width:100%;
    aspect-ratio:4/5;
    background:#080808;
    display:flex;
    align-items:center;
    justify-content:center;
    color:#555;
    font-size:.72rem;
  }
  .reel-library-thumb img {
    width:100%;
    height:100%;
    object-fit:contain;
  }
  .reel-library-body {
    padding:7px;
  }
  .reel-library-label {
    color:#ddd;
    font-size:.7rem;
    font-weight:800;
    white-space:nowrap;
    overflow:hidden;
    text-overflow:ellipsis;
  }
  .reel-library-meta {
    color:#666;
    font-size:.62rem;
    margin-top:2px;
  }
  .reel-library-add {
    width:100%;
    min-height:28px;
    margin-top:7px;
    padding:5px 7px;
    font-size:.68rem;
  }
  .reel-section-separator {
    border-top:1px solid #242424;
    margin:12px 0 10px;
    padding-top:10px;
  }

  /* ── Performance page ── */
  #page-performance { display:none; min-height:calc(100vh - 65px); padding:22px; }
  .perf-wrap { max-width:1280px; margin:0 auto; display:flex; flex-direction:column; gap:14px; }
  .perf-header {
    display:flex;
    align-items:flex-end;
    justify-content:space-between;
    gap:14px;
    border-bottom:1px solid #2a2a2a;
    padding-bottom:14px;
  }
  .perf-title { color:#C8D400; font-size:1.45rem; letter-spacing:.08em; text-transform:uppercase; }
  .perf-sub { color:#888; margin-top:6px; line-height:1.45; max-width:760px; }
  .perf-status { color:#666; font-size:.78rem; margin-top:8px; }
  .perf-overview {
    display:grid;
    grid-template-columns:repeat(2, minmax(0, 1fr));
    gap:12px;
  }
  .perf-event-context {
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:12px;
    padding:11px 14px;
    background:#151700;
    border:1px solid #363b00;
    border-radius:9px;
  }
  .perf-event-competition { color:#eee; font-weight:800; }
  .perf-event-latest { color:#C8D400; font-weight:800; text-align:right; }
  .perf-result-style {
    display:flex;
    align-items:center;
    gap:8px;
    color:#777;
    font-size:.68rem;
    font-weight:800;
    letter-spacing:.08em;
    text-transform:uppercase;
  }
  .perf-result-style select {
    background:#0b0b0b;
    border:1px solid #333800;
    color:#C8D400;
    border-radius:7px;
    padding:7px 9px;
    font-size:.72rem;
    font-weight:800;
    outline:none;
  }
  .perf-overview-card {
    background:#101010;
    border:1px solid #2a2a2a;
    border-radius:10px;
    overflow:hidden;
  }
  .perf-overview-head {
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:10px;
    padding:13px 14px;
    background:linear-gradient(90deg, #1d2100, #111 68%);
    border-bottom:1px solid #303400;
  }
  .perf-overview-gender { color:#C8D400; font-weight:900; font-size:1rem; letter-spacing:.08em; text-transform:uppercase; }
  .perf-overview-event { color:#888; font-size:.72rem; text-align:right; }
  .perf-overview-columns { display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); }
  .perf-overview-section { padding:12px; min-width:0; }
  .perf-overview-section + .perf-overview-section { border-left:1px solid #242424; }
  .perf-overview-label { color:#777; font-size:.65rem; font-weight:800; letter-spacing:.12em; text-transform:uppercase; margin-bottom:8px; }
  .perf-overview-row {
    display:grid;
    grid-template-columns:25px minmax(0, 1fr) auto 27px;
    align-items:center;
    gap:7px;
    min-height:34px;
    border-top:1px solid #202020;
    font-size:.78rem;
  }
  .perf-overview-row:first-of-type { border-top:0; }
  .perf-overview-rank { color:#C8D400; font-weight:900; }
  .perf-overview-name { color:#eee; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .perf-overview-points { color:#aaa; font-weight:800; white-space:nowrap; }
  .perf-card-generate {
    width:27px;
    height:27px;
    border:1px solid #3b4000;
    border-radius:6px;
    background:#202300;
    color:#C8D400;
    cursor:pointer;
    font-size:.72rem;
    font-weight:900;
  }
  .perf-card-generate:hover { background:#C8D400; color:#111; }
  .perf-card-generate:disabled { cursor:not-allowed; opacity:.22; }
  .perf-analysis-title { margin-top:4px; color:#eee; font-size:.95rem; letter-spacing:.06em; text-transform:uppercase; }
  .perf-controls {
    display:grid;
    grid-template-columns:repeat(2, minmax(180px, 1fr));
    gap:10px;
    background:#111;
    border:1px solid #2a2a2a;
    border-radius:8px;
    padding:12px;
  }
  .perf-advanced-toggle {
    justify-self:start;
    background:#181818;
    border:1px solid #333;
    color:#888;
    border-radius:7px;
    padding:8px 12px;
    cursor:pointer;
    font-weight:700;
    font-size:.78rem;
  }
  .perf-advanced-toggle:hover { color:#eee; border-color:#555; }
  .perf-advanced-toggle.active { color:#C8D400; border-color:#C8D400; background:#252800; }
  .perf-advanced {
    display:none;
    grid-template-columns:repeat(4, minmax(140px, 1fr));
    gap:10px;
    background:#101010;
    border:1px solid #242424;
    border-radius:8px;
    padding:12px;
  }
  .perf-advanced.open { display:grid; }
  .perf-control { display:flex; flex-direction:column; gap:6px; }
  .perf-control label {
    font-size:10px;
    color:#666;
    font-weight:700;
    letter-spacing:.12em;
    text-transform:uppercase;
  }
  .perf-select {
    width:100%;
    background:#181818;
    border:1px solid #333;
    color:#eee;
    border-radius:7px;
    padding:9px 10px;
    font-size:.84rem;
    outline:none;
  }
  .perf-select:focus { border-color:#C8D400; }
  .perf-infographic {
    display:grid;
    grid-template-columns:minmax(250px, 310px) minmax(360px, 1fr) minmax(300px, 380px);
    gap:14px;
    align-items:stretch;
    background:#0d0d0d;
    border:1px solid #2a2a2a;
    border-radius:8px;
    padding:14px;
  }
  .perf-infographic-preview {
    min-height:420px;
    background:#080808;
    border:1px solid #202020;
    border-radius:8px;
    display:flex;
    align-items:center;
    justify-content:center;
    overflow:hidden;
    min-width:0;
  }
  .perf-infographic-preview img {
    max-width:100%;
    max-height:70vh;
    object-fit:contain;
    display:block;
  }
  .perf-info-menu,
  .perf-post-panel {
    min-width:0;
    border:1px solid #242424;
    border-radius:8px;
    background:#111;
    padding:12px;
    display:flex;
    flex-direction:column;
    gap:10px;
  }
  .perf-info-menu h3,
  .perf-post-panel h3 {
    color:#C8D400;
    margin:0;
    font-size:.95rem;
    letter-spacing:.08em;
    text-transform:uppercase;
  }
  .perf-info-menu p,
  .perf-post-panel p {
    color:#777;
    font-size:.8rem;
    line-height:1.5;
    margin:0;
  }
  .perf-info-options {
    border:1px solid #242424;
    border-radius:8px;
    padding:10px;
    background:#101010;
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:8px 10px;
  }
  .perf-info-options-title {
    grid-column:1 / -1;
    color:#aaa;
    font-size:10px;
    font-weight:800;
    letter-spacing:.12em;
    text-transform:uppercase;
  }
  .perf-info-options label {
    color:#ddd;
    font-size:.78rem;
    display:flex;
    align-items:center;
    gap:7px;
    cursor:pointer;
    user-select:none;
  }
  .perf-info-options input {
    accent-color:#C8D400;
  }
  .perf-info-fields {
    display:grid;
    grid-template-columns:1fr;
    gap:8px;
  }
  .perf-info-fields label {
    display:flex;
    flex-direction:column;
    gap:5px;
  }
  .perf-info-fields span {
    color:#888;
    font-size:10px;
    font-weight:800;
    letter-spacing:.12em;
    text-transform:uppercase;
  }
  .perf-info-fields input,
  .perf-info-fields select {
    width:100%;
    box-sizing:border-box;
    border:1px solid #2a2a2a;
    border-radius:7px;
    background:#0d0d0d;
    color:#eee;
    padding:10px;
    font:800 .82rem system-ui, sans-serif;
    outline:none;
  }
  .perf-info-fields input:focus,
  .perf-info-fields select:focus {
    border-color:#C8D400;
  }
  .perf-infographic-actions {
    display:grid;
    grid-template-columns:1fr;
    gap:8px;
    margin-top:4px;
  }
  .perf-infographic-actions .btn {
    margin-top:0;
    width:100%;
  }
  .perf-post-textarea {
    width:100%;
    min-height:260px;
    resize:vertical;
    box-sizing:border-box;
    border:1px solid #2a2a2a;
    border-radius:8px;
    background:#0b0b0b;
    color:#eee;
    padding:11px 12px;
    font-size:.84rem;
    line-height:1.55;
    outline:none;
  }
  .perf-post-textarea:focus {
    border-color:#C8D400;
  }
  .perf-post-actions {
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:8px;
  }
  .perf-post-actions .btn {
    margin-top:0;
    width:100%;
  }
  .perf-grid {
    display:grid;
    grid-template-columns:minmax(0, .95fr) minmax(0, 1.35fr);
    gap:14px;
    align-items:start;
  }
  .perf-panel {
    background:#111;
    border:1px solid #2a2a2a;
    border-radius:8px;
    padding:14px;
    min-width:0;
  }
  .perf-panel h3 {
    color:#C8D400;
    font-size:.88rem;
    letter-spacing:.08em;
    text-transform:uppercase;
    margin-bottom:12px;
  }
  .perf-leader-list { display:flex; flex-direction:column; gap:8px; }
  .perf-leader {
    display:grid;
    grid-template-columns:34px minmax(0, 1fr) auto;
    gap:10px;
    align-items:center;
    padding:10px;
    border:1px solid #252525;
    border-radius:7px;
    background:#151515;
  }
  .perf-rank {
    width:30px;
    height:30px;
    display:flex;
    align-items:center;
    justify-content:center;
    border-radius:50%;
    background:#252800;
    color:#C8D400;
    font-weight:800;
    font-size:.8rem;
  }
  .perf-main { min-width:0; }
  .perf-name { color:#eee; font-weight:800; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .perf-meta { color:#777; font-size:.76rem; margin-top:3px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .perf-score { text-align:right; color:#eee; font-weight:800; }
  .perf-score small { display:block; color:#777; font-size:.68rem; font-weight:600; margin-top:2px; }
  .perf-table { width:100%; border-collapse:collapse; font-size:.82rem; }
  .perf-table th {
    color:#777;
    font-size:10px;
    letter-spacing:.1em;
    text-transform:uppercase;
    text-align:left;
    padding:8px;
    border-bottom:1px solid #2a2a2a;
  }
  .perf-table td {
    padding:9px 8px;
    border-bottom:1px solid #202020;
    vertical-align:top;
  }
  .perf-table tr:hover td { background:#151515; }
  .perf-riders { color:#888; font-size:.76rem; line-height:1.45; max-width:420px; }
  .perf-empty {
    color:#666;
    border:1px dashed #333;
    border-radius:8px;
    padding:24px;
    text-align:center;
    line-height:1.5;
  }

  /* ── Publish page ── */
  #page-publish { display:none; height:calc(100vh - 65px); }
  #page-publish .layout { height:100%; }
  .publish-panel { display:flex; flex-direction:column; gap:10px; }
  .publish-source-row { display:flex; gap:8px; flex-wrap:wrap; }
  .publish-source-btn {
    flex:1;
    min-width:105px;
    background:#1a1a1a;
    border:1px solid #333;
    color:#888;
    padding:8px 12px;
    border-radius:7px;
    cursor:pointer;
    font-size:0.78rem;
    font-weight:600;
    transition:all .15s;
  }
  .publish-source-btn:hover { color:#eee; border-color:#555; }
  .publish-source-btn.active { color:#C8D400; border-color:#C8D400; background:#252800; }
  .publish-meta { font-size:11px; color:#666; line-height:1.5; }
  .publish-field { display:flex; flex-direction:column; gap:6px; }
  .publish-field label {
    font-size:10px; font-weight:700; letter-spacing:.12em; color:#555; text-transform:uppercase;
  }
  .publish-input, .publish-textarea {
    width:100%;
    background:#111;
    border:1px solid #2a2a2a;
    color:#eee;
    border-radius:7px;
    padding:9px 10px;
    font-size:0.86rem;
    outline:none;
  }
  .publish-input:focus, .publish-textarea:focus { border-color:#C8D400; }
  .publish-textarea { min-height:82px; resize:vertical; line-height:1.45; }
  .publish-rows { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
  .publish-check { display:flex; gap:8px; align-items:center; font-size:0.82rem; color:#bbb; }
  .publish-status { font-size:12px; color:#888; padding-top:6px; min-height:18px; }
  .publish-action-stack {
    display:flex;
    flex-direction:column;
    gap:8px;
  }
  .publish-action-row {
    display:grid;
    grid-template-columns:repeat(2, minmax(0, 1fr));
    gap:8px;
  }
  .publish-action-row.compact {
    grid-template-columns:repeat(3, minmax(0, 1fr));
  }
  .publish-action-stack .btn {
    width:100%;
    min-width:0;
    min-height:44px;
    margin-top:0;
    padding:9px 10px;
    display:flex;
    align-items:center;
    justify-content:center;
    text-align:center;
    line-height:1.12;
    letter-spacing:.2px;
  }
  .publish-action-stack > .btn {
    min-height:48px;
  }
  .publish-action-row.compact .btn {
    min-height:38px;
    padding:8px 6px;
    font-size:.78rem;
  }
  .publish-helper-row {
    display:flex;
    gap:8px;
    align-items:center;
    flex-wrap:wrap;
  }
  .publish-mini-btn {
    background:#181818;
    color:#aaa;
    border:1px solid #333;
    border-radius:6px;
    padding:7px 10px;
    font-size:.74rem;
    font-weight:700;
    cursor:pointer;
  }
  .publish-mini-btn:hover { color:#eee; border-color:#555; }
  .publish-checklist {
    display:flex;
    flex-direction:column;
    gap:7px;
  }
  .publish-check-summary {
    display:flex;
    justify-content:space-between;
    align-items:center;
    gap:10px;
    padding:9px 10px;
    border:1px solid #2a2a2a;
    border-radius:8px;
    background:#101010;
    color:#aaa;
    font-size:.78rem;
    font-weight:800;
  }
  .publish-check-summary.ok {
    border-color:#C8D400;
    color:#C8D400;
    background:#202400;
  }
  .publish-check-score {
    color:#eee;
    font-size:.82rem;
  }
  .publish-check-row {
    display:flex;
    align-items:flex-start;
    gap:8px;
    color:#888;
    font-size:.78rem;
    line-height:1.35;
  }
  .publish-check-dot {
    width:18px;
    height:18px;
    border-radius:50%;
    display:flex;
    align-items:center;
    justify-content:center;
    flex-shrink:0;
    background:#181818;
    border:1px solid #333;
    color:#555;
    font-size:.68rem;
    font-weight:900;
  }
  .publish-check-row.ok .publish-check-dot {
    background:#252800;
    border-color:#C8D400;
    color:#C8D400;
  }
  .publish-check-row.warn .publish-check-dot {
    background:#241600;
    border-color:#8a5a00;
    color:#f0a000;
  }
  .publish-check-text {
    display:flex;
    flex-direction:column;
    gap:2px;
  }
  .publish-check-label {
    color:#bdbdbd;
    font-weight:800;
  }
  .publish-check-detail {
    color:#666;
    font-size:.72rem;
  }
  .publish-check-row.ok .publish-check-label { color:#C8D400; }
  .publish-check-row.warn .publish-check-label { color:#f0a000; }
  .publish-history-list {
    display:flex;
    flex-direction:column;
    gap:8px;
  }
  .publish-history-item {
    background:#111;
    border:1px solid #2a2a2a;
    border-radius:7px;
    padding:9px;
    cursor:pointer;
  }
  .publish-history-item:hover { border-color:#555; }
  .publish-history-title {
    color:#eee;
    font-weight:800;
    font-size:.8rem;
    white-space:nowrap;
    overflow:hidden;
    text-overflow:ellipsis;
  }
  .publish-history-meta {
    color:#666;
    font-size:.7rem;
    margin-top:4px;
  }
  .publish-history-actions {
    display:flex;
    gap:6px;
    margin-top:8px;
  }
  .publish-history-actions button {
    flex:1;
    min-height:28px;
    margin-top:0;
    padding:5px 8px;
    font-size:.7rem;
  }
  .publish-preview-box {
    width:100%;
    display:flex;
    flex-direction:column;
    gap:12px;
    align-items:center;
    justify-content:center;
    padding:16px;
  }
  .publish-preview-media {
    width:100%;
    max-height:58vh;
    object-fit:contain;
    border:1px solid #2a2a2a;
    border-radius:8px;
    background:#111;
    box-shadow:0 8px 40px rgba(0,0,0,.45);
  }
  .publish-preview-caption {
    width:100%;
    background:#111;
    border:1px solid #2a2a2a;
    border-radius:8px;
    padding:12px;
    color:#888;
    font-size:0.82rem;
    line-height:1.6;
    white-space:pre-wrap;
    max-height:58vh;
    overflow:auto;
  }
  .publish-select-grid {
    display:grid;
    grid-template-columns:1fr;
    gap:8px;
    margin-top:10px;
  }
  .publish-preview-shell {
    display:grid;
    grid-template-columns:minmax(0, 1.35fr) 320px;
    gap:14px;
    width:100%;
    min-height:0;
    align-items:start;
  }
  .publish-preview-media-col {
    display:flex;
    flex-direction:column;
    gap:12px;
    min-width:0;
  }
  .publish-preview-side {
    min-width:0;
    display:flex;
    flex-direction:column;
    gap:10px;
    background:#111;
    border:1px solid #2a2a2a;
    border-radius:8px;
    padding:12px;
  }
  .publish-preview-head {
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:10px;
  }
  .publish-preview-title {
    color:#555;
    font-size:10px;
    font-weight:700;
    letter-spacing:.12em;
    text-transform:uppercase;
  }
  .publish-copy-mini {
    min-height:28px;
    margin-top:0;
    padding:5px 9px;
    border-radius:6px;
    font-size:0.72rem;
    line-height:1;
  }
  .publish-music-hint {
    font-size:11px;
    color:#666;
    line-height:1.5;
  }
  /* ── Library page ── */
  #page-library { display:none; padding:28px 24px 48px; max-width:1400px; margin:0 auto; }
  .library-toolbar {
    display:flex;
    gap:10px;
    align-items:flex-end;
    flex-wrap:wrap;
    margin:18px 0;
  }
  .library-field {
    display:flex;
    flex-direction:column;
    gap:5px;
    min-width:160px;
  }
  .library-field label {
    color:#666;
    font-size:10px;
    text-transform:uppercase;
    letter-spacing:.08em;
  }
  .library-field input,
  .library-field select {
    background:#111;
    border:1px solid #333;
    border-radius:7px;
    color:#ddd;
    padding:8px 10px;
    font-size:13px;
  }
  .library-grid {
    display:grid;
    grid-template-columns:repeat(auto-fill, minmax(240px, 1fr));
    gap:12px;
  }
  .library-card {
    background:#111;
    border:1px solid #2a2a2a;
    border-radius:8px;
    overflow:hidden;
  }
  .library-thumb {
    width:100%;
    aspect-ratio:4/5;
    background:#080808;
    display:flex;
    align-items:center;
    justify-content:center;
    color:#555;
    overflow:hidden;
  }
  .library-thumb img,
  .library-thumb video {
    width:100%;
    height:100%;
    object-fit:contain;
    background:#080808;
  }
  .library-body { padding:11px; }
  .library-title {
    color:#eee;
    font-size:.86rem;
    font-weight:900;
    white-space:nowrap;
    overflow:hidden;
    text-overflow:ellipsis;
  }
  .library-meta {
    color:#666;
    font-size:.72rem;
    margin-top:4px;
    line-height:1.45;
  }
  .library-actions {
    display:grid;
    grid-template-columns:repeat(3, minmax(0, 1fr));
    gap:7px;
    margin-top:10px;
  }
  .library-actions button {
    min-height:30px;
    margin-top:0;
    padding:6px 7px;
    font-size:.7rem;
  }
  .library-empty {
    border:1px dashed #333;
    border-radius:8px;
    padding:28px;
    color:#666;
    text-align:center;
    font-size:.9rem;
  }
  /* ── Logos page ── */
  #page-logos { display:none; padding:24px; max-width:1000px; margin:0 auto; }
  .logos-toolbar { display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-bottom:18px; }
  .logos-url-input { flex:1; min-width:260px; background:#111; border:1px solid #333; color:#eee;
    padding:8px 12px; border-radius:6px; font-size:13px; }
  .logos-url-input:focus { outline:none; border-color:#C8D400; }
  .logos-table { width:100%; border-collapse:collapse; font-size:13px; }
  .logos-table th { text-align:left; padding:8px 10px; color:#888; border-bottom:1px solid #2a2a2a;
    font-weight:600; font-size:12px; text-transform:uppercase; letter-spacing:.05em; }
  .logos-table td { padding:7px 10px; border-bottom:1px solid #1e1e1e; vertical-align:middle; }
  .logos-table tr:hover td { background:#1e1e1e; }
  .logo-thumb { width:56px; height:28px; object-fit:contain; background:#111; border-radius:4px; }
  .logo-status-ok   { color:#C8D400; font-size:12px; }
  .logo-status-miss { color:#f55;    font-size:12px; }
  .logos-progress { height:6px; background:#222; border-radius:3px; overflow:hidden; margin:12px 0 6px; display:none; }
  .logos-progress-bar { height:100%; width:0; background:#C8D400; transition:width .15s; }
  .logos-stats { font-size:12px; color:#888; margin-bottom:14px; }
  .logos-actions { display:flex; gap:8px; align-items:center; margin-bottom:16px; }
  .btn-select-all { background:none; border:1px solid #444; color:#aaa; padding:5px 12px;
    border-radius:5px; cursor:pointer; font-size:12px; }
  .btn-select-all:hover { border-color:#C8D400; color:#C8D400; }

  /* ── Quality Center ── */
  #page-quality { display:none; padding:28px 24px 48px; max-width:1400px; margin:0 auto; }
  .quality-kpis {
    display:grid;
    grid-template-columns:repeat(5, minmax(0, 1fr));
    gap:12px;
    margin:18px 0;
  }
  .quality-kpi {
    background:#111;
    border:1px solid #2a2a2a;
    border-radius:8px;
    padding:14px;
  }
  .quality-kpi-label {
    color:#666;
    font-size:11px;
    text-transform:uppercase;
    letter-spacing:.08em;
  }
  .quality-kpi-value {
    color:#eee;
    font-size:1.55rem;
    font-weight:900;
    margin-top:6px;
  }
  .quality-kpi.good .quality-kpi-value { color:#C8D400; }
  .quality-kpi.warn .quality-kpi-value { color:#f0a000; }
  .quality-kpi.critical .quality-kpi-value { color:#f55; }
  .quality-kpi.optional .quality-kpi-value { color:#8aa0ff; }
  .quality-toolbar {
    display:flex;
    gap:10px;
    align-items:flex-end;
    flex-wrap:wrap;
    margin:18px 0;
  }
  .quality-field {
    display:flex;
    flex-direction:column;
    gap:5px;
    min-width:160px;
  }
  .quality-field label {
    color:#666;
    font-size:10px;
    text-transform:uppercase;
    letter-spacing:.08em;
  }
  .quality-field select,
  .quality-field input {
    background:#111;
    border:1px solid #333;
    border-radius:7px;
    color:#ddd;
    padding:8px 10px;
    font-size:13px;
  }
  .quality-table-wrap {
    background:#0d0d0d;
    border:1px solid #222;
    border-radius:8px;
    overflow:auto;
    max-height:64vh;
  }
  .quality-table {
    width:100%;
    border-collapse:collapse;
    min-width:1180px;
    font-size:12px;
  }
  .quality-table th {
    position:sticky;
    top:0;
    z-index:1;
    background:#111;
    color:#C8D400;
    text-align:left;
    padding:9px 10px;
    font-size:10px;
    text-transform:uppercase;
    letter-spacing:.08em;
    border-bottom:1px solid #333;
  }
  .quality-table td {
    padding:9px 10px;
    border-bottom:1px solid #171717;
    color:#aaa;
    vertical-align:top;
  }
  .quality-table tr:hover td { background:#141414; }
  .quality-pill {
    display:inline-flex;
    align-items:center;
    justify-content:center;
    min-width:68px;
    padding:3px 7px;
    border-radius:999px;
    border:1px solid #333;
    font-size:10px;
    font-weight:900;
    text-transform:uppercase;
    letter-spacing:.05em;
  }
  .quality-pill.critical { color:#f55; border-color:#5a2020; background:#220808; }
  .quality-pill.warning { color:#f0a000; border-color:#5a3a00; background:#241600; }
  .quality-pill.optional { color:#8aa0ff; border-color:#26376f; background:#10162c; }
  .quality-pill.ok { color:#C8D400; border-color:#586000; background:#202400; }
  .quality-pill.active { color:#eee; border-color:#444; background:#181818; }
  .quality-pill.required { color:#eee; border-color:#444; background:#181818; }
  .quality-pill.nice_to_have { color:#8aa0ff; border-color:#26376f; background:#10162c; }
  .quality-pill.ignored { color:#777; border-color:#333; background:#151515; }
  .quality-pill.validated { color:#C8D400; border-color:#586000; background:#202400; }
  .quality-target { color:#eee; font-weight:800; }
  .quality-detail { color:#777; line-height:1.45; }
  .quality-action { color:#C8D400; font-weight:800; }
  .quality-manual-actions {
    display:flex;
    flex-wrap:wrap;
    gap:6px;
    margin-top:8px;
  }
  .quality-manual-btn {
    background:#141414;
    border:1px solid #333;
    color:#aaa;
    border-radius:6px;
    padding:5px 8px;
    font-size:10px;
    font-weight:900;
    cursor:pointer;
    text-transform:uppercase;
    letter-spacing:.04em;
  }
  .quality-manual-btn:hover { border-color:#C8D400; color:#C8D400; }
  .quality-manual-btn.danger:hover { border-color:#f55; color:#f55; }
  .quality-table tr.manual-ignored td { opacity:.58; }
  .quality-table tr.manual-validated td { background:#101406; }
  .quality-daily {
    background:#0d0d0d;
    border:1px solid #2a2a2a;
    border-radius:9px;
    padding:14px;
    margin:14px 0 4px;
  }
  .quality-daily-head {
    display:flex;
    align-items:flex-end;
    justify-content:space-between;
    gap:12px;
    margin-bottom:12px;
  }
  .quality-daily-title {
    color:#C8D400;
    font-size:14px;
    font-weight:950;
    text-transform:uppercase;
    letter-spacing:.08em;
  }
  .quality-daily-subtitle {
    color:#666;
    font-size:11px;
    margin-top:4px;
    line-height:1.35;
  }
  .quality-daily-grid {
    display:grid;
    grid-template-columns:repeat(3, minmax(0, 1fr));
    gap:12px;
  }
  .quality-daily-card {
    background:#111;
    border:1px solid #242424;
    border-radius:8px;
    padding:12px;
    min-width:0;
  }
  .quality-daily-card.warn { border-color:#403000; }
  .quality-daily-card.critical { border-color:#462020; }
  .quality-daily-card.optional { border-color:#26376f; }
  .quality-daily-card-head {
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:8px;
    margin-bottom:10px;
  }
  .quality-daily-card-title {
    color:#eee;
    font-size:12px;
    font-weight:900;
    text-transform:uppercase;
    letter-spacing:.07em;
  }
  .quality-daily-count {
    color:#C8D400;
    font-size:18px;
    font-weight:950;
  }
  .quality-daily-list {
    display:flex;
    flex-direction:column;
    gap:7px;
    margin-bottom:10px;
  }
  .quality-daily-item {
    border:1px solid #202020;
    background:#0b0b0b;
    border-radius:7px;
    padding:8px;
    min-width:0;
  }
  .quality-daily-main {
    color:#ddd;
    font-size:12px;
    font-weight:850;
    line-height:1.3;
    overflow-wrap:anywhere;
  }
  .quality-daily-sub {
    color:#666;
    font-size:10px;
    line-height:1.35;
    margin-top:4px;
    overflow-wrap:anywhere;
  }
  .quality-daily-empty {
    color:#666;
    font-size:12px;
    border:1px dashed #282828;
    border-radius:7px;
    padding:10px;
  }
  .quality-daily-action {
    width:100%;
    background:#161616;
    border:1px solid #333;
    color:#C8D400;
    border-radius:7px;
    padding:8px 10px;
    font-size:11px;
    font-weight:900;
    cursor:pointer;
    text-transform:uppercase;
    letter-spacing:.05em;
  }
  .quality-daily-action:hover { border-color:#C8D400; background:#202400; }
  .quality-assets {
    background:#0d0d0d;
    border:1px solid #222;
    border-radius:8px;
    padding:14px;
    margin:14px 0 4px;
  }
  .quality-assets-head {
    display:flex;
    align-items:flex-end;
    justify-content:space-between;
    gap:12px;
    margin-bottom:12px;
  }
  .quality-assets-title {
    color:#eee;
    font-size:13px;
    font-weight:900;
    text-transform:uppercase;
    letter-spacing:.08em;
  }
  .quality-assets-note { color:#666; font-size:11px; margin-top:4px; }
  .quality-assets-grid {
    display:grid;
    grid-template-columns:repeat(auto-fit, minmax(190px, 1fr));
    gap:10px;
  }
  .quality-work-grid {
    display:grid;
    grid-template-columns:repeat(auto-fit, minmax(210px, 1fr));
    gap:10px;
    margin-bottom:12px;
  }
  .quality-work-card {
    border:1px solid #272727;
    background:#101010;
    border-radius:8px;
    padding:11px;
    cursor:pointer;
    color:inherit;
    font:inherit;
    text-align:left;
    width:100%;
  }
  .quality-work-card:hover { border-color:#C8D400; background:#151515; }
  .quality-work-label {
    color:#777;
    font-size:10px;
    font-weight:900;
    text-transform:uppercase;
    letter-spacing:.08em;
  }
  .quality-work-value {
    color:#eee;
    font-size:24px;
    font-weight:950;
    line-height:1;
    margin:8px 0 6px;
  }
  .quality-work-note { color:#666; font-size:11px; line-height:1.35; }
  .quality-today {
    margin-top:12px;
    border-top:1px solid #222;
    padding-top:12px;
  }
  .quality-today-title {
    color:#eee;
    font-size:12px;
    font-weight:900;
    text-transform:uppercase;
    letter-spacing:.08em;
    margin-bottom:8px;
  }
  .quality-today-list {
    display:grid;
    grid-template-columns:repeat(auto-fit, minmax(240px, 1fr));
    gap:8px;
  }
  .quality-today-item {
    background:#0b0b0b;
    border:1px solid #222;
    border-radius:7px;
    padding:8px;
    color:#aaa;
    font-size:11px;
    line-height:1.35;
  }
  .quality-asset-card {
    border:1px solid #272727;
    background:#111;
    border-radius:8px;
    padding:11px;
    cursor:pointer;
    color:inherit;
    font:inherit;
    text-align:left;
    width:100%;
  }
  .quality-asset-card:hover { border-color:#C8D400; background:#151515; }
  .quality-asset-top {
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:8px;
    margin-bottom:8px;
  }
  .quality-asset-cat { color:#eee; font-weight:900; font-size:13px; }
  .quality-asset-count { color:#C8D400; font-size:22px; font-weight:950; line-height:1; }
  .quality-asset-meta { color:#777; font-size:11px; line-height:1.45; }
  .quality-priority {
    display:inline-flex;
    align-items:center;
    justify-content:center;
    min-width:58px;
    padding:3px 7px;
    border:1px solid #333;
    border-radius:999px;
    color:#aaa;
    background:#151515;
    font-size:10px;
    font-weight:900;
    text-transform:uppercase;
    letter-spacing:.05em;
  }
  .quality-priority.p1,
  .quality-priority.p2,
  .quality-priority.p3 { color:#f55; border-color:#5a2020; background:#220808; }
  .quality-priority.p4,
  .quality-priority.p5,
  .quality-priority.p6 { color:#f0a000; border-color:#5a3a00; background:#241600; }
  .quality-candidate-btn {
    margin-top:8px;
    background:#161616;
    border:1px solid #444;
    color:#C8D400;
    border-radius:6px;
    padding:6px 9px;
    font-size:11px;
    font-weight:900;
    cursor:pointer;
  }
  .quality-candidate-btn:hover { border-color:#C8D400; background:#202400; }
  .quality-candidates { display:none; margin-top:10px; }
  .quality-candidates.open { display:block; }
  .quality-candidate-grid {
    display:grid;
    grid-template-columns:repeat(auto-fit, minmax(120px, 1fr));
    gap:8px;
  }
  .quality-candidate {
    border:1px solid #252525;
    background:#0b0b0b;
    border-radius:7px;
    padding:7px;
  }
  .quality-candidate img {
    width:100%;
    aspect-ratio:1/1;
    object-fit:contain;
    background:#181818;
    border-radius:5px;
    margin-bottom:6px;
  }
  .quality-candidate-name {
    color:#ddd;
    font-size:10px;
    font-weight:800;
    overflow-wrap:anywhere;
    line-height:1.25;
  }
  .quality-candidate-reason { color:#777; font-size:10px; margin-top:4px; line-height:1.25; }
  .quality-expected {
    margin-top:8px;
    color:#777;
    font-size:10px;
    line-height:1.35;
    overflow-wrap:anywhere;
  }
  .quality-expected code {
    color:#C8D400;
    font-family:monospace;
  }
  @media (max-width: 1050px) {
    .quality-daily-grid { grid-template-columns:1fr; }
  }

  /* ── Connections page ── */
  #page-connections { display:none; padding:32px 24px; max-width:960px; margin:0 auto; }
  #page-connections h2 { color:#C8D400; font-size:1.1rem; letter-spacing:1px; margin-bottom:4px; }
  #page-connections .conn-subtitle { color:#555; font-size:12px; margin-bottom:28px; }
  .conn-section-title {
    font-size:10px; font-weight:700; letter-spacing:.12em; color:#444;
    text-transform:uppercase; margin-bottom:12px; padding-bottom:6px;
    border-bottom:1px solid #1e1e1e;
  }
  .conn-grid {
    display:grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap:14px;
    margin-bottom:32px;
  }
  .conn-card {
    background:#111;
    border:1px solid #1e1e1e;
    border-radius:12px;
    padding:20px 16px 16px;
    display:flex; flex-direction:column; align-items:center; gap:10px;
    transition:border-color .15s, box-shadow .15s;
    position:relative;
  }
  .conn-card:hover { border-color:#2a2a2a; box-shadow:0 4px 20px rgba(0,0,0,.4); }
  .conn-card.connected { border-color:#1a3300; }
  .conn-logo {
    width:52px; height:52px; border-radius:12px;
    display:flex; align-items:center; justify-content:center;
    flex-shrink:0;
  }
  .conn-logo svg { width:28px; height:28px; }
  .conn-name { font-size:13px; font-weight:700; color:#ccc; letter-spacing:.3px; }
  .conn-status {
    display:flex; align-items:center; gap:5px;
    font-size:11px; color:#444; font-weight:500;
  }
  .conn-status .dot {
    width:6px; height:6px; border-radius:50%; background:#333; flex-shrink:0;
  }
  .conn-card.connected .conn-status { color:#5a8a00; }
  .conn-card.connected .conn-status .dot { background:#C8D400; }
  .conn-btn {
    margin-top:auto; width:100%;
    padding:7px 0; border-radius:7px;
    font-size:12px; font-weight:700;
    cursor:pointer; border:1px solid #2a2a2a;
    background:#1a1a1a; color:#666;
    transition:all .15s;
  }
  .conn-btn:hover { border-color:#555; color:#eee; }
  .conn-card.connected .conn-btn { color:#cc4400; border-color:#3a1000; background:#1a0a00; }
  .conn-card.connected .conn-btn:hover { border-color:#cc4400; }

  /* ── Settings page ── */
  #page-settings { display:none; padding:32px 24px; max-width:960px; margin:0 auto; }
  #page-settings h2 { color:#C8D400; font-size:1.1rem; letter-spacing:1px; margin-bottom:4px; }
  #page-settings .settings-subtitle { color:#555; font-size:12px; margin-bottom:24px; }
  .settings-card {
    background:#111;
    border:1px solid #222;
    border-radius:10px;
    padding:16px;
    margin-bottom:16px;
  }
  .settings-card-title {
    color:#eee;
    font-size:12px;
    font-weight:900;
    text-transform:uppercase;
    letter-spacing:.08em;
    margin-bottom:12px;
  }
  .settings-field { display:flex; flex-direction:column; gap:7px; margin-bottom:12px; }
  .settings-field label {
    color:#666;
    font-size:10px;
    text-transform:uppercase;
    letter-spacing:.08em;
  }
  .settings-input {
    width:100%;
    background:#0b0b0b;
    border:1px solid #333;
    border-radius:7px;
    color:#eee;
    padding:10px 11px;
    font-size:13px;
    font-family:monospace;
  }
  .settings-input:focus { outline:none; border-color:#C8D400; }
  .settings-actions { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
  .settings-status { color:#777; font-size:12px; margin-top:10px; line-height:1.45; }
  .settings-status.ok { color:#C8D400; }
  .settings-status.err { color:#f55; }
  .settings-current {
    color:#aaa;
    font-size:12px;
    word-break:break-all;
    line-height:1.45;
    background:#0b0b0b;
    border:1px solid #222;
    border-radius:7px;
    padding:10px;
  }
  .settings-test-table {
    width:100%;
    border-collapse:collapse;
    margin-top:12px;
    font-size:12px;
    min-width:720px;
  }
  .settings-test-table th {
    color:#C8D400;
    text-align:left;
    font-size:10px;
    text-transform:uppercase;
    letter-spacing:.08em;
    padding:8px;
    border-bottom:1px solid #333;
  }
  .settings-test-table td {
    color:#aaa;
    padding:8px;
    border-bottom:1px solid #1d1d1d;
    vertical-align:top;
  }
  .settings-test-ok { color:#C8D400; font-weight:900; }
  .settings-test-missing { color:#f55; font-weight:900; }
  .settings-test-muted { color:#666; font-size:11px; }
  .settings-checklist {
    display:grid;
    grid-template-columns:repeat(auto-fit, minmax(220px, 1fr));
    gap:10px;
    margin-top:10px;
  }
  .settings-check-item {
    background:#0b0b0b;
    border:1px solid #222;
    border-radius:8px;
    padding:10px;
  }
  .settings-check-title {
    color:#eee;
    font-size:12px;
    font-weight:900;
    margin-bottom:6px;
  }
  .settings-check-cols {
    color:#777;
    font-size:11px;
    line-height:1.45;
  }

  /* ── Riders page ── */
  #page-riders { display:none; padding:24px; max-width:1100px; margin:0 auto; }
  .riders-folders { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:16px; }
  .riders-folder-card { background:#111; border:1px solid #2a2a2a; border-radius:8px; padding:14px; }
  .riders-folder-card label { font-size:11px; color:#888; text-transform:uppercase; letter-spacing:.08em; display:block; margin-bottom:8px; }
  .riders-folder-row { display:flex; gap:8px; align-items:flex-start; flex-wrap:wrap; }
  .riders-folder-path { flex:1; min-width:0; font-size:11px; color:#555; font-family:monospace;
    background:#1a1a1a; border:1px solid #2a2a2a; border-radius:4px; padding:6px 10px;
    word-break:break-all; line-height:1.5; }
  .riders-folder-path.set { color:#C8D400; }
  .riders-table { width:100%; border-collapse:collapse; font-size:13px; margin-top:8px; }
  .riders-table th { text-align:left; padding:8px 10px; color:#888; border-bottom:1px solid #2a2a2a;
    font-weight:600; font-size:11px; text-transform:uppercase; letter-spacing:.05em; }
  .riders-table td { padding:6px 10px; border-bottom:1px solid #181818; vertical-align:middle; }
  .riders-table tr:hover td { background:#1a1a1a; }
  .rider-thumb { width:40px; height:40px; object-fit:cover; border-radius:50%; background:#1a1a1a; border:1px solid #2a2a2a; }
  .rider-thumb-action { width:56px; height:40px; object-fit:cover; border-radius:4px; background:#1a1a1a; border:1px solid #2a2a2a; }
  .rider-status-ok   { color:#C8D400; font-size:12px; font-weight:600; }
  .rider-status-miss { color:#f55;    font-size:12px; }
  .riders-progress { height:6px; background:#222; border-radius:3px; overflow:hidden; margin:10px 0 6px; display:none; }
  .riders-progress-bar { height:100%; width:0; background:#C8D400; transition:width .2s; }
  .riders-stats { font-size:12px; color:#888; margin-bottom:14px; }
  .ig-link { color:#888; font-size:11px; text-decoration:none; }
  .ig-link:hover { color:#C8D400; }
  .btn-dl-pp { background:#1a2200; border:1px solid #C8D400; color:#C8D400; font-size:11px;
    padding:3px 8px; border-radius:4px; cursor:pointer; margin-left:6px; }
  .btn-dl-pp:hover { background:#2a3300; }
  .btn-dl-pp:disabled { opacity:.4; cursor:not-allowed; }
  .carousel-picker { display:flex; gap:8px; flex-wrap:wrap; margin-top:10px; }
  .carousel-thumb { width:90px; height:90px; object-fit:cover; border-radius:6px;
    border:2px solid #2a2a2a; cursor:pointer; transition:border-color .15s, transform .15s; }
  .carousel-thumb:hover  { border-color:#666; transform:scale(1.03); }
  .carousel-thumb.active { border-color:#C8D400; box-shadow:0 0 0 2px #C8D400; }

  /* ── Equipment page ── */
  #page-equipment {
    display: none;  /* montré via JS → display:block */
    height: calc(100vh - 65px);
    overflow: hidden;
  }
  #page-equipment .layout {
    height: calc(100% - 41px);
    align-items: stretch;
  }
  #page-equipment .panel-wrapper {
    min-height: 0;
  }
  #page-equipment .panel {
    padding-bottom: 6px;
  }
  #page-equipment .collapsible-body {
    padding: 10px;
  }
  #page-equipment .slider-row {
    margin-bottom: 4px;
  }
  #page-equipment .panel-actions { gap: 8px; }
  .eq-page-bar {
    background: #161616;
    border-bottom: 1px solid #2a2a2a;
    padding: 10px 20px;
    display: flex;
    gap: 10px;
    align-items: center;
    flex-shrink: 0;
  }
  .eq-topbar {
    background:#161616;
    border-bottom:1px solid #222;
    padding:8px 16px;
    display:flex;
    align-items:center;
    gap:10px;
    flex-wrap:wrap;
    min-height:41px;
  }
  .eq-topbar-title {
    color:#C8D400;
    font-size:0.8rem;
    font-weight:700;
    letter-spacing:.08em;
  }
  .eq-topbar-btn {
    padding:4px 14px;
    background:#1a1a1a;
    border:1px solid #444;
    border-radius:6px;
    color:#ccc;
    font-size:11px;
    cursor:pointer;
  }
  .eq-topbar-btn:hover {
    border-color:#C8D400;
    color:#C8D400;
  }
  .eq-table-wrap {
    flex: 1;
    overflow: auto;
  }
  .eq-full-table {
    border-collapse: collapse;
    min-width: 100%;
    font-size: 0.76rem;
  }
  .eq-full-table th {
    background: #161616;
    color: #555;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    font-size: 0.6rem;
    padding: 9px 10px;
    border-bottom: 2px solid #252525;
    border-right: 1px solid #1e1e1e;
    position: sticky;
    top: 0;
    z-index: 2;
    white-space: nowrap;
    font-weight: 800;
  }
  .eq-full-table th:first-child {
    position: sticky;
    left: 0;
    z-index: 3;
    background: #111;
    min-width: 160px;
  }
  .eq-full-table td {
    padding: 8px 10px;
    border-bottom: 1px solid #1c1c1c;
    border-right: 1px solid #1a1a1a;
    vertical-align: top;
    white-space: nowrap;
  }
  .eq-full-table tr:hover td { background: rgba(200,212,0,0.04); }
  .eq-full-table td:first-child {
    position: sticky;
    left: 0;
    background: #141414;
    z-index: 1;
    border-right: 2px solid #252525;
    min-width: 160px;
  }
  .eq-full-table tr:hover td:first-child { background: #1a1a0a; }
  .eq-rider-cell { display: flex; align-items: center; gap: 8px; }
  .eq-rider-info .eq-rider-name { font-weight: 700; color: #ccc; font-size: 0.78rem; }
  .eq-rider-info .eq-rider-ig { font-size: 0.65rem; color: #444; margin-top: 1px; }
  .eq-cell-brand { color: #C8D400; font-weight: 700; }
  .eq-cell-ref { color: #666; font-size: 0.68rem; margin-top: 2px; max-width: 130px; overflow: hidden; text-overflow: ellipsis; }
  .eq-cell-empty { color: #282828; }
  .eq-count-badge { font-size: 0.75rem; color: #444; margin-left: 6px; }
  .eq-clickable:hover { background: rgba(200,212,0,0.1) !important; }
  .eq-clickable.active-cell { background: rgba(200,212,0,0.15) !important; outline: 1px solid #C8D400; }

  .layout {
    display: grid;
    grid-template-columns: minmax(320px, 380px) minmax(0, 1fr);
    gap: 0;
    height: calc(100vh - 65px);
    min-width: 0;
  }

  /* ── PANNEAU GAUCHE ── */
  .panel-wrapper {
    display: flex;
    flex-direction: column;
    background: #222;
    border-right: 1px solid #333;
    overflow: hidden;
    min-width: 0;
  }
  .panel {
    flex: 1;
    overflow-y: auto;
    padding: 20px 20px 8px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    align-content: start;
    align-items: stretch;
  }
  .panel-actions {
    padding: 12px 20px 16px;
    background: #222;
    border-top: 1px solid #2e2e2e;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .panel-actions.sticky {
    position: sticky;
    bottom: 0;
    z-index: 4;
  }
  .action-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
    align-items: stretch;
  }
  .action-grid.two { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .action-grid.four { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1fr) 46px; }
  .action-grid.library-rider { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) 46px; }
  .action-grid .btn,
  .action-grid .btn-undo {
    width: 100%;
    min-width: 0;
    margin-top: 0;
    min-height: 52px;
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    line-height: 1.15;
    letter-spacing: .4px;
  }
  .btn-secondary {
    background: #252800;
    color: #C8D400;
    border: 1px solid #C8D400;
    border-radius: 8px;
    font-size: 0.86rem;
  }
  .btn-secondary:hover:not(:disabled) {
    background: #303400;
    border-color: #dae800;
    color: #dae800;
  }
  .btn-secondary:disabled {
    opacity: .45;
    cursor: not-allowed;
  }

  /* ── Reset par section ── */
  .section-reset-btn {
    font-size: 0.78rem; background: transparent; border: none;
    color: #aaa; cursor: pointer; padding: 2px 7px; border-radius: 4px;
    transition: color .15s, background .15s; margin-right: 2px; flex-shrink: 0;
  }
  .section-reset-btn:hover { color: #C8D400; background: rgba(200,212,0,0.08); }

  /* ── Undo button ── */
  .btn-undo {
    background: transparent; border: 1px solid #2e2e2e; border-radius: 6px;
    color: #555; font-size: 0.78rem; padding: 7px 12px; cursor: pointer;
    transition: all .15s; text-align: center; letter-spacing: 0;
  }
  .btn-undo:hover:not(:disabled) { border-color: #C8D400; color: #C8D400; }
  .btn-undo:disabled { opacity: 0.3; cursor: not-allowed; }

  /* ── Collapsible sections ── */
  .section-title {
    font-size: 0.7rem;
    letter-spacing: 2px;
    color: #C8D400;
    text-transform: uppercase;
    margin-bottom: 8px;
    font-weight: 700;
  }
  .collapsible {
    border: 1px solid #2e2e2e;
    border-radius: 8px;
    overflow: hidden;
    flex-shrink: 0;
  }
  .collapsible-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 9px 12px;
    background: #1e1e1e;
    cursor: pointer;
    user-select: none;
    transition: background .15s;
  }
  .collapsible-header:hover { background: #252525; }
  .collapsible-header .section-title { margin-bottom: 0; }
  .collapsible-arrow {
    font-size: 0.65rem;
    color: #555;
    transition: transform .2s;
    flex-shrink: 0;
  }
  .collapsible.open .collapsible-arrow { transform: rotate(180deg); }
  .collapsible-body {
    display: none;
    padding: 12px;
    border-top: 1px solid #2e2e2e;
  }
  .collapsible.open .collapsible-body { display: block; }

  select, input[type=range] { width: 100%; }

  select {
    background: #2a2a2a;
    color: #eee;
    border: 1px solid #444;
    border-radius: 6px;
    padding: 4px 6px;
    font-size: 0.9rem;
    cursor: pointer;
    width: 100%;
  }
  select:focus { outline: none; border-color: #C8D400; }
  select option { padding: 6px 8px; }
  select option:checked, select option:hover {
    background: #C8D400;
    color: #111;
  }

  /* ── Rider filters ── */
  .rider-filters {
    display: flex;
    gap: 6px;
    margin-bottom: 8px;
    align-items: center;
  }
  .search-input {
    flex: 1;
    background: #1a1a1a;
    border: 1px solid #3a3a3a;
    border-radius: 6px;
    padding: 7px 10px;
    color: #eee;
    font-size: 0.85rem;
    outline: none;
    transition: border-color .15s;
  }
  .search-input:focus { border-color: #C8D400; }
  .search-input::placeholder { color: #555; }
  .gender-toggle {
    display: flex;
    background: #1a1a1a;
    border: 1px solid #3a3a3a;
    border-radius: 6px;
    overflow: hidden;
    flex-shrink: 0;
  }
  .gender-btn {
    padding: 7px 10px;
    font-size: 0.8rem;
    font-weight: 700;
    cursor: pointer;
    color: #555;
    border: none;
    background: transparent;
    transition: all .15s;
    letter-spacing: 0.5px;
  }
  .gender-btn:hover { color: #aaa; }
  .gender-btn.active-f { background: #1a003a; color: #c084fc; }
  .gender-btn.active-m { background: #001a2a; color: #60c0f0; }
  .gender-separator { width: 1px; background: #3a3a3a; }

  .slider-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
  }
  .slider-label { font-size: 0.8rem; color: #aaa; width: 105px; flex-shrink: 0; }
  input.slider-val {
    font-size: 0.82rem; color: #C8D400; width: 50px; text-align: right; flex-shrink: 0;
    background: transparent; border: 1px solid transparent; border-radius: 4px;
    outline: none; padding: 2px 4px; cursor: text; font-family: inherit;
    transition: border-color .15s, background .15s;
    -moz-appearance: textfield;
  }
  input.slider-val:hover { border-color: #3a3a3a; }
  input.slider-val:focus { border-color: #C8D400; background: #1a1a1a; color: #fff; }
  input.slider-val::-webkit-outer-spin-button,
  input.slider-val::-webkit-inner-spin-button { -webkit-appearance: none; }
  input[type=range] {
    accent-color: #C8D400;
    flex: 1;
    height: 4px;
  }

  /* Sponsors */
  .sponsors-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 6px;
    max-height: 280px;
    overflow-y: auto;
    padding-right: 2px;
  }
  .sponsor-chip {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 4px;
    background: #2a2a2a;
    border: 2px solid #3a3a3a;
    border-radius: 8px;
    padding: 8px 4px 5px;
    cursor: pointer;
    transition: all .15s;
    user-select: none;
    position: relative;
  }
  .sponsor-chip:hover { border-color: #777; }
  .sponsor-chip.active { border-color: #C8D400; background: #252800; }
  .sponsor-chip.auto-active { border-color: #555; background: #171717; }
  .sponsor-chip.active::after {
    content: '✓';
    position: absolute;
    top: 2px; right: 5px;
    font-size: 0.65rem;
    color: #C8D400;
  }
  .sponsor-chip input { display: none; }
  .sponsor-chip img {
    width: 100%;
    max-height: 32px;
    object-fit: contain;
    filter: brightness(0) invert(1);
    opacity: 0.7;
    transition: opacity .15s;
  }
  .sponsor-chip.active img { opacity: 1; filter: brightness(0) invert(1) sepia(1) saturate(5) hue-rotate(30deg); }
  .sponsor-chip.auto-active img { opacity: .95; }
  .sponsor-chip span {
    font-size: 0.58rem;
    color: #777;
    text-align: center;
    line-height: 1.1;
    letter-spacing: 0.5px;
  }
  .sponsor-chip.active span { color: #C8D400; }
  .sponsor-chip.auto-active span { color: #bbb; }

  .toggle-switch {
    width: 44px; height: 24px;
    background: #333;
    border-radius: 12px;
    border: 1px solid #555;
    cursor: pointer;
    position: relative;
    transition: background .2s;
    flex-shrink: 0;
  }
  .toggle-switch.on { background: #2f3300; border-color: #C8D400; }
  .toggle-knob {
    width: 18px; height: 18px;
    background: #888;
    border-radius: 50%;
    position: absolute;
    top: 2px; left: 2px;
    transition: left .2s, background .2s;
  }
  .toggle-switch.on .toggle-knob { left: 22px; background: #C8D400; }

  .auto-badge {
    font-size: 0.7rem;
    background: #3a3a00;
    color: #C8D400;
    border-radius: 4px;
    padding: 2px 6px;
    margin-top: 4px;
    display: inline-block;
  }

  /* Boutons */
  .btn {
    width: 100%;
    padding: 12px;
    border: none;
    border-radius: 8px;
    font-size: 1rem;
    font-weight: 700;
    cursor: pointer;
    letter-spacing: 1px;
    transition: all .15s;
  }
  .btn-generate {
    background: #C8D400;
    color: #111;
  }
  .btn-generate:hover { background: #dae800; }
  .btn-generate:active { transform: scale(.97); }
  .btn-download {
    background: #333;
    color: #eee;
    margin-top: 8px;
    border: 1px solid #444;
  }
  .btn-download:hover { border-color: #C8D400; color: #C8D400; }
  .btn-download:disabled { opacity: .4; cursor: not-allowed; }
  .btn-reload {
    background: transparent;
    color: #888;
    border: 1px solid #333;
    font-size: 0.8rem;
    padding: 6px 12px;
    border-radius: 6px;
    cursor: pointer;
    width: auto;
    letter-spacing: 0;
  }
  .btn-reload:hover { color: #C8D400; border-color: #C8D400; }

  /* ── PREVIEW ── */
  .preview-area {
    display: flex;
    align-items: center;
    justify-content: center;
    background: #141414;
    position: relative;
    overflow: hidden;
    min-width: 0;
  }
  .preview-area img {
    max-height: 90vh;
    max-width: 90%;
    border-radius: 4px;
    box-shadow: 0 8px 40px rgba(0,0,0,.6);
    transition: opacity .2s;
  }
  #eq-preview-img {
    max-height: 48vh;
    max-width: 100%;
  }
  .spinner {
    display: none;
    position: absolute;
    top: 50%; left: 50%;
    transform: translate(-50%,-50%);
    font-size: 2rem;
    animation: spin 1s linear infinite;
  }
  @keyframes spin { to { transform: translate(-50%,-50%) rotate(360deg); } }
  .preview-area.loading img { opacity: .3; }
  .preview-area.loading .spinner { display: block; }
  .placeholder {
    color: #444;
    font-size: 1.1rem;
    text-align: center;
  }
  .placeholder span { display: block; font-size: 3rem; margin-bottom: 12px; }

  .error-msg {
    color: #ff6b6b;
    font-size: 0.85rem;
    background: #2a0000;
    border: 1px solid #550000;
    border-radius: 6px;
    padding: 10px;
    margin-top: 8px;
    display: none;
  }
  .error-msg.warning {
    color: #C8D400;
    background: #171a00;
    border-color: #3b4000;
  }

  /* ── Équipements ── */
  .eq-list { display: flex; flex-direction: column; gap: 5px; }
  .eq-item {
    display: flex; align-items: center; gap: 8px;
    background: #1e1e1e; border: 1px solid #2e2e2e;
    border-radius: 7px; padding: 7px 10px; cursor: pointer;
    transition: border-color .15s;
  }
  .eq-item:hover { border-color: #555; }
  .eq-item.selected { border-color: #C8D400; background: #1c1e00; }
  .eq-cat {
    font-size: 0.65rem; color: #666; text-transform: uppercase;
    letter-spacing: 1px; width: 80px; flex-shrink: 0;
  }
  .eq-brand { font-size: 0.8rem; font-weight: 700; color: #C8D400; flex-shrink: 0; min-width: 60px; }
  .eq-ref { font-size: 0.8rem; color: #ccc; flex: 1; }
  .eq-details { font-size: 0.72rem; color: #555; margin-top: 2px; }
  .eq-detail-box {
    background: #1a1a1a; border: 1px solid #2e2e2e; border-radius: 7px;
    padding: 10px 12px; margin-top: 6px; display: none;
  }
  .eq-detail-box.show { display: block; }
  .eq-detail-row { display: flex; gap: 8px; margin-bottom: 4px; align-items: baseline; }
  .eq-detail-label { font-size: 0.68rem; color: #555; text-transform: uppercase; letter-spacing: 1px; width: 70px; flex-shrink: 0; }
  .eq-detail-val { font-size: 0.82rem; color: #eee; }
  .eq-empty { font-size: 0.78rem; color: #444; text-align: center; padding: 12px; }
  .eq-rider-item {
    display: flex; align-items: center; gap: 7px;
    padding: 6px 10px; cursor: pointer; font-size: 12px; color: #ccc;
    border-bottom: 1px solid #111; user-select: none;
  }
  .eq-rider-item:hover { background: #161616; }
  .eq-rider-item.active { background: #1c1e00; color: #C8D400; }
  .eq-rider-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
  .eq-dot-ok      { background: #4CAF50; }
  .eq-dot-partial { background: #f90; }
  .eq-dot-empty   { background: #333; border: 1px solid #444; }
  .eq-dot-loading { background: #555; }
  /* ── Audit table ── */
  #eq-audit-table th {
    background: #111; color: #C8D400; font-size: 10px; letter-spacing: .5px;
    padding: 5px 6px; white-space: nowrap; position: sticky; top: 0; z-index: 1;
    border-bottom: 1px solid #333;
  }
  #eq-audit-table th:first-child { position: sticky; left: 0; z-index: 2; min-width: 110px; }
  #eq-audit-table td {
    padding: 4px 6px; border-bottom: 1px solid #111; text-align: center;
    white-space: nowrap;
  }
  #eq-audit-table td:first-child {
    text-align: left; position: sticky; left: 0;
    background: #0d0d0d; color: #ddd; font-size: 11px; padding-right: 10px;
  }
  #eq-audit-table tr:hover td { background: #141414; }
  #eq-audit-table tr:hover td:first-child { background: #141414; }
  .audit-ok      { font-size: 14px; }
  .audit-nophoto { font-size: 14px; filter: grayscale(1) opacity(.6); }
  .audit-empty   { color: #2a2a2a; font-size: 12px; }
  /* ── Grille photos équipement ── */
  .eq-photo-thumb {
    width: 72px; height: 72px; border-radius: 6px; overflow: hidden;
    border: 2px solid #2a2a2a; cursor: pointer; background: #111;
    transition: border-color .15s, transform .1s; flex-shrink: 0;
  }
  .eq-photo-thumb img { width: 100%; height: 100%; object-fit: contain; padding: 4px; }
  .eq-photo-thumb:hover { border-color: #555; transform: scale(1.04); }
  .eq-photo-thumb.selected { border-color: #C8D400; box-shadow: 0 0 0 1px #C8D400; }
  .eq-photo-name { font-size: 0.58rem; color: #555; text-align: center; margin-top: 2px; max-width: 72px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .asset-tags-grid {
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:16px;
  }
  .asset-tags-card {
    background:#111;
    border:1px solid #2a2a2a;
    border-radius:8px;
    padding:16px;
    min-width:0;
  }
  .asset-tags-card h3 {
    color:#C8D400;
    font-size:.9rem;
    letter-spacing:.08em;
    text-transform:uppercase;
    margin-bottom:10px;
  }
  .asset-tags-stats { color:#777; font-size:12px; margin-bottom:12px; }
  .asset-tags-table { width:100%; border-collapse:collapse; font-size:12px; }
  .asset-tags-table th {
    color:#777;
    font-size:10px;
    text-transform:uppercase;
    letter-spacing:.1em;
    text-align:left;
    border-bottom:1px solid #2a2a2a;
    padding:7px 6px;
  }
  .asset-tags-table td {
    border-bottom:1px solid #202020;
    padding:7px 6px;
    vertical-align:top;
  }
  .asset-tag-ok { color:#C8D400; font-weight:700; }
  .asset-tag-missing { color:#666; }

  /* ── Champs éditables équipement ── */
  .field-row { display: flex; align-items: flex-start; gap: 8px; margin-bottom: 7px; }
  .field-label { font-size: 0.72rem; color: #888; width: 70px; flex-shrink: 0; padding-top: 5px; text-transform: uppercase; letter-spacing: .04em; }
  .field-input {
    flex: 1; background: #1a1a1a; border: 1px solid #2e2e2e; border-radius: 5px;
    color: #eee; font-size: 0.84rem; padding: 5px 8px; outline: none;
    font-family: inherit; transition: border-color .15s;
  }
  .field-input:focus { border-color: #C8D400; }
  textarea.field-input { resize: vertical; min-height: 44px; }

  /* ── Texte toggles équipement ── */
  .eq-text-row { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
  .eq-toggle-wrap { display: flex; align-items: center; gap: 5px; cursor: pointer; flex-shrink: 0; min-width: 90px; }
  .eq-toggle-wrap input[type=checkbox] { accent-color: #C8D400; width: 15px; height: 15px; cursor: pointer; }
  .eq-toggle-label { font-size: 0.72rem; color: #aaa; text-transform: uppercase; letter-spacing: .04em; user-select: none; }
  .eq-text-input {
    flex: 1; background: #1a1a1a; border: 1px solid #2e2e2e; border-radius: 5px;
    color: #eee; font-size: 0.82rem; padding: 4px 8px; outline: none;
    font-family: inherit; transition: border-color .15s;
  }
  .eq-text-input:focus { border-color: #C8D400; }
  .eq-mode-tabs { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 10px; }
  .eq-mode-btn {
    background: #121212; border: 1px solid #333; color: #999; border-radius: 6px;
    padding: 8px 10px; cursor: pointer; font-size: .72rem; font-weight: 800;
    letter-spacing: .08em; text-transform: uppercase;
  }
  .eq-mode-btn.active { border-color: #C8D400; color: #C8D400; background: rgba(200,212,0,.08); }
  .eq-free-controls { display: none; gap: 8px; flex-direction: column; }
  .eq-free-row { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 8px; }
  .eq-select {
    width: 100%; background: #111; border: 1px solid #2e2e2e; border-radius: 6px;
    color: #eee; padding: 8px 9px; outline: none; font: inherit; font-size: .78rem;
  }
  .eq-source-note { color: #777; font-size: 11px; line-height: 1.35; }

  /* ── Color swatches ── */
  .eq-swatch {
    width: 60px; height: 60px; border-radius: 6px; overflow: hidden;
    border: 2px solid #2e2e2e; cursor: pointer; transition: border-color .15s;
    background: #111; flex-shrink: 0;
  }
  .eq-swatch img { width: 100%; height: 100%; object-fit: cover; }
  .eq-swatch:hover { border-color: #666; }
  .eq-swatch.active { border-color: #C8D400; box-shadow: 0 0 0 1px #C8D400; }
  .eq-swatch-label { font-size: 0.6rem; color: #888; text-align: center; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 60px; }

  /* ── Edition inline ── */
  .edit-grid {
    display: grid;
    grid-template-columns: 90px 1fr;
    gap: 5px 8px;
    align-items: start;
  }
  .edit-grid label {
    font-size: 0.73rem;
    color: #777;
    text-align: right;
    padding-top: 6px;
  }
  .edit-input {
    background: #1a1a1a;
    border: 1px solid #3a3a3a;
    border-radius: 5px;
    padding: 5px 8px;
    color: #eee;
    font-size: 0.82rem;
    outline: none;
    width: 100%;
    transition: border-color .15s;
    font-family: inherit;
  }
  .edit-input:focus { border-color: #C8D400; }
  textarea.edit-input { resize: vertical; min-height: 46px; }
  .edit-reset {
    grid-column: 1/-1;
    font-size: 0.72rem;
    color: #555;
    cursor: pointer;
    text-align: right;
    margin-top: 2px;
    transition: color .15s;
  }
  .edit-reset:hover { color: #C8D400; }

  /* ── Verrous sliders ── */
  .lock-btn {
    font-size: 0.8rem; background: transparent; border: none;
    cursor: pointer; color: #383838; padding: 0 1px; flex-shrink: 0;
    transition: color .15s; line-height: 1;
  }
  .lock-btn:hover { color: #888; }
  .lock-btn.locked { color: #C8D400; }
  .slider-row.locked input[type=range],
  .slider-row.locked input.slider-val {
    opacity: 0.45;
    cursor: not-allowed;
  }
  .slider-row.locked input.slider-val { opacity: 0.55; }

  /* ── Profils ── */
  .profile-save-row { display: flex; gap: 6px; margin-bottom: 10px; }
  .profile-name-input {
    flex: 1; background: #1a1a1a; border: 1px solid #3a3a3a;
    border-radius: 5px; padding: 6px 8px; color: #eee;
    font-size: 0.82rem; outline: none; transition: border-color .15s;
    font-family: inherit;
  }
  .profile-name-input:focus { border-color: #C8D400; }
  .btn-save-profile {
    background: #252800; border: 1px solid #3a3a00; border-radius: 5px;
    color: #C8D400; font-size: 0.78rem; font-weight: 700;
    padding: 6px 10px; cursor: pointer; white-space: nowrap;
    transition: all .15s;
  }
  .btn-save-profile:hover { background: #333300; border-color: #C8D400; }
  .profile-list { display: flex; flex-direction: column; gap: 5px; }
  .profile-item {
    display: flex; align-items: center; gap: 6px;
    background: #1e1e1e; border: 1px solid #2e2e2e;
    border-radius: 6px; padding: 6px 8px;
    transition: border-color .15s;
  }
  .profile-item:hover { border-color: #3a3a3a; }
  .profile-item-name {
    flex: 1; font-size: 0.82rem; color: #ccc; cursor: pointer;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .profile-item-name:hover { color: #C8D400; }
  .profile-load-btn {
    font-size: 0.72rem; background: #252800; border: 1px solid #3a3a00;
    border-radius: 4px; color: #C8D400; padding: 3px 7px; cursor: pointer;
    flex-shrink: 0; transition: all .15s;
  }
  .profile-load-btn:hover { background: #333300; }
  .profile-del-btn {
    font-size: 0.75rem; background: transparent; border: none;
    color: #3a3a3a; cursor: pointer; flex-shrink: 0; padding: 2px 4px;
    transition: color .15s;
  }
  .profile-del-btn:hover { color: #ff6b6b; }
  .profile-empty { font-size: 0.78rem; color: #444; text-align: center; padding: 8px; }

  /* ══════════════════════════════════════════
     RESPONSIVE TABLETTE / PETIT DESKTOP
  ══════════════════════════════════════════ */
  @media (max-width: 1280px) {
    header {
      padding: 11px 16px;
      gap: 10px;
    }
    header h1 { font-size: 1.05rem; letter-spacing: 1px; }
    .brand-title { gap: 8px; }
    .tab-btn {
      padding: 6px 12px;
      font-size: 0.76rem;
    }
    .dashboard-btn,
    .btn-reload {
      font-size: 0.76rem;
      padding: 6px 10px;
    }
    .layout {
      grid-template-columns: minmax(300px, 340px) minmax(0, 1fr);
    }
    .panel {
      padding: 16px 16px 7px;
    }
    .panel-actions {
      padding: 10px 16px 14px;
    }
    .perf-wrap { max-width: 100%; }
    .publish-preview-shell {
      grid-template-columns: minmax(0, 1fr) minmax(280px, 320px);
    }
  }

  @media (max-width: 1100px) {
    .perf-overview,
    .perf-grid,
    .perf-infographic,
    .publish-preview-shell {
      grid-template-columns: 1fr;
    }
    #page-publish {
      height: auto;
      min-height: calc(100vh - 65px);
    }
    #page-publish .layout {
      height: auto;
      min-height: calc(100vh - 65px);
    }
    #publish-preview-area {
      overflow: visible !important;
    }
    .publish-preview-media,
    .publish-preview-caption,
    #publish-preview-video {
      max-height: 52vh !important;
    }
    .quality-kpis {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
    .riders-folders,
    .asset-tags-grid {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 920px) {
    header {
      min-height: 58px;
    }
    .tab-nav,
    .dashboard-dropdown {
      display: none;
    }
    .header-right {
      gap: 0;
    }
    .header-right > .btn-reload,
    .header-right > #tab-library {
      display: none;
    }
    .burger-btn {
      display: flex !important;
      align-items: center;
      justify-content: center;
    }
    .brand-mark {
      width: 31px;
      height: 31px;
    }
    .brand-title .version-badge {
      font-size: 0.62rem;
      padding: 2px 7px;
    }
    .layout {
      grid-template-columns: minmax(280px, 330px) minmax(0, 1fr);
    }
    .action-grid,
    .action-grid.two,
    .action-grid.four,
    .action-grid.library-rider,
    .publish-action-row,
    .publish-action-row.compact,
    .eq-free-row {
      grid-template-columns: 1fr;
    }
    .publish-action-stack .btn,
    .action-grid .btn,
    .action-grid .btn-undo {
      min-height: 44px;
    }
    .quality-kpis {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .quality-toolbar,
    .library-toolbar,
    .logos-toolbar {
      align-items: stretch;
    }
    .quality-field,
    .library-field,
    .logos-url-input,
    .quality-toolbar .btn,
    .library-toolbar .btn,
    .logos-toolbar .btn {
      flex: 1 1 100%;
      min-width: 0;
    }
    #page-library,
    #page-logos,
    #page-riders,
    #page-quality,
    #page-settings,
    #page-connections,
    #page-brandtags {
      padding: 20px 16px 40px;
      max-width: 100%;
    }
    #page-logos,
    #page-riders,
    #page-brandtags {
      overflow-x: auto;
    }
    .logos-table,
    .riders-table,
    .asset-tags-table {
      min-width: 760px;
    }
    .settings-card {
      overflow-x: auto;
    }
  }

  @media (max-height: 820px) and (min-width: 769px) {
    #page-equipment .panel,
    #page-cards .panel {
      padding-top: 12px;
      gap: 9px;
    }
    #page-equipment .collapsible-header,
    #page-cards .collapsible-header {
      padding: 8px 10px;
    }
    #page-equipment .collapsible-body,
    #page-cards .collapsible-body {
      padding: 9px;
    }
    #eq-preview-img {
      max-height: 44vh;
    }
    .preview-area img {
      max-height: 84vh;
    }
    .sponsors-grid {
      max-height: 220px;
    }
  }

  /* ══════════════════════════════════════════
     RESPONSIVE MOBILE
  ══════════════════════════════════════════ */
  @media (max-width: 768px) {

    /* ── Header ── */
    header {
      flex-wrap: nowrap;
      padding: 10px 14px 8px;
      gap: 8px;
      row-gap: 6px;
    }
    header h1 { font-size: 0.95rem; letter-spacing: 1px; }
    .brand-title span:not(.version-badge) {
      max-width: 48vw;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .brand-mark { width: 30px; height: 30px; border-radius: 7px; }

    /* Mobile : masquer la nav desktop + dropdown, afficher burger */
    .tab-nav { display: none; }
    .dashboard-dropdown { display: none; }
    .burger-btn { display: flex !important; }

    /* Reload button: compact */
    .btn-reload { font-size: 0.72rem; padding: 5px 9px; }

    /* ── Layout : empilement vertical ── */
    .layout {
      grid-template-columns: 1fr;
      height: auto;
      min-height: 0;
    }

    /* Supprime les hauteurs fixes sur les pages */
    #page-reel { height: auto; min-height: calc(100vh - 58px); }
    #page-reel .layout { height: auto; }
    #page-publish { height: auto; min-height: calc(100vh - 58px); }
    #page-publish .layout { height: auto; }
    #page-equipment { height: auto; min-height: calc(100vh - 58px); overflow: visible; }
    #page-equipment .layout { height: auto; }

    /* ── Panneau gauche : hauteur max + scroll ── */
    .panel-wrapper {
      border-right: none;
      border-bottom: 1px solid #333;
      max-height: 58vh;
      overflow: hidden;
    }
    .panel {
      overflow-y: auto;
      -webkit-overflow-scrolling: touch;
      padding: 14px 14px 6px;
    }
    .panel-actions { padding: 10px 14px 12px; }

    /* ── Prévisualisation sous le panel ── */
    .preview-area {
      min-height: 55vw;
      height: auto;
      padding: 14px;
    }
    .preview-area img {
      max-height: 80vw;
      max-width: 96%;
    }
    #eq-preview-img {
      max-height: 72vw;
    }

    /* ── Sliders : label plus court ── */
    .slider-label { width: 74px; font-size: 0.72rem; }
    input.slider-val { width: 36px; font-size: 0.73rem; }

    /* ── Sponsors : 2 colonnes ── */
    .sponsors-grid { grid-template-columns: repeat(2, 1fr); }

    /* ── Grille édition ── */
    .edit-grid { grid-template-columns: 68px 1fr; }
    .publish-rows { grid-template-columns: 1fr; }
    .publish-select-grid { grid-template-columns: 1fr; }
    .publish-preview-shell { grid-template-columns: 1fr; }
    .publish-preview-side {
      padding: 10px;
    }
    .publish-preview-head {
      align-items: stretch;
      flex-direction: column;
    }
    .publish-copy-mini {
      width: 100%;
    }
    .publish-preview-media,
    .publish-preview-caption,
    #publish-preview-video {
      max-height: 68vh !important;
    }
    #page-performance { padding: 14px; }
    .perf-overview { grid-template-columns:1fr; }
    .perf-event-context { align-items:flex-start; flex-direction:column; }
    .perf-event-latest { text-align:left; }
    .perf-overview-columns { grid-template-columns:1fr; }
    .perf-overview-section + .perf-overview-section { border-left:0; border-top:1px solid #242424; }
    .perf-header { align-items:flex-start; flex-direction:column; }
    .perf-controls,
    .perf-grid,
    .perf-advanced,
    .perf-infographic,
    .perf-info-options,
    .perf-post-actions,
    .quality-kpis,
    .asset-tags-grid { grid-template-columns: 1fr; }
    .perf-infographic-preview {
      min-height: 60vw;
    }
    .perf-table { min-width: 760px; }
    #perf-table-wrap { overflow-x: auto; }
    .action-grid,
    .action-grid.two,
    .action-grid.four { grid-template-columns: 1fr; }

    /* ── Boutons : zones de touch plus grandes ── */
    .btn { padding: 14px; }
    .btn-generate { font-size: 0.92rem; }

    /* ── Barre équipements ── */
    .eq-page-bar { flex-wrap: wrap; }
    .eq-topbar {
      padding: 8px 12px;
    }
    .eq-topbar-btn {
      flex: 1 1 auto;
    }
    .eq-full-table {
      min-width: 980px;
    }
    .quality-daily-head,
    .quality-assets-head {
      align-items: flex-start;
      flex-direction: column;
    }
    .quality-daily-action {
      min-width: 0 !important;
    }
    .library-grid {
      grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    }
    .library-actions {
      grid-template-columns: 1fr;
    }
    .settings-actions .btn {
      flex: 1 1 100%;
    }
  }

  @media (max-width: 420px) {
    header h1 { font-size: 0.82rem; }
    .tab-btn { font-size: 0.65rem; padding: 7px 2px; }
    .slider-label { width: 62px; font-size: 0.68rem; }
    input.slider-val { width: 30px; }
    .panel { padding: 12px 10px 4px; }
    .panel-actions { padding: 8px 10px 10px; }
    .sponsors-grid { grid-template-columns: repeat(2, 1fr); }
    .collapsible-body { padding: 10px; }
  }
</style>
</head>
<body>

<!-- Loading overlay -->
<div id="app-loading" style="
  position:fixed;inset:0;z-index:9999;
  background:#111;display:flex;flex-direction:column;
  align-items:center;justify-content:center;gap:18px">
  <img class="loading-brand-mark" src="/assets/brand/freeride-fanatics-summer.jpg?v=20260721" alt="Freeride Fanatics">
  <div style="color:#C8D400;font-family:'BebasNeue-Regular',sans-serif;font-size:1.6rem;letter-spacing:2px">
    FREERIDE FANATICS
  </div>
  <div id="app-loading-msg" style="color:#666;font-size:0.8rem">Chargement des données…</div>
  <div style="width:200px;height:3px;background:#222;border-radius:2px;overflow:hidden">
    <div id="app-loading-bar" style="height:100%;background:#C8D400;width:0%;transition:width .3s ease"></div>
  </div>
</div>

<header>
  <h1 class="brand-title">
    <img class="brand-mark" src="/assets/brand/freeride-fanatics-summer.jpg?v=20260721" alt="">
    <span>Freeride Fanatics</span>
    <span class="version-badge">V0.8</span>
  </h1>

  <!-- Nav principale (gauche) -->
  <nav class="tab-nav" id="main-tab-nav">
    <button class="tab-btn active" onclick="switchTab('cards')" id="tab-cards">🏔️ Riders</button>
    <button class="tab-btn" onclick="switchTab('equipment')" id="tab-equipment">🔧 Équipements</button>
    <button class="tab-btn" onclick="switchTab('performance')" id="tab-performance">🏆 Performance</button>
    <button class="tab-btn" onclick="switchTab('reel')" id="tab-reel">
      🎬 Reel <span id="reel-badge" style="display:none;background:#C8D400;color:#000;
        border-radius:10px;font-size:0.7rem;padding:1px 6px;margin-left:4px;font-weight:700"></span>
    </button>
    <button class="tab-btn" onclick="switchTab('publish')" id="tab-publish">
      📣 Publish <span id="publish-badge" style="display:none;background:#C8D400;color:#000;
        border-radius:10px;font-size:0.7rem;padding:1px 6px;margin-left:4px;font-weight:700"></span>
    </button>
  </nav>

  <!-- Zone droite -->
  <div class="header-right">
    <button class="btn btn-reload" onclick="reloadExcel()">↺ Recharger</button>
    <button class="dashboard-btn" id="tab-library" onclick="switchTab('library')">
      📚 Library <span id="library-badge" style="display:none;background:#C8D400;color:#000;
        border-radius:10px;font-size:0.68rem;padding:1px 6px;margin-left:4px;font-weight:700"></span>
    </button>

    <!-- Dashboard dropdown (desktop) -->
    <div class="dashboard-dropdown" id="dashboard-dropdown">
      <button class="dashboard-btn" id="dashboard-btn" onclick="toggleDashboard(event)">
        ⚙ Dashboard ▾
      </button>
      <div class="dashboard-menu" id="dashboard-menu">
        <div class="dashboard-section-label">Assets Management</div>
        <button class="dashboard-menu-btn" id="tab-riders" onclick="switchTab('riders'); closeDashboard()">
          👤 Riders
        </button>
        <button class="dashboard-menu-btn" id="tab-logos" onclick="switchTab('logos'); closeDashboard()">
          🖼 Logos
        </button>
        <button class="dashboard-menu-btn" id="tab-quality" onclick="switchTab('quality'); closeDashboard()">
          ✅ Quality Center
        </button>
        <button class="dashboard-menu-btn" id="tab-audit" onclick="switchTab('audit'); closeDashboard()">
          📋 Audit Équipements
        </button>
        <button class="dashboard-menu-btn" id="tab-brandtags" onclick="switchTab('brandtags'); closeDashboard()">
          🏷 Brand & Tags
        </button>
        <div class="dashboard-section-label" style="margin-top:6px">Paramètres</div>
        <button class="dashboard-menu-btn" id="tab-settings" onclick="switchTab('settings'); closeDashboard()">
          ⚙ Paramètres
        </button>
        <button class="dashboard-menu-btn" id="tab-connections" onclick="switchTab('connections'); closeDashboard()">
          🔗 Connexions
        </button>
      </div>
    </div>

    <!-- Burger (mobile uniquement) -->
    <button class="burger-btn" id="burger-btn" onclick="toggleBurger()">☰</button>
  </div>
</header>

<!-- Drawer mobile -->
<div class="burger-drawer" id="burger-drawer">
  <div class="burger-overlay" onclick="closeBurger()"></div>
  <div class="burger-panel">
    <button class="burger-item" id="burger-cards" onclick="switchTab('cards'); closeBurger()">🏔️ Riders</button>
    <button class="burger-item" id="burger-equipment" onclick="switchTab('equipment'); closeBurger()">🔧 Équipements</button>
    <button class="burger-item" id="burger-performance" onclick="switchTab('performance'); closeBurger()">🏆 Performance</button>
    <button class="burger-item" id="burger-reel" onclick="switchTab('reel'); closeBurger()">🎬 Reel</button>
    <button class="burger-item" id="burger-publish" onclick="switchTab('publish'); closeBurger()">
      📣 Publish <span id="burger-publish-badge" style="display:none;background:#C8D400;color:#000;
        border-radius:10px;font-size:0.65rem;padding:1px 5px;margin-left:4px;font-weight:700"></span>
    </button>
    <button class="burger-item" id="burger-library" onclick="switchTab('library'); closeBurger()">
      📚 Library <span id="burger-library-badge" style="display:none;background:#C8D400;color:#000;
        border-radius:10px;font-size:0.65rem;padding:1px 5px;margin-left:4px;font-weight:700"></span>
    </button>
    <div class="burger-divider">Assets Management</div>
    <button class="burger-item" id="burger-riders" onclick="switchTab('riders'); closeBurger()">👤 Riders</button>
    <button class="burger-item" id="burger-logos" onclick="switchTab('logos'); closeBurger()">🖼 Logos</button>
    <button class="burger-item" id="burger-quality" onclick="switchTab('quality'); closeBurger()">✅ Quality Center</button>
    <button class="burger-item" id="burger-audit" onclick="switchTab('audit'); closeBurger()">📋 Audit Équipements</button>
    <button class="burger-item" id="burger-brandtags" onclick="switchTab('brandtags'); closeBurger()">🏷 Brand & Tags</button>
    <div class="burger-divider">Paramètres</div>
    <button class="burger-item" id="burger-settings" onclick="switchTab('settings'); closeBurger()">⚙ Paramètres</button>
    <button class="burger-item" id="burger-connections" onclick="switchTab('connections'); closeBurger()">🔗 Connexions</button>
  </div>
</div>

<div class="layout" id="page-cards">

  <!-- PANNEAU GAUCHE -->
  <div class="panel-wrapper">
  <div class="panel">

    <!-- Rider -->
    <div class="collapsible open" id="col-rider">
      <div class="collapsible-header" onclick="toggleCol('col-rider')">
        <span class="section-title">Rider</span>
        <span class="collapsible-arrow">▼</span>
      </div>
      <div class="collapsible-body">
        <div class="rider-filters">
          <input class="search-input" id="rider-search" placeholder="🔍 Rechercher..." oninput="renderRiderList()">
          <div class="gender-toggle">
            <button class="gender-btn" id="btn-f" onclick="setGender('F')" title="Women">♀</button>
            <div class="gender-separator"></div>
            <button class="gender-btn" id="btn-m" onclick="setGender('M')" title="Men">♂</button>
          </div>
        </div>
        <select id="rider" onchange="onRiderChange()" size="8"
          style="height:160px;border-radius:6px;padding:4px 0">
        </select>
        <div style="font-size:0.7rem;color:#555;margin-top:5px">· = photo manquante</div>
      </div>
    </div>

    <!-- Profils -->
    <div class="collapsible" id="col-profiles">
      <div class="collapsible-header" onclick="toggleCol('col-profiles')">
        <span class="section-title">💾 Profils</span>
        <span class="collapsible-arrow">▼</span>
      </div>
      <div class="collapsible-body">
        <div class="profile-save-row">
          <input type="text" class="profile-name-input" id="profile-name" placeholder="Nom du profil...">
          <button class="btn-save-profile" onclick="saveProfile()">Sauvegarder</button>
        </div>
        <div class="profile-list" id="profile-list">
          <div class="profile-empty">Aucun profil sauvegardé</div>
        </div>
      </div>
    </div>

    <!-- Édition inline -->
    <div class="collapsible" id="col-edit" style="display:none">
      <div class="collapsible-header" onclick="toggleCol('col-edit')">
        <span class="section-title">✏️ Forcer les infos</span>
        <span class="collapsible-arrow">▼</span>
      </div>
      <div class="collapsible-body">
        <div class="edit-grid">
          <label>Prénom</label>
          <input id="ed_prenom" class="edit-input" type="text" placeholder="—">
          <label>Nom</label>
          <input id="ed_nom" class="edit-input" type="text" placeholder="—">
          <label>Nationalité</label>
          <input id="ed_nationality" class="edit-input" type="text" placeholder="—">
          <label>Hometown</label>
          <input id="ed_hometown" class="edit-input" type="text" placeholder="—">
          <label>Âge</label>
          <input id="ed_age" class="edit-input" type="text" placeholder="—">
          <label>Palmarès</label>
          <textarea id="ed_achievements" class="edit-input" rows="2" placeholder="—"></textarea>
          <label>Team</label>
          <input id="ed_team" class="edit-input" type="text" placeholder="—">
          <span class="edit-reset" onclick="resetEdits()">↺ Réinitialiser</span>
        </div>
      </div>
    </div>

    <!-- Équipements -->
    <div class="collapsible" id="col-equipment" style="display:none">
      <div class="collapsible-header" onclick="toggleCol('col-equipment')">
        <span class="section-title">🔧 Équipements</span>
        <span class="collapsible-arrow">▼</span>
      </div>
      <div class="collapsible-body">
        <div class="eq-list" id="eq-list">
          <div class="eq-empty">Sélectionne un rider</div>
        </div>
        <div class="eq-detail-box" id="eq-detail-box">
          <div class="eq-detail-row"><span class="eq-detail-label">Brand</span><span class="eq-detail-val" id="eq-d-brand">—</span></div>
          <div class="eq-detail-row"><span class="eq-detail-label">Reference</span><span class="eq-detail-val" id="eq-d-ref">—</span></div>
          <div class="eq-detail-row"><span class="eq-detail-label">Details</span><span class="eq-detail-val" id="eq-d-det">—</span></div>
        </div>
      </div>
    </div>

    <!-- Sponsors -->
    <div class="collapsible" id="col-sponsors">
      <div class="collapsible-header" onclick="toggleCol('col-sponsors')">
        <span class="section-title">Marques &nbsp;<span id="sponsor-mode" class="auto-badge" style="font-size:0.65rem;padding:1px 5px">AUTO</span></span>
        <span class="collapsible-arrow">▼</span>
      </div>
      <div class="collapsible-body">
        <input type="text" id="sponsor-search" placeholder="🔍 Rechercher une marque..." oninput="filterSponsors(this.value)"
          style="width:100%;background:#1a1a1a;border:1px solid #3a3a3a;border-radius:6px;padding:7px 10px;color:#eee;font-size:0.82rem;margin-bottom:8px;outline:none">
        <div class="sponsors-grid" id="sponsors-grid"></div>
        <div id="sponsor-empty" style="display:none;font-size:0.8rem;color:#555;text-align:center;padding:8px">Aucun logo trouvé</div>
      </div>
    </div>

    <!-- Photo -->
    <div class="collapsible" id="col-photo">
      <div class="collapsible-header" onclick="toggleCol('col-photo')">
        <span class="section-title">Photo</span>
        <div style="display:flex;align-items:center;gap:2px">
          <button class="section-reset-btn" onclick="event.stopPropagation();resetSection('photo')" title="Réinitialiser Photo">↺</button>
          <span class="collapsible-arrow">▼</span>
        </div>
      </div>
      <div class="collapsible-body">
        <div class="slider-row">
          <span class="slider-label">Zoom</span>
          <input type="range" id="photo_zoom" min="50" max="300" value="100" onmousedown="captureHistory()" oninput="updateSliderPct(this,'val_zoom')">
          <input type="text" class="slider-val" id="val_zoom" value="100%" onfocus="this.select()" onchange="syncVal('val_zoom','photo_zoom',true)">
          <button class="lock-btn" id="lock_photo_zoom" onclick="toggleLock('lock_photo_zoom','photo_zoom')" title="Verrouiller">🔓</button>
        </div>
        <div class="slider-row">
          <span class="slider-label">Offset X</span>
          <input type="range" id="offset_x" min="-600" max="600" value="-200" onmousedown="captureHistory()" oninput="updateSlider(this,'val_x')">
          <input type="text" class="slider-val" id="val_x" value="-200" onfocus="this.select()" onchange="syncVal('val_x','offset_x')">
          <button class="lock-btn" id="lock_offset_x" onclick="toggleLock('lock_offset_x','offset_x')" title="Verrouiller">🔓</button>
        </div>
        <div class="slider-row">
          <span class="slider-label">Offset Y</span>
          <input type="range" id="offset_y" min="-600" max="600" value="0" onmousedown="captureHistory()" oninput="updateSlider(this,'val_y')">
          <input type="text" class="slider-val" id="val_y" value="0" onfocus="this.select()" onchange="syncVal('val_y','offset_y')">
          <button class="lock-btn" id="lock_offset_y" onclick="toggleLock('lock_offset_y','offset_y')" title="Verrouiller">🔓</button>
        </div>
      </div>
    </div>

    <!-- Texte -->
    <div class="collapsible" id="col-text">
      <div class="collapsible-header" onclick="toggleCol('col-text')">
        <span class="section-title">Texte</span>
        <div style="display:flex;align-items:center;gap:2px">
          <button class="section-reset-btn" onclick="event.stopPropagation();resetSection('text')" title="Réinitialiser Texte">↺</button>
          <span class="collapsible-arrow">▼</span>
        </div>
      </div>
      <div class="collapsible-body">
        <div class="slider-row">
          <span class="slider-label">Position X</span>
          <input type="range" id="text_x" min="400" max="900" value="580" onmousedown="captureHistory()" oninput="updateSlider(this,'val_tx')">
          <input type="text" class="slider-val" id="val_tx" value="580" onfocus="this.select()" onchange="syncVal('val_tx','text_x')">
          <button class="lock-btn" id="lock_text_x" onclick="toggleLock('lock_text_x','text_x')" title="Verrouiller">🔓</button>
        </div>
        <div class="slider-row">
          <span class="slider-label">Position Y</span>
          <input type="range" id="text_top" min="0" max="400" value="80" onmousedown="captureHistory()" oninput="updateSlider(this,'val_tt')">
          <input type="text" class="slider-val" id="val_tt" value="80" onfocus="this.select()" onchange="syncVal('val_tt','text_top')">
          <button class="lock-btn" id="lock_text_top" onclick="toggleLock('lock_text_top','text_top')" title="Verrouiller">🔓</button>
        </div>
        <div class="slider-row">
          <span class="slider-label">Taille titre</span>
          <input type="range" id="sz_label" min="14" max="72" value="36" onmousedown="captureHistory()" oninput="updateSlider(this,'val_sl')">
          <input type="text" class="slider-val" id="val_sl" value="36" onfocus="this.select()" onchange="syncVal('val_sl','sz_label')">
          <button class="lock-btn" id="lock_sz_label" onclick="toggleLock('lock_sz_label','sz_label')" title="Verrouiller">🔓</button>
        </div>
        <div class="slider-row">
          <span class="slider-label">Taille valeur</span>
          <input type="range" id="sz_value" min="14" max="90" value="54" onmousedown="captureHistory()" oninput="updateSlider(this,'val_sv')">
          <input type="text" class="slider-val" id="val_sv" value="54" onfocus="this.select()" onchange="syncVal('val_sv','sz_value')">
          <button class="lock-btn" id="lock_sz_value" onclick="toggleLock('lock_sz_value','sz_value')" title="Verrouiller">🔓</button>
        </div>
        <div class="slider-row">
          <span class="slider-label">Taille valeur SM</span>
          <input type="range" id="sz_value_sm" min="14" max="72" value="40" onmousedown="captureHistory()" oninput="updateSlider(this,'val_ss')">
          <input type="text" class="slider-val" id="val_ss" value="40" onfocus="this.select()" onchange="syncVal('val_ss','sz_value_sm')">
          <button class="lock-btn" id="lock_sz_value_sm" onclick="toggleLock('lock_sz_value_sm','sz_value_sm')" title="Verrouiller">🔓</button>
        </div>
        <div class="slider-row">
          <span class="slider-label">Espacement</span>
          <input type="range" id="gap" min="0" max="80" value="50" onmousedown="captureHistory()" oninput="updateSlider(this,'val_gap')">
          <input type="text" class="slider-val" id="val_gap" value="50" onfocus="this.select()" onchange="syncVal('val_gap','gap')">
          <button class="lock-btn" id="lock_gap" onclick="toggleLock('lock_gap','gap')" title="Verrouiller">🔓</button>
        </div>
      </div>
    </div>

    <!-- Logos -->
    <div class="collapsible" id="col-logos">
      <div class="collapsible-header" onclick="toggleCol('col-logos')">
        <span class="section-title">Logos</span>
        <div style="display:flex;align-items:center;gap:2px">
          <button class="section-reset-btn" onclick="event.stopPropagation();resetSection('logos')" title="Réinitialiser Logos">↺</button>
          <span class="collapsible-arrow">▼</span>
        </div>
      </div>
      <div class="collapsible-body">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">
          <span style="font-size:0.8rem;color:#aaa">Disposition</span>
          <div class="toggle-switch" onclick="switchDir()" id="dir-toggle" title="Cliquer pour changer">
            <div class="toggle-knob"></div>
          </div>
          <span id="dir-label" style="font-size:0.82rem;font-weight:700;color:#C8D400;min-width:70px">▶▶ LIGNE</span>
          <input type="hidden" id="logo_dir" value="row">
        </div>
        <div class="slider-row">
          <span class="slider-label">Hauteur</span>
          <input type="range" id="logo_h" min="20" max="200" value="50" onmousedown="captureHistory()" oninput="updateSlider(this,'val_lh')">
          <input type="text" class="slider-val" id="val_lh" value="50" onfocus="this.select()" onchange="syncVal('val_lh','logo_h')">
          <button class="lock-btn" id="lock_logo_h" onclick="toggleLock('lock_logo_h','logo_h')" title="Verrouiller">🔓</button>
        </div>
        <div class="slider-row">
          <span class="slider-label">Position Y</span>
          <input type="range" id="logo_y" min="0" max="1350" value="1200" onmousedown="captureHistory()" oninput="updateSlider(this,'val_ly')">
          <input type="text" class="slider-val" id="val_ly" value="1200" onfocus="this.select()" onchange="syncVal('val_ly','logo_y')">
          <button class="lock-btn" id="lock_logo_y" onclick="toggleLock('lock_logo_y','logo_y')" title="Verrouiller">🔓</button>
        </div>
        <div class="slider-row">
          <span class="slider-label">Position X</span>
          <input type="range" id="logo_x" min="-1" max="1080" value="810" onmousedown="captureHistory()" oninput="updateSlider(this,'val_lx',true)">
          <input type="text" class="slider-val" id="val_lx" value="810" onfocus="this.select()" onchange="syncVal('val_lx','logo_x',true)">
          <button class="lock-btn" id="lock_logo_x" onclick="toggleLock('lock_logo_x','logo_x')" title="Verrouiller">🔓</button>
        </div>
      </div>
    </div>

  </div><!-- fin .panel -->

  <!-- Actions fixées en bas -->
  <div class="panel-actions sticky">
    <button class="btn btn-generate" onclick="generate()">▶ Générer la carte</button>
    <div class="action-grid library-rider">
      <button class="btn btn-download" id="btn-dl" disabled onclick="download()">⬇ Télécharger</button>
      <button class="btn btn-secondary" id="cards-add-library-btn" disabled onclick="addRiderCardToLibrary()">
        ＋ Library
      </button>
      <button class="btn-undo" id="btn-undo" disabled onclick="undo()" title="Ctrl+Z">↩</button>
    </div>
    <div class="error-msg" id="error-msg"></div>
  </div>

  </div><!-- fin .panel-wrapper -->

  <!-- PREVIEW -->
  <div class="preview-area" id="preview-area">
    <div class="spinner">⚙</div>
    <div class="placeholder" id="placeholder">
      <span>🏔️</span>
      Sélectionne un rider et clique Générer
    </div>
    <img id="preview-img" src="" style="display:none" alt="Preview">
  </div>

</div>

<!-- ═══════════════════════════════════════════════════════════════════════ -->
<!-- PAGE ÉQUIPEMENTS                                                        -->
<!-- ═══════════════════════════════════════════════════════════════════════ -->
<div id="page-equipment" style="display:none">

<!-- Barre de contrôle équipements -->
<div class="eq-topbar">
  <span class="eq-topbar-title">🔧 ÉQUIPEMENTS</span>
  <button class="eq-topbar-btn" onclick="rescanEqPhotos()">
    📸 Rescan photos
  </button>
  <button class="eq-topbar-btn" onclick="reloadEqData()">
    ↺ Actualiser le Sheet
  </button>
</div>

<div class="layout">

  <div class="panel-wrapper">
  <div class="panel">

    <!-- Source -->
    <div class="collapsible open" id="eqcol-rider">
      <div class="collapsible-header" onclick="toggleCol('eqcol-rider')">
        <span class="section-title">Source</span><span class="collapsible-arrow">▼</span>
      </div>
      <div class="collapsible-body">
        <div class="eq-mode-tabs">
          <button class="eq-mode-btn active" id="eq-mode-rider" onclick="setEqMode('rider')">Rider</button>
          <button class="eq-mode-btn" id="eq-mode-free" onclick="setEqMode('free')">Libre</button>
        </div>
        <div id="eq-rider-controls">
          <div class="rider-filters">
            <input class="search-input" id="eq-rider-search" placeholder="🔍 Rechercher…" oninput="renderEqRiderList()">
            <div class="gender-toggle">
              <button class="gender-btn" id="eq-btn-f" onclick="setEqGender('F')">♀</button>
              <div class="gender-separator"></div>
              <button class="gender-btn" id="eq-btn-m" onclick="setEqGender('M')">♂</button>
            </div>
          </div>
          <div id="eq-rider-select"
            style="height:200px;overflow-y:auto;border:1px solid #2a2a2a;border-radius:6px;background:#0d0d0d"></div>
        </div>
      </div>
    </div>

    <!-- Équipements -->
    <div class="collapsible open" id="eqcol-items">
      <div class="collapsible-header" onclick="toggleCol('eqcol-items')">
        <span class="section-title">🔧 Équipement</span><span class="collapsible-arrow">▼</span>
      </div>
      <div class="collapsible-body">
        <div class="eq-free-controls" id="eq-free-controls">
          <div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.05em">Catégorie d’équipement</div>
          <div class="eq-free-row">
            <select class="eq-select" id="eq-free-category" onchange="renderEqFreeList(true)"></select>
            <input class="search-input" id="eq-free-search" placeholder="🔍 Marque ou modèle…" oninput="renderEqFreeList(false)">
          </div>
          <div class="eq-source-note" id="eq-free-note">Choisis une catégorie issue du Google Sheet, puis un équipement.</div>
        </div>
        <div class="eq-list" id="eq-page-list">
          <div class="eq-empty">Sélectionne un rider ou passe en mode libre</div>
        </div>
        <!-- Variantes couleur -->
        <div id="eq-color-variants" style="display:none;margin-top:10px">
          <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:6px">
            <div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.05em">🎨 Variante</div>
            <label class="eq-toggle-wrap" style="min-width:auto;font-size:10px;color:#aaa">
              <input type="checkbox" id="eq_force_category_variants"
                     onchange="if (_eqSelectedItem) { loadColorVariants(_eqSelectedItem); eqDebouncedGenerate(100); }">
              <span class="eq-toggle-label">Choix manuel catégorie</span>
            </label>
          </div>
          <div id="eq-color-swatches" style="display:flex;flex-wrap:wrap;gap:6px"></div>
        </div>
      </div>
    </div>

    <!-- Texte controls -->
    <div class="collapsible open" id="eqcol-textctrl">
      <div class="collapsible-header" onclick="toggleCol('eqcol-textctrl')">
        <span class="section-title">✏️ Texte</span><span class="collapsible-arrow">▼</span>
      </div>
      <div class="collapsible-body">
        <div class="eq-text-row">
          <label class="eq-toggle-wrap">
            <input type="checkbox" id="eq_show_brand" checked onchange="eqDebouncedGenerate()">
            <span class="eq-toggle-label">Brand</span>
          </label>
          <input type="text" class="eq-text-input" id="eq_brand_text" placeholder="Brand…" oninput="eqDebouncedGenerate()">
        </div>
        <div class="eq-text-row">
          <label class="eq-toggle-wrap">
            <input type="checkbox" id="eq_show_reference" checked onchange="eqDebouncedGenerate()">
            <span class="eq-toggle-label">Produit</span>
          </label>
          <input type="text" class="eq-text-input" id="eq_reference_text" placeholder="Référence…" oninput="eqDebouncedGenerate()">
        </div>
        <div class="eq-text-row">
          <label class="eq-toggle-wrap">
            <input type="checkbox" id="eq_show_details" checked onchange="eqDebouncedGenerate()">
            <span class="eq-toggle-label">Détails</span>
          </label>
          <input type="text" class="eq-text-input" id="eq_details_text" placeholder="Détails…" oninput="eqDebouncedGenerate()">
        </div>
        <div class="eq-text-row" style="margin-top:6px">
          <label class="eq-toggle-wrap">
            <input type="checkbox" id="eq_show_logo" onchange="eqDebouncedGenerate();toggleEqLogoControls()">
            <span class="eq-toggle-label">Logo marque</span>
          </label>
        </div>
        <div id="eq-logo-controls" style="display:none;margin-top:8px;padding-top:8px;border-top:1px solid #1e1e1e">
          <div class="slider-row">
            <span class="slider-label">Hauteur</span>
            <input type="range" id="eq_logo_h" min="20" max="150" value="60"
              oninput="updateSlider(this,'eq_val_lh');eqDebouncedGenerate()">
            <input type="text" class="slider-val" id="eq_val_lh" value="60"
              onfocus="this.select()" onchange="syncVal('eq_val_lh','eq_logo_h');eqDebouncedGenerate()">
          </div>
          <div class="slider-row">
            <span class="slider-label">Position Y</span>
            <input type="range" id="eq_logo_y" min="900" max="1320" value="1200"
              oninput="updateSlider(this,'eq_val_ly');eqDebouncedGenerate()">
            <input type="text" class="slider-val" id="eq_val_ly" value="1200"
              onfocus="this.select()" onchange="syncVal('eq_val_ly','eq_logo_y');eqDebouncedGenerate()">
          </div>
          <div class="slider-row">
            <span class="slider-label">Position X</span>
            <input type="range" id="eq_logo_x" min="-1" max="1060" value="-1"
              oninput="updateSlider(this,'eq_val_lx',true);eqDebouncedGenerate()">
            <input type="text" class="slider-val" id="eq_val_lx" value="Auto"
              onfocus="this.select()" onchange="syncVal('eq_val_lx','eq_logo_x',true);eqDebouncedGenerate()">
          </div>
        </div>
        <div class="eq-text-row" style="margin-top:10px;border-top:1px solid #333;padding-top:10px">
          <label class="eq-toggle-wrap">
            <input type="checkbox" id="eq_rider_selection" onchange="eqDebouncedGenerate();toggleEqRiderSelectionControls()">
            <span class="eq-toggle-label">Rider's Selection</span>
          </label>
        </div>
        <div id="eq-rider-selection-controls" style="display:none;margin-top:8px;padding-top:8px;border-top:1px solid #1e1e1e">
          <div style="font-size:0.7rem;color:#666;text-transform:uppercase;letter-spacing:.04em;margin-bottom:4px">
            PP du rider sélectionné
          </div>
          <div class="slider-row">
            <span class="slider-label">Taille PP</span>
            <input type="range" id="eq_badge_radius" min="30" max="120" value="58"
              oninput="updateSlider(this,'eq_val_badge_r');eqDebouncedGenerate()">
            <input type="text" class="slider-val" id="eq_val_badge_r" value="58"
              onfocus="this.select()" onchange="syncVal('eq_val_badge_r','eq_badge_radius');eqDebouncedGenerate()">
          </div>
        </div>
      </div>
    </div>

    <!-- Photo controls -->
    <div class="collapsible open" id="eqcol-photoctrl">
      <div class="collapsible-header" onclick="toggleCol('eqcol-photoctrl')">
        <span class="section-title">🖼 Photo</span><span class="collapsible-arrow">▼</span>
      </div>
      <div class="collapsible-body">
        <div class="slider-row">
          <span class="slider-label">Zoom</span>
          <input type="range" id="eq_zoom" min="30" max="300" value="100" oninput="updateSlider(this,'eq_val_zoom');eqDebouncedGenerate()">
          <input type="text" class="slider-val" id="eq_val_zoom" value="100" onfocus="this.select()" onchange="syncVal('eq_val_zoom','eq_zoom');eqDebouncedGenerate()">
        </div>
        <div class="slider-row">
          <span class="slider-label">Position X</span>
          <input type="range" id="eq_photo_x" min="-500" max="500" value="0" oninput="updateSlider(this,'eq_val_px');eqDebouncedGenerate()">
          <input type="text" class="slider-val" id="eq_val_px" value="0" onfocus="this.select()" onchange="syncVal('eq_val_px','eq_photo_x');eqDebouncedGenerate()">
        </div>
        <div class="slider-row">
          <span class="slider-label">Position Y</span>
          <input type="range" id="eq_photo_y" min="-500" max="500" value="0" oninput="updateSlider(this,'eq_val_py');eqDebouncedGenerate()">
          <input type="text" class="slider-val" id="eq_val_py" value="0" onfocus="this.select()" onchange="syncVal('eq_val_py','eq_photo_y');eqDebouncedGenerate()">
        </div>
        <div class="slider-row" style="align-items:center">
          <span class="slider-label">Fond photo</span>
          <div style="display:flex;gap:6px;align-items:center;flex:1">
            <button class="eq-bg-preset" data-color="#ffffff" onclick="setEqBg('#ffffff')"
              style="background:#fff;border:2px solid #C8D400;width:24px;height:24px;border-radius:4px;cursor:pointer;flex-shrink:0" title="Blanc"></button>
            <button class="eq-bg-preset" data-color="#000000" onclick="setEqBg('#000000')"
              style="background:#000;border:2px solid #444;width:24px;height:24px;border-radius:4px;cursor:pointer;flex-shrink:0" title="Noir"></button>
            <input type="color" id="eq_photo_bg" value="#ffffff"
              style="width:36px;height:24px;border:none;border-radius:4px;cursor:pointer;background:none;padding:0;flex-shrink:0"
              oninput="eqDebouncedGenerate()" title="Couleur personnalisée">
          </div>
        </div>
      </div>
    </div>

  </div><!-- fin .panel -->

  <div class="panel-actions sticky">
    <button class="btn btn-generate" onclick="generateEqCard()">▶ Générer la carte</button>
    <div class="action-grid">
      <button class="btn btn-download" id="eq-page-dl-btn" disabled onclick="downloadEqCard()">⬇ Télécharger</button>
      <button class="btn btn-secondary" id="eq-add-library-btn" disabled onclick="addEqCardToLibrary()">
        ＋ Library
      </button>
    </div>
    <div class="error-msg" id="eq-error-msg"></div>
  </div>
  </div><!-- fin .panel-wrapper -->

  <div class="preview-area" id="eq-preview-area">
    <div class="spinner">⚙</div>
    <div class="placeholder" id="eq-placeholder">
      <span>🔧</span>
      Sélectionne un rider,<br>choisis un item,<br>clique Générer
    </div>
    <img id="eq-preview-img" src="" style="display:none" alt="Equipment Card">
  </div>

</div><!-- fin .layout -->


</div><!-- fin #page-equipment -->

<!-- ═══════════════════════════════════════════════════════════════════════ -->
<!-- PAGE PERFORMANCE ÉQUIPEMENTS                                           -->
<!-- ═══════════════════════════════════════════════════════════════════════ -->
<div id="page-performance">
  <div class="perf-wrap">
    <div class="perf-header">
      <div>
        <div class="perf-title">🏆 Equipment Performance</div>
        <div class="perf-sub">
          Sélectionne un classement et une catégorie pour voir les 3 équipements qui ressortent le mieux selon les points 2026.
        </div>
        <div class="perf-status" id="perf-status">Synchronisation automatique active quand l’onglet est ouvert.</div>
      </div>
      <button class="eq-topbar-btn" onclick="refreshPerformanceData(false)">↺ Actualiser maintenant</button>
    </div>

    <div class="perf-event-context" id="perf-event-context"></div>
    <div class="perf-overview" id="perf-overview"></div>

    <div class="perf-analysis-title">Analyse par équipement</div>

    <div class="perf-controls">
      <div class="perf-control">
        <label for="perf-view">Vue</label>
        <select id="perf-view" class="perf-select" onchange="syncPerformanceInfographicOptions(); renderPerformance()">
          <option value="equipment" selected>Équipements</option>
          <option value="riders">Riders</option>
          <option value="teams">Teams DH</option>
        </select>
      </div>
      <div class="perf-control">
        <label for="perf-gender">Classement</label>
        <select id="perf-gender" class="perf-select" onchange="populatePerformanceInfoFields(); renderPerformance()">
          <option value="F">Femmes</option>
          <option value="M">Hommes</option>
          <option value="all">Mixte</option>
        </select>
      </div>
      <div class="perf-control">
        <label for="perf-category">Catégorie</label>
        <select id="perf-category" class="perf-select" onchange="populatePerformanceInfoFields(); renderPerformance()">
        </select>
      </div>
    </div>

    <button class="perf-advanced-toggle" id="perf-advanced-toggle" onclick="togglePerformanceAdvanced()">
      ▸ Advanced
    </button>

    <div class="perf-advanced" id="perf-advanced">
      <div class="perf-control">
        <label for="perf-scope">Section</label>
        <select id="perf-scope" class="perf-select" onchange="populatePerformanceInfoFields(); renderPerformance()">
          <option value="season" selected>Saison 2026</option>
          <option value="last_race">Last race</option>
        </select>
      </div>
      <div class="perf-control">
        <label for="perf-top">Fenêtre riders</label>
        <select id="perf-top" class="perf-select" onchange="renderPerformance()">
          <option value="3">Top 3 riders</option>
          <option value="5">Top 5 riders</option>
          <option value="10" selected>Top 10 riders</option>
          <option value="20">Top 20 riders</option>
          <option value="all">Tous les classés</option>
        </select>
      </div>
      <div class="perf-control">
        <label for="perf-group">Groupement</label>
        <select id="perf-group" class="perf-select" onchange="renderPerformance()">
          <option value="product">Produit complet</option>
          <option value="brand">Marque</option>
        </select>
      </div>
      <div class="perf-control">
        <label for="perf-sort">Tri</label>
        <select id="perf-sort" class="perf-select" onchange="renderPerformance()">
          <option value="points">Points cumulés</option>
          <option value="count">Présence</option>
          <option value="avg_rank">Meilleur rang moyen</option>
          <option value="best_rank">Meilleur rider</option>
        </select>
      </div>
    </div>

    <div class="perf-infographic">
      <div class="perf-info-menu">
        <h3>Infographie classement</h3>
        <p>
          Format vertical prêt pour Instagram. Le visuel reprend l’esprit classement barres,
          en version Freeride Fanatics : fond sombre, grille technique, rangs, points et présence riders.
        </p>
        <div class="perf-info-options">
          <div class="perf-info-options-title">Informations affichées</div>
          <label><input type="checkbox" id="perf-info-show-subtitle" checked> Sous-titre</label>
          <label><input type="checkbox" id="perf-info-show-competition" checked> Compétition</label>
          <label><input type="checkbox" id="perf-info-show-bars" checked> Barres</label>
          <label><input type="checkbox" id="perf-info-show-points" checked> Points</label>
          <label><input type="checkbox" id="perf-info-show-count" checked> Riders</label>
          <label><input type="checkbox" id="perf-info-show-percent"> Pourcentage</label>
        </div>
        <div class="perf-info-fields">
          <label>
            <span>Arrière-plan</span>
            <select id="perf-info-background">
              <option value="technical" selected>Technique</option>
              <option value="glow">Glow subtil</option>
              <option value="editorial">Editorial</option>
            </select>
          </label>
          <label>
            <span>Compétition</span>
            <input type="text" id="perf-info-competition" list="perf-info-competition-list" placeholder="Ex. Val di Sole World Cup">
            <datalist id="perf-info-competition-list"></datalist>
          </label>
          <label>
            <span>Catégorie</span>
            <input type="text" id="perf-info-category-label" placeholder="Ex. Elite Women DH">
          </label>
        </div>
        <div class="perf-infographic-actions">
          <button class="btn btn-generate" onclick="generatePerformanceInfographic()">▶ Générer l’infographie</button>
          <button class="btn btn-download" id="perf-info-download-btn" disabled onclick="downloadPerformanceInfographic()">⬇ Télécharger</button>
          <button class="btn btn-secondary" id="perf-info-library-btn" disabled onclick="addPerformanceInfographicToLibrary()">＋ Library</button>
        </div>
        <div class="publish-meta" id="perf-infographic-status"></div>
      </div>
      <div class="perf-infographic-preview" id="perf-infographic-preview">
        <div class="perf-empty">Génère une infographie Top 10 depuis le classement sélectionné.</div>
      </div>
      <div class="perf-post-panel">
        <h3>Texte post</h3>
        <p>
          Génère une caption basée sur le classement affiché, puis copie-la pour Instagram.
        </p>
        <textarea id="perf-post-text" class="perf-post-textarea" placeholder="Le texte du post sera généré ici..."></textarea>
        <div class="perf-post-actions">
          <button class="btn btn-secondary" onclick="generatePerformancePostText()">✎ Générer texte</button>
          <button class="btn btn-secondary" id="perf-post-copy-btn" disabled onclick="copyPerformancePostText()">📋 Copier</button>
        </div>
        <div class="publish-meta" id="perf-post-status"></div>
      </div>
    </div>

    <div class="perf-grid" id="perf-advanced-results" style="display:none">
      <div class="perf-panel">
        <h3 id="perf-leaders-title">Leaders par catégorie</h3>
        <div id="perf-leaders" class="perf-leader-list"></div>
      </div>
      <div class="perf-panel">
        <h3 id="perf-table-title">Classement détaillé</h3>
        <div id="perf-table-wrap"></div>
      </div>
    </div>
  </div>
</div>

<!-- ═══════════════════════════════════════════════════════════════════════ -->
<!-- PAGE REEL                                                               -->
<!-- ═══════════════════════════════════════════════════════════════════════ -->
<div id="page-reel">
<div class="layout">

  <div class="panel-wrapper">
  <div class="panel">

    <div class="collapsible open" id="reelcol-items">
      <div class="collapsible-header" onclick="toggleCol('reelcol-items')">
        <span class="section-title">📚 Library & Reel</span><span class="collapsible-arrow">▼</span>
      </div>
      <div class="collapsible-body">
        <div class="reel-library-header">
          <span class="reel-library-title">Library disponible</span>
          <button class="publish-mini-btn" onclick="renderReelLibrary()">↺</button>
        </div>
        <div id="reel-library-list" class="reel-library-grid">
          <div class="reel-empty" style="grid-column:1/-1;padding:14px 0">Aucune carte dans la Library.</div>
        </div>
        <div class="reel-section-separator">
          <div class="reel-library-title">Timeline du Reel</div>
        </div>
        <div id="reel-item-list">
          <div class="reel-empty">Aucune carte ajoutée.<br>Ajoute une carte depuis la Library ci-dessus.</div>
        </div>
      </div>
    </div>

    <div class="collapsible open" id="reelcol-settings">
      <div class="collapsible-header" onclick="toggleCol('reelcol-settings')">
        <span class="section-title">⚙ Paramètres</span><span class="collapsible-arrow">▼</span>
      </div>
      <div class="collapsible-body">
        <div class="publish-field" style="margin-bottom:8px">
          <label for="reel_template">Template</label>
          <select id="reel_template" class="publish-input" onchange="applyReelTemplate(this.value)">
            <option value="equipment_showcase">Equipment showcase</option>
            <option value="rider_setup">Rider setup</option>
            <option value="top3_performance">Top 3 Performance</option>
            <option value="race_recap">Race recap</option>
            <option value="brand_focus">Brand focus</option>
          </select>
        </div>
        <div class="publish-field" style="margin-bottom:8px">
          <label for="reel_format">Format export</label>
          <select id="reel_format" class="publish-input">
            <option value="reel">Instagram Reel · 1080x1920</option>
            <option value="story">Story · 1080x1920</option>
            <option value="square">Square · 1080x1080</option>
            <option value="source">Source card</option>
          </select>
        </div>
        <div class="publish-field" style="margin-bottom:8px">
          <label for="reel_title">Titre reel</label>
          <input id="reel_title" class="publish-input" type="text" placeholder="Ex: Top 3 Forks Women 2026">
        </div>
        <div class="publish-select-grid" style="grid-template-columns:1fr 1fr;margin-bottom:10px">
          <div class="publish-field">
            <label for="reel_perf_category">Équipement ciblé</label>
            <select id="reel_perf_category" class="publish-input"></select>
          </div>
          <div class="publish-field">
            <label for="reel_perf_gender">Classement</label>
            <select id="reel_perf_gender" class="publish-input">
              <option value="F">Femmes</option>
              <option value="M">Hommes</option>
            </select>
          </div>
        </div>
        <div class="publish-helper-row" style="margin-bottom:10px">
          <button class="publish-mini-btn" onclick="addReelTitleCard('intro')">＋ Intro</button>
          <button class="publish-mini-btn" onclick="addReelTitleCard('outro')">＋ Outro</button>
          <button class="publish-mini-btn" onclick="buildPerformanceTop3Reel()">＋ Top 3 Performance</button>
        </div>
        <div class="slider-row">
          <span class="slider-label">Durée/carte</span>
          <input type="range" id="reel_dur_per_card" min="1" max="8" value="3" step="0.5"
                 oninput="updateSlider(this,'reel_val_dur')">
          <input type="text" class="slider-val" id="reel_val_dur" value="3"
                 onfocus="this.select()" onchange="syncVal('reel_val_dur','reel_dur_per_card')">
        </div>
        <div class="slider-row">
          <span class="slider-label">Fondu</span>
          <input type="range" id="reel_crossfade" min="0" max="1.5" value="0.5" step="0.1"
                 oninput="updateSlider(this,'reel_val_cf')">
          <input type="text" class="slider-val" id="reel_val_cf" value="0.5"
                 onfocus="this.select()" onchange="syncVal('reel_val_cf','reel_crossfade')">
        </div>
        <div class="publish-field" style="margin:8px 0">
          <label for="reel_audio_file">Audio</label>
          <input id="reel_audio_file" class="publish-input" type="file" accept="audio/*">
        </div>
        <div class="slider-row">
          <span class="slider-label">Volume</span>
          <input type="range" id="reel_audio_volume" min="0" max="1.5" value="0.75" step="0.05"
                 oninput="updateSlider(this,'reel_val_audio_volume')">
          <input type="text" class="slider-val" id="reel_val_audio_volume" value="0.75"
                 onfocus="this.select()" onchange="syncVal('reel_val_audio_volume','reel_audio_volume')">
        </div>
        <div class="publish-field" style="margin:8px 0">
          <label for="reel_sfx_transition">Effet transition</label>
          <select id="reel_sfx_transition" class="publish-input">
            <option value="">Aucun</option>
            <option value="swoosh_fast">Swoosh fast</option>
            <option value="swoosh_soft">Swoosh soft</option>
            <option value="swoosh_deep">Swoosh deep</option>
            <option value="swoosh_riser">Swoosh riser</option>
            <option value="transition_hit">Transition hit</option>
            <option value="impact_deep">Impact deep</option>
            <option value="camera_click">Camera click</option>
            <option value="pop_clean">Pop clean</option>
          </select>
        </div>
        <div class="slider-row">
          <span class="slider-label">Volume SFX</span>
          <input type="range" id="reel_sfx_volume" min="0" max="1.5" value="0.8" step="0.05"
                 oninput="updateSlider(this,'reel_val_sfx_volume')">
          <input type="text" class="slider-val" id="reel_val_sfx_volume" value="0.8"
                 onfocus="this.select()" onchange="syncVal('reel_val_sfx_volume','reel_sfx_volume')">
        </div>
        <div class="eq-text-row" style="margin-top:6px">
          <label class="eq-toggle-wrap">
            <input type="checkbox" id="reel_show_badge" checked>
            <span class="eq-toggle-label">Rider's Selection</span>
          </label>
        </div>
        <div class="slider-row" style="margin-top:4px">
          <span class="slider-label">Taille PP</span>
          <input type="range" id="reel_badge_radius" min="30" max="120" value="58"
                 oninput="updateSlider(this,'reel_val_badge_r')">
          <input type="text" class="slider-val" id="reel_val_badge_r" value="58"
                 onfocus="this.select()" onchange="syncVal('reel_val_badge_r','reel_badge_radius')">
        </div>
        <!-- Sélecteur rider pour le badge PP -->
        <div id="reel-badge-rider-box" style="margin-top:6px">
          <div style="font-size:0.7rem;color:#666;text-transform:uppercase;letter-spacing:.04em;margin-bottom:4px">
            PP du rider (badge ★)
          </div>
          <div style="display:flex;gap:6px;align-items:center">
            <input class="search-input" id="reel-rider-search" placeholder="🔍 Chercher…"
                   oninput="filterReelRiders()" style="flex:1;font-size:0.78rem;padding:5px 8px">
          </div>
          <select id="reel-rider-select" size="5"
                  style="width:100%;margin-top:4px;border-radius:6px;padding:3px 0;font-size:0.78rem">
            <option value="">— Sans badge —</option>
          </select>
        </div>
      </div>
    </div>

  </div><!-- fin .panel -->

  <div class="panel-actions sticky">
    <button class="btn btn-generate" id="reel-gen-btn" onclick="generateEqReel()">▶ Générer le reel</button>
    <div id="reel-progress" style="display:none;text-align:center;font-size:0.78rem;color:#888;padding:6px 0">
      ⚙ Génération en cours…
    </div>
    <div class="action-grid two">
      <button class="btn btn-download" id="reel-dl-btn" disabled onclick="downloadEqReel()">⬇ Télécharger MP4</button>
      <button class="btn btn-secondary" id="reel-add-library-btn" disabled onclick="addEqReelToLibrary()">
        ＋ Library
      </button>
    </div>
    <div id="reel-error-msg" style="display:none;font-size:0.78rem;padding:4px 0;text-align:center"></div>
  </div>
  </div><!-- fin .panel-wrapper -->

  <!-- Zone preview reel -->
  <div class="preview-area" id="reel-preview-area" style="flex-direction:column;gap:16px;overflow-y:auto;padding:20px">
    <!-- Grille des cartes ajoutées -->
    <div style="display:flex;flex-wrap:wrap;gap:10px;justify-content:center" id="reel-preview-grid"></div>
    <!-- Lecteur vidéo (masqué jusqu'à génération) -->
    <video id="reel-video-player" controls loop
           style="display:none;max-height:60vh;max-width:100%;border-radius:10px;
                  border:2px solid #C8D400;box-shadow:0 0 20px rgba(200,212,0,.25)">
    </video>
  </div>

</div><!-- fin .layout -->
</div><!-- fin #page-reel -->

<!-- ══════════════════ PAGE LIBRARY ══════════════════ -->
<div id="page-library">
  <h2 style="color:#C8D400;margin-bottom:4px;font-size:1.1rem;letter-spacing:1px">📚 LIBRARY</h2>
  <p style="color:#555;font-size:12px;margin-bottom:20px">
    Historique des médias générés. Ajoute ici tes cartes et reels, puis réutilise-les dans Reel ou Publish.
  </p>

  <div class="library-toolbar">
    <div class="library-field">
      <label for="library-kind-filter">Type</label>
      <select id="library-kind-filter" onchange="renderLibraryPage()">
        <option value="all">Tout</option>
        <option value="rider">Rider cards</option>
        <option value="equipment">Equipment cards</option>
        <option value="reel">Reels</option>
      </select>
    </div>
    <div class="library-field" style="flex:1;min-width:260px">
      <label for="library-search">Recherche</label>
      <input id="library-search" placeholder="Rider, équipement, template..." oninput="renderLibraryPage()">
    </div>
    <button class="btn" onclick="renderLibraryPage()">↺ Actualiser</button>
    <button class="btn btn-secondary" onclick="clearLibrary()">Vider</button>
  </div>

  <div class="publish-meta" id="library-status" style="margin-bottom:14px"></div>
  <div class="library-grid" id="library-grid">
    <div class="library-empty">Aucun média dans la Library pour le moment.</div>
  </div>
</div><!-- fin #page-library -->

<!-- ══════════════════ PAGE PUBLISH ══════════════════ -->
<div id="page-publish">
<div class="layout">

  <div class="panel-wrapper">
    <div class="panel publish-panel">

      <div class="collapsible open" id="pubcol-source">
        <div class="collapsible-header" onclick="toggleCol('pubcol-source')">
          <span class="section-title">Source</span><span class="collapsible-arrow">▼</span>
        </div>
        <div class="collapsible-body">
          <div class="publish-source-row">
            <button class="publish-source-btn" id="publish-src-rider" onclick="publishSetDraftKind('rider')">Rider cards</button>
            <button class="publish-source-btn" id="publish-src-equipment" onclick="publishSetDraftKind('equipment')">Equipment cards</button>
            <button class="publish-source-btn" id="publish-src-reel" onclick="publishSetDraftKind('reel')">Reel MP4</button>
          </div>
          <div class="publish-select-grid">
            <div class="publish-field">
              <label for="publish-rider-select">Rider cards</label>
              <select id="publish-rider-select" class="publish-input" multiple size="3" onchange="publishSelectSource('rider', this)"></select>
            </div>
            <div class="publish-field">
              <label for="publish-equipment-select">Equipment cards</label>
              <select id="publish-equipment-select" class="publish-input" multiple size="3" onchange="publishSelectSource('equipment', this)"></select>
            </div>
            <div class="publish-field">
              <label for="publish-reel-select">Reel MP4</label>
              <select id="publish-reel-select" class="publish-input" size="3" onchange="publishSelectSource('reel', this)"></select>
            </div>
          </div>
          <div class="publish-meta" id="publish-source-state" style="margin-top:10px">
            Aucune source sélectionnée. Génère une carte ou un reel, puis reviens ici.
          </div>
          <div class="publish-meta" id="publish-source-meta" style="margin-top:6px"></div>
          <div class="publish-meta" id="publish-source-count" style="margin-top:6px"></div>
          <div class="publish-field" style="margin-top:12px">
            <label for="publish-music-select">Musique Instagram</label>
            <select id="publish-music-select" class="publish-input" onchange="publishSetMusic(this.value)"></select>
          </div>
          <div class="publish-field" style="margin-top:10px">
            <label for="publish-music-note">Music note</label>
            <input id="publish-music-note" class="publish-input" type="text" placeholder="Titre, artiste, vibe..." list="publish-music-suggestions" oninput="publishPersist(); publishRender();">
            <datalist id="publish-music-suggestions"></datalist>
          </div>
          <div class="publish-music-hint" style="margin-top:8px">
            Instagram ne permet pas un sélecteur musical natif depuis une app web. Ici on prépare la musique à choisir dans Instagram, avec une note et des suggestions.
          </div>
        </div>
      </div>

      <div class="collapsible open" id="pubcol-copy">
        <div class="collapsible-header" onclick="toggleCol('pubcol-copy')">
          <span class="section-title">Instagram copy</span><span class="collapsible-arrow">▼</span>
        </div>
        <div class="collapsible-body">
          <div class="publish-field">
            <label for="publish-template">Template</label>
            <div class="publish-helper-row">
              <select id="publish-template" class="publish-input" onchange="publishApplyTemplate(this.value, true)" style="flex:1;min-width:180px">
                <option value="auto">Auto selon la source</option>
                <option value="rider_card">Rider card</option>
                <option value="equipment_highlight">Equipment highlight</option>
                <option value="reel">Reel</option>
                <option value="race_result">Race result</option>
              </select>
              <button class="publish-mini-btn" onclick="publishApplyTemplate(document.getElementById('publish-template')?.value || 'auto', true)">Appliquer</button>
            </div>
          </div>
          <div class="publish-field">
            <label for="publish-title">Titre interne</label>
            <input id="publish-title" class="publish-input" type="text" placeholder="Nom du post" list="publish-title-suggestions">
            <datalist id="publish-title-suggestions"></datalist>
          </div>
          <div class="publish-field" style="margin-top:10px">
            <label for="publish-caption">Caption</label>
            <textarea id="publish-caption" class="publish-textarea" placeholder="Texte Instagram..."></textarea>
          </div>
          <div class="publish-rows" style="margin-top:10px">
            <div class="publish-field">
              <label for="publish-location">Location</label>
              <input id="publish-location" class="publish-input" type="text" placeholder="Ex: Whistler Bike Park" list="publish-location-suggestions">
              <datalist id="publish-location-suggestions"></datalist>
            </div>
            <div class="publish-field">
              <label for="publish-hashtags">Hashtags</label>
              <input id="publish-hashtags" class="publish-input" type="text" placeholder="#mtb #downhill #freeride" list="publish-hashtag-suggestions">
              <datalist id="publish-hashtag-suggestions"></datalist>
            </div>
          </div>
          <div class="publish-field" style="margin-top:10px">
            <label for="publish-first-comment">First comment</label>
            <textarea id="publish-first-comment" class="publish-textarea" placeholder="Premier commentaire..."></textarea>
          </div>
          <div class="publish-field" style="margin-top:10px">
            <label for="publish-alt">Alt text</label>
            <textarea id="publish-alt" class="publish-textarea" placeholder="Texte d'accessibilité / descriptif image..."></textarea>
          </div>
        </div>
      </div>

      <div class="collapsible" id="pubcol-history">
        <div class="collapsible-header" onclick="toggleCol('pubcol-history')">
          <span class="section-title">Historique publish</span><span class="collapsible-arrow">▼</span>
        </div>
        <div class="collapsible-body">
          <div class="publish-helper-row" style="margin-bottom:10px">
            <button class="publish-mini-btn" onclick="publishSaveHistory(true)">＋ Sauver la préparation</button>
            <button class="publish-mini-btn" onclick="publishClearHistory()">Vider</button>
          </div>
          <div class="publish-history-list" id="publish-history-list">
            <div class="publish-meta">Aucune publication préparée.</div>
          </div>
        </div>
      </div>

      <div class="collapsible" id="pubcol-delivery" style="display:none">
        <div class="collapsible-header" onclick="toggleCol('pubcol-delivery')">
          <span class="section-title">Delivery smartphone</span><span class="collapsible-arrow">▼</span>
        </div>
        <div class="collapsible-body">
          <label class="publish-check">
            <input type="checkbox" id="publish-use-share" checked>
            Utiliser la feuille de partage du téléphone
          </label>
          <label class="publish-check" style="margin-top:8px">
            <input type="checkbox" id="publish-open-instagram" checked>
            Ouvrir Instagram après partage si possible
          </label>
          <div class="publish-meta" style="margin-top:10px">
            Sur mobile, l’app envoie le média vers la feuille de partage. Instagram apparaîtra si ton téléphone l’accepte.
          </div>
        </div>
      </div>

    </div><!-- fin .panel -->

    <div class="panel-actions sticky">
      <div class="publish-action-stack">
        <button class="btn btn-generate" onclick="publishGenerateSelection()">▶ Générer la sélection</button>
        <div class="publish-action-row">
          <button class="btn btn-download" id="publish-download-btn" disabled onclick="publishDownload()">⬇ Télécharger</button>
          <button class="btn btn-secondary" id="publish-share-btn" disabled onclick="publishShare()">📣 Partager</button>
        </div>
        <div class="publish-action-row compact">
          <button class="btn btn-secondary" onclick="publishAutoFill(true)">↺ Auto</button>
          <button class="btn btn-secondary" id="publish-open-btn" onclick="publishOpenInstagram()">📱 Instagram</button>
          <button class="btn btn-secondary" onclick="publishCopyCaption()">📋 Copier tout</button>
        </div>
      </div>
      <div class="publish-status" id="publish-status"></div>
    </div>
  </div><!-- fin .panel-wrapper -->

  <div class="preview-area" id="publish-preview-area" style="overflow:hidden;padding:20px">
    <div class="publish-preview-shell">
      <div class="publish-preview-media-col">
        <div class="placeholder" id="publish-placeholder">
          <span>📣</span>
          Génère une carte ou un reel,<br>choisis la source,<br>puis prépare la publication
        </div>
        <img id="publish-preview-img" class="publish-preview-media" src="" style="display:none" alt="Publish preview">
        <video id="publish-preview-video" class="publish-preview-media" style="display:none;max-height:58vh" controls loop></video>
      </div>
      <div class="publish-preview-side">
        <div class="publish-preview-head">
          <span class="publish-preview-title">Preview copy</span>
          <button class="btn btn-secondary publish-copy-mini" id="publish-preview-copy-btn" onclick="publishCopyCaption()" disabled>📋 Copier tout</button>
        </div>
        <div class="publish-checklist" id="publish-checklist"></div>
        <div class="publish-preview-caption" id="publish-preview-caption" style="display:none;max-height:58vh;overflow:auto"></div>
      </div>
    </div>
  </div>

</div><!-- fin .layout -->
</div><!-- fin #page-publish -->

<!-- ══════════════════ PAGE LOGOS ══════════════════ -->
<div id="page-logos">
  <h2 style="color:#C8D400;margin-bottom:6px;font-size:1.1rem;letter-spacing:1px">🖼 GESTIONNAIRE DE LOGOS</h2>
  <p style="color:#666;font-size:12px;margin-bottom:20px">Choisis le dossier logos, scanne un site source, télécharge les manquants.</p>

  <!-- Étape 1 : Dossier -->
  <div style="background:#111;border:1px solid #2a2a2a;border-radius:8px;padding:16px;margin-bottom:16px">
    <div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px">① Dossier logos</div>
    <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
      <button class="btn" onclick="logosBrowseFolder()" id="logos-folder-btn">📁 Choisir le dossier…</button>
      <div id="logos-folder-display" style="flex:1;font-size:12px;color:#666;font-family:monospace;
           background:#1a1a1a;border:1px solid #2a2a2a;border-radius:5px;padding:7px 12px;min-width:200px">
        Aucun dossier sélectionné
      </div>
    </div>
    <div id="logos-folder-stats" style="font-size:12px;color:#888;margin-top:8px"></div>
  </div>

  <!-- Étape 2 : Source web -->
  <div style="background:#111;border:1px solid #2a2a2a;border-radius:8px;padding:16px;margin-bottom:16px" id="logos-step2" style="opacity:.4">
    <div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px">② Site source</div>
    <div class="logos-toolbar" style="margin-bottom:0">
      <input class="logos-url-input" id="logos-url" value="https://probikeshop.fr/pages/marques"
        placeholder="URL de la page à scanner...">
      <button class="btn" onclick="logosScrap()" id="logos-scan-btn">🔍 Scanner</button>
      <button class="btn" id="logos-zip-btn" onclick="logosDownloadZip()" disabled
        style="background:#1a2200;color:#C8D400;border:1px solid #C8D400">
        ⬇ Télécharger ZIP
      </button>
    </div>
  </div>

  <!-- Résultats -->
  <div class="logos-progress" id="logos-progress">
    <div class="logos-progress-bar" id="logos-progress-bar"></div>
  </div>
  <div class="logos-stats" id="logos-stats"></div>

  <div class="logos-actions" id="logos-actions" style="display:none">
    <label style="font-size:12px;color:#aaa;cursor:pointer">
      <input type="checkbox" id="logos-chk-all" onchange="logosToggleAll(this.checked)"> Tout sélectionner
    </label>
    <button class="btn-select-all" onclick="logosSelectMissing()">☑ Sélectionner manquants</button>
    <span id="logos-sel-count" style="font-size:12px;color:#888;margin-left:6px"></span>
  </div>

  <table class="logos-table" id="logos-table" style="display:none">
    <thead>
      <tr>
        <th style="width:32px"></th>
        <th style="width:64px">Aperçu</th>
        <th>Nom</th>
        <th style="width:100px">Statut</th>
        <th>Fichier source</th>
      </tr>
    </thead>
    <tbody id="logos-tbody"></tbody>
  </table>
</div><!-- fin #page-logos -->

<!-- ══════════════════ PAGE RIDERS ══════════════════ -->
<div id="page-riders">
  <h2 style="color:#C8D400;margin-bottom:6px;font-size:1.1rem;letter-spacing:1px">👤 GESTIONNAIRE DE PHOTOS RIDERS</h2>
  <p style="color:#666;font-size:12px;margin-bottom:20px">Scanne les photos PP et action pour chaque rider du CSV.</p>

  <!-- Dossiers -->
  <div class="riders-folders">
    <div class="riders-folder-card">
      <label>📸 Dossier PP (portraits)</label>
      <div class="riders-folder-row">
        <button class="btn" onclick="ridersBrowseFolder('pp')" id="riders-pp-btn">📁 Choisir…</button>
        <div class="riders-folder-path" id="riders-pp-path">Dossier par défaut (PPRiders/)</div>
      </div>
      <div id="riders-pp-stats" style="font-size:11px;color:#555;margin-top:6px"></div>
    </div>
    <div class="riders-folder-card">
      <label>🏔 Dossier Action photos</label>
      <div class="riders-folder-row">
        <button class="btn" onclick="ridersBrowseFolder('pic')" id="riders-pic-btn">📁 Choisir…</button>
        <div class="riders-folder-path" id="riders-pic-path">Dossier par défaut (PictureRiders/)</div>
      </div>
      <div id="riders-pic-stats" style="font-size:11px;color:#555;margin-top:6px"></div>
    </div>
  </div>

  <!-- Scan -->
  <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:16px">
    <button class="btn" onclick="ridersScan()" id="riders-scan-btn">🔍 Scanner les riders</button>
    <button class="btn" id="riders-batch-btn" onclick="ridersDownloadAllPP()" style="display:none;background:#1a2200;color:#C8D400;border:1px solid #C8D400">
      ⬇ Télécharger PP manquantes
    </button>
    <div class="riders-stats" id="riders-stats" style="margin:0"></div>
  </div>

  <!-- Progress -->
  <div class="riders-progress" id="riders-progress">
    <div class="riders-progress-bar" id="riders-progress-bar"></div>
  </div>

  <!-- ③ Downloader photo action -->
  <div style="background:#111;border:1px solid #2a2a2a;border-radius:8px;padding:16px;margin-bottom:20px">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
      <div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.08em">③ Télécharger une photo action depuis Instagram</div>
      <div style="display:flex;gap:8px;align-items:center">
        <span id="pic-dl-missing-count" style="font-size:11px;color:#555"></span>
        <button id="pic-dl-next-btn" onclick="picDlNext()" style="display:none;
          background:#1a1a1a;border:1px solid #444;color:#C8D400;font-size:12px;
          padding:4px 12px;border-radius:5px;cursor:pointer">
          → Suivant
        </button>
      </div>
    </div>

    <!-- Rider actuel (mode guidé) -->
    <div id="pic-dl-current-rider" style="display:none;
      background:#1a1a1a;border:1px solid #2a2a2a;border-radius:6px;
      padding:10px 14px;margin-bottom:12px;display:none">
      <div style="display:flex;gap:12px;align-items:center">
        <img id="pic-dl-rider-pp" style="width:40px;height:40px;border-radius:50%;object-fit:cover;background:#222;border:1px solid #333">
        <div>
          <div id="pic-dl-rider-name" style="font-size:14px;font-weight:600;color:#eee"></div>
          <a id="pic-dl-rider-iglink" href="#" target="_blank"
            style="font-size:12px;color:#C8D400;text-decoration:none">
            Ouvrir Instagram ↗
          </a>
        </div>
      </div>
    </div>

    <div style="display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap">
      <div style="flex:2;min-width:260px">
        <div style="font-size:11px;color:#555;margin-bottom:4px">
          URL du post <em>ou</em> image directe Instagram
          <span id="pic-dl-mode-badge" style="margin-left:6px;font-size:10px;padding:1px 6px;
            border-radius:4px;background:#1a2200;color:#C8D400;display:none">URL directe</span>
        </div>
        <input id="pic-dl-url" type="text"
          placeholder="https://www.instagram.com/p/... ou coller URL image (clic droit → Copier adresse)"
          style="width:100%;background:#1a1a1a;border:1px solid #333;color:#eee;padding:8px 12px;
                 border-radius:6px;font-size:13px;box-sizing:border-box"
          oninput="picDlPreviewUrl(this.value)">
      </div>
      <div style="flex:1;min-width:160px">
        <div style="font-size:11px;color:#555;margin-bottom:4px">Rider</div>
        <select id="pic-dl-rider" style="width:100%;background:#1a1a1a;border:1px solid #333;color:#eee;
          padding:8px 12px;border-radius:6px;font-size:13px;box-sizing:border-box"
          onchange="picDlRiderChanged(this.value)">
          <option value="">— Scanner d'abord —</option>
        </select>
      </div>
      <button class="btn" onclick="picDlDownload()" id="pic-dl-btn" disabled
        style="background:#1a2200;color:#C8D400;border:1px solid #C8D400;white-space:nowrap">
        ⬇ Télécharger
      </button>
    </div>

    <!-- Sélecteur carrousel -->
    <div id="pic-dl-carousel" style="display:none;margin-top:12px">
      <div style="font-size:11px;color:#555;margin-bottom:6px">Sélectionne la photo à télécharger :</div>
      <div class="carousel-picker" id="pic-dl-carousel-grid"></div>
    </div>

    <!-- Panneau fallback URL directe -->
    <div id="pic-dl-fallback" style="display:none;margin-top:10px;padding:12px 14px;
      background:#1a0a00;border:1px solid #3a1800;border-radius:8px;font-size:12px">
      <div style="color:#f90;font-weight:600;margin-bottom:6px">⚠️ Instagram bloque l'accès automatique</div>
      <div style="color:#888;line-height:1.6">
        Solution : ouvre le post dans ton navigateur
        → <a id="pic-dl-fallback-link" href="#" target="_blank" style="color:#C8D400">voir le post ↗</a><br>
        Clic droit sur la photo voulue → <strong style="color:#eee">Copier l'adresse de l'image</strong><br>
        Colle l'URL directement dans le champ ci-dessus.
      </div>
    </div>

    <div style="margin-top:10px;display:flex;gap:14px;align-items:flex-start">
      <div id="pic-dl-preview-box" style="display:none">
        <img id="pic-dl-preview-img" style="width:90px;height:90px;object-fit:cover;border-radius:6px;border:1px solid #2a2a2a">
      </div>
      <div id="pic-dl-status" style="font-size:12px;color:#888;padding-top:4px"></div>
    </div>
  </div>

  <!-- Table -->
  <table class="riders-table" id="riders-table" style="display:none">
    <thead>
      <tr>
        <th style="width:130px">Rider</th>
        <th style="width:64px">PP</th>
        <th style="width:80px">Statut PP</th>
        <th style="width:72px">Action</th>
        <th style="width:100px">Statut Action</th>
        <th>Instagram</th>
        <th>Fichier PP</th>
        <th>Fichier Action</th>
      </tr>
    </thead>
    <tbody id="riders-tbody"></tbody>
  </table>
</div><!-- fin #page-riders -->

<!-- ══════════════════ PAGE BRAND & TAGS ══════════════════ -->
<div id="page-brandtags" style="display:none;padding:28px 24px 48px;max-width:1300px;margin:0 auto">
  <h2 style="color:#C8D400;margin-bottom:6px;font-size:1.1rem;letter-spacing:1px">🏷 BRAND & TAGS</h2>
  <p style="color:#666;font-size:12px;margin-bottom:20px">
    Données lues depuis les onglets Google Sheet Brand et Tags. Elles alimentent automatiquement les captions Publish.
  </p>
  <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:16px">
    <button class="btn" onclick="refreshBrandTags()">↺ Resync Brand & Tags</button>
    <span id="brandtags-status" style="font-size:12px;color:#666"></span>
  </div>
  <div class="asset-tags-grid">
    <div class="asset-tags-card">
      <h3>Brand handles</h3>
      <div class="asset-tags-stats" id="brandtags-brand-stats">Chargement…</div>
      <div style="overflow:auto;max-height:520px">
        <table class="asset-tags-table">
          <thead><tr><th>Brand</th><th>Instagram</th><th>Status</th></tr></thead>
          <tbody id="brandtags-brand-tbody"></tbody>
        </table>
      </div>
    </div>
    <div class="asset-tags-card">
      <h3>Context tags</h3>
      <div class="asset-tags-stats" id="brandtags-context-stats">Chargement…</div>
      <div style="overflow:auto;max-height:520px">
        <table class="asset-tags-table">
          <thead><tr><th>Type</th><th>Name</th><th>Tag</th></tr></thead>
          <tbody id="brandtags-context-tbody"></tbody>
        </table>
      </div>
    </div>
</div>
</div><!-- fin #page-brandtags -->

<!-- ══════════════════ PAGE SETTINGS ══════════════════ -->
<div id="page-settings">
  <h2>⚙ PARAMÈTRES</h2>
  <p class="settings-subtitle">Configuration locale de la source de données.</p>

  <div class="settings-card">
    <div class="settings-card-title">Google Sheet</div>
    <div class="settings-field">
      <label for="settings-gsheet-url">Lien ou ID du Google Sheet</label>
      <input id="settings-gsheet-url" class="settings-input" type="text"
        placeholder="https://docs.google.com/spreadsheets/d/.../edit">
    </div>
    <div class="settings-actions">
      <button class="btn btn-secondary" onclick="settingsTestGoogleSheet()">Tester</button>
      <button class="btn" onclick="settingsSaveGoogleSheet()">Sauvegarder</button>
      <button class="btn btn-secondary" onclick="settingsResetGoogleSheet()">Réinitialiser</button>
      <button class="btn btn-secondary" onclick="settingsOpenGoogleSheet()">Ouvrir</button>
    </div>
    <div class="settings-status" id="settings-gsheet-status"></div>
    <div id="settings-gsheet-test"></div>
  </div>

  <div class="settings-card">
    <div class="settings-card-title">Sheet actif</div>
    <div class="settings-current" id="settings-gsheet-current">Chargement…</div>
  </div>

  <div class="settings-card">
    <div class="settings-card-title">Modèle attendu</div>
    <div class="settings-current">
      Le test vérifie les onglets indispensables, leur nombre de lignes et les colonnes minimales nécessaires au fonctionnement de l’app.
    </div>
    <div class="settings-actions" style="margin-top:12px">
      <button class="btn btn-secondary" onclick="settingsCopySheetChecklist()">Copier la checklist Sheet</button>
    </div>
    <div class="settings-checklist" id="settings-sheet-checklist"></div>
  </div>
</div><!-- fin #page-settings -->

<!-- ══════════════════ PAGE CONNECTIONS ══════════════════ -->
<div id="page-connections">
  <h2>🔗 CONNEXIONS</h2>
  <p class="conn-subtitle">Connecte tes comptes pour activer les fonctionnalités avancées de la plateforme.</p>

  <div class="conn-section-title">Social Media &amp; Platforms</div>
  <div class="conn-grid">

    <!-- Google -->
    <div class="conn-card" id="conn-google">
      <div class="conn-logo" style="background:#fff;border-radius:12px">
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
          <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
          <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
          <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
        </svg>
      </div>
      <div class="conn-name">Google</div>
      <div class="conn-status"><span class="dot"></span>Non connecté</div>
      <button class="conn-btn" onclick="connClick('google')">Se connecter</button>
    </div>

    <!-- Instagram -->
    <div class="conn-card" id="conn-instagram">
      <div class="conn-logo" style="background:linear-gradient(135deg,#405DE6,#833AB4,#C13584,#E1306C,#FD1D1D,#F56040,#FCAF45)">
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path fill="#fff" d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
        </svg>
      </div>
      <div class="conn-name">Instagram</div>
      <div class="conn-status"><span class="dot"></span>Non connecté</div>
      <button class="conn-btn" onclick="connClick('instagram')">Se connecter</button>
    </div>

    <!-- LinkedIn -->
    <div class="conn-card" id="conn-linkedin">
      <div class="conn-logo" style="background:#0077B5;border-radius:12px">
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path fill="#fff" d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
        </svg>
      </div>
      <div class="conn-name">LinkedIn</div>
      <div class="conn-status"><span class="dot"></span>Non connecté</div>
      <button class="conn-btn" onclick="connClick('linkedin')">Se connecter</button>
    </div>

    <!-- Facebook -->
    <div class="conn-card" id="conn-facebook">
      <div class="conn-logo" style="background:#1877F2;border-radius:12px">
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path fill="#fff" d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
        </svg>
      </div>
      <div class="conn-name">Facebook</div>
      <div class="conn-status"><span class="dot"></span>Non connecté</div>
      <button class="conn-btn" onclick="connClick('facebook')">Se connecter</button>
    </div>

    <!-- X / Twitter -->
    <div class="conn-card" id="conn-x">
      <div class="conn-logo" style="background:#000;border-radius:12px">
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path fill="#fff" d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.745l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
        </svg>
      </div>
      <div class="conn-name">X</div>
      <div class="conn-status"><span class="dot"></span>Non connecté</div>
      <button class="conn-btn" onclick="connClick('x')">Se connecter</button>
    </div>

    <!-- TikTok -->
    <div class="conn-card" id="conn-tiktok">
      <div class="conn-logo" style="background:#010101;border-radius:12px">
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path fill="#25F4EE" d="M19.321 5.562a5.122 5.122 0 0 1-.443-.258 6.228 6.228 0 0 1-1.138-1.009 6.273 6.273 0 0 1-1.478-3.43H16.26l.002 13.762a2.98 2.98 0 0 1-2.975 2.553 2.98 2.98 0 0 1-2.974-2.981 2.98 2.98 0 0 1 2.974-2.98c.292 0 .574.042.842.12V8.31a6.46 6.46 0 0 0-.842-.055 6.472 6.472 0 0 0-6.462 6.473 6.473 6.473 0 0 0 6.462 6.472 6.472 6.472 0 0 0 6.461-6.472V8.396a9.766 9.766 0 0 0 3.717.73V5.657a6.24 6.24 0 0 1-3.144-.095z"/>
          <path fill="#FE2C55" d="M19.321 5.562a5.122 5.122 0 0 1-.443-.258 6.228 6.228 0 0 1-1.138-1.009 6.273 6.273 0 0 1-1.478-3.43h-3.002l.002 13.762a2.98 2.98 0 0 1-2.975 2.553 2.98 2.98 0 0 1-2.974-2.981 2.98 2.98 0 0 1 2.974-2.98c.292 0 .574.042.842.12V8.31a6.46 6.46 0 0 0-.842-.055 6.472 6.472 0 0 0-6.462 6.473 6.473 6.473 0 0 0 6.462 6.472 6.472 6.472 0 0 0 6.461-6.472V8.396a9.766 9.766 0 0 0 3.717.73V5.657a6.24 6.24 0 0 1-3.144-.095z" opacity=".5"/>
          <path fill="#fff" d="M16.262.865h-3.002v13.762a2.98 2.98 0 0 1-2.975 2.553 2.98 2.98 0 0 1-2.974-2.981 2.98 2.98 0 0 1 2.974-2.98c.292 0 .574.042.842.12V8.31a6.46 6.46 0 0 0-.842-.055 6.472 6.472 0 0 0-6.462 6.473 6.473 6.473 0 0 0 6.462 6.472 6.472 6.472 0 0 0 6.461-6.472V5.562a9.766 9.766 0 0 0 3.717.73V3.295a6.273 6.273 0 0 1-4.201-2.43z"/>
        </svg>
      </div>
      <div class="conn-name">TikTok</div>
      <div class="conn-status"><span class="dot"></span>Non connecté</div>
      <button class="conn-btn" onclick="connClick('tiktok')">Se connecter</button>
    </div>

    <!-- Reddit -->
    <div class="conn-card" id="conn-reddit">
      <div class="conn-logo" style="background:#FF4500;border-radius:50%">
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path fill="#fff" d="M12 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0zm5.01 4.744c.688 0 1.25.561 1.25 1.249a1.25 1.25 0 0 1-2.498.056l-2.597-.547-.8 3.747c1.824.07 3.48.632 4.674 1.488.308-.309.73-.491 1.207-.491.968 0 1.754.786 1.754 1.754 0 .716-.435 1.333-1.01 1.614a3.111 3.111 0 0 1 .042.52c0 2.694-3.13 4.87-7.004 4.87-3.874 0-7.004-2.176-7.004-4.87 0-.183.015-.366.043-.534A1.748 1.748 0 0 1 4.028 12c0-.968.786-1.754 1.754-1.754.463 0 .898.196 1.207.49 1.207-.883 2.878-1.43 4.744-1.487l.885-4.182a.342.342 0 0 1 .14-.197.35.35 0 0 1 .238-.042l2.906.617a1.214 1.214 0 0 1 1.108-.701zM9.25 12C8.561 12 8 12.562 8 13.25c0 .687.561 1.248 1.25 1.248.687 0 1.248-.561 1.248-1.249 0-.688-.561-1.249-1.249-1.249zm5.5 0c-.687 0-1.248.561-1.248 1.25 0 .687.561 1.248 1.249 1.248.688 0 1.249-.561 1.249-1.249 0-.687-.562-1.249-1.25-1.249zm-5.466 3.99a.327.327 0 0 0-.231.094.33.33 0 0 0 0 .463c.842.842 2.484.913 2.961.913.477 0 2.105-.056 2.961-.913a.361.361 0 0 0 .029-.463.33.33 0 0 0-.464 0c-.547.533-1.684.73-2.512.73-.828 0-1.979-.196-2.512-.73a.326.326 0 0 0-.232-.095z"/>
        </svg>
      </div>
      <div class="conn-name">Reddit</div>
      <div class="conn-status"><span class="dot"></span>Non connecté</div>
      <button class="conn-btn" onclick="connClick('reddit')">Se connecter</button>
    </div>

    <!-- Rednote -->
    <div class="conn-card" id="conn-rednote">
      <div class="conn-logo" style="background:#FF2442;border-radius:12px">
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <rect x="3" y="3" width="18" height="18" rx="3" fill="none"/>
          <path fill="#fff" d="M7 7h4v2H7zm0 4h10v1.5H7zm0 3h10v1.5H7zm6-7h4v2h-4z"/>
          <circle fill="#fff" cx="17" cy="17" r="3"/>
          <path fill="#FF2442" d="M16 16.5h.5V16H16zm.5 0H17v1h-.5zm.5-1h.5v.5H17zm.5.5H18V16h-.5z"/>
          <text x="14.8" y="18.2" font-size="3.5" fill="#fff" font-weight="bold" font-family="sans-serif">+</text>
        </svg>
      </div>
      <div class="conn-name">Rednote</div>
      <div class="conn-status"><span class="dot"></span>Non connecté</div>
      <button class="conn-btn" onclick="connClick('rednote')">Se connecter</button>
    </div>

  </div><!-- /conn-grid -->
</div><!-- fin #page-connections -->

<!-- ══════════════════ PAGE QUALITY CENTER ══════════════════ -->
<div id="page-quality">
  <h2 style="color:#C8D400;margin-bottom:4px;font-size:1.1rem;letter-spacing:1px">✅ QUALITY CENTER</h2>
  <p style="color:#555;font-size:12px;margin-bottom:20px">
    Vue consolidée des assets et données à corriger avant de générer des cartes, reels et posts Publish.
  </p>

  <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
    <button class="btn" onclick="renderQualityCenter()">↺ Actualiser</button>
    <button class="btn" onclick="rescanEqPhotos(true).then(renderQualityCenter)">📸 Rescan photos équipement</button>
    <button class="btn" onclick="refreshBrandTags().then(renderQualityCenter)">🏷 Resync Brand & Tags</button>
    <button class="btn btn-secondary" onclick="qualityCopyDailyTodo()">Copier la todo du jour</button>
    <span id="quality-status" style="font-size:12px;color:#666"></span>
  </div>

  <div class="quality-kpis">
    <div class="quality-kpi good">
      <div class="quality-kpi-label">Score assets</div>
      <div class="quality-kpi-value" id="quality-score">0%</div>
    </div>
    <div class="quality-kpi critical">
      <div class="quality-kpi-label">Critiques</div>
      <div class="quality-kpi-value" id="quality-critical">0</div>
    </div>
    <div class="quality-kpi warn">
      <div class="quality-kpi-label">Manquants</div>
      <div class="quality-kpi-value" id="quality-warning">0</div>
    </div>
    <div class="quality-kpi optional">
      <div class="quality-kpi-label">Optionnels</div>
      <div class="quality-kpi-value" id="quality-optional">0</div>
    </div>
    <div class="quality-kpi">
      <div class="quality-kpi-label">Checks actifs</div>
      <div class="quality-kpi-value" id="quality-total">0</div>
    </div>
  </div>

  <div class="quality-daily" id="quality-daily-dashboard">
    <div class="quality-assets-note">Chargement du tableau de bord quotidien…</div>
  </div>

  <div class="quality-assets" id="quality-asset-summary">
    <div class="quality-assets-note">Chargement des photos équipement manquantes…</div>
  </div>

  <div class="quality-toolbar">
    <div class="quality-field">
      <label for="quality-severity">Severity</label>
      <select id="quality-severity" onchange="renderQualityCenter()">
        <option value="all">Tout</option>
        <option value="critical">Critique</option>
        <option value="warning">Warning</option>
        <option value="optional">Optionnel</option>
        <option value="ok">OK</option>
      </select>
    </div>
    <div class="quality-field">
      <label for="quality-type">Type</label>
      <select id="quality-type" onchange="renderQualityCenter()">
        <option value="all">Tout</option>
        <option value="rider">Rider</option>
        <option value="equipment">Equipment</option>
        <option value="brand">Brand</option>
        <option value="tag">Tags</option>
      </select>
    </div>
    <div class="quality-field">
      <label for="quality-kind">Sujet</label>
      <select id="quality-kind" onchange="renderQualityCenter()">
        <option value="all">Tout</option>
        <option value="equipment_photo">Photos manquantes</option>
        <option value="equipment_category">Catégories suspectes</option>
        <option value="sheet_data">Données Sheet</option>
        <option value="optional">Optionnels Publish</option>
      </select>
    </div>
    <div class="quality-field">
      <label for="quality-state">Statut</label>
      <select id="quality-state" onchange="renderQualityCenter()">
        <option value="active">Actifs</option>
        <option value="ignored">Ignorés</option>
        <option value="validated">Validés</option>
        <option value="all">Tout</option>
      </select>
    </div>
    <div class="quality-field" style="flex:1;min-width:260px">
      <label for="quality-search">Recherche</label>
      <input id="quality-search" placeholder="Rider, marque, équipement, tag..." oninput="renderQualityCenter()">
    </div>
  </div>

  <div class="quality-table-wrap">
    <table class="quality-table">
      <thead>
        <tr>
          <th>Severity</th>
          <th>Type</th>
          <th>Besoin</th>
          <th>Statut</th>
          <th>Priorité</th>
          <th>Cible</th>
          <th>Détail</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody id="quality-tbody">
        <tr><td colspan="8" style="color:#555">Chargement…</td></tr>
      </tbody>
    </table>
  </div>
</div><!-- fin #page-quality -->

<!-- ══════════════════ PAGE AUDIT ══════════════════ -->
<div id="page-audit" style="display:none;padding:28px 24px 48px;max-width:1400px;margin:0 auto">
  <h2 style="color:#C8D400;margin-bottom:4px;font-size:1.1rem;letter-spacing:1px">📋 AUDIT ÉQUIPEMENTS</h2>
  <p style="color:#555;font-size:12px;margin-bottom:20px">Vue d'ensemble — présence des photos par rider × catégorie</p>

  <div style="display:flex;align-items:center;gap:10px;margin-bottom:18px;flex-wrap:wrap">
    <button onclick="loadEqAudit()" style="padding:5px 14px;background:#1a1a1a;border:1px solid #333;border-radius:6px;color:#aaa;font-size:12px;cursor:pointer">↺ Actualiser</button>
    <button onclick="rescanEqPhotos().then(loadEqAudit)" style="padding:5px 14px;background:#1a1a1a;border:1px solid #C8D400;border-radius:6px;color:#C8D400;font-size:12px;cursor:pointer">📸 Rescan photos</button>
    <span style="font-size:11px;color:#444;margin-left:auto">🟢 données + photo &nbsp;·&nbsp; 🟡 données, photo manquante &nbsp;·&nbsp; ⬜ aucune donnée</span>
  </div>

  <div id="eq-audit-wrap" style="overflow-x:auto">
    <div id="eq-audit-placeholder" style="color:#444;font-size:13px;padding:20px 0">
      Chargement…
    </div>
    <table id="eq-audit-table" style="display:none;border-collapse:collapse;min-width:100%;font-size:11px"></table>
  </div>
</div><!-- fin #page-audit -->

<script>
// ── Collapsible ───────────────────────────────────────────────────────────
function toggleCol(id) {
  document.getElementById(id).classList.toggle('open');
}

// ── UX helper : rabat + scroll fluide ─────────────────────────────────────
function smoothCollapseAndScroll(collapseId, targetId, delay = 220) {
  // Rabattre la section source
  const col = document.getElementById(collapseId);
  if (col && col.classList.contains('open')) col.classList.remove('open');

  if (!targetId) return;

  // Après l'animation de fermeture, scroller vers la cible
  setTimeout(() => {
    const target = document.getElementById(targetId);
    if (!target) return;
    // Ouvrir la cible si elle est collapsible
    if (target.classList.contains('collapsible') && !target.classList.contains('open')) {
      target.classList.add('open');
    }
    // Trouver le conteneur scrollable (.panel)
    const panel = target.closest('.panel');
    if (panel) {
      const panelTop  = panel.getBoundingClientRect().top;
      const targetTop = target.getBoundingClientRect().top;
      panel.scrollTo({ top: panel.scrollTop + (targetTop - panelTop) - 10, behavior: 'smooth' });
    } else {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, delay);
}

// ── Verrous ───────────────────────────────────────────────────────────────
const lockedSliders = new Set();

function toggleLock(lockId, rangeId) {
  const btn = document.getElementById(lockId);
  const range = document.getElementById(rangeId);
  const row = btn.closest('.slider-row');
  const valueInput = row ? row.querySelector('.slider-val') : null;
  const setLocked = !lockedSliders.has(rangeId);

  if (range) range.disabled = setLocked;
  if (valueInput) valueInput.disabled = setLocked;
  btn.setAttribute('aria-pressed', setLocked ? 'true' : 'false');
  btn.title = setLocked ? 'Déverrouiller' : 'Verrouiller';

  if (!setLocked) {
    lockedSliders.delete(rangeId);
    btn.textContent = '🔓';
    btn.classList.remove('locked');
    row.classList.remove('locked');
  } else {
    lockedSliders.add(rangeId);
    btn.textContent = '🔒';
    btn.classList.add('locked');
    row.classList.add('locked');
  }
}

// ── Profils ───────────────────────────────────────────────────────────────
const SLIDER_DEFS = [
  { rid: 'photo_zoom',  vid: 'val_zoom', pct: true  },
  { rid: 'offset_x',   vid: 'val_x'                },
  { rid: 'offset_y',   vid: 'val_y'                },
  { rid: 'text_x',     vid: 'val_tx'               },
  { rid: 'text_top',   vid: 'val_tt'               },
  { rid: 'sz_label',   vid: 'val_sl'               },
  { rid: 'sz_value',   vid: 'val_sv'               },
  { rid: 'sz_value_sm',vid: 'val_ss'               },
  { rid: 'gap',        vid: 'val_gap'              },
  { rid: 'logo_h',     vid: 'val_lh'               },
  { rid: 'logo_y',     vid: 'val_ly'               },
  { rid: 'logo_x',     vid: 'val_lx', auto: true   },
];

function _loadProfiles() {
  try { return JSON.parse(localStorage.getItem('ff_profiles') || '{}'); }
  catch(e) { return {}; }
}
function _saveProfiles(p) { localStorage.setItem('ff_profiles', JSON.stringify(p)); }

function getCurrentSnapshot() {
  const snap = { logo_dir: document.getElementById('logo_dir').value };
  SLIDER_DEFS.forEach(({ rid }) => { snap[rid] = parseInt(document.getElementById(rid).value); });
  return snap;
}

function saveProfile() {
  const name = document.getElementById('profile-name').value.trim();
  if (!name) { alert('Donne un nom au profil.'); return; }
  const profiles = _loadProfiles();
  profiles[name] = getCurrentSnapshot();
  _saveProfiles(profiles);
  document.getElementById('profile-name').value = '';
  renderProfiles();
}

function applyProfile(name) {
  const vals = _loadProfiles()[name];
  if (!vals) return;
  captureHistory();
  applySnapshot(vals);
  debouncedGenerate(100);
}

function deleteProfile(name) {
  if (!confirm(`Supprimer le profil "${name}" ?`)) return;
  const profiles = _loadProfiles();
  delete profiles[name];
  _saveProfiles(profiles);
  renderProfiles();
}

function renderProfiles() {
  const list = document.getElementById('profile-list');
  const profiles = _loadProfiles();
  const names = Object.keys(profiles);
  if (names.length === 0) {
    list.innerHTML = '<div class="profile-empty">Aucun profil sauvegardé</div>';
    return;
  }
  list.innerHTML = names.map(n => {
    const safe = n.replace(/\\/g,'\\\\').replace(/'/g,"\\'");
    return `<div class="profile-item">
      <span class="profile-item-name" onclick="applyProfile('${safe}')" title="Cliquer pour charger">${n}</span>
      <button class="profile-load-btn" onclick="applyProfile('${safe}')">Charger</button>
      <button class="profile-del-btn" onclick="deleteProfile('${safe}')">✕</button>
    </div>`;
  }).join('');
}

// ── Cache global (préchargé au démarrage) ─────────────────────────────────
const _app = {
  profiles:        [],   // tous les profils complets
  equipment:       {},   // { handle: [items] }
  results:         [],   // classement Résultats 2026
  resultEvents:    [],   // manches/colonnes de points
  brandTags:       [],   // onglet Brand
  contextTags:     [],   // onglet Tags
  sponsors:        [],   // liste sponsors
  eqVariants:      [],   // liste plate [{name,url,path,folder,stem_slug}]
  categoryFolders: {},   // { "Brake Caliper": ["Brake Caliper","Brakes"], ... }
  varCache:        {},   // cache par-item (clé: "brand|ref|cat")
};

// ── État ──────────────────────────────────────────────────────────────────
let riders = [];
let selectedSponsors = new Set();  // vide = auto
let lastSlug = null;
let genderFilter = 'all';  // 'all' | 'F' | 'M'
let _lastRiderCardUrl = null;
let _lastPublishSource = null; // { kind, url, name, mime }
let _latestResultBadge = null;

function _foldSponsorText(value) {
  return String(value || '')
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .toLowerCase().replace(/[^a-z0-9]+/g, '');
}

function _sponsorChipMatchesName(chip, name) {
  const target = _foldSponsorText(name);
  if (!target) return false;
  const values = [
    chip?.dataset?.key || '',
    chip?.querySelector('span')?.textContent || '',
    chip?.querySelector('img')?.alt || '',
  ].map(_foldSponsorText).filter(Boolean);
  return values.some(v => v.includes(target) || target.includes(v));
}

function clearSponsorSelection() {
  selectedSponsors.clear();
  document.querySelectorAll('.sponsor-chip').forEach(chip => {
    chip.classList.remove('active', 'auto-active');
    const input = chip.querySelector('input');
    if (input) input.checked = false;
  });
}

function syncAutoSponsors(profile) {
  clearSponsorSelection();
  const names = Array.isArray(profile?.sponsors) ? profile.sponsors.filter(Boolean) : [];
  let matched = 0;
  document.querySelectorAll('.sponsor-chip').forEach(chip => {
    const isAuto = names.some(name => _sponsorChipMatchesName(chip, name));
    chip.classList.toggle('auto-active', isAuto);
    if (isAuto) matched++;
  });
  const badge = document.getElementById('sponsor-mode');
  if (badge) {
    badge.textContent = names.length
      ? `AUTO ${matched}/${names.length}`
      : 'AUTO équipement';
  }
}

// ── Rider list ─────────────────────────────────────────────────────────────
function setGender(g) {
  genderFilter = (genderFilter === g) ? 'all' : g;  // re-clic = reset
  document.getElementById('btn-f').className = 'gender-btn' + (genderFilter === 'F' ? ' active-f' : '');
  document.getElementById('btn-m').className = 'gender-btn' + (genderFilter === 'M' ? ' active-m' : '');
  renderRiderList();
}

function renderRiderList() {
  const query  = document.getElementById('rider-search').value.trim().toLowerCase();
  const sel    = document.getElementById('rider');
  const prev   = sel.value;
  sel.innerHTML = '';

  const filtered = riders.filter(r => {
    if (genderFilter !== 'all' && r.genre !== genderFilter) return false;
    if (query) {
      const full = `${r.prenom} ${r.nom}`.toLowerCase();
      if (!full.includes(query)) return false;
    }
    return true;
  });

  if (filtered.length === 0) {
    const opt = document.createElement('option');
    opt.disabled = true;
    opt.textContent = '— Aucun résultat —';
    sel.appendChild(opt);
  } else {
    filtered.forEach(r => {
      const opt = document.createElement('option');
      opt.value = r.slug;
      const icon = r.genre === 'F' ? '♀' : '♂';
      const photo = r.has_photo ? '' : ' ·';
      opt.textContent = `${icon}  ${r.prenom} ${r.nom}${photo}`;
      if (!r.has_photo) opt.style.color = '#888';
      sel.appendChild(opt);
    });
    // Restore selection if still visible
    if (prev && filtered.find(r => r.slug === prev)) sel.value = prev;
  }
}

// ── Helpers loading bar ────────────────────────────────────────────────────
function _setLoadingProgress(pct, msg) {
  const bar = document.getElementById('app-loading-bar');
  const txt = document.getElementById('app-loading-msg');
  if (bar) bar.style.width = pct + '%';
  if (txt && msg) txt.textContent = msg;
}
function _hideLoading() {
  const el = document.getElementById('app-loading');
  if (!el) return;
  el.style.transition = 'opacity .4s';
  el.style.opacity = '0';
  setTimeout(() => el.remove(), 420);
}

// ── Init ──────────────────────────────────────────────────────────────────
async function init() {
  try {
    _setLoadingProgress(10, 'Connexion au serveur…');
    const res = await fetch('/api/preload');
    _setLoadingProgress(50, 'Indexation des données…');
    const data = await res.json();

    // Stocker dans le cache global
    _app.profiles        = data.profiles         || [];
    _app.equipment       = data.equipment        || {};
    _app.results         = data.results?.riders  || [];
    _app.resultEvents    = data.results?.events  || [];
    _app.brandTags       = data.brand_tags       || [];
    _app.contextTags     = data.context_tags     || [];
    _app.sponsors        = data.sponsors         || [];
    _app.eqVariants      = data.eq_variants      || [];
    _app.categoryFolders = data.category_folders || {};
    populatePerformanceInfoFields();

    _setLoadingProgress(70, 'Construction de la liste…');

    // Riders list (compatibilité avec renderRiderList)
    riders = _app.profiles.map(p => ({
      slug:      p.slug,
      prenom:    p.prenom,
      nom:       p.nom,
      genre:     p.genre,
      has_photo: p.has_photo,
    }));
    renderRiderList();
    initReelPerformanceControls();
    updateLibraryBadge();

    _setLoadingProgress(88, 'Chargement des logos…');

    // Sponsors
    const grid = document.getElementById('sponsors-grid');
    if (grid) {
      _app.sponsors.forEach(s => {
        const chip = document.createElement('label');
        chip.className = 'sponsor-chip';
        chip.dataset.key = s.key;
        chip.innerHTML = `
          <input type="checkbox" value="${s.key}" onchange="toggleSponsor('${s.key}', this.checked)">
          <img src="${s.url}" alt="${s.label}" onerror="this.style.display='none'">
          <span>${s.label}</span>`;
        grid.appendChild(chip);
      });
    }

    _setLoadingProgress(100, 'Prêt !');
    setTimeout(_hideLoading, 300);

  } catch(e) {
    console.error('Preload failed:', e);
    document.getElementById('app-loading-msg').textContent = '❌ Erreur de chargement — recharger la page';
    document.getElementById('app-loading-bar').style.background = '#e55';
  }
}

let _originalProfile = null;

async function onRiderChange() {
  const slug = document.getElementById('rider').value;
  _latestResultBadge = null;
  lastSlug = null;
  document.getElementById('btn-dl').disabled = true;
  if (!slug) return;

  // Lookup local — pas de fetch
  const profile = _app.profiles.find(p => p.slug === slug);
  if (!profile) return;
  _originalProfile = profile;
  syncAutoSponsors(profile);
  _fillEditFields(profile);
  const editCol = document.getElementById('col-edit');
  editCol.style.display = 'block';
  editCol.classList.add('open');
  debouncedGenerate(100);

  // UX : rabat la section Rider et scroll vers les infos/sponsors
  smoothCollapseAndScroll('col-rider', 'col-sponsors');

  const instagram = profile.instagram || '';
  if (instagram) loadEquipment(instagram);
}

function loadEquipment(instagram) {
  const handle = (instagram.replace(/^@/, '')).toLowerCase();
  const items = _app.equipment[handle] || [];

  const col = document.getElementById('col-equipment');
  const list = document.getElementById('eq-list');
  document.getElementById('eq-detail-box').classList.remove('show');

  if (items.length === 0) {
    list.innerHTML = '<div class="eq-empty">Aucun équipement enregistré</div>';
    col.style.display = 'none';
    return;
  }

  col.style.display = 'block';

  _cardsEqData = items;
  list.innerHTML = items.map((it, i) => `
    <div class="eq-item" id="eq-item-${i}" onclick="selectEquipment(${i})">
      <span class="eq-cat">${it.category}</span>
      <span class="eq-brand">${it.brand || '—'}</span>
      <span class="eq-ref">${it.reference || ''}</span>
    </div>
  `).join('');
}

let _cardsEqData = [];

function selectEquipment(idx) {
  document.querySelectorAll('.eq-item').forEach((el, i) => el.classList.toggle('selected', i === idx));
  const it = _cardsEqData[idx];
  if (!it) return;
  document.getElementById('eq-d-brand').textContent = it.brand    || '—';
  document.getElementById('eq-d-ref').textContent   = it.reference || '—';
  document.getElementById('eq-d-det').textContent   = it.details  || '—';
  document.getElementById('eq-detail-box').classList.add('show');
}

function _fillEditFields(p) {
  document.getElementById('ed_prenom').value      = p.prenom       || '';
  document.getElementById('ed_nom').value         = p.nom          || '';
  document.getElementById('ed_nationality').value = p.nationality  || '';
  document.getElementById('ed_hometown').value    = p.hometown     || '';
  document.getElementById('ed_age').value         = p.age          || '';
  document.getElementById('ed_achievements').value= p.achievements || '';
  document.getElementById('ed_team').value        = p.team         || '';
}

function resetEdits() {
  if (_originalProfile) _fillEditFields(_originalProfile);
}

function filterSponsors(query) {
  const q = query.toLowerCase().trim();
  let visible = 0;
  document.querySelectorAll('.sponsor-chip').forEach(c => {
    const match = !q || c.dataset.key.includes(q) || c.querySelector('span').textContent.toLowerCase().includes(q);
    c.style.display = match ? '' : 'none';
    if (match) visible++;
  });
  document.getElementById('sponsor-empty').style.display = visible === 0 ? 'block' : 'none';
}

function toggleSponsor(key, checked) {
  if (checked) selectedSponsors.add(key);
  else selectedSponsors.delete(key);
  if (selectedSponsors.size === 0) {
    const slug = document.getElementById('rider')?.value || '';
    const profile = _app.profiles.find(p => p.slug === slug);
    syncAutoSponsors(profile);
    debouncedGenerate(200);
    return;
  }
  document.querySelectorAll('.sponsor-chip').forEach(c => {
    c.classList.remove('auto-active');
    c.classList.toggle('active', c.dataset.key === key && checked ||
                                 c.dataset.key !== key && c.querySelector('input').checked);
  });
  const badge = document.getElementById('sponsor-mode');
  badge.textContent = selectedSponsors.size === 0 ? 'AUTO depuis Excel' : `${selectedSponsors.size} sélectionné(s)`;
  debouncedGenerate(200);
}

// ── Debounce & live preview ───────────────────────────────────────────────
let _debTimer = null;
function debouncedGenerate(delay=450) {
  clearTimeout(_debTimer);
  if (!document.getElementById('rider').value) return;
  _debTimer = setTimeout(generate, delay);
}

// ── Historique (undo) ─────────────────────────────────────────────────────
const _history = [];
const MAX_HIST  = 40;
let   _capLock  = false;   // évite les doublons rapides

function captureHistory() {
  if (_capLock) return;
  _capLock = true;
  setTimeout(() => { _capLock = false; }, 800);
  const snap = getCurrentSnapshot();
  if (_history.length && JSON.stringify(_history[_history.length-1]) === JSON.stringify(snap)) return;
  _history.push(snap);
  if (_history.length > MAX_HIST) _history.shift();
  document.getElementById('btn-undo').disabled = _history.length < 2;
}

function undo() {
  if (_history.length < 2) return;
  _history.pop();                          // retire l'état courant
  const prev = _history[_history.length - 1];
  applySnapshot(prev);
  document.getElementById('btn-undo').disabled = _history.length < 2;
  debouncedGenerate(100);
}

document.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
    e.preventDefault();
    undo();
  }
});

// ── Valeurs par défaut par section ────────────────────────────────────────
const SECTION_DEFAULTS = {
  photo: { photo_zoom: 100, offset_x: -200, offset_y: 0 },
  text:  { text_x: 580, text_top: 80, sz_label: 36, sz_value: 54, sz_value_sm: 40, gap: 50 },
  logos: { logo_h: 50, logo_y: 1200, logo_x: 810, logo_dir: 'row' },
};

function resetSection(section) {
  captureHistory();
  applySnapshot(SECTION_DEFAULTS[section]);
  debouncedGenerate(100);
}

// ── Apply snapshot (utilisé par undo, profils, reset) ─────────────────────
function applySnapshot(vals) {
  SLIDER_DEFS.forEach(({ rid, vid, pct, auto }) => {
    if (lockedSliders.has(rid)) return;
    const v = vals[rid];
    if (v === undefined) return;
    document.getElementById(rid).value = v;
    if (auto && v === -1)   document.getElementById(vid).value = 'Auto';
    else if (pct)           document.getElementById(vid).value = v + '%';
    else                    document.getElementById(vid).value = v;
  });
  if (vals.logo_dir !== undefined) {
    const isCol = vals.logo_dir === 'col';
    document.getElementById('logo_dir').value = vals.logo_dir;
    document.getElementById('dir-toggle').classList.toggle('on', isCol);
    document.getElementById('dir-label').textContent = isCol ? '▼▼ COLONNE' : '▶▶ LIGNE';
  }
}

function updateSlider(el, valId, autoMode=false) {
  const v = parseInt(el.value);
  document.getElementById(valId).value = (autoMode && v === -1) ? 'Auto' : v;
  debouncedGenerate();
}
function updateSliderPct(el, valId) {
  document.getElementById(valId).value = el.value + '%';
  debouncedGenerate();
}
function syncVal(valId, rangeId, autoMode=false) {
  const inp   = document.getElementById(valId);
  const range = document.getElementById(rangeId);
  let raw = inp.value.replace('%','').trim();
  if (autoMode && raw.toLowerCase() === 'auto') { range.value = -1; debouncedGenerate(); return; }
  const v = parseInt(raw);
  if (isNaN(v)) { inp.value = autoMode ? 'Auto' : range.value; return; }
  const clamped = Math.max(parseInt(range.min), Math.min(parseInt(range.max), v));
  range.value = clamped;
  inp.value   = autoMode && clamped === -1 ? 'Auto' : (valId === 'val_zoom' ? clamped + '%' : clamped);
  debouncedGenerate();
}
function switchDir() {
  captureHistory();
  const input  = document.getElementById('logo_dir');
  const toggle = document.getElementById('dir-toggle');
  const isCol  = input.value === 'col';
  input.value  = isCol ? 'row' : 'col';
  toggle.classList.toggle('on', !isCol);
  document.getElementById('dir-label').textContent = isCol ? '▶▶ LIGNE' : '▼▼ COLONNE';
  debouncedGenerate();
}

// ── Génération ────────────────────────────────────────────────────────────
async function generate() {
  const slug = document.getElementById('rider').value;
  if (!slug) return;

  const area = document.getElementById('preview-area');
  area.classList.add('loading');
  const errorMsg = document.getElementById('error-msg');
  errorMsg.classList.remove('warning');
  errorMsg.style.display = 'none';

  const params = {
    slug,
    overrides: {
      prenom:       document.getElementById('ed_prenom').value,
      nom:          document.getElementById('ed_nom').value,
      nationality:  document.getElementById('ed_nationality').value,
      hometown:     document.getElementById('ed_hometown').value,
      age:          document.getElementById('ed_age').value,
      achievements: document.getElementById('ed_achievements').value,
      team:         document.getElementById('ed_team').value,
    },
    photo_zoom:  parseInt(document.getElementById('photo_zoom').value) / 100,
    offset_x:    parseInt(document.getElementById('offset_x').value),
    offset_y:    parseInt(document.getElementById('offset_y').value),
    text_x:      parseInt(document.getElementById('text_x').value),
    text_top:    parseInt(document.getElementById('text_top').value),
    sz_label:    parseInt(document.getElementById('sz_label').value),
    sz_value:    parseInt(document.getElementById('sz_value').value),
    sz_value_sm: parseInt(document.getElementById('sz_value_sm').value),
    gap:         parseInt(document.getElementById('gap').value),
    logo_h:      parseInt(document.getElementById('logo_h').value),
    logo_y:      parseInt(document.getElementById('logo_y').value),
    logo_x:      parseInt(document.getElementById('logo_x').value),
    logo_dir:    document.getElementById('logo_dir').value,
    sponsors:    selectedSponsors.size > 0 ? [...selectedSponsors] : null,
    result_badge: _latestResultBadge,
  };

  try {
    const res = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || 'Erreur inconnue');
    }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const img = document.getElementById('preview-img');
    img.onload = () => { area.classList.remove('loading'); };
    img.src = url;
    img.style.display = 'block';
    document.getElementById('placeholder').style.display = 'none';
    lastSlug = slug;
    document.getElementById('btn-dl').disabled = false;
    document.getElementById('cards-add-library-btn').disabled = false;
    _lastRiderCardUrl = url;
    _lastPublishSource = {
      kind: 'rider',
      url,
      name: (slug || 'card') + '.jpg',
      mime: 'image/jpeg',
    };
    const riderProfile = _app.profiles.find(p => p.slug === slug) || null;
    const riderLabel = riderProfile ? `${riderProfile.prenom} ${riderProfile.nom}` : (slug || 'card');
  } catch(e) {
    area.classList.remove('loading');
    const msg = document.getElementById('error-msg');
    msg.classList.remove('warning');
    msg.textContent = '❌ ' + e.message;
    msg.style.display = 'block';
  }
}

// ── Téléchargement ────────────────────────────────────────────────────────
function download() {
  const img = document.getElementById('preview-img');
  const a = document.createElement('a');
  a.href = img.src;
  a.download = (lastSlug || 'card') + '.jpg';
  a.click();
}

async function reloadExcel() {
  await fetch('/api/reload', { method: 'POST' });
  location.reload();
}

// ── Equipment performance ───────────────────────────────────────────────────
let _perfInitialized = false;
let _perfAdvancedOpen = false;
let _perfRefreshInFlight = false;
let _lastPerfInfographic = null;
let _activeTab = 'cards';
const _PERF_ORDER = [
  'Frame', 'Fork', 'Rear Shock', 'Handlebar', 'Dropper Post', 'Saddle',
  'Crankset', 'Chain', 'Derailleur', 'Brake Lever', 'Brake Caliper',
  'Wheels', 'Tires', 'Pedals', 'Grip', 'Shoes', 'Helmet', 'Protection', 'Goggles', 'Disk'
];

function _esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

function _perfKey(s) {
  return String(s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
}

function _perfCategories() {
  const set = new Set();
  Object.values(_app.equipment || {}).forEach(items => {
    (items || []).forEach(it => { if (it.category) set.add(it.category); });
  });
  return Array.from(set).sort((a, b) => {
    const ia = _PERF_ORDER.indexOf(a);
    const ib = _PERF_ORDER.indexOf(b);
    if (ia >= 0 || ib >= 0) return (ia >= 0 ? ia : 999) - (ib >= 0 ? ib : 999);
    return a.localeCompare(b);
  });
}

function initPerformancePage() {
  if (!_perfInitialized) {
    _perfInitialized = true;
    const sel = document.getElementById('perf-category');
    if (sel) {
      const cats = _perfCategories();
      sel.innerHTML = [
        '<option value="all">Toutes catégories</option>',
        ...cats.map(cat => `<option value="${_esc(cat)}">${_esc(cat)}</option>`)
      ].join('');
      if (cats.includes('Fork')) sel.value = 'Fork';
    }
  }
  populatePerformanceInfoFields();
  renderPerformance();
  refreshPerformanceData(true);
}

function populatePerformanceInfoFields() {
  const list = document.getElementById('perf-info-competition-list');
  if (list) {
    list.innerHTML = (_app.resultEvents || [])
      .map(name => `<option value="${_esc(name)}"></option>`)
      .join('');
  }
  const competition = document.getElementById('perf-info-competition');
  if (competition && !competition.value && (_app.resultEvents || []).length) {
    competition.placeholder = _app.resultEvents[_app.resultEvents.length - 1] || 'Nom de la compétition';
  }
  const category = document.getElementById('perf-info-category-label');
  if (category && !category.value) {
    category.placeholder = _perfDefaultCategoryLabel();
  }
}

function _perfLatestEvent() {
  const events = (_app.resultEvents || []).slice().reverse();
  return events.find(event => (_app.results || []).some(rider =>
    (rider.events || []).some(item => item.event === event && Number(item.points || 0) > 0)
  )) || events[0] || '';
}

function _perfEventPoints(rider, eventName) {
  const item = (rider?.events || []).find(event => event.event === eventName);
  return Number(item?.points || 0);
}

function _perfScopeMode() {
  return document.getElementById('perf-scope')?.value || 'season';
}

function _perfScopeEvent() {
  return _perfLatestEvent();
}

function _perfScoreForRider(rider, scopeMode = _perfScopeMode(), eventName = _perfScopeEvent()) {
  if (scopeMode === 'last_race') return _perfEventPoints(rider, eventName);
  return Number(rider?.total_points || 0);
}

function _perfRankForRider(rider, scopeMode = _perfScopeMode()) {
  if (Number.isFinite(Number(rider?._perf_rank))) return Number(rider._perf_rank);
  if (scopeMode === 'last_race') return 999;
  return Number(rider?.rank || 999);
}

function _perfOverviewRows(gender, mode, eventName) {
  let rows = (_app.results || []).filter(rider => rider.genre === gender);
  if (mode === 'event') {
    rows = rows.filter(rider => _perfEventPoints(rider, eventName) > 0)
      .sort((a, b) => (_perfEventPoints(b, eventName) - _perfEventPoints(a, eventName)) || String(a.name).localeCompare(String(b.name)));
  } else {
    rows = rows.filter(rider => Number(rider.total_points || 0) > 0)
      .sort((a, b) => (Number(a.rank || 999) - Number(b.rank || 999)) || (Number(b.total_points || 0) - Number(a.total_points || 0)));
  }
  return rows.slice(0, 5);
}

function _perfOverviewList(rows, mode, eventName) {
  if (!rows.length) return '<div class="perf-empty">Aucun résultat disponible.</div>';
  return rows.map((rider, index) => {
    const rank = mode === 'event' ? index + 1 : Number(rider.rank || index + 1);
    const points = mode === 'event' ? _perfEventPoints(rider, eventName) : Number(rider.total_points || 0);
    const handle = String(rider.instagram || '').replace(/^@/, '').toLowerCase();
    const canGenerate = !!handle && (_app.profiles || []).some(profile =>
      String(profile.instagram || '').replace(/^@/, '').toLowerCase() === handle
    );
    const generateButton = mode === 'event'
      ? `<button class="perf-card-generate" title="Générer la carte rider avec ce résultat"
          data-handle="${_esc(handle)}" data-event="${_esc(eventName)}" data-position="${rank}"
          onclick="generateLatestResultCard(this)" ${canGenerate ? '' : 'disabled'}>＋</button>`
      : '<span></span>';
    return `<div class="perf-overview-row">
      <div class="perf-overview-rank">#${rank}</div>
      <div class="perf-overview-name" title="${_esc(rider.name)}">${rider.flag ? _esc(rider.flag) + ' ' : ''}${_esc(rider.name)}</div>
      <div class="perf-overview-points">${Math.round(points)} pts</div>
      ${generateButton}
    </div>`;
  }).join('');
}

async function generateLatestResultCard(button) {
  const handle = String(button?.dataset?.handle || '').replace(/^@/, '').toLowerCase();
  const eventName = String(button?.dataset?.event || '').trim();
  const position = Number(button?.dataset?.position || 0);
  const profile = (_app.profiles || []).find(item =>
    String(item.instagram || '').replace(/^@/, '').toLowerCase() === handle
  );
  if (!profile?.slug || !position) return;

  button.disabled = true;
  button.textContent = '…';
  genderFilter = 'all';
  document.getElementById('btn-f').className = 'gender-btn';
  document.getElementById('btn-m').className = 'gender-btn';
  renderRiderList();
  switchTab('cards');

  const riderSelect = document.getElementById('rider');
  riderSelect.value = profile.slug;
  await onRiderChange();
  clearTimeout(_debTimer);

  const achievements = document.getElementById('ed_achievements');
  const ordinal = position % 100 >= 11 && position % 100 <= 13
    ? `${position}th`
    : `${position}${position % 10 === 1 ? 'st' : position % 10 === 2 ? 'nd' : position % 10 === 3 ? 'rd' : 'th'}`;
  const autoLine = `- ${ordinal} ${eventName || 'Dernière étape'} WC026`;
  const existing = String(achievements.value || '').split(/\r?\n/)
    .map(line => line.trim())
    .filter(line => line && !/^WC 2026\s*[·—-]/i.test(line) && !/^-\s*\d+(?:st|nd|rd|th)\s+.+\s+WC026$/i.test(line));
  achievements.value = [autoLine, ...existing].join('\n');

  profile.achievements = achievements.value;
  const badgeStyle = document.getElementById('perf-result-badge-style')?.value || 'banner';
  _latestResultBadge = position <= 3 ? { position, event: eventName, season: 'WC026', style: badgeStyle } : null;

  let syncWarning = '';
  try {
    const syncResponse = await fetch('/api/performance/sync-palmares', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        instagram: handle,
        first_name: profile.prenom || '',
        last_name: profile.nom || '',
        palmares: achievements.value,
      }),
    });
    const syncData = await syncResponse.json();
    if (!syncResponse.ok || !syncData.ok) {
      throw new Error(syncData.error || 'Mise à jour Google Sheets impossible');
    }
  } catch (error) {
    syncWarning = `Google Sheet non synchronisé : ${error.message}`;
    console.warn('[Performance]', syncWarning);
  }

  try {
    await generate();
    if (syncWarning) {
      const msg = document.getElementById('error-msg');
      if (msg) {
        msg.classList.add('warning');
        msg.textContent = '⚠️ Carte générée. Google Sheet non synchronisé.';
        msg.style.display = 'block';
      }
    }
  } catch (error) {
    button.disabled = false;
    button.textContent = '＋';
    window.alert(`Génération carte : ${error.message}`);
  }
}

function renderPerformanceOverview() {
  const root = document.getElementById('perf-overview');
  if (!root) return;
  const latestEvent = _perfLatestEvent();
  const context = document.getElementById('perf-event-context');
  const selectedBadgeStyle = document.getElementById('perf-result-badge-style')?.value || 'banner';
  if (context) {
    context.innerHTML = `
      <div class="perf-event-competition">Compétition · UCI Downhill World Cup 2026</div>
      <div class="perf-event-latest">Dernière étape · ${latestEvent ? _esc(latestEvent) : 'Indisponible'}</div>
      <label class="perf-result-style">
        Badge carte
        <select id="perf-result-badge-style">
          <option value="banner" ${selectedBadgeStyle === 'banner' ? 'selected' : ''}>Bandeau résultat</option>
          <option value="v1" ${selectedBadgeStyle === 'v1' ? 'selected' : ''}>Capsule V1</option>
        </select>
      </label>
    `;
  }
  root.innerHTML = ['F', 'M'].map(gender => {
    const latest = _perfOverviewRows(gender, 'event', latestEvent);
    const overall = _perfOverviewRows(gender, 'overall', latestEvent);
    return `<section class="perf-overview-card">
      <div class="perf-overview-head">
        <div class="perf-overview-gender">${gender === 'F' ? '♀ Femmes' : '♂ Hommes'}</div>
        <div class="perf-overview-event">${latestEvent ? _esc(latestEvent) : 'Dernière compétition indisponible'}</div>
      </div>
      <div class="perf-overview-columns">
        <div class="perf-overview-section">
          <div class="perf-overview-label">Dernier résultat</div>
          ${_perfOverviewList(latest, 'event', latestEvent)}
        </div>
        <div class="perf-overview-section">
          <div class="perf-overview-label">Classement général</div>
          ${_perfOverviewList(overall, 'overall', latestEvent)}
        </div>
      </div>
    </section>`;
  }).join('');
}

function _setPerfInfoCheckbox(id, value) {
  const el = document.getElementById(id);
  if (el) el.checked = value;
}

function syncPerformanceInfographicOptions() {
  const view = document.getElementById('perf-view')?.value || 'equipment';
  if (view === 'riders') {
    _setPerfInfoCheckbox('perf-info-show-subtitle', true);
    _setPerfInfoCheckbox('perf-info-show-competition', true);
    _setPerfInfoCheckbox('perf-info-show-bars', false);
    _setPerfInfoCheckbox('perf-info-show-points', true);
    _setPerfInfoCheckbox('perf-info-show-count', false);
    _setPerfInfoCheckbox('perf-info-show-percent', false);
  } else {
    _setPerfInfoCheckbox('perf-info-show-subtitle', true);
    _setPerfInfoCheckbox('perf-info-show-competition', true);
    _setPerfInfoCheckbox('perf-info-show-bars', true);
    _setPerfInfoCheckbox('perf-info-show-points', true);
    _setPerfInfoCheckbox('perf-info-show-count', true);
    _setPerfInfoCheckbox('perf-info-show-percent', false);
  }
  const category = document.getElementById('perf-info-category-label');
  if (category && !category.value) category.placeholder = _perfDefaultCategoryLabel();
}

function togglePerformanceAdvanced() {
  _perfAdvancedOpen = !_perfAdvancedOpen;
  document.getElementById('perf-advanced')?.classList.toggle('open', _perfAdvancedOpen);
  document.getElementById('perf-advanced-results').style.display = _perfAdvancedOpen ? 'grid' : 'none';
  const btn = document.getElementById('perf-advanced-toggle');
  if (btn) {
    btn.classList.toggle('active', _perfAdvancedOpen);
    btn.textContent = _perfAdvancedOpen ? '▾ Advanced' : '▸ Advanced';
  }
}

async function refreshPerformanceData(silent = false) {
  if (_perfRefreshInFlight) return;
  _perfRefreshInFlight = true;
  const status = document.getElementById('perf-status');
  if (status && !silent) status.textContent = 'Actualisation des résultats depuis Google Sheet...';
  try {
    const res = await fetch('/api/performance-results?refresh=1');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    _app.results = data.results?.riders || [];
    _app.resultEvents = data.results?.events || [];
    populatePerformanceInfoFields();
    renderPerformanceOverview();
    renderPerformance();
    if (status) {
      const d = new Date();
      status.textContent = `Résultats synchronisés à ${d.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}. Auto-refresh actif.`;
    }
  } catch(e) {
    if (status) status.textContent = 'Actualisation impossible pour le moment. Les données locales restent affichées.';
  } finally {
    _perfRefreshInFlight = false;
  }
}

function _perfSelectedRidersFor(gender = 'F', topVal = '10', scopeMode = _perfScopeMode(), eventName = _perfScopeEvent()) {
  let rows = (_app.results || [])
    .filter(r => r.instagram)
    .map(r => ({ ...r, _perf_points: _perfScoreForRider(r, scopeMode, eventName) }))
    .filter(r => r._perf_points > 0);
  if (gender !== 'all') rows = rows.filter(r => r.genre === gender);

  rows = rows.slice().sort((a, b) => {
    if (scopeMode === 'last_race' || gender === 'all') {
      return (Number(b._perf_points || 0) - Number(a._perf_points || 0)) || String(a.name || '').localeCompare(String(b.name || ''));
    }
    return (Number(a.rank || 999) - Number(b.rank || 999)) || (Number(b._perf_points || 0) - Number(a._perf_points || 0));
  }).map((rider, idx) => ({
    ...rider,
    _perf_rank: scopeMode === 'last_race' ? idx + 1 : Number(rider.rank || idx + 1),
  }));

  if (topVal !== 'all') {
    const limit = Number(topVal);
    rows = scopeMode === 'last_race' || gender === 'all'
      ? rows.slice(0, limit)
      : rows.filter(r => Number(r.rank || 999) <= limit);
  }
  return rows;
}

function _perfSelectedRiders() {
  const gender = document.getElementById('perf-gender')?.value || 'F';
  const topVal = document.getElementById('perf-top')?.value || '10';
  const scopeMode = _perfScopeMode();
  const eventName = _perfScopeEvent();
  return _perfSelectedRidersFor(gender, topVal, scopeMode, eventName);
}

function _perfItemLabel(item, groupMode) {
  const brand = (item?.brand || '').trim();
  const ref = (item?.reference || '').trim();
  if (groupMode === 'brand') return brand || 'Unknown brand';
  return [brand, ref].filter(Boolean).join(' · ') || brand || ref || 'Unknown product';
}

function _perfProfileMap() {
  const map = new Map();
  (_app.profiles || []).forEach(profile => {
    const handle = String(profile.instagram || '').replace(/^@/, '').toLowerCase().trim();
    if (handle) map.set(handle, profile);
  });
  return map;
}

function _perfProfileForRider(rider, profileMap = _perfProfileMap()) {
  const handle = String(rider?.instagram || '').replace(/^@/, '').toLowerCase().trim();
  return profileMap.get(handle) || null;
}

function _perfHasRealTeam(team) {
  const key = _perfKey(team);
  return !!key && !['n a', 'na', 'none', 'no team', 'independent', 'independent unknown', 'unknown'].includes(key);
}

function _perfTeamRowsFor(gender = 'all', scopeMode = _perfScopeMode(), eventName = _perfScopeEvent()) {
  const profileMap = _perfProfileMap();
  let riders = (_app.results || [])
    .filter(r => r.instagram)
    .map(r => ({ ...r, _perf_points: _perfScoreForRider(r, scopeMode, eventName) }))
    .filter(r => r._perf_points > 0);
  if (gender !== 'all') riders = riders.filter(r => r.genre === gender);
  riders = riders.filter(rider => {
    const profile = _perfProfileForRider(rider, profileMap);
    const rawTeam = String(profile?.team || rider.team || '').trim();
    return _perfHasRealTeam(rawTeam);
  });

  const teams = new Map();
  riders.forEach(rider => {
    const profile = _perfProfileForRider(rider, profileMap);
    const rawTeam = String(profile?.team || rider.team || '').trim();
    const team = rawTeam;
    const key = _perfKey(team) || 'unknown';
    if (!teams.has(key)) {
      teams.set(key, {
        team,
        count: 0,
        menCount: 0,
        womenCount: 0,
        points: 0,
        menPoints: 0,
        womenPoints: 0,
        bestRank: 999,
        riders: [],
      });
    }
    const st = teams.get(key);
    const pts = Number(rider._perf_points || 0);
    const rank = _perfRankForRider(rider, scopeMode);
    st.count += 1;
    st.points += pts;
    st.bestRank = Math.min(st.bestRank, rank);
    if (rider.genre === 'M') {
      st.menCount += 1;
      st.menPoints += pts;
    } else if (rider.genre === 'F') {
      st.womenCount += 1;
      st.womenPoints += pts;
    }
    st.riders.push({
      name: rider.name,
      genre: rider.genre || '',
      rank,
      points: pts,
      flag: rider.flag || '',
    });
  });

  const rows = Array.from(teams.values()).map(st => {
    const sortedRiders = st.riders.slice().sort((a, b) => {
      return (b.points - a.points) || (a.rank - b.rank);
    });
    return {
      ...st,
      label: st.team,
      topRider: sortedRiders[0] || null,
    };
  }).sort((a, b) => {
    return (b.points - a.points) || (b.count - a.count) || (a.bestRank - b.bestRank);
  });
  return { riders, rows };
}

function _perfSetKpis(items) {
  void items;
}

function _perfGenderLabel(gender) {
  if (gender === 'M') return 'Hommes';
  if (gender === 'F') return 'Femmes';
  return 'Mixte';
}

function _perfDefaultCategoryLabel() {
  const view = document.getElementById('perf-view')?.value || 'equipment';
  const gender = document.getElementById('perf-gender')?.value || 'F';
  if (view === 'riders') {
    if (gender === 'M') return 'Elite Men DH';
    if (gender === 'F') return 'Elite Women DH';
    return 'Elite DH';
  }
  if (view === 'teams') return 'Team DH';
  const category = document.getElementById('perf-category')?.value || 'Equipment';
  return category === 'all' ? 'Equipment DH' : `${category} DH`;
}

function _perfInfoContext() {
  const competitionInput = document.getElementById('perf-info-competition');
  const categoryInput = document.getElementById('perf-info-category-label');
  const latestEvent = _perfLatestEvent();
  const competition = String(competitionInput?.value || latestEvent || 'Saison 2026').trim();
  const category = String(categoryInput?.value || _perfDefaultCategoryLabel()).trim();
  return { competition, category };
}

function _perfInfoSubtitle(context) {
  const showCompetition = document.getElementById('perf-info-show-competition')?.checked !== false;
  const scopeMode = _perfScopeMode();
  const parts = [
    scopeMode === 'last_race' ? 'Last race' : '',
    showCompetition ? context.competition : '',
    context.category,
  ].filter(Boolean);
  return parts.join(' · ') || context.category || context.competition || 'Saison 2026';
}

function _perfStatsFor({ category = 'all', gender = 'F', topVal = '10', groupMode = 'product', scopeMode = _perfScopeMode(), eventName = _perfScopeEvent() } = {}) {
  const riders = _perfSelectedRidersFor(gender, topVal, scopeMode, eventName);
  const stats = new Map();
  let itemHits = 0;
  let pointsCovered = 0;

  riders.forEach(rider => {
    const handle = String(rider.instagram || '').replace(/^@/, '').toLowerCase();
    const items = _app.equipment?.[handle] || [];
    const selectedItems = category === 'all'
      ? items
      : items.filter(it => it.category === category);

    selectedItems.forEach(item => {
      if (!item?.brand && !item?.reference) return;
      const label = _perfItemLabel(item, groupMode);
      const key = `${item.category}::${_perfKey(label)}`;
      if (!stats.has(key)) {
        stats.set(key, {
          category: item.category,
          label,
          brand: item.brand || '',
          reference: item.reference || '',
          count: 0,
          points: 0,
          bestRank: 999,
          rankSum: 0,
          riders: [],
        });
      }
      const st = stats.get(key);
      const pts = Number(rider._perf_points ?? _perfScoreForRider(rider, scopeMode, eventName));
      const rank = _perfRankForRider(rider, scopeMode);
      st.count += 1;
      st.points += pts;
      st.bestRank = Math.min(st.bestRank, rank);
      st.rankSum += rank;
      st.riders.push({
        name: rider.name,
        genre: rider.genre,
        rank,
        points: pts,
        flag: rider.flag || '',
      });
      itemHits += 1;
      pointsCovered += pts;
    });
  });

  const rows = Array.from(stats.values()).map(st => ({
    ...st,
    avgRank: st.count ? st.rankSum / st.count : 999,
  }));
  return { riders, rows, itemHits, pointsCovered };
}

function _perfStats() {
  const category = document.getElementById('perf-category')?.value || 'all';
  const gender = document.getElementById('perf-gender')?.value || 'F';
  const topVal = document.getElementById('perf-top')?.value || '10';
  const groupMode = document.getElementById('perf-group')?.value || 'product';
  const scopeMode = _perfScopeMode();
  const eventName = _perfScopeEvent();
  return _perfStatsFor({ category, gender, topVal, groupMode, scopeMode, eventName });
}

function _perfSortRowsBy(rows, sort = 'points') {
  return rows.slice().sort((a, b) => {
    if (sort === 'count') return (b.count - a.count) || (b.points - a.points) || (a.avgRank - b.avgRank);
    if (sort === 'avg_rank') return (a.avgRank - b.avgRank) || (b.points - a.points) || (b.count - a.count);
    if (sort === 'best_rank') return (a.bestRank - b.bestRank) || (b.points - a.points) || (b.count - a.count);
    return (b.points - a.points) || (b.count - a.count) || (a.avgRank - b.avgRank);
  });
}

function _perfSortRows(rows) {
  const sort = document.getElementById('perf-sort')?.value || 'points';
  return _perfSortRowsBy(rows, sort);
}

function _renderPerformanceRiders(leadersEl, tableEl) {
  const gender = document.getElementById('perf-gender')?.value || 'F';
  const topVal = document.getElementById('perf-top')?.value || '10';
  const scopeMode = _perfScopeMode();
  const eventName = _perfScopeEvent();
  const rows = _perfSelectedRidersFor(gender, topVal, scopeMode, eventName).map(rider => {
    const profile = _perfProfileForRider(rider);
    return {
      ...rider,
      label: rider.name || rider.instagram || 'Unknown rider',
      team: String(profile?.team || rider.team || '').trim() || 'Independent / unknown',
      points: Number(rider._perf_points ?? _perfScoreForRider(rider, scopeMode, eventName)),
      rank: _perfRankForRider(rider, scopeMode),
    };
  }).sort((a, b) => {
    if (scopeMode === 'last_race' || gender === 'all') return (b.points - a.points) || (a.rank - b.rank);
    return (a.rank - b.rank) || (b.points - a.points);
  });
  const totalPoints = rows.reduce((sum, r) => sum + r.points, 0);
  const teamCount = new Set(rows.map(r => _perfKey(r.team)).filter(Boolean)).size;

  _perfSetKpis([
    { label: 'Riders classés', value: rows.length },
    { label: 'Teams représentées', value: teamCount },
    { label: 'Classement', value: _perfGenderLabel(gender) },
    { label: 'Points cumulés', value: Math.round(totalPoints) },
  ]);

  if (!rows.length) {
    leadersEl.innerHTML = '<div class="perf-empty">Aucun rider classé pour cette sélection.</div>';
    tableEl.innerHTML = '<div class="perf-empty">Vérifie l’onglet Résultats 2026.</div>';
    return;
  }

  leadersEl.innerHTML = rows.slice(0, 10).map((rider, idx) => `
    <div class="perf-leader">
      <div class="perf-rank">${idx + 1}</div>
      <div class="perf-main">
        <div class="perf-name">${_esc(rider.label)}</div>
        <div class="perf-meta">${_esc(rider.team)} · ${_esc(_perfGenderLabel(rider.genre || 'all'))} · rang #${rider.rank}</div>
      </div>
      <div class="perf-score">${Math.round(rider.points)}<small>pts</small></div>
    </div>
  `).join('');

  tableEl.innerHTML = `
    <table class="perf-table">
      <thead>
        <tr>
          <th>#</th>
          <th>Rider</th>
          <th>Classement</th>
          <th>Team</th>
          <th>Rang officiel</th>
          <th>Points</th>
        </tr>
      </thead>
      <tbody>
        ${rows.slice(0, 60).map((rider, idx) => `
          <tr>
            <td>${idx + 1}</td>
            <td><strong>${_esc(rider.label)}</strong></td>
            <td>${_esc(_perfGenderLabel(rider.genre || 'all'))}</td>
            <td>${_esc(rider.team)}</td>
            <td>#${rider.rank}</td>
            <td>${Math.round(rider.points)}</td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

function _renderPerformanceTeams(leadersEl, tableEl) {
  const gender = document.getElementById('perf-gender')?.value || 'all';
  const scopeMode = _perfScopeMode();
  const eventName = _perfScopeEvent();
  const { riders, rows } = _perfTeamRowsFor(gender, scopeMode, eventName);
  const totalPoints = rows.reduce((sum, r) => sum + r.points, 0);
  const bestTeam = rows[0];

  _perfSetKpis([
    { label: 'Teams classées', value: rows.length },
    { label: 'Riders comptés', value: riders.length },
    { label: 'Top team', value: bestTeam ? Math.round(bestTeam.points) : 0 },
    { label: 'Points cumulés', value: Math.round(totalPoints) },
  ]);

  if (!rows.length) {
    leadersEl.innerHTML = '<div class="perf-empty">Aucune team détectée pour cette sélection.</div>';
    tableEl.innerHTML = '<div class="perf-empty">Vérifie les teams dans les profils riders.</div>';
    return;
  }

  leadersEl.innerHTML = rows.slice(0, 10).map((team, idx) => `
    <div class="perf-leader">
      <div class="perf-rank">${idx + 1}</div>
      <div class="perf-main">
        <div class="perf-name">${_esc(team.team)}</div>
        <div class="perf-meta">${team.count} rider${team.count > 1 ? 's' : ''} · Femmes ${Math.round(team.womenPoints)} pts · Hommes ${Math.round(team.menPoints)} pts</div>
      </div>
      <div class="perf-score">${Math.round(team.points)}<small>pts</small></div>
    </div>
  `).join('');

  tableEl.innerHTML = `
    <table class="perf-table">
      <thead>
        <tr>
          <th>#</th>
          <th>Team</th>
          <th>Riders</th>
          <th>Points femmes</th>
          <th>Points hommes</th>
          <th>Total</th>
          <th>Top rider</th>
        </tr>
      </thead>
      <tbody>
        ${rows.slice(0, 60).map((team, idx) => {
          const top = team.topRider;
          const topText = top ? `${top.flag ? top.flag + ' ' : ''}${top.name} (${Math.round(top.points)} pts)` : '';
          return `<tr>
            <td>${idx + 1}</td>
            <td><strong>${_esc(team.team)}</strong></td>
            <td>${team.count} <span class="perf-riders">(${team.womenCount} F / ${team.menCount} H)</span></td>
            <td>${Math.round(team.womenPoints)}</td>
            <td>${Math.round(team.menPoints)}</td>
            <td>${Math.round(team.points)}</td>
            <td class="perf-riders">${_esc(topText)}</td>
          </tr>`;
        }).join('')}
      </tbody>
    </table>
  `;
}

function _perfInfoRoundRect(ctx, x, y, w, h, r) {
  const radius = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.lineTo(x + w - radius, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + radius);
  ctx.lineTo(x + w, y + h - radius);
  ctx.quadraticCurveTo(x + w, y + h, x + w - radius, y + h);
  ctx.lineTo(x + radius, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - radius);
  ctx.lineTo(x, y + radius);
  ctx.quadraticCurveTo(x, y, x + radius, y);
  ctx.closePath();
}

function _perfInfoDrawFrame(ctx, x, y, w, h, r, accent) {
  ctx.save();
  _perfInfoRoundRect(ctx, x, y, w, h, r);
  ctx.fillStyle = '#121212';
  ctx.fill();
  ctx.strokeStyle = 'rgba(200,212,0,0.44)';
  ctx.lineWidth = 2;
  ctx.stroke();

  _perfInfoRoundRect(ctx, x + 14, y + 14, w - 28, h - 28, Math.max(12, r - 12));
  ctx.strokeStyle = 'rgba(255,255,255,0.08)';
  ctx.lineWidth = 1;
  ctx.stroke();

  const corners = [
    [x + 28, y + 28, 1, 1],
    [x + w - 28, y + 28, -1, 1],
    [x + 28, y + h - 28, 1, -1],
    [x + w - 28, y + h - 28, -1, -1],
  ];
  corners.forEach(([cx, cy, sx, sy]) => {
    ctx.strokeStyle = 'rgba(200,212,0,0.72)';
    ctx.lineWidth = 6;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + sx * 42, cy);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx, cy + sy * 42);
    ctx.stroke();
    ctx.fillStyle = accent;
    ctx.beginPath();
    ctx.arc(cx, cy, 5, 0, Math.PI * 2);
    ctx.fill();
  });
  ctx.restore();
}

function _perfInfoWrapText(ctx, text, x, y, maxWidth, lineHeight, maxLines = 2) {
  const words = String(text || '').split(/\s+/).filter(Boolean);
  const lines = [];
  let line = '';
  words.forEach(word => {
    const test = line ? `${line} ${word}` : word;
    if (ctx.measureText(test).width > maxWidth && line) {
      lines.push(line);
      line = word;
    } else {
      line = test;
    }
  });
  if (line) lines.push(line);
  lines.slice(0, maxLines).forEach((l, i) => ctx.fillText(l, x, y + i * lineHeight));
  return Math.min(lines.length, maxLines) * lineHeight;
}

function _perfInfoFitText(ctx, text, x, y, maxWidth, opts = {}) {
  const weight = opts.weight || 900;
  const family = opts.family || 'system-ui, sans-serif';
  const minSize = opts.minSize || 18;
  let size = opts.size || 28;
  let label = String(text || '');
  while (size > minSize) {
    ctx.font = `${weight} ${size}px ${family}`;
    if (ctx.measureText(label).width <= maxWidth) break;
    size -= 1;
  }
  ctx.font = `${weight} ${size}px ${family}`;
  if (ctx.measureText(label).width > maxWidth) {
    while (label.length > 3 && ctx.measureText(label + '...').width > maxWidth) {
      label = label.slice(0, -1);
    }
    label = label.trim() + '...';
  }
  ctx.fillText(label, x, y);
  return size;
}

function _perfInfoFilename(category, gender, view = 'equipment') {
  const g = gender === 'F' ? 'women' : (gender === 'M' ? 'men' : 'mixed');
  const v = String(view || 'ranking').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
  const cat = String(category || 'ranking').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
  return `freeride_top10_${v}_${cat}_${g}.png`;
}

function _perfInfoOptions() {
  const checked = id => document.getElementById(id)?.checked !== false;
  return {
    showSubtitle: checked('perf-info-show-subtitle'),
    showBars: checked('perf-info-show-bars'),
    showPoints: checked('perf-info-show-points'),
    showCount: checked('perf-info-show-count'),
    showPercent: document.getElementById('perf-info-show-percent')?.checked === true,
  };
}

function _perfInfographicSource() {
  const view = document.getElementById('perf-view')?.value || 'equipment';
  const category = document.getElementById('perf-category')?.value || 'all';
  const gender = document.getElementById('perf-gender')?.value || 'F';
  const topVal = document.getElementById('perf-top')?.value || '10';
  const groupMode = document.getElementById('perf-group')?.value || 'product';
  const sort = document.getElementById('perf-sort')?.value || 'points';
  const scopeMode = _perfScopeMode();
  const eventName = _perfScopeEvent();
  const context = _perfInfoContext();
  const subtitle = _perfInfoSubtitle(context);
  const labelPrefix = scopeMode === 'last_race' ? 'Last race · ' : '';

  if (view === 'riders') {
    const rows = _perfSelectedRidersFor(gender, topVal, scopeMode, eventName).map(rider => {
      const profile = _perfProfileForRider(rider);
      return {
        label: rider.name || rider.instagram || 'Unknown rider',
        instagram: rider.instagram || '',
        count: 1,
        points: Number(rider._perf_points ?? _perfScoreForRider(rider, scopeMode, eventName)),
        rank: _perfRankForRider(rider, scopeMode),
        team: String(profile?.team || rider.team || '').trim() || 'Independent / unknown',
      };
    }).sort((a, b) => (b.points - a.points) || (a.rank - b.rank));
    return {
      view,
      scope: scopeMode,
      eventName,
      category: 'riders',
      gender,
      riders: rows,
      top: rows.slice(0, 10),
      title: 'RIDERS',
      subtitle,
      sideLabel: 'CLASSEMENT RIDERS',
      sideMeta: context.category,
      label: `${labelPrefix}Top 10 Riders · ${subtitle}`,
      name: _perfInfoFilename('riders', gender, view),
    };
  }

  if (view === 'teams') {
    const { riders, rows } = _perfTeamRowsFor(gender, scopeMode, eventName);
    return {
      view,
      scope: scopeMode,
      eventName,
      category: 'teams',
      gender,
      riders,
      top: rows.slice(0, 10),
      title: 'TEAMS DH',
      subtitle,
      sideLabel: 'CLASSEMENT TEAM',
      sideMeta: context.category,
      label: `${labelPrefix}Top 10 Teams DH · ${subtitle}`,
      name: _perfInfoFilename('teams_dh', gender, view),
    };
  }

  const { riders, rows } = _perfStatsFor({ category, gender, topVal, groupMode, scopeMode, eventName });
  const top = _perfSortRowsBy(rows, sort).slice(0, 10);
  return {
    view,
    scope: scopeMode,
    eventName,
    category,
    gender,
    riders,
    top,
    title: category === 'all' ? 'EQUIPMENT' : category.toUpperCase(),
    subtitle,
    sideLabel: 'CLASSEMENT EQUIPEMENT',
    sideMeta: context.category,
    label: `${labelPrefix}Top 10 ${category === 'all' ? 'Equipment' : category} · ${subtitle}`,
    name: _perfInfoFilename(category, gender, view),
  };
}

function _perfInfoBackgroundStyle() {
  return document.getElementById('perf-info-background')?.value || 'technical';
}

function _perfInfoDrawBackground(ctx, W, H, accent, style = 'technical') {
  ctx.fillStyle = '#0b0b0b';
  ctx.fillRect(0, 0, W, H);

  if (style === 'glow') {
    const base = ctx.createLinearGradient(0, 0, W, H);
    base.addColorStop(0, 'rgba(200,212,0,0.16)');
    base.addColorStop(0.48, 'rgba(15,15,15,0.96)');
    base.addColorStop(1, 'rgba(255,255,255,0.03)');
    ctx.fillStyle = base;
    ctx.fillRect(0, 0, W, H);

    const glow = ctx.createRadialGradient(W * 0.28, H * 0.18, 20, W * 0.28, H * 0.18, 620);
    glow.addColorStop(0, 'rgba(200,212,0,0.18)');
    glow.addColorStop(0.42, 'rgba(200,212,0,0.045)');
    glow.addColorStop(1, 'rgba(200,212,0,0)');
    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, W, H);
  } else if (style === 'editorial') {
    const base = ctx.createLinearGradient(0, 0, W, H);
    base.addColorStop(0, 'rgba(255,255,255,0.035)');
    base.addColorStop(0.52, 'rgba(10,10,10,0.98)');
    base.addColorStop(1, 'rgba(200,212,0,0.10)');
    ctx.fillStyle = base;
    ctx.fillRect(0, 0, W, H);

    ctx.save();
    ctx.globalAlpha = 0.18;
    ctx.fillStyle = accent;
    ctx.translate(-140, 0);
    ctx.rotate(-0.16);
    for (let i = 0; i < 5; i += 1) {
      ctx.fillRect(130 + i * 170, 0, 42, H * 1.22);
    }
    ctx.restore();
  } else {
    const grd = ctx.createLinearGradient(0, 0, W, H);
    grd.addColorStop(0, 'rgba(200,212,0,0.20)');
    grd.addColorStop(0.45, 'rgba(200,212,0,0.07)');
    grd.addColorStop(1, 'rgba(255,255,255,0.02)');
    ctx.fillStyle = grd;
    ctx.fillRect(0, 0, W, H);
  }

  const gridAlpha = style === 'editorial' ? '0.03' : '0.04';
  ctx.strokeStyle = `rgba(255,255,255,${gridAlpha})`;
  ctx.lineWidth = 1;
  for (let x = 115; x < W - 115; x += 72) {
    ctx.beginPath(); ctx.moveTo(x, 130); ctx.lineTo(x, H - 130); ctx.stroke();
  }
  for (let y = 145; y < H - 125; y += 72) {
    ctx.beginPath(); ctx.moveTo(110, y); ctx.lineTo(W - 110, y); ctx.stroke();
  }
}

function generatePerformanceInfographic() {
  const preview = document.getElementById('perf-infographic-preview');
  const status = document.getElementById('perf-infographic-status');
  const sort = document.getElementById('perf-sort')?.value || 'points';
  const source = _perfInfographicSource();
  const options = _perfInfoOptions();
  const { riders, top, gender } = source;
  if (!top.length) {
    if (status) status.textContent = 'Aucun classement disponible pour cette sélection.';
    return;
  }

  const canvas = document.createElement('canvas');
  canvas.width = 1080;
  canvas.height = 1350;
  const ctx = canvas.getContext('2d');
  const W = canvas.width;
  const H = canvas.height;
  const green = '#C8D400';
  _perfInfoDrawBackground(ctx, W, H, green, _perfInfoBackgroundStyle());

  _perfInfoDrawFrame(ctx, 88, 90, 904, 1160, 34, green);

  ctx.save();
  _perfInfoRoundRect(ctx, 106, 108, 868, 1122, 24);
  ctx.clip();

  ctx.fillStyle = green;
  ctx.font = '900 34px system-ui, sans-serif';
  ctx.fillText('FREERIDE FANATICS', 132, 155);
  ctx.fillStyle = '#f2f2f2';
  ctx.font = '800 42px system-ui, sans-serif';
  ctx.fillText('LE TOP 10', 132, 260);
  ctx.font = '900 84px system-ui, sans-serif';
  _perfInfoWrapText(ctx, source.title, 132, 340, 760, 86, 2);

  if (options.showSubtitle) {
    ctx.fillStyle = 'rgba(255,255,255,0.65)';
    ctx.font = '700 25px system-ui, sans-serif';
    _perfInfoFitText(ctx, source.subtitle, 132, 455, 760, { size: 25, minSize: 17, weight: 700 });
  }

  const maxPoints = Math.max(...top.map(r => Number(r.points || 0)), 1);
  const maxCount = Math.max(...top.map(r => Number(r.count || 0)), 1);
  const rankX = 165;
  const labelX = 218;
  const barX = 218;
  const statX = 748;
  const statMax = 198;
  const barY = options.showSubtitle ? 528 : 494;
  const rowH = 57;
  const barMax = 478;
  const barH = 22;
  const labelMax = 492;

  top.forEach((item, idx) => {
    const y = barY + idx * rowH;
    const pct = riders.length ? (item.count / riders.length) * 100 : 0;
    const barW = Math.max(34, Math.round((sort === 'count' ? item.count / maxCount : item.points / maxPoints) * barMax));
    ctx.strokeStyle = 'rgba(255,255,255,0.42)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(rankX, y + 21, 21, 0, Math.PI * 2);
    ctx.stroke();
    ctx.fillStyle = '#f4f4f4';
    ctx.font = '900 20px ui-monospace, SFMono-Regular, Menlo, monospace';
    ctx.textAlign = 'center';
    ctx.fillText(String(idx + 1).padStart(2, '0'), rankX, y + 28);
    ctx.textAlign = 'left';

    ctx.fillStyle = '#f3f3f3';
    _perfInfoFitText(ctx, item.label, labelX, y + 20, labelMax, { size: 24, minSize: 16, weight: 900 });

    if (options.showBars) {
      ctx.fillStyle = 'rgba(255,255,255,0.92)';
      _perfInfoRoundRect(ctx, barX, y + 31, barW, barH, 11);
      ctx.fill();
      ctx.fillStyle = green;
      _perfInfoRoundRect(ctx, barX, y + 31, Math.max(12, Math.round(barW * 0.08)), barH, 11);
      ctx.fill();
    }

    const statParts = [];
    if (options.showCount) statParts.push(`${item.count} rider${item.count > 1 ? 's' : ''}`);
    if (options.showPoints) statParts.push(`${Math.round(item.points)} pts`);
    const primaryStat = options.showPercent
      ? `${pct.toFixed(1).replace('.', ',')}%`
      : (options.showPoints ? `${Math.round(item.points)} pts` : (options.showCount ? statParts[0] : ''));
    const secondaryStat = options.showPercent
      ? statParts.join(' · ')
      : statParts.filter(part => part !== primaryStat).join(' · ');
    ctx.fillStyle = '#f3f3f3';
    if (primaryStat) _perfInfoFitText(ctx, primaryStat, statX, y + 22, statMax, { size: 25, minSize: 17, weight: 900 });
    if (secondaryStat) {
      ctx.fillStyle = 'rgba(255,255,255,0.72)';
      _perfInfoFitText(ctx, secondaryStat, statX, y + 44, statMax, { size: 18, minSize: 13, weight: 700 });
    }
  });

  ctx.fillStyle = green;
  ctx.font = '900 48px system-ui, sans-serif';
  ctx.fillText('FF . 26', 730, 1185);
  ctx.fillStyle = 'rgba(255,255,255,0.76)';
  ctx.font = '800 22px ui-monospace, SFMono-Regular, Menlo, monospace';
  ctx.fillText('INFOGRAPHIE 2026', 730, 1132);
  ctx.fillText(new Date().toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' }).toUpperCase(), 132, 1188);
  ctx.restore();

  const url = canvas.toDataURL('image/png');
  const name = source.name;
  _lastPerfInfographic = { url, name, category: source.category, gender, label: source.label };
  if (preview) preview.innerHTML = `<img src="${url}" alt="Performance infographic">`;
  document.getElementById('perf-info-download-btn').disabled = false;
  document.getElementById('perf-info-library-btn').disabled = false;
  if (status) status.textContent = `Infographie prête : ${top.length} lignes · ${riders.length} riders analysés.`;
  generatePerformancePostText(true);
}

function _perfPostViewLabel(source) {
  if (source.view === 'riders') return 'classement riders';
  if (source.view === 'teams') return 'classement teams DH';
  if (source.category === 'all') return 'classement équipements';
  return `classement ${source.category}`;
}

function _perfPostRankIcon(index) {
  return ['1️⃣','2️⃣','3️⃣','4️⃣','5️⃣','6️⃣','7️⃣','8️⃣','9️⃣','🔟'][index] || `${index + 1}.`;
}

function _perfPostHandle(value) {
  const clean = String(value || '').trim()
    .replace(/^https?:\/\/(www\.)?instagram\.com\//i, '')
    .replace(/^@/, '')
    .replace(/\/.*$/, '');
  return clean ? '@' + clean : '';
}

function _perfPostUnique(values) {
  const seen = new Set();
  return values.map(_perfPostHandle).filter(value => {
    const key = value.toLowerCase();
    if (!value || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function _perfPostContextHandles() {
  return _perfPostUnique((_app.contextTags || []).map(tag => tag.instagram_handle));
}

function _perfPostContextHashtags() {
  return Array.from(new Set((_app.contextTags || [])
    .map(tag => String(tag.default_hashtag || '').trim())
    .filter(Boolean)
    .map(tag => tag.startsWith('#') ? tag : '#' + tag.replace(/^#+/, ''))));
}

function _perfPostBrandHandle(brand) {
  const keys = _brandKeys(brand).filter(key => key.length >= 3);
  const row = (_app.brandTags || []).find(item => keys.includes(_brandKey(item.brand)));
  return _perfPostHandle(row?.instagram_handle);
}

function _perfPostHandlesForName(name, mode = 'team') {
  const target = _brandKey(name);
  const foldedName = _ffFold(name);
  const contextMatches = (_app.contextTags || [])
    .filter(tag => {
      const values = [tag.name, tag.context, tag.tag_type].map(_brandKey).filter(Boolean);
      return values.some(value => value === target || (mode === 'team' && value.length >= 4 && (target.includes(value) || value.includes(target))));
    })
    .map(tag => tag.instagram_handle);

  const generic = new Set(['team', 'racing', 'factory', 'gravity', 'dh', 'mtb', 'bike', 'bikes', 'cycling', 'by', 'the', 'les', 'off']);
  const brandMatches = (_app.brandTags || [])
    .filter(row => {
      const brandKeys = _brandKeys(row.brand).filter(key => key.length >= 3 && !generic.has(key));
      return brandKeys.some(key => foldedName.includes(key));
    })
    .map(row => row.instagram_handle);

  return _perfPostUnique([...contextMatches, ...brandMatches]);
}

function _perfPostDisplayName(item, source) {
  if (source.view === 'riders') {
    return _perfPostHandle(item.instagram) || item.label || item.name || 'Rider';
  }
  if (source.view === 'teams') {
    const handles = _perfPostHandlesForName(item.label || item.team || '');
    return handles.length ? handles.join(' / ') : (item.label || item.team || 'Team');
  }
  const brandHandle = _perfPostBrandHandle(item.brand);
  const product = [brandHandle || item.brand, item.reference].filter(Boolean).join(' · ');
  return product || item.label || 'Equipment';
}

function _perfPostLine(item, index, source) {
  return `${_perfPostRankIcon(index)} ${_perfPostDisplayName(item, source)}`;
}

function _perfPostHashtags(source) {
  const tags = ['#FreerideFanatics', '#DownhillMTB', '#DHMTB', '#MountainBike', '#Downhill', '#MTBRacing', '#DownhillRacing', '#FreerideMTB', '#GravityMTB', '#WorldCupDH', '#UCIWorldCup', '#BikeLife'];
  if (source.view === 'teams') tags.push('#MTBTeam');
  if (source.view === 'riders') tags.push('#RiderRanking');
  if (source.view === 'equipment') tags.push('#EquipmentCheck', '#BikeCheck');
  const category = String(source.category || '').toLowerCase().replace(/[^a-z0-9]+/g, '');
  if (category && !['all', 'riders', 'teams'].includes(category)) tags.push('#' + category);
  _perfPostContextHashtags().forEach(tag => tags.push(tag));
  return Array.from(new Set(tags)).join(' ');
}

function _perfPostHeadline(source) {
  const scopeLabel = source.scope === 'last_race' ? 'THE LAST RACE TOP' : 'THE TOP';
  if (source.view === 'teams') return `🚵‍♂️ ${scopeLabel} 10 DH TEAMS 🔥`;
  if (source.view === 'riders') return `🏁 ${scopeLabel} 10 DH RIDERS 🔥`;
  const category = source.category === 'all' ? 'DH EQUIPMENT' : `DH ${String(source.category || 'EQUIPMENT').toUpperCase()}`;
  return `🔧 ${scopeLabel} 5 ${category} 🔥`;
}

function _perfPostIntro(source) {
  if (source.scope === 'last_race') {
    if (source.view === 'teams') return 'Last race shook up the ranking. Here’s who scored big:';
    if (source.view === 'riders') return 'Last race points are in. Here’s the sharp end of the field:';
    return 'The setups that scored the most points in the last race:';
  }
  if (source.view === 'teams') return 'The battle for the top spot is intense! Here’s the current ranking:';
  if (source.view === 'riders') return 'The pace is high and every point matters. Here’s the current ranking:';
  return 'The setups scoring the most points right now:';
}

function _perfPostQuestion(source) {
  if (source.view === 'teams') return 'Which team are you supporting this season? 👇';
  if (source.view === 'riders') return 'Who are you backing for the next round? 👇';
  return 'Which setup would you run on race day? 👇';
}

function _perfPostMissingTags(top, source) {
  if (source.view === 'riders') {
    return top.filter(item => !_perfPostHandle(item.instagram)).map(item => item.label || item.name).filter(Boolean);
  }
  if (source.view === 'teams') {
    return top.filter(item => !_perfPostHandlesForName(item.label || item.team || '').length).map(item => item.label || item.team).filter(Boolean);
  }
  return top.filter(item => !_perfPostBrandHandle(item.brand)).map(item => item.brand).filter(Boolean);
}

function generatePerformancePostText(silent = false) {
  const textarea = document.getElementById('perf-post-text');
  const status = document.getElementById('perf-post-status');
  const copyBtn = document.getElementById('perf-post-copy-btn');
  if (!textarea) return;

  const source = _perfInfographicSource();
  const top = (source.top || []).slice(0, source.view === 'equipment' ? 5 : 10);
  if (!top.length) {
    textarea.value = '';
    if (copyBtn) copyBtn.disabled = true;
    if (status && !silent) status.textContent = 'Aucun texte généré : aucun classement disponible.';
    return;
  }

  const context = _perfInfoContext();
  const showCompetition = document.getElementById('perf-info-show-competition')?.checked !== false;
  const contextLine = [showCompetition ? context.competition : '', context.category].filter(Boolean).join(' · ');
  const contextHandles = _perfPostContextHandles();
  const contextMentions = contextHandles.join(' ');
  const ranking = top.map((item, index) => _perfPostLine(item, index, source)).join('\n');

  textarea.value = [
    _perfPostHeadline(source),
    '',
    contextLine ? `${contextLine}` : '',
    contextLine ? '' : '',
    _perfPostIntro(source),
    '',
    ranking,
    '',
    _perfPostQuestion(source),
    contextMentions,
    '',
    _perfPostHashtags(source),
  ].filter(line => line !== null && line !== undefined && line !== '').join('\n');

  const missing = _perfPostMissingTags(top, source);
  if (copyBtn) copyBtn.disabled = false;
  if (status && !silent) {
    status.textContent = missing.length
      ? `Texte prêt · ${missing.length} tag${missing.length > 1 ? 's' : ''} à compléter : ${missing.slice(0, 3).join(', ')}${missing.length > 3 ? '…' : ''}`
      : `Texte prêt : ${top.length} tags intégrés.`;
  }
}

async function copyPerformancePostText() {
  const textarea = document.getElementById('perf-post-text');
  const status = document.getElementById('perf-post-status');
  const text = String(textarea?.value || '').trim();
  if (!text) {
    if (status) status.textContent = 'Rien à copier pour le moment.';
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
    if (status) status.textContent = 'Texte copié.';
  } catch(e) {
    if (status) status.textContent = 'Copie impossible automatiquement.';
  }
}

function downloadPerformanceInfographic() {
  if (!_lastPerfInfographic) return;
  const a = document.createElement('a');
  a.href = _lastPerfInfographic.url;
  a.download = _lastPerfInfographic.name;
  a.click();
}

async function addPerformanceInfographicToLibrary() {
  if (!_lastPerfInfographic) return;
  const btn = document.getElementById('perf-info-library-btn');
  const status = document.getElementById('perf-infographic-status');
  try {
    await _libraryAdd('equipment', {
      label: _lastPerfInfographic.label || 'Performance infographic',
      url: _lastPerfInfographic.url,
      name: _lastPerfInfographic.name,
      mime: 'image/png',
    }, {
      type: 'performance_infographic',
      category: _lastPerfInfographic.category || '',
      gender: _lastPerfInfographic.gender || '',
    });
    if (btn) {
      btn.textContent = '✓ Library';
      btn.style.background = '#C8D400';
      btn.style.color = '#000';
      setTimeout(() => { btn.textContent = '＋ Library'; btn.style.background = ''; btn.style.color = ''; }, 1200);
    }
    if (status) status.textContent = 'Infographie ajoutée à la Library.';
  } catch(e) {
    if (status) status.textContent = 'Library : ' + e.message;
  }
}

function renderPerformance() {
  renderPerformanceOverview();
  const leadersEl = document.getElementById('perf-leaders');
  const tableEl = document.getElementById('perf-table-wrap');
  if (!leadersEl || !tableEl) return;

  const view = document.getElementById('perf-view')?.value || 'equipment';
  const category = document.getElementById('perf-category')?.value || 'all';
  const leadersTitle = document.getElementById('perf-leaders-title');
  const tableTitle = document.getElementById('perf-table-title');
  if (leadersTitle) {
    leadersTitle.textContent = view === 'riders'
      ? 'Top riders'
      : (view === 'teams' ? 'Top teams' : (category === 'all' ? 'Leaders par catégorie' : `Top ${category}`));
  }
  if (tableTitle) {
    tableTitle.textContent = view === 'riders'
      ? 'Classement riders détaillé'
      : (view === 'teams' ? 'Classement teams détaillé' : 'Classement équipements détaillé');
  }
  const categoryControl = document.getElementById('perf-category')?.closest('.perf-control');
  const groupControl = document.getElementById('perf-group')?.closest('.perf-control');
  if (categoryControl) categoryControl.style.display = view === 'equipment' ? '' : 'none';
  if (groupControl) groupControl.style.display = view === 'equipment' ? '' : 'none';

  if (view === 'riders') {
    _renderPerformanceRiders(leadersEl, tableEl);
    return;
  }
  if (view === 'teams') {
    _renderPerformanceTeams(leadersEl, tableEl);
    return;
  }

  const { riders, rows, itemHits, pointsCovered } = _perfStats();
  const sorted = _perfSortRows(rows);
  const cats = new Set(rows.map(r => r.category));

  _perfSetKpis([
    { label: 'Riders analysés', value: riders.length },
    { label: 'Équipements matchés', value: itemHits },
    { label: 'Catégories', value: cats.size },
    { label: 'Points couverts', value: Math.round(pointsCovered) },
  ]);

  if (!riders.length) {
    leadersEl.innerHTML = '<div class="perf-empty">Aucun rider classé avec un handle Instagram exploitable.</div>';
    tableEl.innerHTML = '<div class="perf-empty">Vérifie l’onglet Résultats 2026 et les profils Instagram.</div>';
    return;
  }
  if (!rows.length) {
    leadersEl.innerHTML = '<div class="perf-empty">Aucun équipement trouvé pour cette sélection.</div>';
    tableEl.innerHTML = '<div class="perf-empty">Essaie une autre catégorie ou une fenêtre plus large.</div>';
    return;
  }

  let leaderRows = [];
  if (category === 'all') {
    _perfCategories().forEach(cat => {
      const best = _perfSortRows(rows.filter(r => r.category === cat))[0];
      if (best) leaderRows.push(best);
    });
  } else {
    leaderRows = sorted.slice(0, 8);
  }

  leadersEl.innerHTML = leaderRows.map((st, idx) => `
    <div class="perf-leader">
      <div class="perf-rank">${idx + 1}</div>
      <div class="perf-main">
        <div class="perf-name">${_esc(st.label)}</div>
        <div class="perf-meta">${_esc(st.category)} · ${st.count} rider${st.count > 1 ? 's' : ''} · rang moyen ${st.avgRank.toFixed(1)}</div>
      </div>
      <div class="perf-score">${Math.round(st.points)}<small>pts</small></div>
    </div>
  `).join('');

  tableEl.innerHTML = `
    <table class="perf-table">
      <thead>
        <tr>
          <th>Catégorie</th>
          <th>Équipement</th>
          <th>Riders</th>
          <th>Points</th>
          <th>Rang moy.</th>
          <th>Top rider</th>
        </tr>
      </thead>
      <tbody>
        ${sorted.slice(0, 40).map(st => {
          const riderText = st.riders
            .sort((a, b) => a.rank - b.rank)
            .slice(0, 5)
            .map(r => `${r.flag ? r.flag + ' ' : ''}#${r.rank} ${r.name} (${Math.round(r.points)} pts)`)
            .join('<br>');
          return `<tr>
            <td>${_esc(st.category)}</td>
            <td><strong>${_esc(st.label)}</strong></td>
            <td>${st.count}</td>
            <td>${Math.round(st.points)}</td>
            <td>${st.avgRank.toFixed(1)}</td>
            <td class="perf-riders">${riderText}</td>
          </tr>`;
        }).join('')}
      </tbody>
    </table>
  `;
}

// ── Tab navigation ────────────────────────────────────────────────────────
const _DASHBOARD_TABS = ['logos', 'riders', 'settings', 'connections', 'quality', 'audit', 'brandtags'];

function switchTab(tab) {
  _activeTab = tab;
  // Tabs principaux
  ['cards','equipment','performance','reel','publish','library'].forEach(t => {
    document.getElementById('tab-'+t)?.classList.toggle('active', t === tab);
    document.getElementById('burger-'+t)?.classList.toggle('active', t === tab);
  });
  // Tabs dashboard
  _DASHBOARD_TABS.forEach(t => {
    document.getElementById('tab-'+t)?.classList.toggle('active', t === tab);
    document.getElementById('burger-'+t)?.classList.toggle('active', t === tab);
  });

  // Dashboard btn highlight si un de ses onglets est actif
  const inDash = _DASHBOARD_TABS.includes(tab);
  document.getElementById('dashboard-btn')?.classList.toggle('has-active', inDash);

  // Affichage pages
  document.getElementById('page-cards').style.display       = tab === 'cards'       ? 'grid'  : 'none';
  document.getElementById('page-equipment').style.display   = tab === 'equipment'   ? 'block' : 'none';
  document.getElementById('page-performance').style.display = tab === 'performance' ? 'block' : 'none';
  document.getElementById('page-logos').style.display       = tab === 'logos'       ? 'block' : 'none';
  document.getElementById('page-riders').style.display      = tab === 'riders'      ? 'block' : 'none';
  document.getElementById('page-reel').style.display        = tab === 'reel'        ? 'block' : 'none';
  document.getElementById('page-library').style.display     = tab === 'library'     ? 'block' : 'none';
  document.getElementById('page-publish').style.display     = tab === 'publish'     ? 'block' : 'none';
  document.getElementById('page-settings').style.display    = tab === 'settings'    ? 'block' : 'none';
  document.getElementById('page-connections').style.display = tab === 'connections' ? 'block' : 'none';
  document.getElementById('page-quality').style.display     = tab === 'quality'     ? 'block' : 'none';
  document.getElementById('page-audit').style.display       = tab === 'audit'       ? 'block' : 'none';
  document.getElementById('page-brandtags').style.display   = tab === 'brandtags'   ? 'block' : 'none';

  if (tab === 'equipment' && !_eqRidersLoaded) initEqPage();
  if (tab === 'performance') initPerformancePage();
  if (tab === 'reel') { initReelPerformanceControls(); renderReelPage(); _initReelRiderList(); }
  if (tab === 'library') renderLibraryPage();
  if (tab === 'publish') publishInit();
  if (tab === 'settings') settingsLoadGoogleSheet();
  if (tab === 'connections') connRefreshGoogle();
  if (tab === 'quality') renderQualityCenter();
  if (tab === 'audit') loadEqAudit();
  if (tab === 'brandtags') renderBrandTagsPage();
}

setInterval(() => {
  if (_activeTab === 'performance') refreshPerformanceData(true);
}, 60000);

// ── Brand & Tags assets ─────────────────────────────────────────────────────
function _tagStatusClass(value) {
  return String(value || '').trim() ? 'asset-tag-ok' : 'asset-tag-missing';
}

function renderBrandTagsPage() {
  const brandBody = document.getElementById('brandtags-brand-tbody');
  const contextBody = document.getElementById('brandtags-context-tbody');
  if (!brandBody || !contextBody) return;

  const brands = (_app.brandTags || []).slice().sort((a, b) => String(a.brand || '').localeCompare(String(b.brand || '')));
  const contexts = (_app.contextTags || []).slice().sort((a, b) => String(a.tag_type || '').localeCompare(String(b.tag_type || '')) || String(a.name || '').localeCompare(String(b.name || '')));
  const brandsWithHandle = brands.filter(b => b.instagram_handle).length;
  const contextWithTag = contexts.filter(t => t.instagram_handle || t.default_hashtag).length;

  document.getElementById('brandtags-brand-stats').textContent =
    `${brands.length} marques · ${brandsWithHandle} handles renseignés`;
  document.getElementById('brandtags-context-stats').textContent =
    `${contexts.length} tags contextuels · ${contextWithTag} actifs`;

  brandBody.innerHTML = brands.map(b => `
    <tr>
      <td>${_esc(b.brand || '')}</td>
      <td class="${_tagStatusClass(b.instagram_handle)}">${_esc(b.instagram_handle || 'à compléter')}</td>
      <td>${_esc(b.status || '')}</td>
    </tr>
  `).join('');

  contextBody.innerHTML = contexts.map(t => {
    const tag = [t.instagram_handle, t.default_hashtag].filter(Boolean).join(' · ');
    return `<tr>
      <td>${_esc(t.tag_type || '')}</td>
      <td>${_esc(t.name || '')}</td>
      <td class="${_tagStatusClass(tag)}">${_esc(tag || 'à compléter')}</td>
    </tr>`;
  }).join('');
}

async function refreshBrandTags() {
  const status = document.getElementById('brandtags-status');
  if (status) status.textContent = 'Synchronisation depuis Google Sheet...';
  try {
    const res = await fetch('/api/brand-tags?refresh=1');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    _app.brandTags = data.brand_tags || [];
    _app.contextTags = data.context_tags || [];
    renderBrandTagsPage();
    if (status) status.textContent = 'Brand & Tags synchronisés.';
  } catch(e) {
    if (status) status.textContent = 'Synchronisation impossible pour le moment.';
  }
}

// ── Settings ────────────────────────────────────────────────────────────────
const _SETTINGS_SHEET_MODEL = [
  { label: 'Riders', cols: ['First Name', 'Last Name', 'Instagram', 'Team'] },
  { label: 'Equipment Women', cols: ['G', 'Instagram', 'Frame', 'Fork', 'Tires'] },
  { label: 'Equipment Men', cols: ['G', 'Instagram', 'Frame', 'Fork', 'Tires'] },
  { label: 'Résultats 2026', cols: ['First Name', 'Last Name', 'event columns'] },
  { label: 'Brand', cols: ['brand', 'instagram_handle', 'status'] },
  { label: 'Tags', cols: ['tag_type', 'name', 'instagram_handle', 'default_hashtag'] },
];

function settingsRenderSheetChecklist() {
  const box = document.getElementById('settings-sheet-checklist');
  if (!box) return;
  box.innerHTML = _SETTINGS_SHEET_MODEL.map(item => `
    <div class="settings-check-item">
      <div class="settings-check-title">${_esc(item.label)}</div>
      <div class="settings-check-cols">${item.cols.map(col => _esc(col)).join(' · ')}</div>
    </div>
  `).join('');
}

function settingsSheetChecklistText() {
  return [
    'Freeride Fanatics - checklist Google Sheet',
    '',
    ..._SETTINGS_SHEET_MODEL.map(item => `- ${item.label}: ${item.cols.join(', ')}`),
  ].join('\n');
}

async function settingsCopySheetChecklist() {
  const status = document.getElementById('settings-gsheet-status');
  try {
    await navigator.clipboard.writeText(settingsSheetChecklistText());
    if (status) {
      status.className = 'settings-status ok';
      status.textContent = 'Checklist Google Sheet copiée.';
    }
  } catch(e) {
    if (status) {
      status.className = 'settings-status err';
      status.textContent = 'Impossible de copier la checklist.';
    }
  }
}

async function settingsLoadGoogleSheet() {
  const input = document.getElementById('settings-gsheet-url');
  const current = document.getElementById('settings-gsheet-current');
  const status = document.getElementById('settings-gsheet-status');
  if (!input || !current) return;
  settingsRenderSheetChecklist();
  try {
    const data = await fetch('/api/settings/google-sheet').then(r => r.json());
    input.value = data.active_url || '';
    current.textContent = data.active_url || 'Aucun Google Sheet configuré';
    if (status) {
      status.className = 'settings-status';
      status.textContent = data.source === 'settings' ? 'Source personnalisée active.' : 'Source par défaut active.';
    }
  } catch(e) {
    if (status) {
      status.className = 'settings-status err';
      status.textContent = 'Impossible de charger les paramètres.';
    }
  }
}

async function settingsSaveGoogleSheet() {
  const input = document.getElementById('settings-gsheet-url');
  const status = document.getElementById('settings-gsheet-status');
  const value = input?.value?.trim() || '';
  if (!value) {
    if (status) {
      status.className = 'settings-status err';
      status.textContent = 'Ajoute un lien ou un ID Google Sheet.';
    }
    return;
  }
  try {
    const res = await fetch('/api/settings/google-sheet', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sheet_url: value }),
    });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || 'Paramètre invalide');
    if (status) {
      status.className = 'settings-status ok';
      status.textContent = 'Google Sheet sauvegardé. Rechargement des données…';
    }
    setTimeout(() => location.reload(), 600);
  } catch(e) {
    if (status) {
      status.className = 'settings-status err';
      status.textContent = e.message || 'Sauvegarde impossible.';
    }
  }
}

async function settingsTestGoogleSheet() {
  const input = document.getElementById('settings-gsheet-url');
  const status = document.getElementById('settings-gsheet-status');
  const target = document.getElementById('settings-gsheet-test');
  const value = input?.value?.trim() || '';
  if (!value) {
    if (status) {
      status.className = 'settings-status err';
      status.textContent = 'Ajoute un lien ou un ID Google Sheet à tester.';
    }
    if (target) target.innerHTML = '';
    return;
  }
  if (status) {
    status.className = 'settings-status';
    status.textContent = 'Test du Google Sheet en cours…';
  }
  if (target) target.innerHTML = '';
  try {
    const res = await fetch('/api/settings/google-sheet/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sheet_url: value }),
    });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || 'Test impossible');
    if (status) {
      status.className = data.all_ok ? 'settings-status ok' : 'settings-status err';
      status.textContent = data.all_ok
        ? 'Google Sheet compatible.'
        : 'Google Sheet incomplet : vérifie les onglets manquants.';
    }
    if (target) {
      target.innerHTML = `
        <table class="settings-test-table">
          <thead>
            <tr><th>Onglet</th><th>Statut</th><th>Lignes</th><th>Détail</th></tr>
          </thead>
          <tbody>
            ${(data.sheets || []).map(sheet => `
              <tr>
                <td>${_esc(sheet.label || sheet.key)}</td>
                <td class="${sheet.ok ? 'settings-test-ok' : 'settings-test-missing'}">${sheet.ok ? 'OK' : 'Manquant'}</td>
                <td>${Number(sheet.row_count || 0)}</td>
                <td>
                  ${_esc(sheet.detail || '')}
                  ${sheet.matched ? `<div class="settings-test-muted">${_esc(sheet.matched)}</div>` : ''}
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    }
  } catch(e) {
    if (status) {
      status.className = 'settings-status err';
      status.textContent = e.message || 'Test impossible.';
    }
  }
}

async function settingsResetGoogleSheet() {
  const status = document.getElementById('settings-gsheet-status');
  try {
    const res = await fetch('/api/settings/google-sheet', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reset: true }),
    });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || 'Réinitialisation impossible');
    if (status) {
      status.className = 'settings-status ok';
      status.textContent = 'Source par défaut restaurée. Rechargement des données…';
    }
    setTimeout(() => location.reload(), 600);
  } catch(e) {
    if (status) {
      status.className = 'settings-status err';
      status.textContent = e.message || 'Réinitialisation impossible.';
    }
  }
}

function settingsOpenGoogleSheet() {
  const value = document.getElementById('settings-gsheet-url')?.value?.trim();
  if (!value) return;
  const url = value.startsWith('http')
    ? value
    : `https://docs.google.com/spreadsheets/d/${encodeURIComponent(value)}/edit`;
  window.open(url, '_blank', 'noopener,noreferrer');
}

// ── Quality Center ───────────────────────────────────────────────────────────
function _qualityIssue(severity, type, target, detail, action, search = '', extra = {}) {
  const requirement = extra.requirement || (severity === 'optional' ? 'nice_to_have' : 'required');
  return { severity, type, target, detail, action, requirement, search: `${type} ${target} ${detail} ${action} ${search}`.toLowerCase(), ...extra };
}

const _QUALITY_MANUAL_STORAGE = 'frf_quality_manual_status_v1';

function _qualityManualMap() {
  try { return JSON.parse(localStorage.getItem(_QUALITY_MANUAL_STORAGE) || '{}') || {}; }
  catch(e) { return {}; }
}

function _qualitySaveManualMap(map) {
  try { localStorage.setItem(_QUALITY_MANUAL_STORAGE, JSON.stringify(map || {})); }
  catch(e) {}
}

function _qualityIssueKey(issue) {
  return [
    issue.type,
    issue.target,
    issue.detail,
    issue.category || '',
    issue.brand || '',
    issue.reference || '',
    issue.assetKind || '',
  ].map(_ffFold).join('|');
}

function _qualityDecorateManual(issue) {
  const key = _qualityIssueKey(issue);
  const state = _qualityManualMap()[key] || 'active';
  return { ...issue, key, manualState: state };
}

function qualitySetManualStatus(key, status) {
  const map = _qualityManualMap();
  if (!status || status === 'active') delete map[key];
  else map[key] = status;
  _qualitySaveManualMap(map);
  renderQualityCenter();
}

function _ffFold(value) {
  return String(value || '')
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .toLowerCase().replace(/[^a-z0-9]+/g, '');
}

const _BRAND_ALIASES = {
  brembolever: 'brembo',
  commencal: 'commencal',
  comencal: 'commencal',
  e13: 'ethirteen',
  ethirteen: 'ethirteen',
  oneupcomponents: 'oneup',
  ohlins: 'ohlins',
  rental: 'renthal',
  specialized: 'sworks',
  sworks: 'specialized',
};

function _brandKey(value) {
  const key = _ffFold(value);
  return _BRAND_ALIASES[key] || key;
}

function _brandKeys(value) {
  const key = _brandKey(value);
  const raw = _ffFold(value);
  return Array.from(new Set([key, raw, _BRAND_ALIASES[raw]].filter(Boolean)));
}

function _referenceTokens(value) {
  const generic = new Set([
    'pro', 'team', 'factory', 'ultimate', 'carbon', 'alloy', 'aluminum',
    'proto', 'prototype', 'racing', 'line', 'black', 'white', 'red', 'blue',
    'green', 'gold', 'silver', 'gravity', 'dh', 'mtb', 'coil'
  ]);
  return String(value || '')
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .map(_ffFold)
    .filter(w => (w.length >= 3 || (w.length >= 2 && /\d/.test(w))) && !generic.has(w));
}

function _equipmentPhotoScore(item, file) {
  const fileKey = _ffFold(file?.name || file?.stem || '');
  if (!fileKey) return 99;
  const brandMatches = _brandKeys(item?.brand).some(key => key && fileKey.includes(key));
  const refKey = _ffFold(item?.reference);
  const tokens = _referenceTokens(item?.reference);
  const modelQualifiers = ['live', 'valve', 'neo'];
  if (modelQualifiers.some(q => fileKey.includes(q) !== refKey.includes(q))) return 99;
  const hasSpecificRef = tokens.length > 0;
  const strongTokens = tokens.filter(t => t.length >= 3 && !modelQualifiers.includes(t));
  const shortDigitTokens = tokens.filter(t => t.length < 3 && /\d/.test(t));
  const strongHit = strongTokens.length === 0 || strongTokens.some(t => fileKey.includes(t));
  const shortDigitHit = shortDigitTokens.every(t => fileKey.includes(t));
  const tokenHit = hasSpecificRef && strongHit && shortDigitHit;
  const distinctiveRefHit = tokenHit || (hasSpecificRef && refKey.length >= 4 && fileKey.includes(refKey));

  if (brandMatches && hasSpecificRef && refKey && fileKey.includes(refKey)) return 0;
  if (brandMatches && distinctiveRefHit) return 1;
  if (distinctiveRefHit) return 6;
  return 99;
}

const _QUALITY_ASSET_PRIORITY = {
  Frame: 1,
  Fork: 2,
  Helmet: 3,
  Tires: 4,
  'Rear Shock': 5,
  Wheels: 6,
  'Brake Lever': 7,
  Derailleur: 8,
  Handlebar: 9,
  Crankset: 10,
  Pedals: 11,
  Goggles: 12,
  Protection: 13,
  'Dropper Post': 14,
  Saddle: 15,
  Shoes: 16,
  GRIP: 17,
  CHAIN: 18,
  Disk: 19,
};

function _qualityPriority(category) {
  return _QUALITY_ASSET_PRIORITY[category] || 99;
}

function _qualityPriorityClass(priority) {
  if (!priority || priority >= 99) return 'p99';
  return `p${Math.min(priority, 9)}`;
}

function _qualityPriorityLabel(priority) {
  return priority && priority < 99 ? `P${priority}` : 'P?';
}

function _qualityCategoryFiles(category) {
  const norm = s => (s || '').toLowerCase().replace(/[\s\-_\/\.]/g, '');
  const folders = (_app.categoryFolders?.[category] || [category]).map(norm);
  return (_app.eqVariants || []).filter(f => folders.includes(norm(f.folder || '')));
}

function _qualityTokenScore(queryToken, fileTokens, fileKey) {
  if (!queryToken || queryToken.length < 3) return 0;
  if (fileKey.includes(queryToken)) return 8;
  let best = 0;
  fileTokens.forEach(token => {
    if (!token || token.length < 3) return;
    if (token.includes(queryToken) || queryToken.includes(token)) best = Math.max(best, 5);
    else if (token.slice(0, 4) === queryToken.slice(0, 4)) best = Math.max(best, 3);
    else if (token.slice(0, 3) === queryToken.slice(0, 3)) best = Math.max(best, 2);
  });
  return best;
}

function _qualityFindPhotoCandidates(item, limit = 5) {
  const files = _qualityCategoryFiles(item.category);
  const brandKeys = _brandKeys(item.brand).filter(k => k.length >= 3);
  const refTokens = _referenceTokens(item.reference);
  const queryTokens = Array.from(new Set([...brandKeys, ...refTokens]));
  if (!files.length || !queryTokens.length) return [];

  return files.map(file => {
    const fileKey = _ffFold(file.name || file.stem || '');
    const fileTokens = String(file.name || file.stem || '')
      .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .split(/[^a-z0-9]+/)
      .map(_ffFold)
      .filter(w => w.length >= 3);
    const hits = [];
    let score = 0;
    queryTokens.forEach(token => {
      const tokenScore = _qualityTokenScore(token, fileTokens, fileKey);
      if (tokenScore > 0) {
        score += tokenScore;
        hits.push(token);
      }
    });
    return {
      ...file,
      candidateScore: score,
      reason: hits.length ? `match: ${hits.slice(0, 3).join(', ')}` : '',
    };
  })
    .filter(file => file.candidateScore >= 5)
    .sort((a, b) => b.candidateScore - a.candidateScore || String(a.name).localeCompare(String(b.name)))
    .slice(0, limit);
}

function _qualityExpectedFilename(item) {
  const category = String(item?.category || 'Equipment').trim() || 'Equipment';
  const cleanPart = value => String(value || '')
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[\/\\:]/g, '-')
    .replace(/\s+/g, ' ')
    .trim();
  const base = [cleanPart(item?.brand), cleanPart(item?.reference)]
    .filter(Boolean)
    .join(';') || 'image';
  return `Equipment/${category}/${base}.png`;
}

const _QUALITY_TIRE_BRANDS = new Set(['continental', 'maxxis', 'michelin', 'schwalbe', 'vittoria', 'pirelli', 'goodyear']);

function _qualitySuspectedCategory(item) {
  const category = item?.category || '';
  const brand = _brandKey(item?.brand);
  const ref = _ffFold(item?.reference);

  if (category !== 'Crankset' && (brand === '5dev' || /crank|cranks|crankset/.test(ref))) return 'Crankset';
  if (category !== 'Tires' && (_QUALITY_TIRE_BRANDS.has(brand) || /assegai|argotal|kryptotal|shorty|highroller|hillbilly|butcher|magicmary|tackychan|albert|tire|tyre/.test(ref))) return 'Tires';
  if (category !== 'Wheels' && /wheel|wheelset|rim|rims|fr1500|ex471|synthesis|blacklabel|carbondh|30dh|mc32/.test(ref)) return 'Wheels';
  if (category !== 'Pedals' && (/pedal|mallet|x3ti/.test(ref) || brand === 'ht')) return 'Pedals';
  if (category !== 'Saddle' && /saddle|alpaca|cloud|kaslo|ifly/.test(ref)) return 'Saddle';
  if (category !== 'Helmet' && /helmet|legitcarbon|status/.test(ref) && category !== 'Goggles') return 'Helmet';
  return '';
}

function _qualityBrandHasLogo(brand) {
  if (!brand) return false;
  const brandKeys = _brandKeys(brand);
  return (_app.sponsors || []).some(s => {
    const values = [s.key, s.label, s.file].map(_brandKey).filter(Boolean);
    return values.some(v => brandKeys.some(b => v.includes(b) || b.includes(v)));
  });
}

function _qualityBrandHandle(brand) {
  if (!brand) return '';
  const brandKeys = _brandKeys(brand);
  const row = (_app.brandTags || []).find(b => brandKeys.includes(_brandKey(b.brand)));
  return row?.instagram_handle || '';
}

function _qualityBuildIssues() {
  const issues = [];
  const seenBrands = new Map();
  const profiles = _app.profiles || [];
  const equipment = _app.equipment || {};

  profiles.forEach(profile => {
    const name = `${profile.prenom || ''} ${profile.nom || ''}`.trim() || profile.instagram || 'Rider';
    const handle = String(profile.instagram || '').replace(/^@/, '').toLowerCase();
    if (!profile.has_photo) {
      issues.push(_qualityIssue(
        'critical',
        'rider',
        name,
        'Photo PP manquante.',
        'Ajoute une photo dans PPRiders ou utilise le gestionnaire Riders.',
        profile.instagram
      ));
    }
    if (!handle) {
      issues.push(_qualityIssue(
        'critical',
        'rider',
        name,
        'Handle Instagram manquant.',
        'Complète Instagram dans le Sheet riders.',
        name
      ));
      return;
    }

    const items = equipment[handle] || [];
    if (!items.length) {
      issues.push(_qualityIssue(
        'warning',
        'equipment',
        name,
        'Aucun équipement renseigné pour ce rider.',
        'Complète les colonnes équipement dans le Google Sheet.',
        profile.instagram
      ));
    }

    items.forEach(item => {
      const label = `${name} · ${item.category || 'Equipment'}`;
      const itemName = [item.brand, item.reference].filter(Boolean).join(' ');
      if (!item.brand || !item.reference) {
        issues.push(_qualityIssue(
          'critical',
          'equipment',
          label,
          `Donnée équipement incomplète${itemName ? ` : ${itemName}` : ''}.`,
          'Complète marque et référence dans le Sheet.',
          `${profile.instagram} ${itemName}`
        ));
      }
      if (item.brand) {
        seenBrands.set(_brandKey(item.brand), item.brand);
      }
      const suspectedCategory = _qualitySuspectedCategory(item);
      const categoryMismatch = Boolean(suspectedCategory && suspectedCategory !== item.category);
      if (categoryMismatch) {
        issues.push(_qualityIssue(
          'warning',
          'equipment',
          label,
          `Catégorie suspecte pour ${itemName}. Attendu plutôt : ${suspectedCategory}.`,
          'Corrige la colonne dans le Google Sheet, puis actualise les données.',
          `${profile.instagram} ${item.category || ''} ${suspectedCategory} ${itemName} ${item.details || ''}`,
          {
            assetKind: 'equipment_category',
            category: item.category || 'Equipment',
            expectedCategory: suspectedCategory,
            brand: item.brand || '',
            reference: item.reference || '',
            itemName,
            riderName: name,
            instagram: profile.instagram || '',
            priority: _qualityPriority(suspectedCategory),
          }
        ));
      }
      if (item.brand && item.reference && !categoryMismatch && !_eqCheckPhoto(item)) {
        const priority = _qualityPriority(item.category);
        const candidates = _qualityFindPhotoCandidates(item);
        const expectedFilename = _qualityExpectedFilename(item);
        issues.push(_qualityIssue(
          'warning',
          'equipment',
          label,
          `Photo équipement manquante pour ${itemName}.`,
          'Ajoute une image dans le dossier Equipment de cette catégorie, puis Rescan photos.',
          `${profile.instagram} ${item.category || ''} ${itemName} ${item.details || ''}`,
          {
            assetKind: 'equipment_photo',
            category: item.category || 'Equipment',
            brand: item.brand || '',
            reference: item.reference || '',
            itemName,
            riderName: name,
            instagram: profile.instagram || '',
            priority,
            candidates,
            expectedFilename,
          }
        ));
      }
      if (item.brand && !_qualityBrandHasLogo(item.brand)) {
        issues.push(_qualityIssue(
          'optional',
          'brand',
          item.brand,
          'Logo marque non détecté.',
          'Optionnel : ajoute le logo pour améliorer le rendu visuel des cartes.',
          itemName,
          { requirement: 'nice_to_have' }
        ));
      }
      if (item.brand && !_qualityBrandHandle(item.brand)) {
        issues.push(_qualityIssue(
          'optional',
          'brand',
          item.brand,
          'Handle Instagram marque manquant dans Brand.',
          'Optionnel : complète instagram_handle pour améliorer Publish.',
          itemName,
          { requirement: 'nice_to_have' }
        ));
      }
    });
  });

  (_app.brandTags || []).forEach(row => {
    const brand = String(row.brand || '').trim();
    if (!brand) return;
    const used = seenBrands.has(_brandKey(brand));
    if (used && !row.instagram_handle) {
      issues.push(_qualityIssue(
        'optional',
        'brand',
        brand,
        'Marque utilisée mais handle Instagram vide.',
        'Optionnel : complète le handle dans Brand pour améliorer Publish.',
        row.status || '',
        { requirement: 'nice_to_have' }
      ));
    }
  });

  const contexts = _app.contextTags || [];
  if (!contexts.length) {
    issues.push(_qualityIssue(
      'optional',
      'tag',
      'Tags',
      'Aucun tag contextuel chargé.',
      'Optionnel : ajoute ou resynchronise l’onglet Tags pour Publish.',
      '',
      { requirement: 'nice_to_have' }
    ));
  }
  contexts.forEach(row => {
    const name = row.name || row.tag_type || 'Tag';
    if (!row.instagram_handle && !row.default_hashtag) {
      issues.push(_qualityIssue(
        'optional',
        'tag',
        name,
        'Tag contextuel sans handle ni hashtag.',
        'Optionnel : complète instagram_handle ou default_hashtag dans Tags.',
        row.tag_type || '',
        { requirement: 'nice_to_have' }
      ));
    }
  });

  const okRows = [];
  const totalProfiles = profiles.length;
  const completeProfiles = profiles.filter(profile => {
    const handle = String(profile.instagram || '').replace(/^@/, '').toLowerCase();
    const items = equipment[handle] || [];
    return profile.has_photo && handle && items.length && items.every(item =>
      item.brand && item.reference && _eqCheckPhoto(item) && _qualityBrandHasLogo(item.brand)
    );
  }).length;
  okRows.push(_qualityIssue(
    'ok',
    'rider',
    'Riders complets',
    `${completeProfiles}/${totalProfiles} riders ont PP + équipements exploitables.`,
    'Continuer à compléter les warnings restants.',
    ''
  ));

  const brands = Array.from(seenBrands.values());
  const brandsWithHandle = brands.filter(brand => _qualityBrandHandle(brand)).length;
  okRows.push(_qualityIssue(
    'ok',
    'brand',
    'Brand handles',
    `${brandsWithHandle}/${brands.length} marques utilisées ont un handle Instagram.`,
    'Compléter Brand pour atteindre 100%.',
    ''
  ));

  const unique = [];
  const seen = new Set();
  [...issues, ...okRows].forEach(issue => {
    const key = `${issue.severity}|${issue.type}|${issue.target}|${issue.detail}`;
    if (seen.has(key)) return;
    seen.add(key);
    unique.push(_qualityDecorateManual(issue));
  });
  return unique;
}

function renderQualityAssetSummary(allIssues) {
  const box = document.getElementById('quality-asset-summary');
  if (!box) return;
  const missing = allIssues.filter(i => i.assetKind === 'equipment_photo');
  const categoryIssues = allIssues.filter(i => i.assetKind === 'equipment_category');
  const optionalIssues = allIssues.filter(i => i.severity === 'optional');
  const summaryCards = `
    <div class="quality-work-grid">
      <button class="quality-work-card" onclick="qualityFilterIssueKind('equipment_photo')">
        <div class="quality-work-label">Vraiment manquant</div>
        <div class="quality-work-value">${missing.length}</div>
        <div class="quality-work-note">Photos équipement à créer ou récupérer.</div>
      </button>
      <button class="quality-work-card" onclick="qualityFilterIssueKind('equipment_category')">
        <div class="quality-work-label">Catégorie suspecte</div>
        <div class="quality-work-value">${categoryIssues.length}</div>
        <div class="quality-work-note">Lignes Sheet probablement placées dans la mauvaise colonne.</div>
      </button>
      <button class="quality-work-card" onclick="qualityFilterIssueKind('optional')">
        <div class="quality-work-label">Optionnel Publish</div>
        <div class="quality-work-value">${optionalIssues.length}</div>
        <div class="quality-work-note">Handles, logos et tags utiles mais non bloquants.</div>
      </button>
    </div>
  `;
  if (!missing.length) {
    box.innerHTML = `
      ${summaryCards}
      <div class="quality-assets-head">
        <div>
          <div class="quality-assets-title">Photos équipement manquantes</div>
          <div class="quality-assets-note">Aucune photo équipement manquante détectée avec les règles actuelles.</div>
        </div>
        <span class="quality-pill ok">OK</span>
      </div>
    `;
    return;
  }

  const groups = new Map();
  missing.forEach(issue => {
    const category = issue.category || 'Equipment';
    if (!groups.has(category)) {
      groups.set(category, {
        category,
        priority: issue.priority || _qualityPriority(category),
        rows: [],
        unique: new Set(),
        candidates: 0,
      });
    }
    const group = groups.get(category);
    group.rows.push(issue);
    group.unique.add(`${_brandKey(issue.brand)}|${_ffFold(issue.reference)}`);
    if ((issue.candidates || []).length) group.candidates += 1;
  });

  const ordered = Array.from(groups.values())
    .sort((a, b) => a.priority - b.priority || b.rows.length - a.rows.length || a.category.localeCompare(b.category));
  const totalUnique = new Set(missing.map(i => `${i.category}|${_brandKey(i.brand)}|${_ffFold(i.reference)}`)).size;
  const today = [];
  const seenToday = new Set();
  missing
    .slice()
    .sort((a, b) => (a.priority || 99) - (b.priority || 99) || String(a.itemName).localeCompare(String(b.itemName)))
    .forEach(item => {
      const key = `${item.category}|${_brandKey(item.brand)}|${_ffFold(item.reference)}`;
      if (seenToday.has(key) || today.length >= 10) return;
      seenToday.add(key);
      today.push(item);
    });

  box.innerHTML = `
    ${summaryCards}
    <div class="quality-assets-head">
      <div>
        <div class="quality-assets-title">Photos équipement réellement manquantes</div>
        <div class="quality-assets-note">${missing.length} lignes rider · ${totalUnique} équipements uniques · priorité automatique par impact visuel.</div>
      </div>
      <span class="quality-pill warning">${missing.length}</span>
    </div>
    <div class="quality-assets-grid">
      ${ordered.map(group => `
        <button class="quality-asset-card" onclick="qualityFilterAssetCategory('${_esc(group.category)}')" title="Filtrer ${_esc(group.category)}">
          <div class="quality-asset-top">
            <span class="quality-asset-cat">${_esc(group.category)}</span>
            <span class="quality-priority ${_qualityPriorityClass(group.priority)}">${_qualityPriorityLabel(group.priority)}</span>
          </div>
          <div class="quality-asset-count">${group.rows.length}</div>
          <div class="quality-asset-meta">${group.unique.size} équipement${group.unique.size > 1 ? 's' : ''} unique${group.unique.size > 1 ? 's' : ''}<br>${group.candidates} avec candidat proche</div>
        </button>
      `).join('')}
    </div>
    <div class="quality-today">
      <div class="quality-today-title">Photos à récupérer aujourd’hui</div>
      <div class="quality-today-list">
        ${today.map(item => `
          <div class="quality-today-item">
            <strong>${_qualityPriorityLabel(item.priority)} · ${_esc(item.category)}</strong><br>
            ${_esc(item.itemName || [item.brand, item.reference].filter(Boolean).join(' '))}<br>
            <span style="color:#666">${_esc(item.expectedFilename || _qualityExpectedFilename(item))}</span>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}

function _qualityTopUniquePhotos(missing, limit = 6) {
  const rows = [];
  const seen = new Set();
  missing
    .slice()
    .sort((a, b) => (a.priority || 99) - (b.priority || 99) || String(a.itemName).localeCompare(String(b.itemName)))
    .forEach(item => {
      const key = `${item.category}|${_brandKey(item.brand)}|${_ffFold(item.reference)}`;
      if (seen.has(key) || rows.length >= limit) return;
      seen.add(key);
      rows.push(item);
    });
  return rows;
}

function _qualitySheetDataIssues(issues) {
  return issues.filter(item =>
    item.type === 'equipment'
    && !item.assetKind
    && item.severity !== 'ok'
    && (item.detail.includes('incomplète') || item.detail.includes('Aucun équipement'))
  );
}

function renderQualityDailyDashboard(activeIssues) {
  const box = document.getElementById('quality-daily-dashboard');
  if (!box) return;
  const missing = activeIssues.filter(i => i.assetKind === 'equipment_photo');
  const categories = activeIssues.filter(i => i.assetKind === 'equipment_category');
  const sheetData = _qualitySheetDataIssues(activeIssues);
  const photos = _qualityTopUniquePhotos(missing, 6);
  const categoryRows = categories.slice().sort((a, b) => (a.priority || 99) - (b.priority || 99)).slice(0, 5);
  const sheetRows = sheetData.slice().sort((a, b) => a.severity.localeCompare(b.severity) || a.target.localeCompare(b.target)).slice(0, 5);

  const list = (rows, empty, render) => rows.length
    ? `<div class="quality-daily-list">${rows.map(render).join('')}</div>`
    : `<div class="quality-daily-empty">${_esc(empty)}</div>`;

  box.innerHTML = `
    <div class="quality-daily-head">
      <div>
        <div class="quality-daily-title">Aujourd’hui</div>
        <div class="quality-daily-subtitle">Les corrections utiles à faire en premier, sans parcourir toute la table.</div>
      </div>
      <button class="quality-daily-action" style="width:auto;min-width:180px" onclick="qualityCopyDailyTodo()">Copier la todo</button>
    </div>
    <div class="quality-daily-grid">
      <div class="quality-daily-card warn">
        <div class="quality-daily-card-head">
          <span class="quality-daily-card-title">Photos prioritaires</span>
          <span class="quality-daily-count">${missing.length}</span>
        </div>
        ${list(photos, 'Aucune photo équipement prioritaire à traiter.', item => `
          <div class="quality-daily-item">
            <div class="quality-daily-main">${_qualityPriorityLabel(item.priority)} · ${_esc(item.category)} · ${_esc(item.itemName || [item.brand, item.reference].filter(Boolean).join(' '))}</div>
            <div class="quality-daily-sub">${_esc(item.expectedFilename || _qualityExpectedFilename(item))}</div>
          </div>
        `)}
        <button class="quality-daily-action" onclick="qualityFilterIssueKind('equipment_photo')">Voir les photos</button>
      </div>
      <div class="quality-daily-card critical">
        <div class="quality-daily-card-head">
          <span class="quality-daily-card-title">Catégories suspectes</span>
          <span class="quality-daily-count">${categories.length}</span>
        </div>
        ${list(categoryRows, 'Aucune catégorie suspecte détectée.', item => `
          <div class="quality-daily-item">
            <div class="quality-daily-main">${_esc(item.itemName || item.target)}</div>
            <div class="quality-daily-sub">${_esc(item.riderName || item.target)} · ${_esc(item.category)} → ${_esc(item.expectedCategory || '')}</div>
          </div>
        `)}
        <button class="quality-daily-action" onclick="qualityFilterIssueKind('equipment_category')">Voir les catégories</button>
      </div>
      <div class="quality-daily-card optional">
        <div class="quality-daily-card-head">
          <span class="quality-daily-card-title">Données Sheet</span>
          <span class="quality-daily-count">${sheetData.length}</span>
        </div>
        ${list(sheetRows, 'Aucune donnée Sheet bloquante à corriger.', item => `
          <div class="quality-daily-item">
            <div class="quality-daily-main">${_esc(item.target)}</div>
            <div class="quality-daily-sub">${_esc(item.detail)}</div>
          </div>
        `)}
        <button class="quality-daily-action" onclick="qualityFilterIssueKind('sheet_data')">Voir les données</button>
      </div>
    </div>
  `;
}

function qualityFilterAssetCategory(category) {
  const sev = document.getElementById('quality-severity');
  const type = document.getElementById('quality-type');
  const kind = document.getElementById('quality-kind');
  const search = document.getElementById('quality-search');
  if (sev) sev.value = 'warning';
  if (type) type.value = 'equipment';
  if (kind) kind.value = 'equipment_photo';
  if (search) search.value = category;
  renderQualityCenter();
}

function qualityFilterIssueKind(issueKind) {
  const sev = document.getElementById('quality-severity');
  const type = document.getElementById('quality-type');
  const kind = document.getElementById('quality-kind');
  const state = document.getElementById('quality-state');
  const search = document.getElementById('quality-search');
  if (state) state.value = 'active';
  if (type) type.value = issueKind === 'optional' ? 'all' : 'equipment';
  if (sev) sev.value = issueKind === 'optional' ? 'optional' : issueKind === 'sheet_data' ? 'all' : 'warning';
  if (kind) kind.value = issueKind;
  if (search) search.value = '';
  renderQualityCenter();
}

function qualityToggleCandidatePanel(btn) {
  const panel = btn?.closest('td')?.querySelector('.quality-candidates');
  if (!panel) return;
  panel.classList.toggle('open');
}

function _qualityPriorityCell(item) {
  if (!['equipment_photo', 'equipment_category'].includes(item.assetKind)) return '<span style="color:#444">-</span>';
  const priority = item.priority || _qualityPriority(item.category);
  return `<span class="quality-priority ${_qualityPriorityClass(priority)}">${_qualityPriorityLabel(priority)}</span>`;
}

function _qualityRequirementCell(item) {
  const value = item.requirement === 'nice_to_have' ? 'optionnel' : 'requis';
  const cls = item.requirement === 'nice_to_have' ? 'nice_to_have' : 'required';
  return `<span class="quality-pill ${cls}">${value}</span>`;
}

function _qualityManualStateCell(item) {
  const state = item.manualState || 'active';
  const labels = { active: 'actif', ignored: 'ignoré', validated: 'validé' };
  return `<span class="quality-pill ${state}">${labels[state] || state}</span>`;
}

function _qualityManualControls(item) {
  if (item.severity === 'ok') return '';
  const key = _esc(item.key || '');
  if (item.manualState === 'ignored' || item.manualState === 'validated') {
    return `
      <div class="quality-manual-actions">
        <button class="quality-manual-btn" onclick="qualitySetManualStatus('${key}', 'active')">Réactiver</button>
      </div>
    `;
  }
  return `
    <div class="quality-manual-actions">
      <button class="quality-manual-btn" onclick="qualitySetManualStatus('${key}', 'validated')">Valider</button>
      <button class="quality-manual-btn danger" onclick="qualitySetManualStatus('${key}', 'ignored')">Ignorer</button>
    </div>
  `;
}

function _qualityActionHtml(item) {
  const candidates = item.candidates || [];
  const expected = item.assetKind === 'equipment_photo'
    ? `<div class="quality-expected">Nom attendu : <code>${_esc(item.expectedFilename || _qualityExpectedFilename(item))}</code></div>`
    : '';
  const candidateHtml = item.assetKind === 'equipment_photo' ? (candidates.length ? `
    <button class="quality-candidate-btn" onclick="qualityToggleCandidatePanel(this)">Voir ${candidates.length} candidat${candidates.length > 1 ? 's' : ''}</button>
    <div class="quality-candidates">
      <div class="quality-candidate-grid">
        ${candidates.map(c => `
          <div class="quality-candidate">
            <img src="${_esc(c.url)}" alt="${_esc(c.name)}">
            <div class="quality-candidate-name">${_esc(c.folder ? `${c.folder}/` : '')}${_esc(c.name)}</div>
            <div class="quality-candidate-reason">${_esc(c.reason || 'fichier proche')}</div>
          </div>
        `).join('')}
      </div>
    </div>
  ` : '<div class="quality-assets-note" style="margin-top:8px">Aucun candidat proche dans le dossier de cette catégorie.</div>') : '';
  return `<div class="quality-action">${_esc(item.action)}</div>${expected}${candidateHtml}${_qualityManualControls(item)}`;
}

async function qualityCopyDailyTodo() {
  const issues = _qualityBuildIssues().filter(i => (i.manualState || 'active') === 'active');
  const photos = issues
    .filter(i => i.assetKind === 'equipment_photo')
    .sort((a, b) => (a.priority || 99) - (b.priority || 99) || String(a.itemName).localeCompare(String(b.itemName)));
  const categories = issues.filter(i => i.assetKind === 'equipment_category');
  const optionals = issues.filter(i => i.severity === 'optional');
  const lines = ['Freeride Fanatics - todo qualité du jour', ''];
  lines.push(`Photos réellement manquantes (${photos.length})`);
  photos.slice(0, 25).forEach(item => {
    lines.push(`- ${_qualityPriorityLabel(item.priority)} ${item.category}: ${item.itemName || `${item.brand} ${item.reference}`} -> ${item.expectedFilename || _qualityExpectedFilename(item)}`);
  });
  if (photos.length > 25) lines.push(`- ... ${photos.length - 25} autres photos`);
  lines.push('', `Catégories suspectes (${categories.length})`);
  categories.slice(0, 25).forEach(item => {
    lines.push(`- ${item.riderName || item.target}: ${item.itemName || `${item.brand} ${item.reference}`} est dans ${item.category}, vérifier ${item.expectedCategory}`);
  });
  if (categories.length > 25) lines.push(`- ... ${categories.length - 25} autres lignes`);
  lines.push('', `Optionnels Publish (${optionals.length})`);
  optionals.slice(0, 15).forEach(item => lines.push(`- ${item.target}: ${item.detail}`));
  try {
    await navigator.clipboard.writeText(lines.join('\n'));
    const status = document.getElementById('quality-status');
    if (status) status.textContent = 'Todo qualité copiée.';
  } catch(e) {
    const status = document.getElementById('quality-status');
    if (status) status.textContent = 'Impossible de copier la todo.';
  }
}

function renderQualityCenter() {
  const tbody = document.getElementById('quality-tbody');
  if (!tbody) return;
  const severity = document.getElementById('quality-severity')?.value || 'all';
  const type = document.getElementById('quality-type')?.value || 'all';
  const issueKind = document.getElementById('quality-kind')?.value || 'all';
  const stateFilter = document.getElementById('quality-state')?.value || 'active';
  const query = (document.getElementById('quality-search')?.value || '').trim().toLowerCase();
  const all = _qualityBuildIssues();
  const active = all.filter(i => (i.manualState || 'active') === 'active');
  const critical = active.filter(i => i.severity === 'critical').length;
  const warning = active.filter(i => i.severity === 'warning').length;
  const optional = active.filter(i => i.severity === 'optional').length;
  const actionable = critical + warning;
  const totalChecks = active.length;
  const score = totalChecks ? Math.max(0, Math.round((totalChecks - actionable) / totalChecks * 100)) : 100;
  renderQualityDailyDashboard(active);
  renderQualityAssetSummary(active);

  document.getElementById('quality-score').textContent = `${score}%`;
  document.getElementById('quality-critical').textContent = critical;
  document.getElementById('quality-warning').textContent = warning;
  document.getElementById('quality-optional').textContent = optional;
  document.getElementById('quality-total').textContent = totalChecks;
  const status = document.getElementById('quality-status');
  if (status) status.textContent = `${_app.profiles.length} riders · ${Object.keys(_app.equipment || {}).length} fiches équipements · ${(_app.eqVariants || []).length} photos équipement`;

  const filtered = all.filter(item => {
    const itemState = item.manualState || 'active';
    if (stateFilter !== 'all' && itemState !== stateFilter) return false;
    if (severity !== 'all' && item.severity !== severity) return false;
    if (type !== 'all' && item.type !== type) return false;
    if (issueKind === 'equipment_photo' && item.assetKind !== 'equipment_photo') return false;
    if (issueKind === 'equipment_category' && item.assetKind !== 'equipment_category') return false;
    if (issueKind === 'sheet_data' && !_qualitySheetDataIssues([item]).length) return false;
    if (issueKind === 'optional' && item.severity !== 'optional') return false;
    if (query && !item.search.includes(query)) return false;
    return true;
  });

  const order = { critical: 0, warning: 1, optional: 2, ok: 3 };
  filtered.sort((a, b) => {
    const pa = a.assetKind === 'equipment_photo' ? (a.priority || 99) : 99;
    const pb = b.assetKind === 'equipment_photo' ? (b.priority || 99) : 99;
    return (order[a.severity] - order[b.severity]) || a.type.localeCompare(b.type) || (pa - pb) || a.target.localeCompare(b.target);
  });

  if (!filtered.length) {
    tbody.innerHTML = '<tr><td colspan="8" style="color:#666">Aucun résultat pour ces filtres.</td></tr>';
    return;
  }

  tbody.innerHTML = filtered.map(item => `
    <tr class="${item.manualState === 'ignored' ? 'manual-ignored' : item.manualState === 'validated' ? 'manual-validated' : ''}">
      <td><span class="quality-pill ${item.severity}">${_esc(item.severity)}</span></td>
      <td>${_esc(item.type)}</td>
      <td>${_qualityRequirementCell(item)}</td>
      <td>${_qualityManualStateCell(item)}</td>
      <td>${_qualityPriorityCell(item)}</td>
      <td class="quality-target">${_esc(item.target)}</td>
      <td class="quality-detail">${_esc(item.detail)}</td>
      <td>${_qualityActionHtml(item)}</td>
    </tr>
  `).join('');
}

// ── Connexions ────────────────────────────────────────────────────────────────
function connClick(platform) {
  // Dispatch vers le handler spécifique, sinon fallback "bientôt dispo"
  if (platform === 'google') { connOAuthPopup('google'); return; }
  const card = document.getElementById('conn-' + platform);
  if (!card) return;
  const btn  = card.querySelector('.conn-btn');
  const orig = btn.textContent;
  btn.textContent = '⏳ Bientôt disponible';
  btn.disabled = true;
  setTimeout(() => { btn.textContent = orig; btn.disabled = false; }, 2000);
}

// Ouvre un popup OAuth et attend le message de succès
function connOAuthPopup(platform) {
  const w = window.open(
    `/api/auth/${platform}`,
    `${platform}_oauth`,
    'width=620,height=720,scrollbars=yes,resizable=yes'
  );
  const handler = (e) => {
    if (e.data?.type === `${platform}_oauth_success`) {
      window.removeEventListener('message', handler);
      if (platform === 'google') connRefreshGoogle();
    }
  };
  window.addEventListener('message', handler);
}

// Met à jour la carte Google en fonction du statut serveur
async function connRefreshGoogle() {
  const card = document.getElementById('conn-google');
  if (!card) return;
  const statusEl = card.querySelector('.conn-status');
  const btn = card.querySelector('.conn-btn');
  try {
    const d = await fetch('/api/auth/google/status').then(r => r.json());
    if (!d.configured) {
      card.classList.remove('connected');
      statusEl.innerHTML = '<span class="dot" style="background:#f90"></span>client_secret.json requis';
      btn.textContent = 'Configurer ↗';
      btn.style.background = '';
      btn.onclick = () => window.open('https://console.cloud.google.com/apis/credentials', '_blank');
    } else if (d.connected) {
      card.classList.add('connected');
      statusEl.innerHTML = `<span class="dot" style="background:#4CAF50"></span>${d.email || 'Connecté'}`;
      btn.textContent = 'Déconnecter';
      btn.style.background = '#2a2a2a';
      btn.onclick = async () => {
        await fetch('/api/auth/google/logout', {method:'POST'});
        btn.onclick = () => connClick('google');
        connRefreshGoogle();
      };
    } else {
      card.classList.remove('connected');
      statusEl.innerHTML = '<span class="dot"></span>Non connecté';
      btn.textContent = 'Se connecter';
      btn.style.background = '';
      btn.onclick = () => connClick('google');
    }
  } catch(e) { console.error('Google status error', e); }
}

// ── Dashboard dropdown ────────────────────────────────────────────────────
function toggleDashboard(e) {
  e?.stopPropagation();
  document.getElementById('dashboard-dropdown').classList.toggle('open');
}
function closeDashboard() {
  document.getElementById('dashboard-dropdown').classList.remove('open');
}
document.addEventListener('click', function(e) {
  const dd = document.getElementById('dashboard-dropdown');
  if (dd && !dd.contains(e.target)) closeDashboard();
});

// ── Burger menu ───────────────────────────────────────────────────────────
function toggleBurger() {
  document.getElementById('burger-drawer').classList.toggle('open');
}
function closeBurger() {
  document.getElementById('burger-drawer').classList.remove('open');
}

// ── Logos page ────────────────────────────────────────────────────────────
let _logosData   = [];
let _logosFolder = '';

async function logosBrowseFolder() {
  const btn = document.getElementById('logos-folder-btn');
  btn.disabled = true;
  btn.textContent = '⏳…';
  try {
    const r = await fetch('/api/logos/browse-folder');
    const d = await r.json();
    if (!d.ok || !d.path) {
      document.getElementById('logos-folder-stats').textContent = d.error || 'Annulé.';
      return;
    }
    _logosFolder = d.path;
    document.getElementById('logos-folder-display').textContent = d.path;
    document.getElementById('logos-folder-display').style.color = '#C8D400';
    const modeNote = d.native_dialog
      ? '<span style="color:#888">Dialogue natif utilisé</span>'
      : '<span style="color:#888">Dossier par défaut utilisé</span>';
    const extraNote = d.message ? ` · <span style="color:#888">${d.message}</span>` : '';
    document.getElementById('logos-folder-stats').innerHTML =
      `${modeNote}${extraNote}<br><span style="color:#C8D400">✅ ${d.count} logos détectés dans ce dossier</span>`;
    // Auto-scan si une URL est déjà présente
    if (document.getElementById('logos-url').value.trim()) logosScrap();
  } finally {
    btn.disabled = false;
    btn.textContent = '📁 Choisir le dossier…';
  }
}

async function logosScrap() {
  const url = document.getElementById('logos-url').value.trim();
  if (!url) return;
  if (!_logosFolder) {
    document.getElementById('logos-stats').innerHTML =
      '<span style="color:#f55">⚠️ Choisis d\'abord le dossier logos (étape ①)</span>';
    return;
  }

  const stats   = document.getElementById('logos-stats');
  const tbody   = document.getElementById('logos-tbody');
  const table   = document.getElementById('logos-table');
  const actions = document.getElementById('logos-actions');
  const zipBtn  = document.getElementById('logos-zip-btn');

  stats.textContent = '⏳ Scan en cours…';
  tbody.innerHTML   = '';
  table.style.display   = 'none';
  actions.style.display = 'none';
  zipBtn.disabled = true;
  _logosData = [];

  try {
    const r = await fetch('/api/logos/scrape', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({url, folder: _logosFolder})
    });
    const data = await r.json();
    if (!data.ok) { stats.innerHTML = '❌ ' + (data.error||'Erreur'); return; }

    _logosData = data.logos;
    const existing = data.logos.filter(l => l.exists).length;
    const missing  = data.logos.filter(l => !l.exists).length;

    stats.innerHTML =
      `<b style="color:#eee">${data.logos.length}</b> logos trouvés sur le site — ` +
      `<span style="color:#C8D400">✅ ${existing} déjà présents</span> · ` +
      `<span style="color:#f55">⬜ ${missing} manquants</span>`;

    tbody.innerHTML = data.logos.map((l,i) => `
      <tr>
        <td><input type="checkbox" class="logo-chk" data-i="${i}" ${!l.exists ? 'checked' : ''}
          onchange="logosUpdateCount()"></td>
        <td><img class="logo-thumb" src="${l.preview_url}" onerror="this.style.opacity=.15"></td>
        <td style="font-weight:600;color:#ddd">${l.label||l.name}</td>
        <td>${l.exists
          ? '<span class="logo-status-ok">✅ présent</span>'
          : '<span class="logo-status-miss">⬜ manquant</span>'}</td>
        <td style="color:#555;font-size:11px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${l.file}</td>
      </tr>`).join('');

    table.style.display   = 'table';
    actions.style.display = 'flex';
    logosUpdateCount();
  } catch(e) {
    stats.textContent = '❌ ' + e.message;
  }
}

function logosUpdateCount() {
  const checked = document.querySelectorAll('.logo-chk:checked').length;
  document.getElementById('logos-sel-count').textContent = checked ? `${checked} sélectionnés` : '';
  document.getElementById('logos-zip-btn').disabled = checked === 0;
  document.getElementById('logos-chk-all').checked =
    checked === document.querySelectorAll('.logo-chk').length;
}

function logosToggleAll(checked) {
  document.querySelectorAll('.logo-chk').forEach(c => c.checked = checked);
  logosUpdateCount();
}

function logosSelectMissing() {
  document.querySelectorAll('.logo-chk').forEach((c, i) => {
    c.checked = !_logosData[i]?.exists;
  });
  logosUpdateCount();
}

async function logosDownloadZip() {
  const selected = [...document.querySelectorAll('.logo-chk:checked')]
    .map(c => _logosData[parseInt(c.dataset.i)])
    .filter(Boolean);

  if (!selected.length) return;

  const prog    = document.getElementById('logos-progress');
  const bar     = document.getElementById('logos-progress-bar');
  const stats   = document.getElementById('logos-stats');
  const zipBtn  = document.getElementById('logos-zip-btn');

  prog.style.display = 'block';
  bar.style.width    = '5%';
  zipBtn.disabled    = true;
  stats.innerHTML    = `⏳ Téléchargement de ${selected.length} logos…`;

  try {
    const r = await fetch('/api/logos/download-zip', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({logos: selected.map(l => ({name:l.name, file:l.file, url:l.url})), folder: _logosFolder})
    });

    bar.style.width = '80%';

    if (!r.ok) {
      const e = await r.json();
      throw new Error(e.error || 'Erreur serveur');
    }

    const blob = await r.blob();
    bar.style.width = '100%';

    // Déclencher téléchargement ZIP
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'logos_freeride.zip';
    document.body.appendChild(a); a.click(); document.body.removeChild(a);

    stats.innerHTML = `✅ ZIP téléchargé — ${selected.length} logos`;
    // Rafraîchir le scan
    setTimeout(logosScrap, 800);
  } catch(e) {
    stats.innerHTML = '❌ ' + e.message;
  } finally {
    setTimeout(() => { prog.style.display = 'none'; bar.style.width = '0'; }, 2000);
    zipBtn.disabled = false;
  }
}

// ── Riders page ──────────────────────────────────────────────────────────
let _ridersMgr = { ppFolder: '', picFolder: '' };

async function ridersBrowseFolder(type) {
  const btnId   = type === 'pp' ? 'riders-pp-btn'   : 'riders-pic-btn';
  const pathId  = type === 'pp' ? 'riders-pp-path'  : 'riders-pic-path';
  const statsId = type === 'pp' ? 'riders-pp-stats' : 'riders-pic-stats';
  const btn = document.getElementById(btnId);
  btn.disabled = true; btn.textContent = '⏳…';
  try {
    const r = await fetch(`/api/riders/browse-folder?type=${type}`);
    const d = await r.json();
    if (!d.ok) { document.getElementById(statsId).textContent = d.error || 'Annulé'; return; }
    if (type === 'pp') _ridersMgr.ppFolder  = d.path;
    else               _ridersMgr.picFolder = d.path;
    const el = document.getElementById(pathId);
    el.textContent = d.path; el.classList.add('set');
    const modeNote = d.native_dialog ? 'Dialogue natif utilisé' : 'Dossier par défaut utilisé';
    const extraNote = d.message ? ` · ${d.message}` : '';
    document.getElementById(statsId).innerHTML = `${modeNote}${extraNote}<br>${d.count} fichier(s) trouvé(s)`;
  } catch(e) {
    document.getElementById(statsId).textContent = '❌ ' + e.message;
  } finally {
    btn.disabled = false; btn.textContent = '📁 Choisir…';
  }
}

async function ridersScan() {
  const btn = document.getElementById('riders-scan-btn');
  const prog = document.getElementById('riders-progress');
  const bar  = document.getElementById('riders-progress-bar');
  const stats = document.getElementById('riders-stats');
  const table = document.getElementById('riders-table');
  const tbody = document.getElementById('riders-tbody');

  btn.disabled = true; btn.textContent = '⏳ Scan…';
  prog.style.display = 'block'; bar.style.width = '20%';
  stats.textContent = ''; tbody.innerHTML = ''; table.style.display = 'none';

  try {
    const r = await fetch('/api/riders/scan-photos', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ pp_folder: _ridersMgr.ppFolder, pic_folder: _ridersMgr.picFolder })
    });
    const d = await r.json();
    if (!d.ok) { stats.textContent = '❌ ' + d.error; return; }

    bar.style.width = '100%';
    const ppOk  = d.riders.filter(x => x.pp_found).length;
    const picOk = d.riders.filter(x => x.pic_found).length;
    stats.innerHTML = `<b style="color:#eee">${d.riders.length}</b> riders ·
      PP: <b style="color:#C8D400">${ppOk}/${d.riders.length}</b> ·
      Action: <b style="color:#C8D400">${picOk}/${d.riders.length}</b>`;

    // Stocke les handles manquants pour le batch
    _ridersMgr.missing = d.riders.filter(x => !x.pp_found).map(x => x.instagram);
    document.getElementById('riders-batch-btn').style.display =
      _ridersMgr.missing.length > 0 ? 'inline-flex' : 'none';

    tbody.innerHTML = d.riders.map(r => {
      const ig = r.instagram.replace('@','');
      const ppThumb = r.pp_found
        ? `<img class="rider-thumb" src="/api/riders/thumb?path=${encodeURIComponent(r.pp_path)}" onerror="this.style.display='none'">`
        : `<div id="pp-thumb-${ig}" style="width:40px;height:40px;border-radius:50%;background:#1a1a1a;border:1px solid #2a2a2a"></div>`;
      const ppStatus = r.pp_found
        ? '<span class="rider-status-ok">✅ OK</span>'
        : `<span class="rider-status-miss" id="pp-status-${ig}">❌ Manquant</span>
           <button class="btn-dl-pp" id="pp-btn-${ig}" onclick="ridersDownloadPP('${r.instagram}')">⬇</button>`;
      return `
      <tr id="pp-row-${ig}">
        <td style="font-weight:600;color:#eee">${r.display_name}</td>
        <td id="pp-cell-thumb-${ig}">${ppThumb}</td>
        <td>${ppStatus}</td>
        <td>${r.pic_found
          ? `<img class="rider-thumb-action" src="/api/riders/thumb?path=${encodeURIComponent(r.pic_path)}" onerror="this.style.display='none'">`
          : '<div style="width:56px;height:40px;border-radius:4px;background:#1a1a1a;border:1px solid #2a2a2a"></div>'
        }</td>
        <td>${r.pic_found
          ? '<span class="rider-status-ok">✅ OK</span>'
          : '<span class="rider-status-miss">❌ Manquant</span>'
        }</td>
        <td><a class="ig-link" href="https://instagram.com/${ig}" target="_blank">@${ig} ↗</a></td>
        <td style="font-size:11px;color:#444;font-family:monospace">${r.pp_file || '—'}</td>
        <td style="font-size:11px;color:#444;font-family:monospace">${r.pic_file || '—'}</td>
      </tr>`;
    }).join('');

    table.style.display = 'table';

    // Peuple le dropdown rider du downloader
    const sel = document.getElementById('pic-dl-rider');
    sel.innerHTML = '<option value="">— Choisir un rider —</option>' +
      d.riders.map(r => {
        const ig = r.instagram.replace('@','');
        const miss = r.pic_found ? '' : ' ❌';
        return `<option value="${ig}" data-name="${r.display_name}" data-pp="${r.pp_path}">${r.display_name}${miss}</option>`;
      }).join('');

    // Init liste manquants pour le bouton Suivant
    _ridersMgr.missingPic    = d.riders.filter(x => !x.pic_found);
    _ridersMgr.missingPicIdx = -1;
    const nextBtn   = document.getElementById('pic-dl-next-btn');
    const missCount = document.getElementById('pic-dl-missing-count');
    if (_ridersMgr.missingPic.length > 0) {
      nextBtn.style.display = 'inline-block';
      missCount.textContent = `${_ridersMgr.missingPic.length} photos manquantes`;
      picDlNext(); // avance directement au premier manquant
    } else {
      nextBtn.style.display = 'none';
      missCount.textContent = '✅ Toutes les photos sont là !';
    }

  } catch(e) {
    stats.textContent = '❌ ' + e.message;
  } finally {
    btn.disabled = false; btn.textContent = '🔍 Scanner les riders';
    setTimeout(() => { prog.style.display = 'none'; bar.style.width = '0'; }, 1500);
  }
}

async function ridersDownloadPP(instagram) {
  const ig  = instagram.replace('@','');
  const btn = document.getElementById(`pp-btn-${ig}`);
  const st  = document.getElementById(`pp-status-${ig}`);
  const th  = document.getElementById(`pp-cell-thumb-${ig}`);
  if (btn) { btn.disabled = true; btn.textContent = '⏳'; }
  if (st)  { st.textContent = '⏳ Téléchargement…'; st.className = ''; st.style.color='#888'; }
  try {
    const r = await fetch('/api/riders/download-pp', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ handle: ig, pp_folder: _ridersMgr.ppFolder })
    });
    const d = await r.json();
    if (!d.ok) throw new Error(d.error);
    if (st) { st.textContent = '✅ OK'; st.style.color = '#C8D400'; }
    if (btn) btn.style.display = 'none';
    if (th) {
      // Rafraîchit la miniature
      const img = document.createElement('img');
      img.className = 'rider-thumb';
      img.src = d.thumb + '&t=' + Date.now();
      img.onerror = () => {};
      th.innerHTML = '';
      th.appendChild(img);
    }
    // Retire de la liste manquants + re-scan silencieux
    _ridersMgr.missing = (_ridersMgr.missing || []).filter(h => h.replace('@','') !== ig);
    if (_ridersMgr.missing.length === 0)
      document.getElementById('riders-batch-btn').style.display = 'none';
    ridersSilentRescan();
  } catch(e) {
    if (st) { st.textContent = '❌ ' + e.message; st.style.color = '#f55'; }
    if (btn) { btn.disabled = false; btn.textContent = '⬇'; }
  }
}

async function ridersSilentRescan() {
  try {
    const r = await fetch('/api/riders/scan-photos', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ pp_folder: _ridersMgr.ppFolder, pic_folder: _ridersMgr.picFolder })
    });
    const d = await r.json();
    if (!d.ok) return;

    // Met à jour uniquement les cellules fichier + statut action dans chaque ligne
    d.riders.forEach(r => {
      const ig = r.instagram.replace('@','');

      // Colonne "Fichier PP" (7e col, index 6)
      const ppFileCell = document.querySelector(`#pp-row-${ig} td:nth-child(7)`);
      if (ppFileCell) ppFileCell.textContent = r.pp_file || '—';

      // Colonne "Fichier Action" (8e col, index 7)
      const picFileCell = document.querySelector(`#pp-row-${ig} td:nth-child(8)`);
      if (picFileCell) picFileCell.textContent = r.pic_file || '—';

      // Colonne "Statut Action" (5e col) — met à jour si maintenant trouvé
      if (r.pic_found) {
        const stCell = document.querySelector(`#pp-row-${ig} td:nth-child(5)`);
        if (stCell && stCell.querySelector('.rider-status-miss'))
          stCell.innerHTML = '<span class="rider-status-ok">✅ OK</span>';
        const thCell = document.querySelector(`#pp-row-${ig} td:nth-child(4)`);
        if (thCell && !thCell.querySelector('img')) {
          const img = document.createElement('img');
          img.className = 'rider-thumb-action';
          img.src = `/api/riders/thumb?path=${encodeURIComponent(r.pic_path)}&t=${Date.now()}`;
          thCell.innerHTML = '';
          thCell.appendChild(img);
        }
      }
    });
  } catch(_) {}
}

function picDlNext() {
  const missing = _ridersMgr.missingPic || [];
  if (!missing.length) return;
  _ridersMgr.missingPicIdx = (_ridersMgr.missingPicIdx + 1) % missing.length;
  const rider = missing[_ridersMgr.missingPicIdx];
  const ig    = rider.instagram.replace('@','');

  // Update dropdown
  document.getElementById('pic-dl-rider').value = ig;

  // Update compteur
  document.getElementById('pic-dl-missing-count').textContent =
    `${_ridersMgr.missingPicIdx + 1}/${missing.length} manquants`;

  // Affiche la carte rider
  picDlRiderChanged(ig, rider);

  // Reset champs
  document.getElementById('pic-dl-url').value = '';
  document.getElementById('pic-dl-status').textContent = '';
  document.getElementById('pic-dl-preview-box').style.display = 'none';
  document.getElementById('pic-dl-carousel').style.display = 'none';
  document.getElementById('pic-dl-carousel-grid').innerHTML = '';
  _picDlSelectedUrl = '';
}

/* ── Instagram login/logout ── */
async function igCheckStatus() {
  try {
    const r = await fetch('/api/riders/ig-status');
    const d = await r.json();
    const dot   = document.getElementById('ig-status-dot');
    const label = document.getElementById('ig-status-label');
    const btnIn  = document.getElementById('ig-login-btn');
    const btnOut = document.getElementById('ig-logout-btn');
    if (d.logged_in) {
      dot.style.background   = '#C8D400';
      label.style.color      = '#C8D400';
      label.textContent      = `Instagram : @${d.username}`;
      btnIn.style.display    = 'none';
      btnOut.style.display   = 'inline-block';
    } else {
      dot.style.background   = '#555';
      label.style.color      = '#666';
      label.textContent      = 'Instagram : non connecté';
      btnIn.style.display    = 'inline-block';
      btnOut.style.display   = 'none';
    }
  } catch(_) {}
}

async function igLogin() {
  const username = prompt('Nom d\'utilisateur Instagram (sans @) :');
  if (!username) return;
  const label = document.getElementById('ig-status-label');
  label.style.color   = '#888';
  label.textContent   = 'Connexion en cours…';
  try {
    const r = await fetch('/api/riders/ig-login', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ username })
    });
    const d = await r.json();
    if (d.ok) {
      igCheckStatus();
    } else {
      label.style.color = '#cc4400';
      label.textContent = '❌ ' + d.error;
      setTimeout(igCheckStatus, 4000);
    }
  } catch(e) {
    label.style.color = '#cc4400';
    label.textContent = '❌ Erreur réseau';
    setTimeout(igCheckStatus, 4000);
  }
}

async function igLogout() {
  await fetch('/api/riders/ig-logout', { method:'POST' });
  igCheckStatus();
}

function picDlRiderChanged(ig, riderData) {
  if (!ig) return;
  const card    = document.getElementById('pic-dl-current-rider');
  const nameEl  = document.getElementById('pic-dl-rider-name');
  const igLink  = document.getElementById('pic-dl-rider-iglink');
  const ppImg   = document.getElementById('pic-dl-rider-pp');

  // Trouve les données du rider (depuis le scan ou le dropdown)
  let displayName = ig;
  let ppPath = '';
  if (riderData) {
    displayName = riderData.display_name;
    ppPath      = riderData.pp_path;
  } else {
    const opt = document.querySelector(`#pic-dl-rider option[value="${ig}"]`);
    if (opt) {
      displayName = opt.dataset.name || opt.textContent.replace(' ❌','');
      ppPath      = opt.dataset.pp   || '';
    }
  }

  nameEl.textContent    = displayName;
  igLink.href           = `https://www.instagram.com/${ig}/`;
  igLink.textContent    = `@${ig} — Ouvrir Instagram ↗`;
  ppImg.src             = ppPath
    ? `/api/riders/thumb?path=${encodeURIComponent(ppPath)}`
    : '';
  ppImg.style.display   = ppPath ? 'block' : 'none';
  card.style.display    = 'block';
}

let _picDlSelectedUrl = '';  // URL pleine résolution de l'image sélectionnée

function _picDlReset() {
  _picDlSelectedUrl = '';
  document.getElementById('pic-dl-carousel').style.display   = 'none';
  document.getElementById('pic-dl-carousel-grid').innerHTML  = '';
  document.getElementById('pic-dl-fallback').style.display   = 'none';
  document.getElementById('pic-dl-mode-badge').style.display = 'none';
  document.getElementById('pic-dl-btn').disabled             = true;
  document.getElementById('pic-dl-status').textContent       = '';
  document.getElementById('pic-dl-status').style.color       = '#888';
}

function _isCdnUrl(url) {
  return /scontent[^/]*\.cdninstagram\.com|cdninstagram\.com|fbcdn\.net|instagram\.f[a-z]{3,4}\d*-\d+\.fna/i.test(url);
}

async function picDlPreviewUrl(val) {
  val = val.trim();
  if (!val) { _picDlReset(); return; }

  const status  = document.getElementById('pic-dl-status');
  const badge   = document.getElementById('pic-dl-mode-badge');
  const btn     = document.getElementById('pic-dl-btn');

  _picDlReset();

  // ── Mode URL directe (CDN Instagram) ──────────────────────────────────
  if (_isCdnUrl(val)) {
    badge.style.display    = 'inline';
    status.style.color     = '#C8D400';
    status.textContent     = '✅ URL image directe détectée';
    _picDlSelectedUrl      = val;
    btn.disabled           = false;

    // Affiche preview via proxy
    const prev = document.getElementById('pic-dl-preview-box');
    const img  = document.getElementById('pic-dl-preview-img');
    img.src    = `/api/riders/proxy-img?url=${encodeURIComponent(val)}`;
    prev.style.display = 'block';
    return;
  }

  // ── Mode URL de post Instagram ────────────────────────────────────────
  const mPost = val.match(/instagram\.com\/(?:p|reel|tv)\/([A-Za-z0-9_-]+)/);
  if (!mPost) return;

  status.textContent = '🔍 Inspection du post…';

  try {
    const r = await fetch('/api/riders/inspect-pic', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ url: val })
    });
    const d = await r.json();
    if (!d.ok) throw new Error(d.error);

    status.style.color = '#888';
    status.textContent = d.count === 1 ? '1 photo trouvée' : `Carrousel — ${d.count} photos`;

    const grid     = document.getElementById('pic-dl-carousel-grid');
    const carousel = document.getElementById('pic-dl-carousel');
    grid.innerHTML = d.images.map((img, i) =>
      `<img class="carousel-thumb${i===0?' active':''}"
        src="/api/riders/proxy-img?url=${encodeURIComponent(img.thumb_url)}"
        data-full="${img.full_url}" data-idx="${i}"
        onclick="picDlSelectThumb(this)" title="Photo ${i+1}">`
    ).join('');
    carousel.style.display = 'block';
    _picDlSelectedUrl = d.images[0].full_url;
    btn.disabled = false;

  } catch(e) {
    // Échec → affiche le panneau fallback avec lien vers le post
    const fallback = document.getElementById('pic-dl-fallback');
    document.getElementById('pic-dl-fallback-link').href = val;
    fallback.style.display = 'block';
    status.style.color  = '#888';
    status.textContent  = '';
  }
}

function picDlSelectThumb(el) {
  document.querySelectorAll('.carousel-thumb').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  _picDlSelectedUrl = el.dataset.full;
}

async function picDlDownload() {
  const handle = document.getElementById('pic-dl-rider').value.trim();
  const status = document.getElementById('pic-dl-status');
  const btn    = document.getElementById('pic-dl-btn');
  const prev   = document.getElementById('pic-dl-preview-box');
  const prevImg= document.getElementById('pic-dl-preview-img');

  if (!_picDlSelectedUrl) { status.textContent = '⚠️ Colle une URL Instagram d\'abord'; return; }
  if (!handle)             { status.textContent = '⚠️ Sélectionne un rider'; return; }

  btn.disabled = true; btn.textContent = '⏳…';
  status.style.color = '#888'; status.textContent = 'Téléchargement…';
  prev.style.display = 'none';

  try {
    const r = await fetch('/api/riders/download-pic', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ img_url: _picDlSelectedUrl, handle, pic_folder: _ridersMgr.picFolder })
    });
    const d = await r.json();
    if (!d.ok) throw new Error(d.error);

    status.style.color = '#C8D400';
    status.textContent = `✅ Sauvegardé : ${d.file}`;
    const thumbUrl = d.thumb + '&t=' + Date.now();
    prevImg.src = thumbUrl;
    prev.style.display = 'block';

    // ── Mise à jour directe de la ligne dans la table ──────────────────
    const row = document.querySelector(`#pp-row-${handle}`);
    if (row) {
      // Statut action (col 5)
      const stCell = row.querySelector('td:nth-child(5)');
      if (stCell) stCell.innerHTML = '<span class="rider-status-ok">✅ OK</span>';

      // Miniature action (col 4)
      const thCell = row.querySelector('td:nth-child(4)');
      if (thCell) {
        const img = document.createElement('img');
        img.className = 'rider-thumb-action';
        img.src = thumbUrl;
        thCell.innerHTML = '';
        thCell.appendChild(img);
      }

      // Nom de fichier action (col 8)
      const fileCell = row.querySelector('td:nth-child(8)');
      if (fileCell) fileCell.textContent = d.file;
    }

    // Retire le rider de la liste manquants + met à jour le dropdown
    const opt = document.querySelector(`#pic-dl-rider option[value="${handle}"]`);
    if (opt) opt.textContent = opt.textContent.replace(' ❌','');
    _ridersMgr.missingPic = (_ridersMgr.missingPic || []).filter(r => r.instagram.replace('@','') !== handle);
    document.getElementById('pic-dl-missing-count').textContent =
      _ridersMgr.missingPic.length > 0
        ? `${_ridersMgr.missingPic.length} photos manquantes`
        : '✅ Toutes les photos sont là !';
    if (_ridersMgr.missingPic.length === 0)
      document.getElementById('pic-dl-next-btn').style.display = 'none';

    document.getElementById('pic-dl-url').value = '';
    _picDlReset();

    // Rescan en arrière-plan + avance au rider suivant
    ridersSilentRescan().finally(() => {
      if (_ridersMgr.missingPic.length > 0)
        setTimeout(() => { _ridersMgr.missingPicIdx--; picDlNext(); }, 400);
    });
  } catch(e) {
    status.style.color = '#f55';
    status.textContent = '❌ ' + e.message;
  } finally {
    btn.disabled = false; btn.textContent = '⬇ Télécharger';
  }
}

async function ridersDownloadAllPP() {
  const missing = [...(_ridersMgr.missing || [])];
  if (!missing.length) return;
  const batchBtn = document.getElementById('riders-batch-btn');
  batchBtn.disabled = true;
  batchBtn.textContent = `⏳ 0/${missing.length}…`;
  for (let i = 0; i < missing.length; i++) {
    batchBtn.textContent = `⏳ ${i+1}/${missing.length}…`;
    await ridersDownloadPP(missing[i]);
    if (i < missing.length - 1) await new Promise(r => setTimeout(r, 4000)); // 4s entre requêtes
  }
  batchBtn.textContent = '✅ Terminé';
  setTimeout(() => {
    batchBtn.disabled = false;
    batchBtn.textContent = '⬇ Télécharger PP manquantes';
  }, 3000);
}

// ── Equipment page ────────────────────────────────────────────────────────
let _eqRidersLoaded = false;
let _eqRiders       = [];
let _eqGender       = 'all';
let _eqSelectedItem = null;
let _eqSelectedPhotoPath = '';
let _eqItemsData    = [];
let _lastEqCard     = null;
let _eqMode         = 'rider';  // 'rider' | 'free'

async function rescanEqPhotos(silent = false) {
  try {
    const d = await fetch('/api/rescan-eq-photos', { method: 'POST' }).then(r => r.json());
    _app.eqVariants      = d.eq_variants      || [];
    _app.categoryFolders = d.category_folders || {};
    _app.varCache        = {};  // vide le cache de variants par item
    if (!silent) console.log(`📸 Rescan photos : ${d.count} fichiers trouvés`);
  } catch(e) { console.warn('rescanEqPhotos error', e); }
}

async function initEqPage() {
  _eqRiders = riders;
  _eqRidersLoaded = true;
  renderEqRiderList();
  renderEqFreeCategoryOptions();
  fetch('/api/reload-equipment', { method: 'POST' });
  rescanEqPhotos(true);   // rescan photos au premier chargement
}

async function loadEqAudit() {
  const ph  = document.getElementById('eq-audit-placeholder');
  const tbl = document.getElementById('eq-audit-table');
  ph.textContent = '⏳ Analyse en cours…';
  ph.style.display = 'block';
  tbl.style.display = 'none';
  try {
    const d = await fetch('/api/equipment-audit').then(r => r.json());
    const cols = d.columns;
    const rows = d.rows;

    // Abréviations colonnes
    const abbr = { 'Rear Shock':'RShock','Handlebar':'Hbar','Dropper Post':'Dropper',
                   'Brake Lever':'BLever','Brake Caliper':'BCalip' };

    // En-tête
    let html = '<thead><tr><th>Rider</th>';
    cols.forEach(c => { html += `<th title="${c}">${abbr[c] || c}</th>`; });
    html += '</tr></thead><tbody>';

    let totOk = 0, totNp = 0, totEmpty = 0;

    // Calcul du statut global par rider → dot dans la liste
    _eqAuditBySlug = {};
    rows.forEach(r => {
      const slug = _app.profiles.find(p =>
        p.prenom === r.prenom && p.nom === r.nom)?.slug || '';
      const vals = Object.values(r.cats);
      const hasData  = vals.some(v => v !== 'empty');
      const allOk    = vals.filter(v => v !== 'empty').every(v => v === 'ok');
      if (!hasData)       _eqAuditBySlug[slug] = 'empty';
      else if (allOk)     _eqAuditBySlug[slug] = 'ok';
      else                _eqAuditBySlug[slug] = 'partial';
    });
    renderEqRiderList();  // re-render avec les dots

    rows.forEach(r => {
      const name = `${r.genre === 'F' ? '♀' : '♂'} ${r.prenom} ${r.nom}`;
      html += `<tr><td>${name}</td>`;
      cols.forEach(c => {
        const st = r.cats[c];
        if (st === 'ok')            { html += '<td class="audit-ok">🟢</td>';      totOk++;    }
        else if (st === 'no_photo') { html += '<td class="audit-nophoto">🟡</td>'; totNp++;    }
        else                        { html += '<td class="audit-empty">·</td>';     totEmpty++; }
      });
      html += '</tr>';
    });

    const total = totOk + totNp + totEmpty;
    html += `<tr style="border-top:2px solid #333">
      <td style="color:#888;font-size:10px">TOTAL</td>`;
    cols.forEach(c => {
      const colOk = rows.filter(r => r.cats[c] === 'ok').length;
      const colNp = rows.filter(r => r.cats[c] === 'no_photo').length;
      const pct   = Math.round(colOk / rows.length * 100);
      html += `<td style="font-size:9px;color:${pct===100?'#4CAF50':pct>50?'#C8D400':'#f90'}">${pct}%</td>`;
    });
    html += '</tr></tbody>';

    tbl.innerHTML = html;
    tbl.style.display = 'table';
    ph.textContent = `✅ ${rows.length} riders · 🟢 ${totOk} · 🟡 ${totNp} · ⬜ ${totEmpty}`;
    ph.style.color = '#888';
  } catch(e) {
    ph.textContent = '❌ Erreur : ' + e.message;
    ph.style.color = '#e55';
  }
}

async function reloadEqData() {
  const btn = event?.currentTarget || null;
  const orig = btn?.textContent;
  if (btn) { btn.textContent = '⏳'; btn.disabled = true; }
  await fetch('/api/reload-equipment', { method: 'POST' });
  try {
    const data = await fetch('/api/preload').then(r => r.json());
    _app.profiles        = data.profiles         || _app.profiles;
    _app.equipment       = data.equipment        || {};
    _app.eqVariants      = data.eq_variants      || _app.eqVariants;
    _app.categoryFolders = data.category_folders || _app.categoryFolders;
    _app.varCache        = {};
    riders = _app.profiles.map(p => ({
      slug: p.slug, prenom: p.prenom, nom: p.nom, genre: p.genre,
      has_photo: p.has_photo, instagram: p.instagram,
    }));
    _eqRiders = riders;
    renderEqRiderList();
    renderEqFreeCategoryOptions();
  } catch(e) {
    console.warn('reloadEqData preload error', e);
  }
  if (btn) { btn.textContent = orig || '↺ Actualiser le Sheet'; btn.disabled = false; }
  if (_eqMode === 'free') renderEqFreeList(false);
  else if (_eqSelectedSlug) onEqRiderChange(_eqSelectedSlug);
}

function _eqResetGeneratedState(message = 'Sélectionne un équipement') {
  _eqSelectedItem = null;
  _eqSelectedPhotoPath = '';
  _lastEqCard = null;
  _lastPublishSource = null;
  const dl = document.getElementById('eq-page-dl-btn');
  const lib = document.getElementById('eq-add-library-btn');
  const ph = document.getElementById('eq-placeholder');
  const img = document.getElementById('eq-preview-img');
  const variants = document.getElementById('eq-color-variants');
  if (dl) dl.disabled = true;
  if (lib) lib.disabled = true;
  if (ph) { ph.style.display = 'block'; ph.innerHTML = `<span>🔧</span>${message}`; }
  if (img) img.style.display = 'none';
  if (variants) variants.style.display = 'none';
  document.getElementById('eq-preview-area')?.classList.remove('loading');
}

function _eqAllSheetItems() {
  const rows = [];
  Object.entries(_app.equipment || {}).forEach(([handle, items]) => {
    (items || []).forEach(it => {
      if (!it?.category) return;
      if (!(it.brand || it.reference || it.details)) return;
      rows.push({
        category: it.category || '',
        brand: it.brand || '',
        reference: it.reference || '',
        details: it.details || '',
        raw: it.raw || '',
        rider_handle: handle || '',
      });
    });
  });
  return rows;
}

function _eqFreeCategories() {
  return Array.from(new Set(_eqAllSheetItems().map(it => it.category).filter(Boolean)))
    .sort((a, b) => {
      const pa = _qualityPriority(a);
      const pb = _qualityPriority(b);
      if (pa !== pb) return pa - pb;
      return a.localeCompare(b);
    });
}

function _eqFreeItemsForCategory(category) {
  const map = new Map();
  _eqAllSheetItems()
    .filter(it => it.category === category)
    .forEach(it => {
      const key = [it.category, it.brand, it.reference, it.details].map(v => String(v || '').trim()).join('|');
      if (!map.has(key)) {
        map.set(key, { ...it, count: 0, riders: [] });
      }
      const entry = map.get(key);
      entry.count += 1;
      if (it.rider_handle) entry.riders.push(it.rider_handle);
    });
  return Array.from(map.values()).sort((a, b) => {
    const sa = _equipmentPhotoScore(a, { name: `${a.brand}${a.reference}` });
    const sb = _equipmentPhotoScore(b, { name: `${b.brand}${b.reference}` });
    if (sa !== sb) return sa - sb;
    return `${a.brand} ${a.reference}`.localeCompare(`${b.brand} ${b.reference}`);
  });
}

function renderEqFreeCategoryOptions() {
  const sel = document.getElementById('eq-free-category');
  if (!sel) return;
  const prev = sel.value;
  const cats = _eqFreeCategories();
  sel.innerHTML = cats.length
    ? cats.map(c => `<option value="${c}">${c}</option>`).join('')
    : '<option value="">Aucune catégorie</option>';
  if (prev && cats.includes(prev)) sel.value = prev;
  else if (cats.length) sel.value = cats[0];
}

function renderEqFreeList(resetSelection = false) {
  const list = document.getElementById('eq-page-list');
  const category = document.getElementById('eq-free-category')?.value || '';
  const query = (document.getElementById('eq-free-search')?.value || '').trim().toLowerCase();
  const note = document.getElementById('eq-free-note');
  if (!list) return;
  if (resetSelection) _eqResetGeneratedState('Choisis un équipement libre');
  if (!category) {
    _eqItemsData = [];
    list.innerHTML = '<div class="eq-empty">Aucune catégorie disponible dans le Sheet</div>';
    if (note) note.textContent = 'Aucun équipement exploitable trouvé dans le Google Sheet.';
    return;
  }
  const items = _eqFreeItemsForCategory(category).filter(it => {
    if (!query) return true;
    return `${it.category} ${it.brand} ${it.reference} ${it.details}`.toLowerCase().includes(query);
  });
  _eqItemsData = items.map(it => ({ ...it, source: 'free' }));
  if (note) {
    const total = _eqFreeItemsForCategory(category).length;
    note.textContent = `${items.length}/${total} modèle${total > 1 ? 's' : ''} disponible${total > 1 ? 's' : ''} depuis le Google Sheet.`;
  }
  if (!items.length) {
    list.innerHTML = '<div class="eq-empty">Aucun équipement pour cette recherche</div>';
    return;
  }
  list.innerHTML = _eqItemsData.map((it, i) => {
    const hasDesc  = !!(it.brand && it.reference);
    const hasPhoto = _eqCheckPhoto(it);
    const hasLogo  = _eqCheckLogo(it.brand);
    const score    = (hasDesc ? 1 : 0) + (hasPhoto ? 1 : 0) + (hasLogo ? 1 : 0);
    const dotCls   = score === 3 ? 'eq-dot-ok' : score > 0 ? 'eq-dot-partial' : 'eq-dot-empty';
    const count    = it.count ? `<span style="margin-left:auto;font-size:9px;color:#777">${it.count}x</span>` : '';
    return `
    <div class="eq-item" id="eq-page-item-${i}" onclick="selectEqItem(${i})" style="display:flex;align-items:center;gap:5px">
      <span class="eq-rider-dot ${dotCls}" style="flex-shrink:0"></span>
      <span class="eq-cat" style="flex-shrink:0">${it.category}</span>
      <span class="eq-brand" style="flex-shrink:0">${it.brand || '—'}</span>
      <span class="eq-ref" style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis">${it.reference || ''}</span>
      ${count}
    </div>`;
  }).join('');
}

function setEqMode(mode) {
  _eqMode = mode === 'free' ? 'free' : 'rider';
  document.getElementById('eq-mode-rider')?.classList.toggle('active', _eqMode === 'rider');
  document.getElementById('eq-mode-free')?.classList.toggle('active', _eqMode === 'free');
  const riderControls = document.getElementById('eq-rider-controls');
  const freeControls = document.getElementById('eq-free-controls');
  if (riderControls) riderControls.style.display = _eqMode === 'rider' ? 'block' : 'none';
  if (freeControls) freeControls.style.display = _eqMode === 'free' ? 'flex' : 'none';
  const badgeToggle = document.getElementById('eq_rider_selection');
  if (badgeToggle) {
    badgeToggle.disabled = _eqMode === 'free';
    if (_eqMode === 'free') badgeToggle.checked = false;
  }
  toggleEqRiderSelectionControls();

  _eqSelectedRider = null;
  _eqSelectedSlug = _eqMode === 'rider' ? _eqSelectedSlug : '';
  document.querySelectorAll('#eq-rider-select .eq-rider-item').forEach(el => el.classList.remove('active'));
  _eqResetGeneratedState(_eqMode === 'free' ? 'Choisis une catégorie puis un équipement' : 'Sélectionne un rider');

  if (_eqMode === 'free') {
    renderEqFreeCategoryOptions();
    renderEqFreeList(true);
    smoothCollapseAndScroll('eqcol-rider', 'eqcol-items');
  } else if (_eqSelectedSlug) {
    onEqRiderChange(_eqSelectedSlug);
  } else {
    const list = document.getElementById('eq-page-list');
    if (list) list.innerHTML = '<div class="eq-empty">Sélectionne un rider</div>';
  }
}

function setEqGender(g) {
  _eqGender = (_eqGender === g) ? 'all' : g;
  document.getElementById('eq-btn-f').className = 'gender-btn' + (_eqGender === 'F' ? ' active-f' : '');
  document.getElementById('eq-btn-m').className = 'gender-btn' + (_eqGender === 'M' ? ' active-m' : '');
  renderEqRiderList();
}

let _eqSelectedSlug = '';
let _eqAuditBySlug  = {};  // { slug: 'ok'|'partial'|'empty'|'loading' }

function _eqRiderDotClass(slug) {
  const st = _eqAuditBySlug[slug];
  if (!st || st === 'loading') return 'eq-dot-loading';
  if (st === 'ok')      return 'eq-dot-ok';
  if (st === 'partial') return 'eq-dot-partial';
  return 'eq-dot-empty';
}

function renderEqRiderList() {
  const query = (document.getElementById('eq-rider-search').value || '').trim().toLowerCase();
  const container = document.getElementById('eq-rider-select');
  const filtered = _eqRiders.filter(r => {
    if (_eqGender !== 'all' && r.genre !== _eqGender) return false;
    if (query && !`${r.prenom} ${r.nom}`.toLowerCase().includes(query)) return false;
    return true;
  });
  container.innerHTML = filtered.map(r => `
    <div class="eq-rider-item${r.slug === _eqSelectedSlug ? ' active' : ''}"
         data-slug="${r.slug}" onclick="onEqRiderClick('${r.slug}')">
      <span class="eq-rider-dot ${_eqRiderDotClass(r.slug)}"></span>
      <span>${r.genre === 'F' ? '♀' : '♂'} ${r.prenom} ${r.nom}</span>
    </div>`).join('');
}

let _eqSelectedRider = null;  // profil complet du rider sélectionné (pour badge reel)

// ── Checks statut par item d'équipement ──────────────────────────────────────
function _eqCheckPhoto(it) {
  const norm = s => (s || '').toLowerCase().replace(/[\s\-_\/\.]/g, '');
  const catFolders = (_app.categoryFolders[it.category] || [it.category]).map(norm);
  return _app.eqVariants.some(f => {
    if (!catFolders.includes(norm(f.folder || ''))) return false;
    return _equipmentPhotoScore(it, f) < 7;
  });
}

function _eqCheckLogo(brand) {
  if (!brand) return false;
  return _qualityBrandHasLogo(brand);
}

function onEqRiderClick(slug) {
  _eqSelectedSlug = slug;
  // Met à jour l'item actif visuellement
  document.querySelectorAll('#eq-rider-select .eq-rider-item').forEach(el => {
    el.classList.toggle('active', el.dataset.slug === slug);
  });
  onEqRiderChange(slug);
}

function onEqRiderChange(slug) {
  if (!slug) slug = _eqSelectedSlug;
  if (!slug) return;

  // Lookup local
  const profile = _app.profiles.find(p => p.slug === slug);
  if (!profile) return;
  _eqSelectedRider = profile;
  const instagram = (profile.instagram || '').replace(/^@/, '').toLowerCase();
  if (!instagram) return;

  const items = _app.equipment[instagram] || [];

  _eqSelectedItem = null;
  _eqSelectedPhotoPath = '';
  document.getElementById('eq-page-dl-btn').disabled = true;
  document.getElementById('eq-placeholder').style.display = 'block';
  document.getElementById('eq-preview-img').style.display = 'none';
  document.getElementById('eq-preview-area').classList.remove('loading');

  const list = document.getElementById('eq-page-list');
  if (items.length === 0) {
    list.innerHTML = '<div class="eq-empty">Aucun équipement dans le Sheet pour ce rider</div>';
    return;
  }
  _eqItemsData = items;
  list.innerHTML = items.map((it, i) => {
    const hasDesc  = !!(it.brand && it.reference);
    const hasPhoto = _eqCheckPhoto(it);
    const hasLogo  = _eqCheckLogo(it.brand);
    const score    = (hasDesc ? 1 : 0) + (hasPhoto ? 1 : 0) + (hasLogo ? 1 : 0);
    const dotCls   = score === 3 ? 'eq-dot-ok' : score > 0 ? 'eq-dot-partial' : 'eq-dot-empty';
    const missing  = [!hasDesc&&'desc', !hasPhoto&&'photo', !hasLogo&&'logo'].filter(Boolean);
    const badge    = missing.length ? `<span style="margin-left:auto;font-size:9px;color:#f90;opacity:.8">${missing.join(' · ')}</span>` : '';
    return `
    <div class="eq-item" id="eq-page-item-${i}" onclick="selectEqItem(${i})" style="display:flex;align-items:center;gap:5px">
      <span class="eq-rider-dot ${dotCls}" style="flex-shrink:0"></span>
      <span class="eq-cat" style="flex-shrink:0">${it.category}</span>
      <span class="eq-brand" style="flex-shrink:0">${it.brand || '—'}</span>
      <span class="eq-ref" style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis">${it.reference || ''}</span>
      ${badge}
    </div>`;
  }).join('');

  // UX : rabat la section Rider et scroll vers la liste d'équipements
  smoothCollapseAndScroll('eqcol-rider', 'eqcol-items');
}

function selectEqItem(idx) {
  document.querySelectorAll('#eq-page-list .eq-item').forEach((el, i) =>
    el.classList.toggle('selected', i === idx));
  const it = _eqItemsData[idx];
  if (!it) return;
  _eqSelectedItem = it;
  _eqSelectedPhotoPath = '';
  // Pré-remplir les champs texte avec les données du Sheet
  const el = (id) => document.getElementById(id);
  if (el('eq_brand_text'))     el('eq_brand_text').value     = it.brand     || '';
  if (el('eq_reference_text')) el('eq_reference_text').value = it.reference || '';
  if (el('eq_details_text'))   el('eq_details_text').value   = it.details   || '';
  // Charger les variantes couleur
  loadColorVariants(it);

  // UX : scroll vers les variantes (sans rabattre la section qui les contient)
  setTimeout(() => {
    const target = document.getElementById('eq-color-variants');
    if (!target || target.style.display === 'none') {
      // Pas de variantes → scroll vers les contrôles texte
      const fallback = document.getElementById('eqcol-textctrl');
      if (fallback) {
        const panel = fallback.closest('.panel');
        if (panel) {
          const panelTop  = panel.getBoundingClientRect().top;
          const targetTop = fallback.getBoundingClientRect().top;
          panel.scrollTo({ top: panel.scrollTop + (targetTop - panelTop) - 10, behavior: 'smooth' });
        }
      }
      return;
    }
    const panel = target.closest('.panel');
    if (panel) {
      const panelTop  = panel.getBoundingClientRect().top;
      const targetTop = target.getBoundingClientRect().top;
      panel.scrollTo({ top: panel.scrollTop + (targetTop - panelTop) - 10, behavior: 'smooth' });
    }
  }, 80);
}

function loadColorVariants(it) {
  if (!it) return;
  const varBox   = document.getElementById('eq-color-variants');
  const swatches = document.getElementById('eq-color-swatches');
  varBox.style.display = 'none';
  swatches.innerHTML = '';
  _eqSelectedPhotoPath = '';
  varBox.querySelectorAll('.eq-variant-warning').forEach(el => el.remove());

  // Lookup local — dossier catégorie d'abord, puis score de pertinence
  const forceCategory = document.getElementById('eq_force_category_variants')?.checked || false;
  const cacheKey = `${it.brand||''}|${it.reference||''}|${it.category||''}|${forceCategory ? 'manual' : 'strict'}`;
  let variants = _app.varCache[cacheKey];
  const norm = s => (s||'').toLowerCase().replace(/[\s\-\_\/\.]/g, '');
  // Dossiers valides pour cette catégorie
  const catFolders = (_app.categoryFolders[it.category] || [it.category])
    .map(f => norm(f));

  // 1. Filtrer par dossier catégorie
  const inFolder = _app.eqVariants.filter(f => {
    if (!f.folder) return false;
    return catFolders.includes(norm(f.folder));
  });

  if (!variants) {
    const score = f => _equipmentPhotoScore(it, f);

    if (forceCategory) {
      variants = [...inFolder].sort((a, b) => {
        const sa = score(a);
        const sb = score(b);
        if (sa !== sb) return sa - sb;
        return String(a.name || '').localeCompare(String(b.name || ''));
      });
      variants._manualCategory = true;
    } else if (inFolder.length === 0) {
      // Fallback : racine Equipment/ si aucun dossier matche
      variants = _app.eqVariants.filter(f => !f.folder && score(f) < 7);
    } else {
      const matched = inFolder.filter(f => score(f) < 7).sort((a, b) => score(a) - score(b));
      if (matched.length > 0) {
        variants = matched;
      } else {
        // Rider sélectionné : ne jamais afficher toute la catégorie si le modèle ne matche pas.
        variants = [];
        variants._noMatch = true;
      }
    }
    _app.varCache[cacheKey] = variants;
  }

  if (variants.length > 0) {
    varBox.style.display = 'block';
    if (variants._manualCategory) {
      swatches.insertAdjacentHTML('beforebegin',
        `<div class="eq-variant-warning" style="color:#C8D400;font-size:11px;margin-bottom:6px">
          Choix manuel actif : toutes les photos disponibles dans « ${it.category||'cette catégorie'} » sont affichées.
        </div>`);
    }
    if (variants._noMatch) {
      swatches.insertAdjacentHTML('beforebegin',
        `<div class="eq-variant-warning" style="color:#f90;font-size:11px;margin-bottom:6px">
          ⚠️ Aucune photo trouvée pour « ${it.brand||''} ${it.reference||''} » — toutes les variantes affichées
        </div>`);
    }
    variants.forEach((v, i) => {
      const wrap = document.createElement('div');
      wrap.style.cssText = 'display:flex;flex-direction:column;align-items:center;gap:2px';
      const sw = document.createElement('div');
      sw.className = 'eq-swatch' + (i === 0 ? ' active' : '');
      sw.title = v.name;
      sw.innerHTML = `<img src="${v.url}" loading="lazy">`;
      sw.onclick = () => {
        document.querySelectorAll('.eq-swatch').forEach(s => s.classList.remove('active'));
        sw.classList.add('active');
        _eqSelectedPhotoPath = v.path;
        eqDebouncedGenerate(100);
      };
      const lbl = document.createElement('div');
      lbl.className = 'eq-swatch-label';
      const base = ((it.brand||'') + (it.reference||'')).replace(/\s/g,'');
      lbl.textContent = v.name.replace(new RegExp('^'+base, 'i'), '') || v.name;
      wrap.appendChild(sw); wrap.appendChild(lbl);
      swatches.appendChild(wrap);
      if (i === 0) _eqSelectedPhotoPath = v.path;
    });
  } else if (variants._noMatch || (it.brand || it.reference)) {
    varBox.style.display = 'block';
    swatches.insertAdjacentHTML('beforebegin',
      `<div class="eq-variant-warning" style="color:#f90;font-size:11px;margin-bottom:6px">
        ⚠️ Aucune photo exacte trouvée pour « ${it.brand||''} ${it.reference||''} ». La carte utilisera le logo de marque si disponible.
      </div>`);
  }
}

// Debounce live preview
let _eqDebTimer = null;
function toggleEqLogoControls() {
  const show = document.getElementById('eq_show_logo')?.checked;
  const ctrl = document.getElementById('eq-logo-controls');
  if (ctrl) ctrl.style.display = show ? 'block' : 'none';
}

function toggleEqRiderSelectionControls() {
  const show = document.getElementById('eq_rider_selection')?.checked;
  const ctrl = document.getElementById('eq-rider-selection-controls');
  if (ctrl) ctrl.style.display = show ? 'block' : 'none';
}

function eqDebouncedGenerate(delay = 500) {
  clearTimeout(_eqDebTimer);
  _eqDebTimer = setTimeout(() => generateEqCard(true), delay);
}

function setEqBg(hex) {
  const picker = document.getElementById('eq_photo_bg');
  if (picker) picker.value = hex;
  // Mettre à jour le highlight des presets
  document.querySelectorAll('.eq-bg-preset').forEach(btn => {
    btn.style.borderColor = btn.dataset.color === hex ? '#C8D400' : '#444';
  });
  eqDebouncedGenerate(100);
}

function _hexToRgb(hex) {
  const r = parseInt(hex.slice(1,3),16);
  const g = parseInt(hex.slice(3,5),16);
  const b = parseInt(hex.slice(5,7),16);
  return [r, g, b];
}

async function generateEqCard(silent = false) {
  if (!_eqSelectedItem) {
    if (!silent) { document.getElementById('eq-error-msg').textContent = '❌ Sélectionne un équipement'; document.getElementById('eq-error-msg').style.display = 'block'; }
    return;
  }
  document.getElementById('eq-error-msg').style.display = 'none';
  const area = document.getElementById('eq-preview-area');
  area.classList.add('loading');

  const it      = _eqSelectedItem;
  const zoom    = parseInt(document.getElementById('eq_zoom')?.value    || 100);
  const photo_x = parseInt(document.getElementById('eq_photo_x')?.value || 0);
  const photo_y = parseInt(document.getElementById('eq_photo_y')?.value || 0);

  const g = (id) => document.getElementById(id);
  const show_brand     = g('eq_show_brand')?.checked     ?? true;
  const show_reference = g('eq_show_reference')?.checked ?? true;
  const show_details   = g('eq_show_details')?.checked   ?? true;
  const show_logo      = g('eq_show_logo')?.checked      ?? false;
  const rider_selection = g('eq_rider_selection')?.checked ?? false;
  const use_v2         = false;
  const brand_text     = g('eq_brand_text')?.value     || it.brand     || '';
  const reference_text = g('eq_reference_text')?.value || it.reference || '';
  const details_text   = g('eq_details_text')?.value   || it.details   || '';
  const photo_bg       = _hexToRgb(g('eq_photo_bg')?.value || '#ffffff');
  const rider_instagram = (_eqSelectedRider?.instagram || '').replace(/^@/, '');

  try {
    const res = await fetch('/api/generate-eq-card', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        category: it.category,
        brand: brand_text, reference: reference_text, details: details_text,
        photo_path: _eqSelectedPhotoPath || '',
        zoom, photo_x, photo_y,
        text_x: 0, text_y: 0,
        show_brand, show_reference, show_details, show_logo,
        logo_h: parseInt(g('eq_logo_h')?.value || 60),
        logo_y: parseInt(g('eq_logo_y')?.value || 1200),
        logo_x: parseInt(g('eq_logo_x')?.value || -1),
        show_rider_badge: rider_selection,
        rider_instagram,
        badge_radius: parseInt(g('eq_badge_radius')?.value || 58),
        photo_bg, use_v2,
      }),
    });
    if (!res.ok) { const e = await res.json(); throw new Error(e.error); }
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const name = `${it.brand}_${it.reference || it.category}`.replace(/\s+/g,'_') + '.png';
    _lastEqCard = { url, name, is_selection: rider_selection, rider_instagram };
    _lastPublishSource = {
      kind: 'equipment',
      url,
      name,
      mime: 'image/png',
    };
    const img = document.getElementById('eq-preview-img');
    img.onload = () => area.classList.remove('loading');
    img.src = url; img.style.display = 'block';
    document.getElementById('eq-placeholder').style.display = 'none';
    document.getElementById('eq-page-dl-btn').disabled = false;
    document.getElementById('eq-add-library-btn').disabled = false;
  } catch(e) {
    area.classList.remove('loading');
    if (!silent) { document.getElementById('eq-error-msg').textContent = '❌ ' + e.message; document.getElementById('eq-error-msg').style.display = 'block'; }
  }
}

function downloadEqCard() {
  if (!_lastEqCard) return;
  const a = document.createElement('a');
  a.href = _lastEqCard.url; a.download = _lastEqCard.name; a.click();
}

// ── Rider card → Reel ─────────────────────────────────────────────────────────
function addRiderCardToReel() {
  if (!_lastRiderCardUrl || !lastSlug) return;
  const sel = document.getElementById('rider');
  const label = sel.options[sel.selectedIndex]?.text?.trim() || lastSlug;
  const id = ++_reelIdSeq;
  _reelItems.push({
    id,
    label:           label,
    sub:             'Rider card',
    preview_url:     _lastRiderCardUrl,
    photo_path:      '',           // pas de photo produit — carte déjà générée
    rider_instagram: '',
    is_selection:    false,
    card_params:     null,         // null = carte rider pré-rendue (pas régénérée)
    prerendered_url: _lastRiderCardUrl,
    type:            'rider',
  });
  _updateReelBadge();
  const btn = document.getElementById('cards-add-reel-btn');
  if (btn) {
    btn.textContent = '✓ Ajouté';
    btn.style.background = '#C8D400'; btn.style.color = '#000';
    setTimeout(() => { btn.textContent = '＋ Reel'; btn.style.background=''; btn.style.color=''; }, 1200);
  }
}

function addRiderCardToPublish() {
  publishAddCurrent('rider');
  const btn = document.getElementById('cards-add-publish-btn');
  if (!btn) return;
  btn.textContent = '✓ Ajouté';
  btn.style.background = '#C8D400'; btn.style.color = '#000';
  setTimeout(() => { btn.textContent = '＋ Publish'; btn.style.background=''; btn.style.color=''; }, 1200);
}

// ── Reel ──────────────────────────────────────────────────────────────────────
let _reelItems  = [];    // [{id, label, preview_url, photo_path, card_params, is_selection, rider_instagram}]
let _reelIdSeq  = 0;
let _lastEqReel = null;

function applyReelTemplate(template) {
  const g = (id) => document.getElementById(id);
  const settings = {
    equipment_showcase: { dur: 2.6, cf: 0.35, format: 'reel', badge: true, title: 'Equipment showcase' },
    rider_setup:       { dur: 2.8, cf: 0.45, format: 'reel', badge: true, title: 'Rider setup' },
    top3_performance:  { dur: 2.2, cf: 0.3,  format: 'reel', badge: false, title: 'Top 3 Performance' },
    race_recap:        { dur: 2.4, cf: 0.4,  format: 'reel', badge: true, title: 'Race recap' },
    brand_focus:       { dur: 2.5, cf: 0.35, format: 'square', badge: false, title: 'Brand focus' },
  }[template] || {};
  if (g('reel_dur_per_card')) { g('reel_dur_per_card').value = settings.dur || 3; updateSlider(g('reel_dur_per_card'), 'reel_val_dur'); }
  if (g('reel_crossfade')) { g('reel_crossfade').value = settings.cf || 0.5; updateSlider(g('reel_crossfade'), 'reel_val_cf'); }
  if (g('reel_format')) g('reel_format').value = settings.format || 'reel';
  if (g('reel_show_badge')) g('reel_show_badge').checked = settings.badge ?? true;
  if (g('reel_title') && !g('reel_title').value.trim()) g('reel_title').value = settings.title || '';
}

function _reelTitleCanvas(title, subtitle = '', mode = 'intro') {
  const canvas = document.createElement('canvas');
  canvas.width = 1080;
  canvas.height = 1350;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#101010';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = '#C8D400';
  ctx.fillRect(0, 0, canvas.width, 16);
  ctx.fillRect(0, canvas.height - 16, canvas.width, 16);
  ctx.textAlign = 'center';
  ctx.fillStyle = '#C8D400';
  ctx.font = '700 52px system-ui, sans-serif';
  ctx.fillText('FREERIDE FANATICS', canvas.width / 2, 210);
  ctx.fillStyle = '#f4f4f4';
  ctx.font = '900 92px system-ui, sans-serif';
  const words = String(title || (mode === 'outro' ? 'Full setup ready' : 'Reel')).split(/\s+/);
  const lines = [];
  let line = '';
  words.forEach(word => {
    const test = line ? `${line} ${word}` : word;
    if (ctx.measureText(test).width > 860 && line) {
      lines.push(line);
      line = word;
    } else {
      line = test;
    }
  });
  if (line) lines.push(line);
  const startY = 560 - (lines.length - 1) * 58;
  lines.slice(0, 4).forEach((l, i) => ctx.fillText(l.toUpperCase(), canvas.width / 2, startY + i * 108));
  ctx.fillStyle = '#8d8d8d';
  ctx.font = '600 38px system-ui, sans-serif';
  ctx.fillText(subtitle || (mode === 'outro' ? 'Generated for Instagram' : 'Equipment edit'), canvas.width / 2, 980);
  ctx.fillStyle = '#C8D400';
  ctx.font = '800 32px system-ui, sans-serif';
  ctx.fillText(mode === 'outro' ? '@freeridefanatics' : '2026 SEASON', canvas.width / 2, 1105);
  return canvas.toDataURL('image/png');
}

function addReelTitleCard(mode = 'intro', title = '', subtitle = '') {
  const typedTitle = document.getElementById('reel_title')?.value.trim();
  const url = _reelTitleCanvas(title || typedTitle || (mode === 'outro' ? 'Follow for more' : 'Freeride Fanatics'), subtitle, mode);
  _reelItems.push({
    id: ++_reelIdSeq,
    label: mode === 'outro' ? 'Outro' : 'Intro',
    sub: title || typedTitle || 'Title card',
    preview_url: url,
    photo_path: '',
    rider_instagram: '',
    is_selection: false,
    card_params: null,
    prerendered_url: url,
    type: 'title',
  });
  _updateReelBadge();
  renderReelPage();
}

function initReelPerformanceControls() {
  const sel = document.getElementById('reel_perf_category');
  if (!sel) return;
  const previous = sel.value;
  const cats = _perfCategories();
  sel.innerHTML = cats.map(cat => `<option value="${_esc(cat)}">${_esc(cat)}</option>`).join('');
  if (previous && cats.includes(previous)) sel.value = previous;
  else if (cats.includes('Fork')) sel.value = 'Fork';
}

function _reelLoadImage(src) {
  return new Promise((resolve) => {
    if (!src) return resolve(null);
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null);
    img.src = src;
  });
}

function _reelDrawCover(ctx, img, x, y, w, h) {
  const scale = Math.min(w / img.width, h / img.height);
  const iw = img.width * scale;
  const ih = img.height * scale;
  ctx.drawImage(img, x + (w - iw) / 2, y + (h - ih) / 2, iw, ih);
}

function _reelWrapText(ctx, text, x, y, maxWidth, lineHeight, maxLines = 3) {
  const words = String(text || '').split(/\s+/).filter(Boolean);
  const lines = [];
  let line = '';
  words.forEach(word => {
    const test = line ? `${line} ${word}` : word;
    if (ctx.measureText(test).width > maxWidth && line) {
      lines.push(line);
      line = word;
    } else {
      line = test;
    }
  });
  if (line) lines.push(line);
  lines.slice(0, maxLines).forEach((l, i) => ctx.fillText(l, x, y + i * lineHeight));
  return Math.min(lines.length, maxLines) * lineHeight;
}

function _reelFindEquipmentPhoto(item) {
  const norm = s => (s || '').toLowerCase().replace(/[\s\-_\/\.]/g, '');
  const catFolders = (_app.categoryFolders[item.category] || [item.category]).map(norm);
  const inFolder = _app.eqVariants.filter(f => f.folder && catFolders.includes(norm(f.folder)));
  const candidates = inFolder.length ? inFolder : _app.eqVariants.filter(f => !f.folder);
  return candidates
    .map(f => ({ ...f, score: _equipmentPhotoScore(item, f) }))
    .filter(f => f.score < 7)
    .sort((a, b) => a.score - b.score)[0] || null;
}

async function _reelPerformanceCardCanvas(stat, idx, gender, category) {
  const canvas = document.createElement('canvas');
  canvas.width = 1080;
  canvas.height = 1350;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#101010';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = '#C8D400';
  ctx.fillRect(0, 0, canvas.width, 14);
  ctx.fillRect(0, canvas.height - 14, canvas.width, 14);

  ctx.fillStyle = '#1b1b1b';
  ctx.fillRect(82, 130, 916, 620);
  const photo = _reelFindEquipmentPhoto(stat);
  const img = await _reelLoadImage(photo?.url || '');
  if (img) {
    ctx.fillStyle = '#f4f4f4';
    ctx.fillRect(112, 160, 856, 560);
    _reelDrawCover(ctx, img, 145, 185, 790, 510);
  } else {
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 3;
    ctx.strokeRect(112, 160, 856, 560);
    ctx.fillStyle = '#555';
    ctx.font = '800 42px system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('NO EQUIPMENT PHOTO', canvas.width / 2, 455);
  }

  ctx.textAlign = 'left';
  ctx.fillStyle = '#C8D400';
  ctx.font = '900 88px system-ui, sans-serif';
  ctx.fillText(`#${idx + 1}`, 90, 895);
  ctx.fillStyle = '#f5f5f5';
  ctx.font = '900 58px system-ui, sans-serif';
  _reelWrapText(ctx, stat.label, 230, 865, 760, 66, 3);

  ctx.fillStyle = '#9a9a9a';
  ctx.font = '700 30px system-ui, sans-serif';
  const genderLabel = gender === 'F' ? 'Women' : 'Men';
  ctx.fillText(`${genderLabel} · ${category} · ${stat.count} rider${stat.count > 1 ? 's' : ''}`, 90, 1045);

  ctx.fillStyle = '#C8D400';
  ctx.font = '900 54px system-ui, sans-serif';
  ctx.fillText(`${Math.round(stat.points)} pts`, 90, 1122);
  ctx.fillStyle = '#777';
  ctx.font = '700 27px system-ui, sans-serif';
  ctx.fillText(`Average rank ${stat.avgRank.toFixed(1)} · Best rank #${stat.bestRank}`, 90, 1172);

  const ridersText = stat.riders
    .slice().sort((a, b) => a.rank - b.rank)
    .slice(0, 3)
    .map(r => `#${r.rank} ${r.name}`)
    .join('   ');
  ctx.fillStyle = '#bdbdbd';
  ctx.font = '700 27px system-ui, sans-serif';
  _reelWrapText(ctx, ridersText, 90, 1232, 900, 34, 2);
  return canvas.toDataURL('image/png');
}

async function buildPerformanceTop3Reel() {
  initReelPerformanceControls();
  const category = document.getElementById('reel_perf_category')?.value || 'Fork';
  const gender = document.getElementById('reel_perf_gender')?.value || 'F';
  const { rows } = _perfStatsFor({ category, gender, topVal: '10', groupMode: 'product' });
  const top = _perfSortRowsBy(rows, 'points').slice(0, 3);
  if (!top.length) {
    _reelLog('❌ Aucun Top 3 Performance disponible pour ce genre et cet équipement.', true);
    return;
  }
  const label = `${gender === 'F' ? 'Women' : 'Men'} Top 3 ${category}`;
  document.getElementById('reel_title').value = label;
  _reelLog(`⚙ Construction du Top 3 ${category} ${gender === 'F' ? 'femmes' : 'hommes'}…`);
  addReelTitleCard('intro', label, 'Equipment performance ranking');
  for (const [idx, item] of top.entries()) {
    const url = await _reelPerformanceCardCanvas(item, idx, gender, category);
    _reelItems.push({
      id: ++_reelIdSeq,
      label: `#${idx + 1} ${item.label}`,
      sub: `${Math.round(item.points)} pts · ${item.count} rider${item.count > 1 ? 's' : ''}`,
      preview_url: url,
      photo_path: '',
      rider_instagram: '',
      is_selection: false,
      card_params: null,
      prerendered_url: url,
      type: 'performance',
    });
  }
  addReelTitleCard('outro', 'Full breakdown', 'Built from 2026 results');
  _reelLog(`✅ Top 3 Performance ajouté (${top.length} cartes visuelles).`);
}

function _updateReelBadge() {
  const badge = document.getElementById('reel-badge');
  if (!badge) return;
  const n = _reelItems.length;
  badge.textContent = n;
  badge.style.display = n > 0 ? 'inline' : 'none';
}

function addToReel() {
  if (!_lastEqCard || !_eqSelectedItem) return;
  const g   = (id) => document.getElementById(id);
  const it  = _eqSelectedItem;
  const id  = ++_reelIdSeq;
  const riderSelection = g('eq_rider_selection')?.checked ?? false;

  const item = {
    id,
    label:           `${it.category} · ${it.brand || ''} ${it.reference || ''}`.trim(),
    sub:             g('eq_brand_text')?.value || it.brand || '',
    preview_url:     _lastEqCard.url,
    photo_path:      _eqSelectedPhotoPath || '',
    rider_instagram: _eqSelectedRider?.instagram || '',
    is_selection:    riderSelection,
    card_params: {
      category:      it.category,
      brand:         g('eq_brand_text')?.value     || it.brand     || '',
      reference:     g('eq_reference_text')?.value || it.reference || '',
      details:       g('eq_details_text')?.value   || it.details   || '',
      zoom:          parseInt(g('eq_zoom')?.value    || 100),
      photo_x:       parseInt(g('eq_photo_x')?.value || 0),
      photo_y:       parseInt(g('eq_photo_y')?.value || 0),
      text_x: 0, text_y: 0,
      show_brand:     g('eq_show_brand')?.checked     ?? true,
      show_reference: g('eq_show_reference')?.checked ?? true,
      show_details:   g('eq_show_details')?.checked   ?? true,
      show_logo:      g('eq_show_logo')?.checked      ?? false,
      photo_bg:       _hexToRgb(g('eq_photo_bg')?.value || '#ffffff'),
      use_v2:         false,
      show_rider_badge: riderSelection,
      rider_instagram: (_eqSelectedRider?.instagram || '').replace(/^@/, ''),
      badge_radius:   parseInt(g('eq_badge_radius')?.value || 58),
    },
  };

  _reelItems.push(item);
  _updateReelBadge();

  // Flash du bouton
  const btn = document.getElementById('eq-add-reel-btn');
  if (btn) {
    btn.textContent = '✓ Ajouté';
    btn.style.background = '#C8D400'; btn.style.color = '#000';
    setTimeout(() => { btn.textContent = '＋ Reel'; btn.style.background=''; btn.style.color=''; }, 1200);
  }
}

function addEqCardToPublish() {
  publishAddCurrent('equipment');
  const btn = document.getElementById('eq-add-publish-btn');
  if (!btn) return;
  btn.textContent = '✓ Ajouté';
  btn.style.background = '#C8D400'; btn.style.color = '#000';
  setTimeout(() => { btn.textContent = '＋ Publish'; btn.style.background=''; btn.style.color=''; }, 1200);
}

function removeReelItem(id) {
  _reelItems = _reelItems.filter(it => it.id !== id);
  _updateReelBadge();
  renderReelPage();
}

function toggleReelSelection(id) {
  const already = _reelItems.find(it => it.id === id)?.is_selection;
  _reelItems.forEach(it => it.is_selection = false);
  if (!already) { const it = _reelItems.find(it => it.id === id); if (it) it.is_selection = true; }
  renderReelPage();
}

let _reelRiderListReady = false;
async function _initReelRiderList() {
  if (_reelRiderListReady) { filterReelRiders(); return; }
  // Lookup local — tout est déjà préchargé
  window._allRiders = _app.profiles.length ? _app.profiles : riders;
  _reelRiderListReady = true;
  filterReelRiders();
}

function filterReelRiders() {
  const q   = (document.getElementById('reel-rider-search').value || '').toLowerCase();
  const sel = document.getElementById('reel-rider-select');
  const cur = sel.value;
  sel.innerHTML = '<option value="">— Sans badge —</option>';
  (window._allRiders || []).filter(r =>
    !q || `${r.prenom} ${r.nom}`.toLowerCase().includes(q)
  ).forEach(r => {
    const opt = document.createElement('option');
    opt.value = (r.instagram || '').replace(/^@/, '');
    opt.textContent = `${r.genre === 'F' ? '♀' : '♂'} ${r.prenom} ${r.nom}`;
    sel.appendChild(opt);
  });
  if (cur) sel.value = cur;
}

function renderReelPage() {
  const list = document.getElementById('reel-item-list');
  const grid = document.getElementById('reel-preview-grid');
  if (!list) return;
  renderReelLibrary();

  if (_reelItems.length === 0) {
    list.innerHTML = '<div class="reel-empty">Aucune carte ajoutée.<br>Ajoute une carte depuis la Library ci-dessus.</div>';
    if (grid) grid.innerHTML = '';
    return;
  }

  list.innerHTML = _reelItems.map(it => `
    <div class="reel-item ${it.is_selection ? 'is-selection' : ''}"
         draggable="true" data-id="${it.id}">
      <img class="reel-thumb" src="${it.preview_url}" alt="">
      <div class="reel-info">
        <div class="reel-label">${it.label}</div>
        <div class="reel-sub">${it.type === 'title' ? 'Title card' : it.type === 'performance' ? 'Performance card' : it.type === 'library' ? 'Library card' : it.rider_instagram ? '@' + it.rider_instagram.replace(/^@/,'') : '—'}</div>
      </div>
      <span class="reel-star ${it.is_selection ? 'active' : ''}"
            onclick="toggleReelSelection(${it.id})" title="Rider's Selection">★</span>
      <span class="reel-remove" onclick="removeReelItem(${it.id})" title="Retirer">✕</span>
    </div>
  `).join('');

  // Drag-and-drop reorder
  let _dragId = null;
  list.querySelectorAll('.reel-item').forEach(el => {
    el.addEventListener('dragstart', e => {
      _dragId = parseInt(el.dataset.id);
      el.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
    });
    el.addEventListener('dragend', () => el.classList.remove('dragging'));
    el.addEventListener('dragover', e => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      list.querySelectorAll('.reel-item').forEach(x => x.classList.remove('drag-over'));
      el.classList.add('drag-over');
    });
    el.addEventListener('dragleave', () => el.classList.remove('drag-over'));
    el.addEventListener('drop', e => {
      e.preventDefault();
      el.classList.remove('drag-over');
      const targetId = parseInt(el.dataset.id);
      if (_dragId === targetId) return;
      const fromIdx = _reelItems.findIndex(x => x.id === _dragId);
      const toIdx   = _reelItems.findIndex(x => x.id === targetId);
      if (fromIdx < 0 || toIdx < 0) return;
      const [moved] = _reelItems.splice(fromIdx, 1);
      _reelItems.splice(toIdx, 0, moved);
      renderReelPage();
    });
  });

  if (grid) {
    grid.innerHTML = _reelItems.map(it => `
      <div style="text-align:center">
        <img src="${it.preview_url}" style="height:220px;border-radius:8px;
          border:2px solid ${it.is_selection ? '#C8D400' : '#2a2a2a'}" alt="">
        <div style="font-size:0.68rem;color:#888;margin-top:4px">${it.label}</div>
        ${it.is_selection ? '<div style="font-size:0.6rem;color:#C8D400">★ Rider\'s Selection</div>' : ''}
      </div>
    `).join('');
  }
}

function _reelLibraryItems() {
  return (_libraryItems || []).filter(item => item.kind !== 'reel' && String(item.mime || '').startsWith('image'));
}

function renderReelLibrary() {
  const box = document.getElementById('reel-library-list');
  if (!box) return;
  const items = _reelLibraryItems().slice(0, 8);
  if (!items.length) {
    box.innerHTML = '<div class="reel-empty" style="grid-column:1/-1;padding:14px 0">Aucune carte dans la Library.<br>Génère une carte puis clique <b>＋ Library</b>.</div>';
    return;
  }
  box.innerHTML = items.map(item => `
    <div class="reel-library-card">
      <div class="reel-library-thumb" id="reel-lib-thumb-${item.id}">Chargement…</div>
      <div class="reel-library-body">
        <div class="reel-library-label">${_esc(item.label || item.name || item.kind)}</div>
        <div class="reel-library-meta">${_esc(item.kind)} · ${_esc(item.name || '')}</div>
        <button class="btn btn-secondary reel-library-add" onclick="libraryAddToReel('${item.id}')">＋ Ajouter</button>
      </div>
    </div>
  `).join('');
  items.forEach(item => _renderReelLibraryThumb(item));
}

async function _renderReelLibraryThumb(item) {
  const box = document.getElementById(`reel-lib-thumb-${item.id}`);
  if (!box) return;
  const url = await _libraryUrl(item.id);
  if (!url) {
    box.textContent = 'Média indisponible';
    return;
  }
  box.innerHTML = `<img src="${url}" alt="">`;
}

// Convertit un blob URL en base64 via canvas (fiable pour les grandes images)
async function _imgToBase64(blobUrl) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width  = img.naturalWidth;
      canvas.height = img.naturalHeight;
      canvas.getContext('2d').drawImage(img, 0, 0);
      resolve(canvas.toDataURL('image/png').split(',')[1]);
    };
    img.onerror = reject;
    img.src = blobUrl;
  });
}

function _fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || '').split(',')[1] || '');
    reader.onerror = () => reject(reader.error || new Error('Lecture du fichier impossible'));
    reader.readAsDataURL(file);
  });
}

function _reelLog(msg, isError = false) {
  const el = document.getElementById('reel-error-msg');
  if (!el) return;
  el.textContent = msg;
  el.style.display = msg ? 'block' : 'none';
  el.style.color = isError ? '#e55' : '#C8D400';
  console.log('[Reel]', msg);
}

async function generateEqReel() {
  const g = (id) => document.getElementById(id);
  _reelLog('');

  if (_reelItems.length === 0) {
    _reelLog('❌ Ajoute au moins une carte depuis la Library', true); return;
  }

  _reelLog(`⚙ Préparation de ${_reelItems.length} carte(s)…`);
  g('reel-gen-btn').disabled = true;
  g('reel-progress').style.display = 'block';
  g('reel-dl-btn').disabled = true;

  try {
    // Construire les items — rider cards envoyées en base64 via canvas
    _reelLog('⚙ Encodage des images…');
    const items_payload = [];
    for (const it of _reelItems) {
      let b64 = null;
      if ((it.type === 'rider' || it.type === 'title' || it.type === 'performance' || it.type === 'library') && it.preview_url) {
        try {
          b64 = await _imgToBase64(it.preview_url);
        } catch(e) {
          console.error('base64 failed for', it.label, e);
        }
      }
      items_payload.push({
        photo_path:      it.photo_path      || '',
        rider_instagram: it.rider_instagram || '',
        is_selection:    it.is_selection    || false,
        card_params:     it.card_params     || null,
        prerendered_b64: b64,
      });
    }

    const dur = parseFloat(g('reel_dur_per_card')?.value || 3);
    const cf  = parseFloat(g('reel_crossfade')?.value    || 0.5);
    const showBadge = g('reel_show_badge')?.checked ?? true;
    const exportFormat = g('reel_format')?.value || 'reel';
    const transitionSfx = g('reel_sfx_transition')?.value || '';
    const transitionSfxVolume = Math.max(0, Math.min(1.5, parseFloat(g('reel_sfx_volume')?.value || 0.8)));
    const audioFile = g('reel_audio_file')?.files?.[0] || null;
    const audioVolume = Math.max(0, Math.min(1.5, parseFloat(g('reel_audio_volume')?.value || 0.75)));
    let audioPayload = null;
    if (audioFile) {
      _reelLog('⚙ Encodage de l’audio…');
      audioPayload = {
        name: audioFile.name || 'audio',
        mime: audioFile.type || 'audio/mpeg',
        b64: await _fileToBase64(audioFile),
        volume: audioVolume,
      };
    }

    _reelLog(`⚙ Génération du MP4 (${items_payload.length} frames${audioPayload ? ' + audio' : ''})…`);
    const badgeRiderIg  = document.getElementById('reel-rider-select')?.value || '';
    const badgeRadius   = parseInt(g('reel_badge_radius')?.value || 58);
    const res = await fetch('/api/generate-eq-reel', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items: items_payload, dur_per_card: dur,
                             crossfade: cf, show_rider_badge: showBadge,
                             export_format: exportFormat,
                             badge_rider_ig: badgeRiderIg,
                             badge_radius: badgeRadius,
                             audio: audioPayload,
                             transition_sfx: transitionSfx,
                             transition_sfx_volume: transitionSfxVolume }),
    });

    if (!res.ok) {
      let errMsg = `HTTP ${res.status}`;
      try { errMsg = (await res.json()).error || errMsg; } catch {}
      throw new Error(errMsg);
    }

    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const name = `reel_${exportFormat}.mp4`;
    _lastEqReel = { url, name };
    _lastPublishSource = {
      kind: 'reel',
      url,
      name,
      mime: 'video/mp4',
    };
    g('reel-dl-btn').disabled = false;
    g('reel-add-library-btn').disabled = false;

    // Lecteur vidéo
    const vid = g('reel-video-player');
    if (vid) {
      vid.src = url;
      vid.style.display = 'block';
      vid.load();
      vid.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    _reelLog('✅ Reel prêt — clique Télécharger MP4');

  } catch(e) {
    _reelLog('❌ ' + e.message, true);
    console.error('[Reel error]', e);
  } finally {
    g('reel-gen-btn').disabled = false;
    g('reel-progress').style.display = 'none';
  }
}

function downloadEqReel() {
  if (!_lastEqReel) return;
  const a = document.createElement('a');
  a.href = _lastEqReel.url; a.download = _lastEqReel.name; a.click();
}

function addEqReelToPublish() {
  publishAddCurrent('reel');
  const btn = document.getElementById('reel-add-publish-btn');
  if (!btn) return;
  btn.textContent = '✓ Ajouté';
  btn.style.background = '#C8D400'; btn.style.color = '#000';
  setTimeout(() => { btn.textContent = '＋ Publish'; btn.style.background=''; btn.style.color=''; }, 1200);
}

// ── Library ──────────────────────────────────────────────────────────────────
const _LIBRARY_META_KEY = 'freeride_creation_library';
let _libraryItems = _libraryLoadMeta();
let _libraryObjectUrls = {};

function _libraryLoadMeta() {
  try {
    const data = JSON.parse(localStorage.getItem(_LIBRARY_META_KEY) || '[]');
    return Array.isArray(data) ? data : [];
  } catch(_) {
    return [];
  }
}

function _librarySaveMeta() {
  localStorage.setItem(_LIBRARY_META_KEY, JSON.stringify(_libraryItems.slice(0, 120)));
  updateLibraryBadge();
}

function _libraryDb() {
  return new Promise((resolve, reject) => {
    if (!window.indexedDB) {
      reject(new Error('IndexedDB indisponible dans ce navigateur'));
      return;
    }
    const req = indexedDB.open('freeride_creation_library_db', 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains('media')) db.createObjectStore('media', { keyPath: 'id' });
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error || new Error('Ouverture Library impossible'));
  });
}

async function _libraryPutBlob(id, blob) {
  const db = await _libraryDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('media', 'readwrite');
    tx.objectStore('media').put({ id, blob });
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error || new Error('Sauvegarde média impossible'));
  });
}

async function _libraryGetBlob(id) {
  const db = await _libraryDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('media', 'readonly');
    const req = tx.objectStore('media').get(id);
    req.onsuccess = () => resolve(req.result?.blob || null);
    req.onerror = () => reject(req.error || new Error('Lecture média impossible'));
  });
}

async function _libraryDeleteBlob(id) {
  const db = await _libraryDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('media', 'readwrite');
    tx.objectStore('media').delete(id);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error || new Error('Suppression média impossible'));
  });
}

function updateLibraryBadge() {
  const count = _libraryItems.length;
  ['library-badge', 'burger-library-badge'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = count;
    el.style.display = count ? 'inline' : 'none';
  });
}

function _libraryFlash(btnId, label = '＋ Library') {
  const btn = document.getElementById(btnId);
  if (!btn) return;
  btn.textContent = '✓ Library';
  btn.style.background = '#C8D400';
  btn.style.color = '#000';
  setTimeout(() => { btn.textContent = label; btn.style.background = ''; btn.style.color = ''; }, 1200);
}

async function _libraryUrl(id) {
  if (_libraryObjectUrls[id]) return _libraryObjectUrls[id];
  const blob = await _libraryGetBlob(id);
  if (!blob) return '';
  const url = URL.createObjectURL(blob);
  _libraryObjectUrls[id] = url;
  return url;
}

async function _libraryAdd(kind, item, meta = {}) {
  if (!item?.url) return null;
  const res = await fetch(item.url);
  if (!res.ok) throw new Error('Média introuvable');
  const blob = await res.blob();
  const id = `lib_${Date.now()}_${Math.random().toString(16).slice(2)}`;
  await _libraryPutBlob(id, blob);
  const entry = {
    id,
    kind,
    label: item.label || item.name || kind,
    name: item.name || `${kind}_${id}`,
    mime: item.mime || blob.type || 'application/octet-stream',
    created_at: new Date().toISOString(),
    meta,
  };
  _libraryItems = [entry, ..._libraryItems.filter(x => !(x.kind === kind && x.name === entry.name && x.label === entry.label))].slice(0, 120);
  _librarySaveMeta();
  if (_activeTab === 'library') renderLibraryPage();
  return entry;
}

async function addRiderCardToLibrary() {
  if (!_lastRiderCardUrl || !lastSlug) return;
  const sel = document.getElementById('rider');
  const label = sel.options[sel.selectedIndex]?.text?.trim() || lastSlug;
  try {
    await _libraryAdd('rider', {
      label,
      url: _lastRiderCardUrl,
      name: `${lastSlug || 'rider_card'}.jpg`,
      mime: 'image/jpeg',
    }, { rider_slug: lastSlug });
    _libraryFlash('cards-add-library-btn');
  } catch(e) {
    document.getElementById('error-msg').textContent = '❌ Library : ' + e.message;
  }
}

async function addEqCardToLibrary() {
  if (!_lastEqCard || !_eqSelectedItem) return;
  const it = _eqSelectedItem;
  try {
    await _libraryAdd('equipment', {
      label: `${it.category} · ${[it.brand, it.reference].filter(Boolean).join(' ')}`.trim(),
      url: _lastEqCard.url,
      name: _lastEqCard.name || 'equipment_card.png',
      mime: 'image/png',
    }, {
      category: it.category || '',
      brand: it.brand || '',
      reference: it.reference || '',
      rider: _eqSelectedRider?.instagram || '',
      is_selection: _lastEqCard?.is_selection || false,
    });
    _libraryFlash('eq-add-library-btn');
  } catch(e) {
    document.getElementById('eq-error-msg').textContent = '❌ Library : ' + e.message;
    document.getElementById('eq-error-msg').style.display = 'block';
  }
}

async function addEqReelToLibrary() {
  if (!_lastEqReel) return;
  try {
    await _libraryAdd('reel', {
      label: document.getElementById('reel_title')?.value || 'Reel MP4',
      url: _lastEqReel.url,
      name: _lastEqReel.name || 'reel.mp4',
      mime: 'video/mp4',
    }, {
      cards: _reelItems.length,
      format: document.getElementById('reel_format')?.value || 'reel',
    });
    _libraryFlash('reel-add-library-btn');
  } catch(e) {
    _reelLog('❌ Library : ' + e.message, true);
  }
}

function _libraryFilteredItems() {
  const kind = document.getElementById('library-kind-filter')?.value || 'all';
  const query = (document.getElementById('library-search')?.value || '').trim().toLowerCase();
  return _libraryItems.filter(item => {
    if (kind !== 'all' && item.kind !== kind) return false;
    const text = `${item.kind} ${item.label} ${item.name} ${Object.values(item.meta || {}).join(' ')}`.toLowerCase();
    return !query || text.includes(query);
  });
}

function renderLibraryPage() {
  updateLibraryBadge();
  const grid = document.getElementById('library-grid');
  const status = document.getElementById('library-status');
  if (!grid) return;
  const items = _libraryFilteredItems();
  if (status) {
    const rider = _libraryItems.filter(x => x.kind === 'rider').length;
    const equipment = _libraryItems.filter(x => x.kind === 'equipment').length;
    const reel = _libraryItems.filter(x => x.kind === 'reel').length;
    status.textContent = `${_libraryItems.length} création${_libraryItems.length > 1 ? 's' : ''} · Rider ${rider} · Equipment ${equipment} · Reel ${reel}`;
  }
  if (!items.length) {
    grid.innerHTML = '<div class="library-empty">Aucun média dans la Library pour ces filtres.</div>';
    return;
  }
  grid.innerHTML = items.map(item => {
    const date = new Date(item.created_at);
    const canReel = item.kind !== 'reel';
    return `<div class="library-card" data-library-id="${item.id}">
      <div class="library-thumb" id="library-thumb-${item.id}">Chargement…</div>
      <div class="library-body">
        <div class="library-title">${_esc(item.label)}</div>
        <div class="library-meta">${_esc(item.kind)} · ${date.toLocaleDateString()} ${date.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}<br>${_esc(item.name || '')}</div>
        <div class="library-actions">
          ${canReel ? `<button class="btn btn-secondary" onclick="libraryAddToReel('${item.id}')">＋ Reel</button>` : `<button class="btn btn-secondary" disabled>Reel</button>`}
          <button class="btn btn-secondary" onclick="libraryAddToPublish('${item.id}')">＋ Publish</button>
          <button class="btn btn-secondary" onclick="libraryDownload('${item.id}')">⬇</button>
          <button class="btn btn-secondary" onclick="libraryDelete('${item.id}')">Suppr.</button>
        </div>
      </div>
    </div>`;
  }).join('');
  items.forEach(item => _libraryRenderThumb(item));
}

async function _libraryRenderThumb(item) {
  const box = document.getElementById(`library-thumb-${item.id}`);
  if (!box) return;
  const url = await _libraryUrl(item.id);
  if (!url) {
    box.textContent = 'Média indisponible';
    return;
  }
  if (String(item.mime || '').startsWith('video')) {
    box.innerHTML = `<video src="${url}" muted preload="metadata"></video>`;
  } else {
    box.innerHTML = `<img src="${url}" alt="">`;
  }
}

async function libraryAddToReel(id) {
  const item = _libraryItems.find(x => x.id === id);
  if (!item || item.kind === 'reel') return;
  const url = await _libraryUrl(id);
  if (!url) return;
  _reelItems.push({
    id: ++_reelIdSeq,
    label: item.label,
    sub: 'Library',
    preview_url: url,
    photo_path: '',
    rider_instagram: item.meta?.rider || '',
    is_selection: !!item.meta?.is_selection,
    card_params: null,
    prerendered_url: url,
    type: 'library',
  });
  _updateReelBadge();
  if (_activeTab === 'reel') renderReelPage();
  const status = document.getElementById('library-status');
  if (status) status.textContent = 'Ajouté au Reel.';
}

async function libraryAddToPublish(id) {
  const item = _libraryItems.find(x => x.id === id);
  if (!item) return;
  const url = await _libraryUrl(id);
  if (!url) return;
  if (!_publishInitialized) publishInit();
  const entry = _publishAdd(item.kind, {
    label: item.label,
    url,
    name: item.name,
    mime: item.mime,
  });
  if (entry) {
    _publishMarkSelected(item.kind, entry.id);
    _publishDraftKind = item.kind;
    _publishState = { kind: item.kind, id: entry.id, url, name: item.name, mime: item.mime };
    publishAutoFill(false);
    publishPersist();
    publishRefreshOptions(entry.id);
    publishRender();
  }
  const status = document.getElementById('library-status');
  if (status) status.textContent = 'Ajouté à Publish.';
}

async function libraryDownload(id) {
  const item = _libraryItems.find(x => x.id === id);
  if (!item) return;
  const url = await _libraryUrl(id);
  if (!url) return;
  const a = document.createElement('a');
  a.href = url;
  a.download = item.name || 'library-media';
  a.click();
}

async function libraryDelete(id) {
  _libraryItems = _libraryItems.filter(x => x.id !== id);
  if (_libraryObjectUrls[id]) {
    URL.revokeObjectURL(_libraryObjectUrls[id]);
    delete _libraryObjectUrls[id];
  }
  try { await _libraryDeleteBlob(id); } catch(_) {}
  _librarySaveMeta();
  renderLibraryPage();
}

async function clearLibrary() {
  if (!confirm('Vider toute la Library ?')) return;
  const ids = _libraryItems.map(x => x.id);
  _libraryItems = [];
  Object.values(_libraryObjectUrls).forEach(url => URL.revokeObjectURL(url));
  _libraryObjectUrls = {};
  for (const id of ids) {
    try { await _libraryDeleteBlob(id); } catch(_) {}
  }
  _librarySaveMeta();
  renderLibraryPage();
}

let _publishInitialized = false;
let _publishState = {
  kind: '',
  id: '',
  url: '',
  name: '',
  mime: '',
};
let _publishDraftKind = 'rider';
let _publishSelection = {
  rider: [],
  equipment: [],
  reel: [],
};
let _publishSeq = 0;
let _publishLibrary = {
  rider: [],
  equipment: [],
  reel: [],
};
const _publishMusicPresets = [
  { value: '', label: 'Aucune' },
  { value: 'custom', label: 'Choix manuel' },
  { value: 'high_energy', label: 'High energy' },
  { value: 'cinematic', label: 'Cinematic build' },
  { value: 'punk', label: 'Punk / aggressive' },
  { value: 'clean_electro', label: 'Clean electro' },
  { value: 'drum_bass', label: 'Drum & bass' },
];

function _publishAvailable(kind) {
  const selected = kind === _publishState.kind ? _publishSelectedItem(kind, _publishState.id) : null;
  const item = selected || _publishLibrary[kind]?.[0];
  if (item) return item.url;
  if (kind === 'rider') return _lastRiderCardUrl;
  if (kind === 'equipment') return _lastEqCard?.url || '';
  if (kind === 'reel') return _lastEqReel?.url || '';
  return '';
}

function _publishGetItem(kind, id) {
  return (_publishLibrary[kind] || []).find(it => String(it.id) === String(id)) || null;
}

function _publishSelectedItem(kind = _publishState.kind, id = _publishState.id) {
  return _publishGetItem(kind, id) || (_publishLibrary[kind] || [])[0] || null;
}

function _publishAdd(kind, item) {
  if (!kind || !item?.url) return;
  const list = _publishLibrary[kind] || (_publishLibrary[kind] = []);
  const seen = list.findIndex(x => x.url === item.url && x.name === item.name);
  const entry = {
    id: ++_publishSeq,
    kind,
    label: item.label || item.name || kind,
    url: item.url,
    name: item.name || 'publish',
    mime: item.mime || 'application/octet-stream',
  };
  if (seen >= 0) list.splice(seen, 1);
  list.unshift(entry);
  _publishUpdateBadge();
  publishRefreshOptions(kind);
  return entry;
}

function _publishMarkSelected(kind, id) {
  const list = _publishSelection[kind] || (_publishSelection[kind] = []);
  const sid = String(id);
  if (!list.includes(sid)) list.unshift(sid);
}

function _publishCurrentItemMeta(kind) {
  if (kind === 'rider') {
    const riderProfile = _app.profiles.find(p => p.slug === lastSlug) || null;
    return {
      label: `Rider card${riderProfile ? ` · ${riderProfile.prenom} ${riderProfile.nom}` : lastSlug ? ` · ${lastSlug}` : ''}`,
      url: _lastRiderCardUrl,
      name: (lastSlug || 'card') + '.jpg',
      mime: 'image/jpeg',
    };
  }
  if (kind === 'equipment' && _lastEqCard) {
    const label = `Equipment card · ${[_eqSelectedItem?.brand, _eqSelectedItem?.reference].filter(Boolean).join(' ').trim() || _eqSelectedItem?.category || 'card'}`;
    return { label, url: _lastEqCard.url, name: _lastEqCard.name || 'publish.png', mime: 'image/png' };
  }
  if (kind === 'reel' && _lastEqReel) {
    return { label: 'Reel MP4', url: _lastEqReel.url, name: _lastEqReel.name || 'reel_equipment.mp4', mime: 'video/mp4' };
  }
  return null;
}

function publishAddCurrent(kind) {
  const item = _publishCurrentItemMeta(kind);
  if (!item?.url) return;
  const entry = _publishAdd(kind, item);
  if (entry) {
    _publishMarkSelected(kind, entry.id);
    if (!_publishState.kind || _publishDraftKind === kind) {
      _publishDraftKind = kind;
    }
    publishPersist();
    publishRefreshOptions(entry.id);
    publishRender();
  }
}

function _publishUpdateBadge() {
  const total = Object.values(_publishLibrary).reduce((sum, arr) => sum + arr.length, 0);
  const badge = document.getElementById('publish-badge');
  const burgerBadge = document.getElementById('burger-publish-badge');
  const count = document.getElementById('publish-source-count');
  if (count) {
    const rider = _publishLibrary.rider.length;
    const equipment = _publishLibrary.equipment.length;
    const reel = _publishLibrary.reel.length;
    count.textContent = total
      ? `${total} élément${total > 1 ? 's' : ''} · Rider ${rider} · Equipment ${equipment} · Reel ${reel}`
      : '0 élément';
  }
  [badge, burgerBadge].forEach(el => {
    if (!el) return;
    el.textContent = total;
    el.style.display = total > 0 ? 'inline' : 'none';
  });
}

function _publishMeta(kind) {
  const item = _publishSelectedItem(kind) || (_publishLibrary[kind] || [])[0] || null;
  if (kind === 'rider' && item) return `Carte rider prête : ${item.label || lastSlug || 'card'}`;
  if (kind === 'equipment' && item) return `Carte équipement prête : ${item.label || _lastEqCard?.name || 'card'}`;
  if (kind === 'reel' && item) return `Reel prêt : ${item.label || _lastEqReel?.name || 'reel'}`;
  return '';
}

function _publishDefaultTitle(kind) {
  const rider = _eqSelectedRider || _app.profiles.find(p => p.slug === lastSlug) || null;
  const riderName = rider ? `${rider.prenom} ${rider.nom}` : '';
  if (kind === 'rider') return riderName ? `Rider card · ${riderName}` : 'Rider card';
  if (kind === 'equipment') {
    const it = _eqSelectedItem;
    const item = it ? [it.brand, it.reference].filter(Boolean).join(' ') : '';
    return item ? `Equipment · ${item}` : 'Equipment card';
  }
  if (kind === 'reel') return riderName ? `Reel · ${riderName}` : 'Equipment reel';
  return 'Publish';
}

function _publishDefaultCaption(kind) {
  const rider = _eqSelectedRider || _app.profiles.find(p => p.slug === lastSlug) || null;
  const riderName = rider ? `${rider.prenom} ${rider.nom}` : '';
  const ig = rider?.instagram ? '@' + rider.instagram.replace(/^@/, '') : '';
  const it = _eqSelectedItem;
  const brandHandle = _publishBrandHandle(it);
  const contextHandles = _publishContextHandles().slice(0, 3);
  const parts = [];
  if (riderName) parts.push(riderName);
  if (ig) parts.push(ig);
  if (kind === 'equipment' && it) {
    if (it.category) parts.push(it.category);
    const item = [it.brand, it.reference].filter(Boolean).join(' ');
    if (item) parts.push(item);
    if (brandHandle) parts.push(brandHandle);
    if (it.details) parts.push(it.details);
  } else if (kind === 'reel') {
    parts.push('Selection reel');
  } else {
    parts.push('Freeride Fanatics');
  }
  contextHandles.forEach(h => parts.push(h));
  const lead = parts.filter(Boolean).join(' · ');
  const tags = _publishDefaultHashtags(kind);
  return lead ? `${lead}\n\n${tags}` : tags;
}

function _publishBrandHandle(item) {
  const brand = String(item?.brand || '').trim();
  if (brand) {
    const brandKeys = _brandKeys(brand);
    const found = (_app.brandTags || []).find(b => brandKeys.includes(_brandKey(b.brand)));
    if (found?.instagram_handle) return found.instagram_handle;
  }
  const raw = [
    item?.brand_instagram,
    item?.brandInstagram,
    item?.brand_ig,
    item?.instagram_brand,
    item?.brand_handle,
    item?.marque_instagram,
    item?.tag_marque,
  ].find(v => String(v || '').trim());
  if (!raw) return '';
  const clean = String(raw).trim().replace(/^https?:\/\/(www\.)?instagram\.com\//i, '').replace(/^@/, '').replace(/\/.*$/, '');
  return clean ? '@' + clean : '';
}

function _publishSlug(value) {
  return String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .toLowerCase().replace(/[^a-z0-9]+/g, '');
}

function _publishContextHandles() {
  return Array.from(new Set((_app.contextTags || [])
    .map(t => t.instagram_handle)
    .filter(Boolean)));
}

function _publishContextHashtags() {
  return Array.from(new Set((_app.contextTags || [])
    .map(t => t.default_hashtag)
    .filter(Boolean)));
}

function _publishContext(kind) {
  const rider = _eqSelectedRider || _app.profiles.find(p => p.slug === lastSlug) || null;
  const riderName = rider ? `${rider.prenom} ${rider.nom}`.trim() : '';
  const instagram = rider?.instagram ? '@' + rider.instagram.replace(/^@/, '') : '';
  const item = _eqSelectedItem || null;
  const equipmentName = item ? [item.brand, item.reference].filter(Boolean).join(' ').trim() : '';
  const category = item?.category || '';
  const details = item?.details || '';
  const source = _publishSelectedItem(kind) || null;
  const brandHandle = _publishBrandHandle(item);
  return { rider, riderName, instagram, item, equipmentName, category, details, source, brandHandle };
}

function _publishDefaultLocation(kind) {
  const ctx = _publishContext(kind);
  const raw = [
    ctx.rider?.location,
    ctx.rider?.spot,
    ctx.rider?.home_spot,
    ctx.rider?.station,
    ctx.rider?.resort,
    ctx.rider?.city,
    ctx.item?.location,
  ].find(v => String(v || '').trim());
  return raw ? String(raw).trim() : 'Freeride spot';
}

function _publishDefaultHashtags(kind) {
  const ctx = _publishContext(kind);
  const tags = ['#freeridefanatics'];
  if (kind === 'rider') tags.push('#ridercard', '#mtb', '#downhill');
  if (kind === 'equipment') tags.push('#equipmentcheck', '#mtb', '#bikecheck');
  if (kind === 'reel') tags.push('#reels', '#mtb', '#downhill');
  _publishContextHashtags().slice(0, 4).forEach(tag => tags.push(tag));
  if (ctx.category) tags.push('#' + ctx.category.toLowerCase().replace(/[^a-z0-9]+/g, ''));
  if (ctx.equipmentName) {
    const brand = (ctx.item?.brand || '').toLowerCase().replace(/[^a-z0-9]+/g, '');
    if (brand) tags.push('#' + brand);
  }
  return Array.from(new Set(tags.filter(t => t.length > 1))).join(' ');
}

function _publishDefaultFirstComment(kind) {
  const ctx = _publishContext(kind);
  const bits = [];
  if (ctx.instagram) bits.push(ctx.instagram);
  if (ctx.brandHandle) bits.push(ctx.brandHandle);
  _publishContextHandles().slice(0, 3).forEach(h => bits.push(h));
  if (ctx.equipmentName) bits.push(ctx.equipmentName);
  if (ctx.category && !ctx.equipmentName) bits.push(ctx.category);
  const unique = Array.from(new Set(bits.filter(Boolean)));
  return unique.length ? unique.join(' · ') : 'Full setup on Freeride Fanatics.';
}

function _publishDefaultAlt(kind) {
  const ctx = _publishContext(kind);
  if (kind === 'equipment') {
    const item = ctx.equipmentName || ctx.category || 'equipment';
    return `Freeride Fanatics equipment card showing ${item}${ctx.riderName ? ` for ${ctx.riderName}` : ''}.`;
  }
  if (kind === 'reel') {
    return `Freeride Fanatics reel preview${ctx.riderName ? ` featuring ${ctx.riderName}` : ''}.`;
  }
  return `Freeride Fanatics rider card${ctx.riderName ? ` featuring ${ctx.riderName}` : ''}.`;
}

function _publishDefaultMusic(kind) {
  if (kind === 'reel') return { value: 'high_energy', note: 'High energy / quick cuts' };
  if (kind === 'equipment') return { value: 'clean_electro', note: 'Clean electro / product reveal' };
  return { value: 'cinematic', note: 'Cinematic build / athlete intro' };
}

function _publishTemplateKind(kind, template) {
  if (template && template !== 'auto') return template;
  if (kind === 'equipment') return 'equipment_highlight';
  if (kind === 'reel') return 'reel';
  return 'rider_card';
}

function _publishRiderResult(ctx) {
  const handle = String(ctx.rider?.instagram || '').replace(/^@/, '').toLowerCase();
  if (!handle) return null;
  return (_app.results || []).find(r => String(r.instagram || '').replace(/^@/, '').toLowerCase() === handle) || null;
}

function _publishTemplateDefaults(kind, template = 'auto') {
  const ctx = _publishContext(kind);
  const mode = _publishTemplateKind(kind, template);
  const result = _publishRiderResult(ctx);
  const riderLine = [ctx.riderName, ctx.instagram].filter(Boolean).join(' · ');
  const itemLine = [ctx.category, ctx.equipmentName, ctx.brandHandle, ctx.details].filter(Boolean).join(' · ');
  const contextHandles = _publishContextHandles().slice(0, 3).join(' · ');
  const contextLine = contextHandles ? `\n\n${contextHandles}` : '';
  const resultLine = result
    ? `Current 2026 ranking: #${result.rank} ${result.genre === 'F' ? 'Women Elite' : 'Men Elite'} · ${Math.round(result.total_points)} pts`
    : 'Current 2026 ranking update';

  if (mode === 'race_result') {
    return {
      title: result && ctx.riderName ? `Race result · ${ctx.riderName}` : 'Race result update',
      caption: [riderLine, resultLine, itemLine ? `Setup focus: ${itemLine}` : 'Race result recap.'].filter(Boolean).join('\n') + contextLine,
      hashtags: ['#freeridefanatics', '#ucimtbworldseries', '#downhill', '#mtb', ..._publishContextHashtags()].join(' '),
      firstComment: [ctx.instagram, ctx.brandHandle, ..._publishContextHandles().slice(0, 3)].filter(Boolean).join(' · '),
      alt: `Freeride Fanatics race result post${ctx.riderName ? ` featuring ${ctx.riderName}` : ''}.`,
      music: { value: 'high_energy', note: 'High energy / race recap' },
    };
  }

  if (mode === 'equipment_highlight') {
    return {
      title: ctx.equipmentName ? `Equipment highlight · ${ctx.equipmentName}` : _publishDefaultTitle(kind),
      caption: [riderLine, itemLine || 'Equipment highlight', 'Bike check prepared for Freeride Fanatics.'].filter(Boolean).join('\n') + contextLine,
      hashtags: _publishDefaultHashtags('equipment'),
      firstComment: _publishDefaultFirstComment('equipment'),
      alt: _publishDefaultAlt('equipment'),
      music: _publishDefaultMusic('equipment'),
    };
  }

  if (mode === 'reel') {
    return {
      title: ctx.riderName ? `Reel · ${ctx.riderName}` : 'Freeride Fanatics reel',
      caption: [riderLine || 'Freeride Fanatics reel', 'Equipment selection ready for Instagram Reel.'].filter(Boolean).join('\n') + contextLine,
      hashtags: _publishDefaultHashtags('reel'),
      firstComment: [ctx.instagram, ..._publishContextHandles().slice(0, 3)].filter(Boolean).join(' · '),
      alt: _publishDefaultAlt('reel'),
      music: _publishDefaultMusic('reel'),
    };
  }

  return {
    title: _publishDefaultTitle('rider'),
    caption: [riderLine || 'Freeride Fanatics rider card', result ? resultLine : 'Rider profile ready for the season.', contextHandles].filter(Boolean).join('\n'),
    hashtags: _publishDefaultHashtags('rider'),
    firstComment: [ctx.instagram, ..._publishContextHandles().slice(0, 3)].filter(Boolean).join(' · '),
    alt: _publishDefaultAlt('rider'),
    music: _publishDefaultMusic('rider'),
  };
}

function publishApplyTemplate(template = 'auto', force = true) {
  const kind = _publishState.kind || _publishDraftKind || 'rider';
  const defaults = _publishTemplateDefaults(kind, template);
  const set = (id, value) => {
    const el = document.getElementById(id);
    if (!el) return;
    if (force || !String(el.value || '').trim()) el.value = value || '';
  };
  set('publish-title', defaults.title);
  set('publish-caption', defaults.caption);
  set('publish-location', _publishDefaultLocation(kind));
  set('publish-hashtags', defaults.hashtags);
  set('publish-first-comment', defaults.firstComment);
  set('publish-alt', defaults.alt);
  const musicSel = document.getElementById('publish-music-select');
  const musicNote = document.getElementById('publish-music-note');
  if (musicSel && (force || !musicSel.value)) musicSel.value = defaults.music?.value || '';
  if (musicNote && (force || !musicNote.value.trim())) musicNote.value = defaults.music?.note || '';
  publishPersist();
  publishRender();
}

function _publishFillDatalists(kind) {
  const ctx = _publishContext(kind);
  const setOptions = (id, values) => {
    const list = document.getElementById(id);
    if (!list) return;
    list.innerHTML = Array.from(new Set(values.filter(Boolean).map(v => String(v).trim()).filter(Boolean)))
      .map(v => `<option value="${v.replace(/"/g, '&quot;')}"></option>`)
      .join('');
  };
  setOptions('publish-title-suggestions', [
    _publishDefaultTitle(kind),
    ctx.riderName ? `Rider card · ${ctx.riderName}` : '',
    ctx.equipmentName ? `Equipment · ${ctx.equipmentName}` : '',
    ctx.riderName ? `Reel · ${ctx.riderName}` : '',
  ]);
  setOptions('publish-location-suggestions', [
    _publishDefaultLocation(kind),
    ctx.rider?.location,
    ctx.rider?.spot,
    ctx.rider?.home_spot,
    ctx.rider?.station,
    ctx.rider?.resort,
    ctx.rider?.city,
  ]);
  setOptions('publish-hashtag-suggestions', [
    _publishDefaultHashtags(kind),
    '#freeridefanatics #mtb #downhill',
    '#freeridefanatics #equipmentcheck #bikecheck',
    '#freeridefanatics #reels #mtb',
  ]);
  setOptions('publish-music-suggestions', [
    _publishDefaultMusic(kind).note,
    'High energy / quick cuts',
    'Cinematic build / clean transitions',
    'Clean electro / product reveal',
    'Drum & bass / fast pacing',
  ]);
}

function _publishCombinedText() {
  const title = (document.getElementById('publish-title')?.value || '').trim();
  const caption = (document.getElementById('publish-caption')?.value || '').trim();
  const location = (document.getElementById('publish-location')?.value || '').trim();
  const hashtags = (document.getElementById('publish-hashtags')?.value || '').trim();
  const firstComment = (document.getElementById('publish-first-comment')?.value || '').trim();
  const alt = (document.getElementById('publish-alt')?.value || '').trim();
  const musicSel = document.getElementById('publish-music-select');
  const musicNote = (document.getElementById('publish-music-note')?.value || '').trim();
  const musicLabel = musicSel && musicSel.value
    ? (musicSel.options[musicSel.selectedIndex]?.textContent || '').trim()
    : '';

  const blocks = [];
  if (title) blocks.push(title);
  if (caption) blocks.push(caption);
  if (location) blocks.push(`📍 ${location}`);
  if (hashtags) blocks.push(hashtags);
  if (musicLabel && musicLabel !== 'Aucune') {
    blocks.push(`🎵 ${musicLabel}${musicNote ? ` — ${musicNote}` : ''}`);
  } else if (musicNote) {
    blocks.push(`🎵 ${musicNote}`);
  }
  if (firstComment) blocks.push(`First comment:\n${firstComment}`);
  if (alt) blocks.push(`Alt text:\n${alt}`);
  return blocks.join('\n\n');
}

function _publishTextIncludesAny(text, values) {
  const haystack = String(text || '').toLowerCase();
  return values.some(v => {
    const needle = String(v || '').trim().toLowerCase();
    return needle && haystack.includes(needle);
  });
}

function _publishInstagramFormatStatus() {
  if (!_publishState.url) {
    return { ok: false, detail: 'Aucun média sélectionné.' };
  }
  const mime = String(_publishState.mime || '').toLowerCase();
  const name = String(_publishState.name || '').toLowerCase();
  const isVideo = mime.startsWith('video/') || /\.(mp4|mov|m4v)$/.test(name);
  const isImage = mime.startsWith('image/') || /\.(jpg|jpeg|png|webp)$/.test(name);
  if (isVideo) {
    const isMp4 = mime.includes('mp4') || name.endsWith('.mp4');
    return {
      ok: isMp4,
      warn: !isMp4,
      detail: isMp4 ? 'Vidéo MP4 prête pour Reel/Story Instagram.' : 'Vidéo détectée, idéalement exporte en MP4.',
    };
  }
  if (isImage) {
    return { ok: true, detail: 'Image compatible Instagram.' };
  }
  return { ok: false, warn: true, detail: 'Format média à vérifier avant publication.' };
}

function _publishChecklistReport() {
  const text = _publishCombinedText();
  const caption = (document.getElementById('publish-caption')?.value || '').trim();
  const hashtags = (document.getElementById('publish-hashtags')?.value || '').trim();
  const firstComment = (document.getElementById('publish-first-comment')?.value || '').trim();
  const kind = _publishState.kind || _publishDraftKind || 'rider';
  const ctx = _publishContext(kind);
  const brandHandles = [ctx.brandHandle].filter(Boolean);
  const needsBrand = ['equipment', 'reel'].includes(kind) && !!ctx.item?.brand;
  const brandMentioned = !needsBrand || _publishTextIncludesAny(`${caption}\n${firstComment}`, brandHandles);
  const contextValues = [..._publishContextHandles(), ..._publishContextHashtags()];
  const hasEventTags = contextValues.length > 0 && _publishTextIncludesAny(text, contextValues);
  const format = _publishInstagramFormatStatus();
  const captionOk = caption.length >= 20 && hashtags.includes('#');

  const items = [
    {
      key: 'media',
      ok: !!_publishState.url,
      label: 'Média OK',
      detail: _publishState.url ? `${(_publishState.kind || kind).toUpperCase()} sélectionné : ${_publishState.name || 'source prête'}.` : 'Génère ou choisis une source avant publication.',
    },
    {
      key: 'caption',
      ok: captionOk,
      warn: caption.length > 0 && !captionOk,
      label: 'Caption OK',
      detail: captionOk ? 'Caption et hashtags prêts.' : 'Ajoute une caption claire avec au moins un hashtag.',
    },
    {
      key: 'brands',
      ok: brandMentioned,
      warn: needsBrand && !brandMentioned,
      label: 'Handles marques OK',
      detail: needsBrand
        ? (brandMentioned ? `${brandHandles.join(' · ')} présent dans la publication.` : `Handle manquant pour ${ctx.item?.brand || 'la marque'}. Vérifie l’onglet Brand.`)
        : 'Aucun handle marque obligatoire pour cette source.',
    },
    {
      key: 'events',
      ok: hasEventTags,
      warn: !hasEventTags,
      label: 'Tags event OK',
      detail: hasEventTags ? 'Tags contextuels présents dans la copy.' : 'Ajoute au moins un tag depuis l’onglet Tags : UCI, Red Bull Bike, event, série, etc.',
    },
    {
      key: 'format',
      ok: format.ok,
      warn: format.warn,
      label: 'Format Instagram OK',
      detail: format.detail,
    },
  ];
  const ready = items.filter(item => item.ok).length;
  return { items, ready, total: items.length, allOk: ready === items.length };
}

function _publishChecklistItems() {
  return _publishChecklistReport().items;
}

function renderPublishChecklist() {
  const el = document.getElementById('publish-checklist');
  if (!el) return;
  const report = _publishChecklistReport();
  const rows = report.items.map(item => {
    const cls = item.ok ? 'ok' : item.warn ? 'warn' : '';
    const icon = item.ok ? '✓' : item.warn ? '!' : '·';
    return `<div class="publish-check-row ${cls}">
      <span class="publish-check-dot">${icon}</span>
      <span class="publish-check-text">
        <span class="publish-check-label">${_esc(item.label)}</span>
        <span class="publish-check-detail">${_esc(item.detail || '')}</span>
      </span>
    </div>`;
  }).join('');
  el.innerHTML = `
    <div class="publish-check-summary ${report.allOk ? 'ok' : ''}">
      <span>Checklist publication</span>
      <span class="publish-check-score">${report.ready}/${report.total} prêt</span>
    </div>
    ${rows}`;
}

function _publishHistoryLoad() {
  try {
    const data = JSON.parse(localStorage.getItem('freeride_publish_history') || '[]');
    return Array.isArray(data) ? data : [];
  } catch(_) {
    return [];
  }
}

function _publishHistorySave(items) {
  localStorage.setItem('freeride_publish_history', JSON.stringify(items.slice(0, 30)));
}

function publishSaveHistory(manual = false) {
  const text = _publishCombinedText();
  if (!text.trim()) {
    if (manual) document.getElementById('publish-status').textContent = '⚠️ Rien à sauvegarder';
    return;
  }
  const checklist = _publishChecklistReport();
  const item = {
    id: Date.now(),
    created_at: new Date().toISOString(),
    kind: _publishState.kind || _publishDraftKind || '',
    template: document.getElementById('publish-template')?.value || 'auto',
    source_name: _publishState.name || '',
    title: document.getElementById('publish-title')?.value || '',
    caption: document.getElementById('publish-caption')?.value || '',
    location: document.getElementById('publish-location')?.value || '',
    hashtags: document.getElementById('publish-hashtags')?.value || '',
    first_comment: document.getElementById('publish-first-comment')?.value || '',
    alt: document.getElementById('publish-alt')?.value || '',
    music_select: document.getElementById('publish-music-select')?.value || '',
    music_note: document.getElementById('publish-music-note')?.value || '',
    checklist_ready: checklist.ready,
    checklist_total: checklist.total,
    checklist_all_ok: checklist.allOk,
    checklist_items: checklist.items.map(x => ({
      key: x.key,
      ok: !!x.ok,
      warn: !!x.warn,
      label: x.label,
      detail: x.detail,
    })),
    text,
  };
  const prev = _publishHistoryLoad().filter(x => x.text !== item.text);
  _publishHistorySave([item, ...prev]);
  renderPublishHistory();
  if (manual) {
    document.getElementById('publish-status').textContent =
      `💾 Préparation sauvegardée · checklist ${checklist.ready}/${checklist.total}`;
  }
}

function renderPublishHistory() {
  const el = document.getElementById('publish-history-list');
  if (!el) return;
  const items = _publishHistoryLoad();
  if (!items.length) {
    el.innerHTML = '<div class="publish-meta">Aucune publication préparée.</div>';
    return;
  }
  el.innerHTML = items.slice(0, 12).map(item => {
    const date = new Date(item.created_at);
    const label = item.title || item.source_name || 'Publication préparée';
    const score = item.checklist_total ? ` · checklist ${item.checklist_ready || 0}/${item.checklist_total}` : '';
    const cls = item.checklist_all_ok ? 'ok' : '';
    const missing = (item.checklist_items || []).filter(x => !x.ok).map(x => x.label).slice(0, 3);
    const preview = [item.caption, item.hashtags].filter(Boolean).join(' ').replace(/\s+/g, ' ').trim();
    return `<div class="publish-history-item">
      <div class="publish-history-title">${_esc(label)}</div>
      <div class="publish-history-meta">${_esc(item.kind || 'publish')} · ${_esc(item.template || 'auto')} · ${date.toLocaleDateString()} ${date.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}${_esc(score)}${item.source_name ? `<br>Source : ${_esc(item.source_name)}` : ''}</div>
      <div class="publish-check-summary ${cls}" style="margin-top:8px;padding:7px 8px">
        <span>${item.checklist_all_ok ? 'Prêt Instagram' : 'À vérifier'}</span>
        <span class="publish-check-score">${item.checklist_ready || 0}/${item.checklist_total || 5}</span>
      </div>
      ${missing.length ? `<div class="publish-history-meta" style="margin-top:6px;color:#f0a000">À vérifier : ${_esc(missing.join(' · '))}</div>` : ''}
      ${preview ? `<div class="publish-history-meta" style="margin-top:6px">${_esc(preview.slice(0, 150))}${preview.length > 150 ? '…' : ''}</div>` : ''}
      <div class="publish-history-actions">
        <button class="btn btn-secondary" onclick="publishRestoreHistory(${item.id})">Restaurer</button>
        <button class="btn btn-secondary" onclick="publishDeleteHistory(${item.id})">Supprimer</button>
      </div>
    </div>`;
  }).join('');
}

function publishRestoreHistory(id) {
  const item = _publishHistoryLoad().find(x => Number(x.id) === Number(id));
  if (!item) return;
  const set = (field, value) => {
    const el = document.getElementById(field);
    if (el) el.value = value || '';
  };
  set('publish-template', item.template || 'auto');
  set('publish-title', item.title);
  set('publish-caption', item.caption);
  set('publish-location', item.location);
  set('publish-hashtags', item.hashtags);
  set('publish-first-comment', item.first_comment);
  set('publish-alt', item.alt);
  set('publish-music-select', item.music_select);
  set('publish-music-note', item.music_note);
  publishPersist();
  publishRender();
  document.getElementById('publish-status').textContent = '↺ Préparation restaurée';
}

function publishDeleteHistory(id) {
  _publishHistorySave(_publishHistoryLoad().filter(x => Number(x.id) !== Number(id)));
  renderPublishHistory();
}

function publishClearHistory() {
  if (!confirm('Vider l’historique Publish ?')) return;
  _publishHistorySave([]);
  renderPublishHistory();
}

function publishPersist() {
  try {
    localStorage.setItem('freeride_publish_settings', JSON.stringify({
      source_kind: _publishState.kind || '',
      source_id: _publishState.id || '',
      draft_kind: _publishDraftKind || '',
      selection_rider: _publishSelection.rider || [],
      selection_equipment: _publishSelection.equipment || [],
      selection_reel: _publishSelection.reel || [],
      title: document.getElementById('publish-title')?.value || '',
      template: document.getElementById('publish-template')?.value || 'auto',
      caption: document.getElementById('publish-caption')?.value || '',
      location: document.getElementById('publish-location')?.value || '',
      hashtags: document.getElementById('publish-hashtags')?.value || '',
      first_comment: document.getElementById('publish-first-comment')?.value || '',
      alt: document.getElementById('publish-alt')?.value || '',
      music_select: document.getElementById('publish-music-select')?.value || '',
      music_note: document.getElementById('publish-music-note')?.value || '',
      use_share: document.getElementById('publish-use-share')?.checked ?? true,
      open_instagram: document.getElementById('publish-open-instagram')?.checked ?? true,
    }));
  } catch(_) {}
}

function publishLoadSettings() {
  try {
    const saved = JSON.parse(localStorage.getItem('freeride_publish_settings') || '{}');
    const set = (id, value) => {
      const el = document.getElementById(id);
      if (el && value != null) el.value = value;
    };
    set('publish-title', saved.title);
    set('publish-template', saved.template || 'auto');
    set('publish-caption', saved.caption);
    set('publish-location', saved.location);
    set('publish-hashtags', saved.hashtags);
    set('publish-first-comment', saved.first_comment);
    set('publish-alt', saved.alt);
    set('publish-music-note', saved.music_note);
    const useShare = document.getElementById('publish-use-share');
    if (useShare && typeof saved.use_share === 'boolean') useShare.checked = saved.use_share;
    const openIg = document.getElementById('publish-open-instagram');
    if (openIg && typeof saved.open_instagram === 'boolean') openIg.checked = saved.open_instagram;
    if (saved.source_kind) _publishState.kind = saved.source_kind;
    if (saved.source_id) _publishState.id = saved.source_id;
    if (saved.draft_kind) _publishDraftKind = saved.draft_kind;
    _publishSelection.rider = Array.isArray(saved.selection_rider) ? saved.selection_rider.map(String) : [];
    _publishSelection.equipment = Array.isArray(saved.selection_equipment) ? saved.selection_equipment.map(String) : [];
    _publishSelection.reel = Array.isArray(saved.selection_reel) ? saved.selection_reel.map(String) : [];
    const musicSel = document.getElementById('publish-music-select');
    if (musicSel && saved.music_select != null) musicSel.value = saved.music_select;
  } catch(_) {}
}

function _publishOptions() {
  const opts = [];
  if (_lastRiderCardUrl) {
    opts.push({
      kind: 'rider',
      label: `Rider card${lastSlug ? ` · ${lastSlug}` : ''}`,
      name: (lastSlug || 'card') + '.jpg',
      url: _lastRiderCardUrl,
      mime: 'image/jpeg',
    });
  }
  if (_lastEqCard?.url) {
    opts.push({
      kind: 'equipment',
      label: `Equipment card${_lastEqCard.name ? ` · ${_lastEqCard.name}` : ''}`,
      name: _lastEqCard.name || 'publish.png',
      url: _lastEqCard.url,
      mime: 'image/png',
    });
  }
  if (_lastEqReel?.url) {
    opts.push({
      kind: 'reel',
      label: `Reel MP4${_lastEqReel.name ? ` · ${_lastEqReel.name}` : ''}`,
      name: _lastEqReel.name || 'publish.mp4',
      url: _lastEqReel.url,
      mime: 'video/mp4',
    });
  }
  return opts;
}

function publishRefreshOptions(selectValue = null) {
  const kinds = ['rider', 'equipment', 'reel'];
  kinds.forEach(kind => {
    const sel = document.getElementById(`publish-${kind}-select`);
    if (!sel) return;
    const items = _publishLibrary[kind] || [];
    const currentIds = kind === 'reel'
      ? [kind === _publishState.kind ? _publishState.id : '', ...(_publishSelection[kind] || [])]
      : (_publishSelection[kind] || []);
    sel.innerHTML = `
      <option value="">${items.length ? 'Choisir une source' : 'Aucune source disponible'}</option>
      ${items.map(opt => `<option value="${opt.id}">${opt.label}</option>`).join('')}`;
    const allowed = new Set(items.map(o => String(o.id)));
    const selectedIds = (currentIds || []).map(String).filter(id => allowed.has(id));
    Array.from(sel.options).forEach(opt => {
      opt.selected = selectedIds.includes(String(opt.value));
    });
    if (kind === 'reel' && selectedIds.length === 0) {
      const fallback = selectValue && allowed.has(String(selectValue)) ? String(selectValue) : (items[0] ? String(items[0].id) : '');
      sel.value = fallback || '';
    }
  });

  const musicSel = document.getElementById('publish-music-select');
  if (musicSel && !musicSel.options.length) {
    musicSel.innerHTML = _publishMusicPresets.map(opt => `<option value="${opt.value}">${opt.label}</option>`).join('');
  }

  _publishUpdateBadge();
}

function publishSelectSource(kind, el) {
  const values = kind === 'reel'
    ? [el?.value].filter(Boolean)
    : Array.from(el?.selectedOptions || []).map(opt => opt.value).filter(Boolean);
  _publishSelection[kind] = values;
  if (kind === 'reel') {
    _publishDraftKind = 'reel';
  } else if (values.length) {
    _publishDraftKind = kind;
  }
  publishPersist();
  publishRefreshOptions(values[0] || '');
  publishRender();
}

function publishSetDraftKind(kind) {
  _publishDraftKind = kind;
  publishPersist();
  publishRender();
}

function _publishSelectionItems(kind) {
  const ids = _publishSelection[kind] || [];
  return ids.map(id => _publishGetItem(kind, id)).filter(Boolean);
}

function _publishSelectionSummary() {
  const parts = [];
  const rider = _publishSelectionItems('rider');
  const equipment = _publishSelectionItems('equipment');
  const reel = _publishSelectionItems('reel');
  if (rider.length) parts.push(`Riders ${rider.length}`);
  if (equipment.length) parts.push(`Equipment ${equipment.length}`);
  if (reel.length) parts.push(`Reel ${reel.length}`);
  return parts.join(' · ');
}

function publishGenerateSelection() {
  const order = [_publishDraftKind, 'rider', 'equipment', 'reel'];
  const pickedKind = order.find(kind => _publishSelectionItems(kind).length) || '';
  const pickedItem = pickedKind ? _publishSelectionItems(pickedKind)[0] : null;
  if (!pickedItem) {
    _publishState = { kind: '', id: '', url: '', name: '', mime: '' };
    publishRender();
    return;
  }
  _publishState = {
    kind: pickedKind,
    id: String(pickedItem.id),
    url: pickedItem.url,
    name: pickedItem.name,
    mime: pickedItem.mime,
  };
  publishAutoFill(true);
  publishPersist();
  publishRefreshOptions(pickedItem.id);
  publishRender();
}

function publishSetMusic(value) {
  const note = document.getElementById('publish-music-note');
  if (!note) return;
  if (value === 'high_energy' && !note.value.trim()) note.value = 'High energy / quick cuts';
  else if (value === 'cinematic' && !note.value.trim()) note.value = 'Cinematic build / clean transitions';
  else if (value === 'punk' && !note.value.trim()) note.value = 'Punk / raw energy';
  else if (value === 'clean_electro' && !note.value.trim()) note.value = 'Clean electro / minimal';
  else if (value === 'drum_bass' && !note.value.trim()) note.value = 'Drum & bass / fast pacing';
  publishPersist();
  publishRender();
}

function publishRender() {
  const src = _publishState.url;
  const kind = _publishState.kind;
  const status = document.getElementById('publish-status');
  const state = document.getElementById('publish-source-state');
  const meta = document.getElementById('publish-source-meta');
  const placeholder = document.getElementById('publish-placeholder');
  const img = document.getElementById('publish-preview-img');
  const video = document.getElementById('publish-preview-video');
  const captionBox = document.getElementById('publish-preview-caption');
  const dlBtn = document.getElementById('publish-download-btn');
  const shareBtn = document.getElementById('publish-share-btn');
  const copyBtn = document.getElementById('publish-preview-copy-btn');
  const count = document.getElementById('publish-source-count');

  ['rider','equipment','reel'].forEach(k => {
    const active = kind ? (k === kind) : (k === _publishDraftKind);
    document.getElementById('publish-src-' + k)?.classList.toggle('active', active);
  });
  publishRefreshOptions(kind);
  _publishFillDatalists(kind || _publishDraftKind || 'rider');

  if (!src) {
    placeholder.style.display = 'block';
    img.style.display = 'none';
    video.style.display = 'none';
    captionBox.style.display = 'none';
    if (copyBtn) copyBtn.disabled = true;
    dlBtn.disabled = true;
    shareBtn.disabled = true;
    const summary = _publishSelectionSummary();
    state.textContent = summary
      ? `Sélection prête: ${summary}. Clique "Générer la sélection".`
      : 'Aucune source sélectionnée.';
    meta.textContent = '';
    if (count) count.textContent = '0 élément';
    if (status) status.textContent = 'Génère d’abord une carte ou un reel.';
    renderPublishChecklist();
    return;
  }

  placeholder.style.display = 'none';
  dlBtn.disabled = false;
  shareBtn.disabled = false;
  const selected = _publishSelectedItem();
  state.textContent = _publishMeta(kind) || 'Source prête.';
  const summary = _publishSelectionSummary();
  meta.textContent = `${kind.toUpperCase()} · ${selected?.label || _publishState.name || 'source prête'}${summary ? ` · ${summary}` : ''}`;
  if (count) {
    const total = Object.values(_publishLibrary).reduce((sum, arr) => sum + arr.length, 0);
    const rider = _publishLibrary.rider.length;
    const equipment = _publishLibrary.equipment.length;
    const reel = _publishLibrary.reel.length;
    count.textContent = total
      ? `${total} élément${total > 1 ? 's' : ''} · Rider ${rider} · Equipment ${equipment} · Reel ${reel}`
      : '0 élément';
  }

  if (_publishState.mime.startsWith('video')) {
    img.style.display = 'none';
    video.style.display = 'block';
    video.src = src;
    video.load();
  } else {
    video.style.display = 'none';
    img.style.display = 'block';
    img.src = src;
  }

  const combined = _publishCombinedText();
  captionBox.style.display = 'block';
  captionBox.textContent = combined || 'Aucun texte saisi.';
  if (copyBtn) copyBtn.disabled = !combined;
  renderPublishChecklist();
  if (status) status.textContent = '';
}

function publishAutoFill(force = false) {
  const kind = _publishState.kind || _publishDraftKind || (_publishAvailable('reel') ? 'reel' : _publishAvailable('equipment') ? 'equipment' : 'rider');
  if (!kind || !_publishAvailable(kind)) {
    publishRender();
    return;
  }

  const template = document.getElementById('publish-template')?.value || 'auto';
  const defaults = _publishTemplateDefaults(kind, template);
  const set = (id, value) => {
    const el = document.getElementById(id);
    if (el && (force || !String(el.value || '').trim())) el.value = value || '';
  };
  set('publish-title', defaults.title);
  set('publish-caption', defaults.caption);
  set('publish-location', _publishDefaultLocation(kind));
  set('publish-hashtags', defaults.hashtags);
  set('publish-first-comment', defaults.firstComment);
  set('publish-alt', defaults.alt);
  const musicSel = document.getElementById('publish-music-select');
  const musicNote = document.getElementById('publish-music-note');
  if (musicSel && (force || !musicSel.value)) musicSel.value = defaults.music?.value || '';
  if (musicNote && (force || !musicNote.value.trim())) musicNote.value = defaults.music?.note || '';
  _publishFillDatalists(kind);

  publishPersist();
  publishRender();
}

function publishUseSource(kind, force = false) {
  publishSetDraftKind(kind);
}

async function _publishCurrentFile() {
  if (!_publishState.url) throw new Error('Aucune source sélectionnée');
  const res = await fetch(_publishState.url);
  if (!res.ok) throw new Error('Source introuvable');
  const blob = await res.blob();
  return new File([blob], _publishState.name || 'publish', { type: _publishState.mime || blob.type || 'application/octet-stream' });
}

async function _publishCurrentFiles() {
  const selectedItems = _publishState.kind ? _publishSelectionItems(_publishState.kind) : [];
  if (selectedItems.length <= 1) return [await _publishCurrentFile()];
  const files = [];
  for (const item of selectedItems) {
    const res = await fetch(item.url);
    if (!res.ok) continue;
    const blob = await res.blob();
    files.push(new File([blob], item.name || 'publish', { type: item.mime || blob.type || 'application/octet-stream' }));
  }
  return files.length ? files : [await _publishCurrentFile()];
}

async function publishCopyCaption() {
  const txt = _publishCombinedText();
  if (!txt) return;
  try {
    await navigator.clipboard.writeText(txt);
    publishSaveHistory(false);
    const checklist = _publishChecklistReport();
    document.getElementById('publish-status').textContent =
      `✅ Tout le texte Instagram est copié · checklist ${checklist.ready}/${checklist.total}`;
  } catch(e) {
    document.getElementById('publish-status').textContent = '❌ Impossible de copier';
  }
}

async function publishDownload() {
  if (!_publishState.url) return;
  const a = document.createElement('a');
  a.href = _publishState.url;
  a.download = _publishState.name || 'publish';
  a.click();
  document.getElementById('publish-status').textContent = '⬇ Média téléchargé';
}

async function publishShare() {
  const status = document.getElementById('publish-status');
  const useShare = document.getElementById('publish-use-share')?.checked ?? true;
  const openInstagram = document.getElementById('publish-open-instagram')?.checked ?? true;
  if (!_publishState.url) {
    status.textContent = '⚠️ Choisis une source d’abord';
    return;
  }

  const text = _publishCombinedText();
  try {
    const files = await _publishCurrentFiles();
    const canShareFiles = useShare && navigator.canShare && navigator.canShare({ files });
    if (navigator.share && canShareFiles) {
      publishSaveHistory(false);
      await navigator.share({
        title: document.getElementById('publish-title')?.value || 'Freeride Fanatics',
        text,
        files,
      });
      const checklist = _publishChecklistReport();
      status.textContent = `✅ Partagé vers le téléphone · checklist ${checklist.ready}/${checklist.total}`;
      if (openInstagram) {
        setTimeout(() => { _publishLaunchInstagramApp(); }, 400);
      }
      return;
    }
    await publishDownload();
    if (text) await navigator.clipboard.writeText(text);
    publishSaveHistory(false);
    const checklist = _publishChecklistReport();
    status.textContent = `⚠️ Partage natif indisponible, média téléchargé + caption copiée · checklist ${checklist.ready}/${checklist.total}`;
    if (openInstagram) {
      setTimeout(() => { _publishLaunchInstagramApp(); }, 400);
    }
  } catch(e) {
    status.textContent = '❌ ' + e.message;
  }
}

function _publishLaunchInstagramApp() {
  const webUrl = 'https://www.instagram.com/';
  const ua = navigator.userAgent || '';
  const isAndroid = /Android/i.test(ua);
  const isIOS = /iPhone|iPad|iPod/i.test(ua);

  if (!isAndroid && !isIOS) {
    window.open(webUrl, '_blank', 'noopener,noreferrer');
    return 'web';
  }

  const startedAt = Date.now();
  const fallback = () => {
    if (document.hidden || Date.now() - startedAt < 700) return;
    window.open(webUrl, '_blank', 'noopener,noreferrer');
  };

  if (isAndroid) {
    window.location.href = 'intent://instagram.com/#Intent;scheme=https;package=com.instagram.android;S.browser_fallback_url=https%3A%2F%2Fwww.instagram.com%2F;end';
  } else {
    window.location.href = 'instagram://app';
    setTimeout(fallback, 900);
  }
  return 'app';
}

function publishOpenInstagram() {
  const status = document.getElementById('publish-status');
  try {
    const mode = _publishLaunchInstagramApp();
    if (status) {
      status.textContent = mode === 'app'
        ? '📱 Ouverture de l’app Instagram si elle est installée'
        : '📱 Instagram ouvert dans un nouvel onglet';
    }
  } catch(e) {
    if (status) status.textContent = '❌ Impossible d’ouvrir Instagram';
  }
}

function publishInit() {
  if (!_publishInitialized) {
    _publishInitialized = true;
    ['publish-title','publish-caption','publish-location','publish-hashtags','publish-first-comment','publish-alt']
      .forEach(id => document.getElementById(id)?.addEventListener('input', () => {
        publishPersist();
        publishRender();
      }));
    ['publish-use-share','publish-open-instagram']
      .forEach(id => document.getElementById(id)?.addEventListener('change', () => {
        publishPersist();
        publishRender();
      }));
    publishLoadSettings();
  }

  publishRefreshOptions(_publishState.id || null);
  renderPublishHistory();
  publishRender();
}

init();
renderProfiles();
</script>
</body>
</html>
"""

# ── ROUTES ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return Response(HTML, mimetype="text/html")


@app.route("/api/riders")
def api_riders():
    _, _, profiles = get_engine()
    data = [{"slug":      f"{p['nom'].lower().replace(' ','_')}_{p['prenom'].lower()}",
             "prenom":    p["prenom"],
             "nom":       p["nom"],
             "genre":     p["genre"],
             "has_photo": gc.find_photo(p) is not None}
            for p in profiles]
    return jsonify(data)


LOGO_EXTS = {".jpg", ".jpeg", ".webp", ".png", ".svg"}
# Priorité d'affichage : SVG > PNG > JPG/WEBP
_LOGO_PRIORITY = {".svg": 3, ".png": 2, ".webp": 1, ".jpg": 1, ".jpeg": 1}

def _scan_logos():
    """Scanne LOGOS_DIR — toutes extensions (jpg, png, webp, svg).
    Si plusieurs fichiers ont le même stem, garde celui avec la meilleure priorité."""
    seen = {}  # stem_lower → (priority, Path)
    if gc.LOGOS_DIR.exists():
        for f in sorted(gc.LOGOS_DIR.iterdir()):
            ext = f.suffix.lower()
            if ext not in LOGO_EXTS:
                continue
            stem = f.stem.lower()
            prio = _LOGO_PRIORITY.get(ext, 0)
            if stem not in seen or prio > seen[stem][0]:
                seen[stem] = (prio, f)
    return {stem: v[1] for stem, v in seen.items()}


@app.route("/api/sponsors")
def api_sponsors():
    """Liste tous les logos présents dans logos/ (jpg, png, webp, svg)."""
    seen_stems = _scan_logos()
    if not seen_stems:
        seen_stems = {}

    available = []
    for stem, f in sorted(seen_stems.items()):
        key = next((k for k, v in gc.BRAND_MAP.items() if v == f.name), f.stem)
        available.append({
            "key":   key,
            "file":  f.name,
            "label": f.stem.upper(),
            "url":   f"/logos/{f.name}",
        })
    return jsonify(available)


@app.route("/logos/<path:filename>")
def serve_logo(filename):
    return send_from_directory(str(gc.LOGOS_DIR), filename)


@app.route("/assets/<path:filename>")
def serve_asset(filename):
    return send_from_directory(str(ASSETS_DIR), filename)


@app.route("/favicon.ico")
def serve_favicon():
    return send_from_directory(str(ASSETS_DIR / "brand"), "favicon.ico", mimetype="image/x-icon")


@app.route("/api/equipment/<instagram>")
def api_equipment(instagram):
    """Retourne les équipements d'un rider (par handle Instagram)."""
    handle = instagram.lower().lstrip("@")
    eq = get_equipment().get(handle, {})
    result = []
    for cat in gc.EQUIPMENT_COLUMNS:
        item = eq.get(cat)
        if not item:
            continue
        result.append({
            "category":  cat,
            "brand":     item["brand"],
            "reference": item["reference"],
            "details":   item["details"],
            "raw":       item["raw"],
        })
    return jsonify(result)


@app.route("/api/profile/<slug>")
def api_profile(slug):
    _, _, profiles = get_engine()
    profile = next((p for p in profiles
                    if f"{p['nom'].lower().replace(' ','_')}_{p['prenom'].lower()}" == slug), None)
    if not profile:
        return jsonify({"error": "Rider introuvable"}), 404
    # Retourne uniquement les champs éditables
    return jsonify({
        "prenom":       profile.get("prenom", ""),
        "nom":          profile.get("nom", ""),
        "nationality":  profile.get("nationalite", ""),   # clé interne = "nationalite"
        "hometown":     profile.get("ville", ""),          # clé interne = "ville"
        "age":          profile.get("age", ""),
        "achievements": profile.get("palmares", ""),       # clé interne = "palmares"
        "team":         profile.get("team", ""),
        "instagram":    profile.get("instagram", ""),
        "sponsors":     profile.get("sponsors", []),
    })


@app.route("/api/generate", methods=["POST"])
def api_generate():
    try:
        data = request.get_json()
        slug = data.get("slug", "")

        bg, _, profiles = get_engine()

        # Trouver le profil
        profile = next((p for p in profiles
                        if f"{p['nom'].lower().replace(' ','_')}_{p['prenom'].lower()}" == slug), None)
        if not profile:
            return jsonify({"error": f"Rider introuvable : {slug}"}), 404

        # ── Overrides édition inline ──
        overrides = data.get("overrides", {})
        if overrides:
            override_keys = {
                "nationality": "nationalite",
                "hometown": "ville",
                "achievements": "palmares",
            }
            normalized_overrides = {
                override_keys.get(k, k): v
                for k, v in overrides.items()
                if v != ""
            }
            profile = {**profile, **normalized_overrides}

        # ── Paramètres photo ──
        gc.PHOTO_ZOOM     = float(data.get("photo_zoom",  1.0))
        gc.PHOTO_OFFSET_X = int(data.get("offset_x",     gc.PHOTO_OFFSET_X))
        gc.PHOTO_OFFSET_Y = int(data.get("offset_y",     gc.PHOTO_OFFSET_Y))

        # ── Paramètres texte ──
        gc.TEXT_X   = int(data.get("text_x",   gc.TEXT_X))
        gc.TEXT_TOP = int(data.get("text_top",  gc.TEXT_TOP))
        gc.GAP      = int(data.get("gap",       gc.GAP))

        # ── Polices (rechargées si tailles changées) ──
        gc.SZ_LABEL    = int(data.get("sz_label",    gc.SZ_LABEL))
        gc.SZ_VALUE    = int(data.get("sz_value",    gc.SZ_VALUE))
        gc.SZ_VALUE_SM = int(data.get("sz_value_sm", gc.SZ_VALUE_SM))
        fonts = gc.load_fonts()

        # ── Paramètres logos ──
        gc.LOGO_H         = int(data.get("logo_h", gc.LOGO_H))
        gc.LOGO_Y         = int(data.get("logo_y", gc.LOGO_Y))
        lx = int(data.get("logo_x", -1))
        gc.LOGO_X         = None if lx < 0 else lx
        gc.LOGO_DIRECTION = data.get("logo_dir", gc.LOGO_DIRECTION)

        sponsors = data.get("sponsors")
        card = gc.generate_card(profile, fonts, bg, forced_sponsors=sponsors)
        card = _apply_result_badge(card, data.get("result_badge"), fonts)

        # Retourner l'image en mémoire
        buf = io.BytesIO()
        card.save(buf, "JPEG", quality=92)
        buf.seek(0)
        return send_file(buf, mimetype="image/jpeg",
                         download_name=f"{slug}.jpg")

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


def _apply_result_badge(card, badge, fonts):
    """Ajoute un badge podium premium aux cartes issues des résultats Performance."""
    if not isinstance(badge, dict):
        return card
    try:
        position = int(badge.get("position") or 0)
    except (TypeError, ValueError):
        return card
    if position not in (1, 2, 3):
        return card

    from PIL import Image, ImageDraw, ImageFont
    if str(badge.get("style") or "").lower() == "v1":
        return _apply_result_badge_v1(card, badge, fonts, position, Image, ImageDraw, ImageFont)

    colors = {
        1: (212, 175, 55, 255),
        2: (192, 200, 208, 255),
        3: (205, 127, 50, 255),
    }
    ordinals = {1: "1ST", 2: "2ND", 3: "3RD"}
    event = str(badge.get("event") or "").strip()
    event = event.replace("(", "· ").replace(")", "").strip()
    event = event.upper()[:30] or "RACE RESULT"
    season = str(badge.get("season") or "WC026").upper()

    def badge_font(path, size, fallback_key="label"):
        try:
            return ImageFont.truetype(str(path), size)
        except Exception:
            return fonts.get(fallback_key) or ImageFont.load_default()

    rank_font = badge_font(gc.FONT_LABEL_PATH, 56, "label")
    title_font = badge_font(gc.FONT_LABEL_PATH, 44, "label")
    meta_font = badge_font(gc.FONT_VALUE_PATH, 25, "value_sm")
    season_font = badge_font(gc.FONT_VALUE_PATH, 21, "value_sm")

    base = card.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    x1, y1 = 42, 42
    h = 118
    rank_w = 128
    gap = 20
    title = f"{ordinals[position]} PLACE"
    title_box = draw.textbbox((0, 0), title, font=title_font)
    event_box = draw.textbbox((0, 0), event, font=meta_font)
    season_box = draw.textbbox((0, 0), season, font=season_font)
    text_w = max(title_box[2] - title_box[0], event_box[2] - event_box[0])
    season_w = season_box[2] - season_box[0]
    w = min(650, max(500, rank_w + gap + text_w + season_w + 70))
    x2, y2 = x1 + w, y1 + h

    draw.rounded_rectangle((x1 + 7, y1 + 9, x2 + 7, y2 + 9), radius=26, fill=(0, 0, 0, 88))
    draw.rounded_rectangle((x1, y1, x2, y2), radius=26, fill=(10, 12, 12, 226), outline=(210, 224, 0, 190), width=3)
    draw.rectangle((x1 + 24, y1, x2 - 24, y1 + 4), fill=(210, 224, 0, 230))
    draw.rounded_rectangle((x1 + 14, y1 + 14, x1 + rank_w, y2 - 14), radius=22, fill=colors[position])
    draw.text((x1 + 71, y1 + 59), str(position), font=rank_font, fill=(10, 12, 12, 255), anchor="mm")
    draw.text((x1 + rank_w + gap, y1 + 23), title, font=title_font, fill=(245, 245, 245, 255))
    draw.text((x1 + rank_w + gap, y1 + 72), event, font=meta_font, fill=(210, 224, 0, 245))
    draw.text((x2 - 24, y2 - 28), season, font=season_font, fill=(185, 185, 185, 230), anchor="ra")
    return Image.alpha_composite(base, overlay).convert("RGB")


def _apply_result_badge_v1(card, badge, fonts, position, Image, ImageDraw, ImageFont):
    """Conserve la première capsule compacte sous l'option Capsule V1."""
    colors = {
        1: (212, 175, 55, 255),
        2: (192, 200, 208, 255),
        3: (205, 127, 50, 255),
    }
    event = str(badge.get("event") or "").strip()
    event = event.split("(")[0].strip() or "RACE RESULT"
    event = event.upper()[:18]

    def badge_font(path, size, fallback_key="label"):
        try:
            return ImageFont.truetype(str(path), size)
        except Exception:
            return fonts.get(fallback_key) or ImageFont.load_default()

    rank_font = badge_font(gc.FONT_LABEL_PATH, 31, "label")
    text_font = badge_font(gc.FONT_LABEL_PATH, 25, "label")
    meta_font = badge_font(gc.FONT_VALUE_PATH, 18, "value_sm")

    base = card.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    x1, y1 = 42, 42
    h = 68
    chip = 70
    gap = 12
    rank_text = f"P{position}"
    title = "RACE RESULT"
    title_box = draw.textbbox((0, 0), title, font=text_font)
    event_box = draw.textbbox((0, 0), event, font=meta_font)
    text_w = max(title_box[2] - title_box[0], event_box[2] - event_box[0])
    w = min(348, chip + gap + text_w + 34)
    x2, y2 = x1 + w, y1 + h

    draw.rounded_rectangle((x1 + 5, y1 + 6, x2 + 5, y2 + 6), radius=18, fill=(0, 0, 0, 72))
    draw.rounded_rectangle((x1, y1, x2, y2), radius=18, fill=(12, 14, 14, 214), outline=(210, 224, 0, 170), width=2)
    draw.rounded_rectangle((x1 + 8, y1 + 8, x1 + chip, y2 - 8), radius=14, fill=colors[position])
    draw.text((x1 + 39, y1 + 36), rank_text, font=rank_font, fill=(12, 14, 14, 255), anchor="mm")
    draw.text((x1 + chip + gap, y1 + 13), title, font=text_font, fill=(245, 245, 245, 255))
    draw.text((x1 + chip + gap, y1 + 41), event, font=meta_font, fill=(210, 224, 0, 235))
    return Image.alpha_composite(base, overlay).convert("RGB")


@app.route("/api/equipment-library")
def api_equipment_library():
    """
    Liste toutes les photos dispo dans Equipment/ groupées par sous-dossier (catégorie).
    Réponse : { "categories": [ { "name": "Frame", "photos": [ { "stem", "url", "path" }, ... ] } ] }
    """
    import generate_equipment_card as gec
    if not gec.EQ_PHOTOS.exists():
        return jsonify({"categories": []})
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    cats = []
    # Sous-dossiers = catégories
    for sub in sorted(gec.EQ_PHOTOS.iterdir()):
        if sub.is_dir() and not sub.name.startswith('.'):
            photos = []
            for f in sorted(sub.iterdir()):
                if f.suffix.lower() in exts:
                    rel = f.relative_to(gec.EQ_PHOTOS)
                    photos.append({"stem": f.stem, "url": f"/api/eq-photo/{rel.as_posix()}", "path": str(f)})
            if photos:
                cats.append({"name": sub.name, "photos": photos})
    # Fichiers à la racine Equipment/ (sans sous-dossier)
    root_photos = []
    for f in sorted(gec.EQ_PHOTOS.iterdir()):
        if f.is_file() and not f.name.startswith('.') and f.suffix.lower() in exts:
            root_photos.append({"stem": f.stem, "url": f"/api/eq-photo/{f.name}", "path": str(f)})
    if root_photos:
        cats.insert(0, {"name": "Autres", "photos": root_photos})
    return jsonify({"categories": cats})


@app.route("/api/equipment-photos")
def api_equipment_photos():
    """
    Retourne les variantes de photos disponibles pour brand+reference+category.
    Query params : brand, reference, category
    Réponse : { "variants": [{"name": "ZerodeG3black", "url": "/api/eq-photo/Frame/ZerodeG3black.webp"}, ...] }
    """
    import generate_equipment_card as gec
    brand     = request.args.get("brand", "")
    reference = request.args.get("reference", "")
    category  = request.args.get("category", "")
    variants  = gec.find_eq_photo_variants(brand, reference, category)
    result = []
    for p in variants:
        # URL relative pour servir le fichier
        rel = p.relative_to(gec.EQ_PHOTOS)
        result.append({
            "name": p.stem,
            "url":  f"/api/eq-photo/{rel.as_posix()}",
            "path": str(p),
        })
    return jsonify({"variants": result})


@app.route("/api/eq-photo/<path:subpath>")
def api_eq_photo(subpath):
    """Sert une photo produit depuis Equipment/."""
    import generate_equipment_card as gec
    from flask import send_from_directory
    photo_dir = str(gec.EQ_PHOTOS)
    return send_from_directory(photo_dir, subpath)


@app.route("/api/generate-eq-card", methods=["POST"])
def api_generate_eq_card():
    """Génère une carte visuelle pour un item d'équipement."""
    try:
        import generate_equipment_card as gec
        data       = request.get_json()
        category   = data.get("category",   "")
        brand      = data.get("brand",      "")
        reference  = data.get("reference",  "")
        details    = data.get("details",    "")
        photo_path_str = data.get("photo_path", "")
        zoom       = float(data.get("zoom",    100)) / 100.0
        photo_x    = int(data.get("photo_x",   0))
        photo_y    = int(data.get("photo_y",   0))
        panel_y_raw = data.get("panel_y")
        panel_y    = int(panel_y_raw) if panel_y_raw else None
        text_x     = int(data.get("text_x",    0))
        text_y     = int(data.get("text_y",    0))
        use_v2     = bool(data.get("use_v2",   False))
        show_brand     = bool(data.get("show_brand",     True))
        show_reference = bool(data.get("show_reference", True))
        show_details   = bool(data.get("show_details",   True))
        show_logo      = bool(data.get("show_logo",      False))
        logo_h_raw     = int(data.get("logo_h", 60))
        logo_y_raw     = int(data.get("logo_y", 1200))
        logo_x_raw     = int(data.get("logo_x", -1))
        logo_x         = None if logo_x_raw < 0 else logo_x_raw
        show_rider_badge = bool(data.get("show_rider_badge", False))
        rider_instagram  = str(data.get("rider_instagram", "") or "").lstrip("@")
        badge_radius     = int(data.get("badge_radius", 58))
        raw_bg         = data.get("photo_bg", [255, 255, 255])
        photo_bg       = tuple(int(v) for v in raw_bg[:3]) if raw_bg else (255, 255, 255)
        fonts      = gec.load_eq_fonts()
        photo_path = Path(photo_path_str) if photo_path_str else None
        card       = gec.generate_equipment_card(
            category, brand, reference, details,
            fonts=fonts, photo_path=photo_path,
            zoom=zoom, photo_x=photo_x, photo_y=photo_y,
            panel_y=panel_y, text_x=text_x, text_y=text_y,
            show_brand=show_brand, show_reference=show_reference,
            show_details=show_details, show_logo=show_logo,
            logo_h=logo_h_raw, logo_y=logo_y_raw, logo_x=logo_x,
            photo_bg=photo_bg, use_v2=use_v2,
            show_rider_badge=show_rider_badge,
            rider_instagram=rider_instagram,
            badge_radius=badge_radius,
        )
        buf = io.BytesIO()
        card.save(buf, "PNG")   # PNG pour conserver la transparence
        buf.seek(0)
        fname = f"{brand}_{reference or category}".replace(" ", "_") + ".png"
        return send_file(buf, mimetype="image/png", download_name=fname)
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/generate-eq-reel", methods=["POST"])
def api_generate_eq_reel():
    """Génère un MP4 animé depuis une liste d'items (chacun avec ses params de carte)."""
    try:
        import generate_equipment_card as gec
        data             = request.get_json()
        items            = data.get("items", [])
        dur_per_card     = float(data.get("dur_per_card",  3.0))
        crossfade        = float(data.get("crossfade",     0.5))
        show_rider_badge = bool(data.get("show_rider_badge", True))
        badge_rider_ig   = data.get("badge_rider_ig", "")
        badge_radius     = int(data.get("badge_radius", 58))
        export_format    = data.get("export_format", "reel")
        audio_data       = data.get("audio") or {}
        transition_sfx   = str(data.get("transition_sfx") or "").strip()
        transition_sfx_volume = max(0.0, min(1.5, float(data.get("transition_sfx_volume", 0.8) or 0.8)))

        if not items:
            return jsonify({"error": "Aucun item"}), 400

        fonts = gec.load_eq_fonts()

        # Composite + badge + encode
        import tempfile, subprocess, shutil
        tmpdir = Path(tempfile.mkdtemp())
        ffmpeg_bin = shutil.which("ffmpeg") or next(
            (p for p in ["/opt/homebrew/bin/ffmpeg","/usr/local/bin/ffmpeg","/usr/bin/ffmpeg"]
             if Path(p).exists()), None)
        if not ffmpeg_bin:
            return jsonify({"error": "ffmpeg introuvable. brew install ffmpeg"}), 500

        BG = (20, 20, 20)
        png_paths = []
        import base64

        def _composite_to_rgb(card_rgba, cp=None, is_sel=False,
                              rider_ig="", show_badge=False):
            """Compose la carte RGBA sur fond sombre → RGB propre, sans double stroke."""
            # alpha_composite respecte l'alpha de la carte (coins arrondis sans artefact)
            bg = gec.Image.new("RGBA", (gec.W, gec.H), (*BG, 255))
            bg = gec.Image.alpha_composite(bg, card_rgba)
            result = bg.convert("RGB")
            if is_sel and show_badge and rider_ig:
                rp = gec.find_rider_photo(rider_ig)
                if rp:
                    result_rgba = result.convert("RGBA")
                    panel_y = (cp or {}).get("panel_y")
                    panel_y = int(panel_y) if panel_y else None
                    result_rgba = gec.draw_rider_badge(result_rgba, rp, panel_y,
                                                       badge_radius=badge_radius,
                                                       instagram=rider_ig)
                    result = result_rgba.convert("RGB")
            return result

        for i, item in enumerate(items):
            b64 = item.get("prerendered_b64")
            if b64:
                img_bytes = base64.b64decode(b64)
                frame_img = gec.Image.open(io.BytesIO(img_bytes)).convert("RGB")
            else:
                cp        = item.get("card_params", {}) or {}
                photo_str = item.get("photo_path", "")
                is_sel    = bool(item.get("is_selection", False))
                rider_ig  = item.get("rider_instagram", "") or badge_rider_ig
                card = gec.generate_equipment_card(
                    category   = cp.get("category",  ""),
                    brand      = cp.get("brand",     ""),
                    reference  = cp.get("reference", ""),
                    details    = cp.get("details",   ""),
                    fonts      = fonts,
                    photo_path = Path(photo_str) if photo_str else None,
                    zoom       = float(cp.get("zoom",    100)) / 100.0,
                    photo_x    = int(cp.get("photo_x",   0)),
                    photo_y    = int(cp.get("photo_y",   0)),
                    panel_y    = int(cp["panel_y"]) if cp.get("panel_y") else None,
                    text_x     = int(cp.get("text_x",    0)),
                    text_y     = int(cp.get("text_y",    0)),
                    show_brand     = bool(cp.get("show_brand",     True)),
                    show_reference = bool(cp.get("show_reference", True)),
                    show_details   = bool(cp.get("show_details",   True)),
                    show_logo      = bool(cp.get("show_logo",      False)),
                    photo_bg       = tuple(int(v) for v in (cp.get("photo_bg") or [255,255,255])[:3]),
                    use_v2         = bool(cp.get("use_v2", False)),
                )
                frame_img = _composite_to_rgb(card, cp, is_sel, rider_ig, show_rider_badge)
            # Normalise toutes les frames à la même taille (rider=1080×1350, equip=970×1250)
            if frame_img.size != (gec.W, gec.H):
                frame_img = frame_img.resize((gec.W, gec.H), gec.Image.LANCZOS)
            p = tmpdir / f"frame_{i:04d}.png"
            frame_img.save(p, "PNG")
            png_paths.append(p)

        n   = len(png_paths)
        dur = dur_per_card
        video_output = tmpdir / "reel_video.mp4"
        output = tmpdir / "reel.mp4"
        size_map = {
            "reel":   (1080, 1920),
            "story":  (1080, 1920),
            "square": (1080, 1080),
            "source": (gec.W, gec.H),
        }
        out_w, out_h = size_map.get(export_format, (1080, 1920))
        vf_single = (
            f"scale={out_w}:{out_h}:force_original_aspect_ratio=decrease,"
            f"pad={out_w}:{out_h}:(ow-iw)/2:(oh-ih)/2:color=0x141414,"
            "format=yuv420p"
        )

        if n == 1:
            cmd = ["ffmpeg","-y","-r","30","-loop","1","-t",str(dur),"-i",str(png_paths[0]),
                   "-vf", vf_single,
                   "-c:v","libx264","-r","30",str(video_output)]
        else:
            inputs = []
            for p in png_paths:
                inputs += ["-r","30","-loop","1","-t",str(dur + crossfade),"-i",str(p)]
            # format=yuv420p sur chaque input (les PNG sont RGBA, xfade ne supporte pas RGBA)
            fmt_parts = [
                f"[{i}:v]scale={out_w}:{out_h}:force_original_aspect_ratio=decrease,"
                f"pad={out_w}:{out_h}:(ow-iw)/2:(oh-ih)/2:color=0x141414,format=yuv420p[f{i}]"
                for i in range(n)
            ]
            xfade_parts, prev = [], "[f0]"
            for i in range(1, n):
                out_lbl = f"[x{i}]" if i < n-1 else "[vout]"
                offset  = round(i * (dur - crossfade), 3)
                xfade_parts.append(f"{prev}[f{i}]xfade=transition=fade:duration={crossfade}:offset={offset}{out_lbl}")
                prev = out_lbl
            fc = ";".join(fmt_parts + xfade_parts)
            cmd = ["ffmpeg","-y"] + inputs + [
                "-filter_complex", fc,
                "-map","[vout]","-c:v","libx264","-r","30",str(video_output)]

        cmd[0] = ffmpeg_bin
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode()[-600:])

        total_duration = dur if n == 1 else max(0.5, n * dur - (n - 1) * crossfade)
        audio_tracks = []
        audio_b64 = audio_data.get("b64") if isinstance(audio_data, dict) else ""
        if audio_b64:
            if len(audio_b64) > 70_000_000:
                return jsonify({"error": "Audio trop lourd"}), 400
            raw_audio = base64.b64decode(audio_b64.split(",")[-1])
            mime = str(audio_data.get("mime") or "").lower()
            ext = ".mp3"
            if "wav" in mime:
                ext = ".wav"
            elif "mp4" in mime or "m4a" in mime or "aac" in mime:
                ext = ".m4a"
            elif "ogg" in mime:
                ext = ".ogg"
            audio_path = tmpdir / f"audio{ext}"
            audio_path.write_bytes(raw_audio)
            volume = max(0.0, min(1.5, float(audio_data.get("volume", 0.75) or 0.75)))
            fade_out = max(0.0, total_duration - 0.6)
            audio_tracks.append({
                "path": audio_path,
                "loop": True,
                "filter": f"volume={volume},afade=t=in:st=0:d=0.25,afade=t=out:st={fade_out:.3f}:d=0.45",
            })

        if transition_sfx and n > 1:
            safe_sfx = "".join(c for c in transition_sfx if c.isalnum() or c == "_")
            sfx_path = Path(__file__).resolve().parent / "assets" / "sfx" / f"{safe_sfx}.wav"
            if not safe_sfx or not sfx_path.exists():
                return jsonify({"error": "Effet sonore introuvable"}), 400
            import array, sys, wave
            with wave.open(str(sfx_path), "rb") as src:
                if src.getnchannels() != 1 or src.getsampwidth() != 2:
                    return jsonify({"error": "Format SFX non supporté"}), 400
                sample_rate = src.getframerate()
                samples = array.array("h")
                samples.frombytes(src.readframes(src.getnframes()))
                if sys.byteorder != "little":
                    samples.byteswap()
            total_frames = int(total_duration * sample_rate) + len(samples) + 1
            mix = array.array("h", [0]) * total_frames
            transition_step = max(0.1, dur - crossfade)
            for idx in range(1, n):
                start = int(idx * transition_step * sample_rate)
                for j, sample in enumerate(samples):
                    pos = start + j
                    if pos >= len(mix):
                        break
                    value = mix[pos] + int(sample * transition_sfx_volume)
                    mix[pos] = max(-32768, min(32767, value))
            sfx_mix_path = tmpdir / "transition_sfx.wav"
            with wave.open(str(sfx_mix_path), "wb") as dst:
                dst.setnchannels(1)
                dst.setsampwidth(2)
                dst.setframerate(sample_rate)
                dst.writeframes(mix.tobytes())
            audio_tracks.append({
                "path": sfx_mix_path,
                "loop": False,
                "filter": "anull",
            })

        if audio_tracks:
            mux_cmd = [
                ffmpeg_bin, "-y",
                "-i", str(video_output),
            ]
            for track in audio_tracks:
                if track["loop"]:
                    mux_cmd += ["-stream_loop", "-1"]
                mux_cmd += ["-i", str(track["path"])]
            filter_parts = []
            labels = []
            for idx, track in enumerate(audio_tracks, start=1):
                label = f"a{idx}"
                filter_parts.append(f"[{idx}:a]{track['filter']}[{label}]")
                labels.append(f"[{label}]")
            if len(labels) == 1:
                filter_parts.append(f"{labels[0]}anull[aout]")
            else:
                filter_parts.append("".join(labels) + f"amix=inputs={len(labels)}:duration=first:dropout_transition=0[aout]")
            mux_cmd += [
                "-t", f"{total_duration:.3f}",
                "-filter_complex", ";".join(filter_parts),
                "-map", "0:v:0", "-map", "[aout]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-shortest", str(output),
            ]
            result = subprocess.run(mux_cmd, capture_output=True, timeout=120)
            if result.returncode != 0:
                raise RuntimeError(result.stderr.decode()[-600:])
        else:
            output = video_output

        buf = io.BytesIO(output.read_bytes())
        return send_file(buf, mimetype="video/mp4", download_name="reel_equipment.mp4")
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/equipment-audit")
def api_equipment_audit():
    """Audit croisé : pour chaque rider, vérifie données Sheet + photo dossier."""
    import generate_equipment_card as _gec
    eq  = get_equipment()
    _, _, profiles = get_engine()

    rows = []
    for p in profiles:
        handle = (p.get("instagram") or "").lstrip("@").lower()
        rider_eq = eq.get(handle, {})
        cats = {}
        for cat in gc.EQUIPMENT_COLUMNS:
            item = rider_eq.get(cat)
            if not item:
                cats[cat] = "empty"           # pas de données
            else:
                brand = item.get("brand", "")
                ref   = item.get("reference", "")
                if _gec.find_eq_photo_variants(brand, ref, cat):
                    cats[cat] = "ok"          # données + photo
                else:
                    cats[cat] = "no_photo"    # données mais pas de photo
        rows.append({
            "prenom":    p.get("prenom", ""),
            "nom":       p.get("nom", ""),
            "genre":     p.get("genre", ""),
            "instagram": p.get("instagram", ""),
            "cats":      cats,
        })

    return jsonify({
        "columns": gc.EQUIPMENT_COLUMNS,
        "rows":    rows,
    })


@app.route("/api/equipment-all")
def api_equipment_all():
    """Retourne l'équipement complet de tous les riders (pour la page Equipment)."""
    eq = get_equipment()
    _, _, profiles = get_engine()
    result = []
    for p in profiles:
        handle = (p.get("instagram") or "").lstrip("@").lower()
        rider_eq = eq.get(handle, {})
        items = {}
        for cat in gc.EQUIPMENT_COLUMNS:
            item = rider_eq.get(cat)
            items[cat] = {
                "brand":     item["brand"],
                "reference": item["reference"],
                "details":   item["details"],
            } if item else None
        result.append({
            "prenom":    p.get("prenom", ""),
            "nom":       p.get("nom", ""),
            "genre":     p.get("genre", ""),
            "instagram": p.get("instagram", ""),
            "equipment": items,
        })
    return jsonify(result)


def _scan_eq_variants():
    """Scanne le dossier Equipment/ et retourne la liste des variantes photos."""
    import generate_equipment_card as gec
    variants = []
    if gec.EQ_PHOTOS.exists():
        exts = {".jpg", ".jpeg", ".png", ".webp"}
        for f in sorted(gec.EQ_PHOTOS.rglob("*")):
            if f.is_file() and f.suffix.lower() in exts:
                rel    = f.relative_to(gec.EQ_PHOTOS)
                folder = rel.parts[0] if len(rel.parts) > 1 else ""
                variants.append({
                    "name":      f.stem,
                    "url":       f"/api/eq-photo/{rel.as_posix()}",
                    "path":      str(f),
                    "folder":    folder,
                    "stem_slug": gec._eq_slug(f.stem),
                })
    return variants


@app.route("/api/rescan-eq-photos", methods=["POST"])
def api_rescan_eq_photos():
    """Rescanne le dossier Equipment/ sans redémarrer l'app."""
    import generate_equipment_card as gec
    variants = _scan_eq_variants()
    return jsonify({
        "eq_variants":      variants,
        "category_folders": gec.CATEGORY_FOLDERS,
        "count":            len(variants),
    })


@app.route("/api/preload")
def api_preload():
    """Retourne TOUT en un seul appel : profils, équipements, sponsors."""
    _, _, profiles = get_engine()
    eq = get_equipment()
    results = get_results_2026()
    brand_tags = get_brand_tags()
    context_tags = get_context_tags()

    # ── Profils complets ──
    full_profiles = []
    for p in profiles:
        slug = f"{p['nom'].lower().replace(' ','_')}_{p['prenom'].lower()}"
        full_profiles.append({
            "slug":         slug,
            "prenom":       p.get("prenom", ""),
            "nom":          p.get("nom", ""),
            "genre":        p.get("genre", ""),
            "has_photo":    gc.find_photo(p) is not None,
            "nationality":  p.get("nationalite", ""),   # clé interne = "nationalite"
            "hometown":     p.get("ville", ""),           # clé interne = "ville"
            "age":          p.get("age", ""),
            "achievements": p.get("palmares", ""),        # clé interne = "palmares"
            "team":         p.get("team", ""),
            "instagram":    p.get("instagram", ""),
            "sponsors":     p.get("sponsors", []),
        })

    # ── Équipements indexés par handle ──
    eq_by_handle = {}
    for p in profiles:
        handle = (p.get("instagram") or "").lstrip("@").lower()
        rider_eq = eq.get(handle, {})
        items = []
        for cat in gc.EQUIPMENT_COLUMNS:
            item = rider_eq.get(cat)
            if item:
                items.append({
                    "category":  cat,
                    "brand":     item["brand"],
                    "reference": item["reference"],
                    "details":   item["details"],
                    "raw":       item["raw"],
                })
        eq_by_handle[handle] = items

    # ── Sponsors ──
    import generate_equipment_card as gec
    seen_stems = _scan_logos()
    sponsors = []
    for stem, f in sorted(seen_stems.items()):
        key = next((k for k, v in gc.BRAND_MAP.items() if v == f.name), f.stem)
        sponsors.append({"key": key, "file": f.name, "label": f.stem.upper(), "url": f"/logos/{f.name}"})

    # ── Variantes photos équipement (liste plate avec dossier + slug) ──
    eq_variants = _scan_eq_variants()

    return jsonify({
        "profiles":         full_profiles,
        "equipment":        eq_by_handle,
        "results":          results,
        "brand_tags":       brand_tags,
        "context_tags":     context_tags,
        "sponsors":         sponsors,
        "eq_variants":      eq_variants,
        "category_folders": gec.CATEGORY_FOLDERS,
    })


@app.route("/api/performance-results")
def api_performance_results():
    """Retourne les résultats 2026, avec refresh optionnel du cache Google Sheet."""
    if request.args.get("refresh") == "1":
        _cache.pop("results_2026", None)
    return jsonify({"results": get_results_2026()})


def _sheet_column_name(index):
    """Convertit un index de colonne zéro-based en notation A1."""
    value = int(index) + 1
    letters = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _google_sheets_access_token():
    if not _GOOGLE_TOKEN_FILE.exists():
        raise PermissionError("Reconnecte Google depuis Dashboard → Connections pour autoriser Google Sheets.")
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request as GoogleAuthRequest
    except ImportError as exc:
        raise RuntimeError("Dépendances Google OAuth manquantes.") from exc

    token_data = _json.loads(_GOOGLE_TOKEN_FILE.read_text())
    granted = set(token_data.get("scopes") or [])
    sheets_scope = "https://www.googleapis.com/auth/spreadsheets"
    if sheets_scope not in granted:
        raise PermissionError("Reconnecte Google pour autoriser l’écriture dans Google Sheets.")

    credentials = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri") or "https://oauth2.googleapis.com/token",
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
        scopes=list(granted),
    )
    if credentials.refresh_token:
        credentials.refresh(GoogleAuthRequest())
        token_data["token"] = credentials.token
        _GOOGLE_TOKEN_FILE.write_text(_json.dumps(token_data, indent=2))
    if not credentials.token:
        raise PermissionError("Jeton Google indisponible. Reconnecte Google.")
    return credentials.token


@app.route("/api/performance/sync-palmares", methods=["POST"])
def api_performance_sync_palmares():
    data = request.get_json(silent=True) or {}
    instagram = str(data.get("instagram") or "").lstrip("@").strip().lower()
    first_name = str(data.get("first_name") or "").strip()
    last_name = str(data.get("last_name") or "").strip()
    palmares = str(data.get("palmares") or "").strip()
    if not palmares or not (instagram or (first_name and last_name)):
        return jsonify({"ok": False, "error": "Rider ou palmarès manquant."}), 400

    sheet_name = "👤 Profils"
    gsheet_id = _active_gsheet_id()
    rows = _fetch_gsheet_rows_for_id(gsheet_id, sheet_name=sheet_name)
    if not rows:
        return jsonify({"ok": False, "error": "Onglet Profils introuvable."}), 404

    header_index = _sheet_header_index(rows)
    headers = [_sheet_header_key(value) for value in rows[header_index]]

    def find_column(*aliases):
        alias_keys = {_sheet_header_key(alias) for alias in aliases}
        return next((idx for idx, key in enumerate(headers) if key in alias_keys), None)

    first_col = find_column("First Name", "Prénom", "Prenom")
    last_col = find_column("Last Name", "Nom")
    instagram_col = find_column("Instagram", "Instagram Handle", "Handle")
    palmares_col = find_column("Achievements", "Palmarès", "Palmares")
    if palmares_col is None:
        return jsonify({"ok": False, "error": "Colonne Achievements/Palmarès introuvable."}), 404

    target_row = None
    for row_index, row in enumerate(rows[header_index + 1:], start=header_index + 1):
        padded = list(row) + [""] * max(0, len(headers) - len(row))
        row_instagram = str(padded[instagram_col] if instagram_col is not None else "").lstrip("@").strip().lower()
        same_handle = bool(instagram and row_instagram and instagram == row_instagram)
        same_name = (
            first_col is not None and last_col is not None
            and _norm_match_name(padded[first_col]) == _norm_match_name(first_name)
            and _norm_match_name(padded[last_col]) == _norm_match_name(last_name)
        )
        if same_handle or same_name:
            target_row = row_index + 1
            break
    if target_row is None:
        return jsonify({"ok": False, "error": "Rider introuvable dans l’onglet Profils."}), 404

    cell = f"'{sheet_name}'!{_sheet_column_name(palmares_col)}{target_row}"
    import urllib.parse as _urlparse
    import urllib.request as _urlrequest
    import urllib.error as _urlerror
    try:
        access_token = _google_sheets_access_token()
        encoded_range = _urlparse.quote(cell, safe="")
        url = (
            f"https://sheets.googleapis.com/v4/spreadsheets/{gsheet_id}/values/{encoded_range}"
            "?valueInputOption=RAW"
        )
        body = _json.dumps({"range": cell, "majorDimension": "ROWS", "values": [[palmares]]}).encode("utf-8")
        update_request = _urlrequest.Request(
            url,
            data=body,
            method="PUT",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        )
        with _urlrequest.urlopen(update_request, timeout=20) as response:
            update_result = _json.loads(response.read().decode("utf-8"))
    except PermissionError as exc:
        return jsonify({"ok": False, "code": "google_reconnect", "error": str(exc)}), 401
    except _urlerror.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return jsonify({"ok": False, "error": f"Google Sheets HTTP {exc.code}: {detail[:300]}"}), 502
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502

    _, _, profiles = get_engine()
    for profile in profiles:
        profile_handle = str(profile.get("instagram") or "").lstrip("@").strip().lower()
        if (instagram and profile_handle == instagram) or (
            _norm_match_name(profile.get("prenom")) == _norm_match_name(first_name)
            and _norm_match_name(profile.get("nom")) == _norm_match_name(last_name)
        ):
            profile["palmares"] = palmares
            break
    return jsonify({"ok": True, "cell": cell, "updated_range": update_result.get("updatedRange", cell)})


@app.route("/api/brand-tags")
def api_brand_tags():
    """Retourne les handles marques et tags contextuels depuis Google Sheet."""
    if request.args.get("refresh") == "1":
        _cache.pop("brand_tags", None)
        _cache.pop("context_tags", None)
    return jsonify({
        "brand_tags": get_brand_tags(),
        "context_tags": get_context_tags(),
    })

@app.route("/api/settings/google-sheet")
def api_settings_google_sheet():
    settings = _load_app_settings()
    active_id = _active_gsheet_id()
    return jsonify({
        "active_id": active_id,
        "active_url": _active_gsheet_url(),
        "default_id": _DEFAULT_GSHEET_ID,
        "source": "settings" if settings.get("gsheet_id") else "config",
    })

@app.route("/api/settings/google-sheet", methods=["POST"])
def api_settings_google_sheet_update():
    data = request.get_json(silent=True) or {}
    settings = _load_app_settings()
    if data.get("reset"):
        settings.pop("gsheet_id", None)
        settings.pop("gsheet_url", None)
    else:
        raw_value = str(data.get("sheet_url") or data.get("sheet_id") or "").strip()
        gsheet_id = _extract_gsheet_id(raw_value)
        if not gsheet_id:
            return jsonify({"ok": False, "error": "Lien ou ID Google Sheet invalide."}), 400
        settings["gsheet_id"] = gsheet_id
        settings["gsheet_url"] = f"https://docs.google.com/spreadsheets/d/{gsheet_id}/edit"
    _save_app_settings(settings)
    _apply_gsheet_settings()
    _cache.clear()
    return jsonify({
        "ok": True,
        "active_id": _active_gsheet_id(),
        "active_url": _active_gsheet_url(),
        "source": "settings" if settings.get("gsheet_id") else "config",
    })

@app.route("/api/settings/google-sheet/test", methods=["POST"])
def api_settings_google_sheet_test():
    data = request.get_json(silent=True) or {}
    raw_value = str(data.get("sheet_url") or data.get("sheet_id") or "").strip()
    gsheet_id = _extract_gsheet_id(raw_value)
    if not gsheet_id:
        return jsonify({"ok": False, "error": "Lien ou ID Google Sheet invalide."}), 400

    specs = [
        {
            "key": "riders",
            "label": "Riders",
            "required_headers": [
                ("First Name", "Prénom", "Prenom"),
                ("Last Name", "Nom"),
                ("Instagram", "Handle"),
                ("Team", "Équipe", "Equipe"),
            ],
            "candidates": [
                {"name": "👤 Profils", "label": "👤 Profils"},
                {"name": "Riders", "label": "Riders"},
                {"name": "🏆 Riders", "label": "🏆 Riders"},
            ],
        },
        {
            "key": "equipment_women",
            "label": "Equipment Women",
            "required_headers": [
                ("G", "Gender", "Genre"),
                ("Instagram", "Handle"),
                ("Frame", "Cadre"),
                ("Fork", "Fourche"),
                ("Tires", "Tyres", "Pneus"),
            ],
            "candidates": [
                {"name": "🔧 Equipment Women", "label": "🔧 Equipment Women"},
                {"name": "Equipment Women", "label": "Equipment Women"},
                {"gid": 455020136, "label": "gid 455020136"},
            ],
        },
        {
            "key": "equipment_men",
            "label": "Equipment Men",
            "required_headers": [
                ("G", "Gender", "Genre"),
                ("Instagram", "Handle"),
                ("Frame", "Cadre"),
                ("Fork", "Fourche"),
                ("Tires", "Tyres", "Pneus"),
            ],
            "candidates": [
                {"name": "🔧 Equipment Men", "label": "🔧 Equipment Men"},
                {"name": "Equipment Men", "label": "Equipment Men"},
                {"gid": 1424770374, "label": "gid 1424770374"},
            ],
        },
        {
            "key": "results_2026",
            "label": "Résultats 2026",
            "required_headers": [
                ("First Name", "Prénom", "Prenom"),
                ("Last Name", "Nom"),
            ],
            "candidates": [
                {"name": "📊 Résultats 2026", "label": "📊 Résultats 2026"},
                {"name": "Résultats 2026", "label": "Résultats 2026"},
                {"gid": 581226329, "label": "gid 581226329"},
            ],
        },
        {
            "key": "brand",
            "label": "Brand",
            "required_headers": [
                ("brand", "marque"),
                ("instagram_handle", "instagram", "handle"),
            ],
            "candidates": [
                {"name": "Brand", "label": "Brand"},
                {"gid": 1345104699, "label": "gid 1345104699"},
            ],
        },
        {
            "key": "tags",
            "label": "Tags",
            "required_headers": [
                ("tag_type", "type"),
                ("name", "nom"),
                ("instagram_handle", "instagram", "handle"),
                ("default_hashtag", "hashtag"),
            ],
            "candidates": [
                {"name": "Tags", "label": "Tags"},
                {"gid": 755371970, "label": "gid 755371970"},
            ],
        },
    ]

    sheets = []
    for spec in specs:
        result = _test_sheet_candidate(gsheet_id, spec["candidates"], spec.get("required_headers", ()))
        sheets.append({
            "key": spec["key"],
            "label": spec["label"],
            **result,
        })
    return jsonify({
        "ok": True,
        "sheet_id": gsheet_id,
        "all_ok": all(sheet["ok"] for sheet in sheets),
        "sheets": sheets,
    })


@app.route("/api/reload", methods=["POST"])
def api_reload():
    reload_engine()
    return jsonify({"ok": True})


@app.route("/api/reload-equipment", methods=["POST"])
def api_reload_equipment():
    """Force le rechargement des données equipment depuis Google Sheets."""
    _cache.pop("equipment", None)
    eq = get_equipment()
    return jsonify({"ok": True, "riders": len(eq)})


# ── Logos Manager ─────────────────────────────────────────────────────────────

import urllib.request, urllib.error, ssl, re, zipfile, tempfile, subprocess, shutil

_logos_ssl = ssl.create_default_context()
_logos_ssl.check_hostname = False
_logos_ssl.verify_mode    = ssl.CERT_NONE

def _logos_fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Referer':    'https://probikeshop.fr/',
        'Accept':     '*/*',
    })
    with urllib.request.urlopen(req, timeout=timeout, context=_logos_ssl) as r:
        return r.read()

def _probikeshop_logos(page_html):
    """Extrait les logos SVG depuis la page marques de probikeshop."""
    CDN = "https://probikeshop.fr/cdn/shop/files/"
    results = []
    seen = set()
    # Cherche les <img src="...cdn/shop/files/xxx-logo.yyy" alt="BRAND">
    for m in re.finditer(
        r'<img[^>]+src=["\']([^"\']*cdn/shop/files/[^"\']*-logo[^"\']*)["\'][^>]*alt=["\']([^"\']+)["\']',
        page_html, re.IGNORECASE
    ):
        src, alt = m.group(1), m.group(2).strip()
        # aussi l'ordre inversé (alt avant src)
        if not src or not alt:
            continue
        file_with_qs = src.split('/')[-1]
        file_name    = file_with_qs.split('?')[0]
        if not file_name or file_name in seen:
            continue
        # Filtrer les icônes non-marques
        if any(x in alt for x in ['Probikeshop','Livraison','Paiement','experts','PBS']):
            continue
        seen.add(file_name)
        # Nom normalisé
        key = alt.lower()
        key = key.replace("100%","100percent").replace("e.thirteen","ethirteen")
        key = re.sub(r"[^a-z0-9]", "", key)
        results.append({"name": key, "label": alt, "file": file_name,
                        "url": CDN + file_name})

    # Aussi alt après src
    for m in re.finditer(
        r'<img[^>]+alt=["\']([^"\']+)["\'][^>]+src=["\']([^"\']*cdn/shop/files/[^"\']*-logo[^"\']*)["\']',
        page_html, re.IGNORECASE
    ):
        alt, src = m.group(1).strip(), m.group(2)
        file_name = src.split('/')[-1].split('?')[0]
        if not file_name or file_name in seen:
            continue
        if any(x in alt for x in ['Probikeshop','Livraison','Paiement','experts','PBS']):
            continue
        seen.add(file_name)
        key = alt.lower()
        key = key.replace("100%","100percent").replace("e.thirteen","ethirteen")
        key = re.sub(r"[^a-z0-9]", "", key)
        results.append({"name": key, "label": alt, "file": file_name,
                        "url": CDN + file_name})
    return results

def _generic_logos(page_html, base_url):
    """Extrait les logos depuis une page générique (cherche les <img> dans header/nav)."""
    results = []
    seen = set()
    for m in re.finditer(
        r'<img[^>]+src=["\']([^"\']+\.(svg|png|webp))["\'][^>]*(?:alt=["\']([^"\']*)["\'])?',
        page_html, re.IGNORECASE
    ):
        src, ext, alt = m.group(1), m.group(2), (m.group(3) or "").strip()
        if not src or src in seen:
            continue
        seen.add(src)
        # Reconstituer l'URL absolue si relative
        if src.startswith('//'):
            src = 'https:' + src
        elif src.startswith('/'):
            from urllib.parse import urlparse
            p = urlparse(base_url)
            src = f"{p.scheme}://{p.netloc}{src}"
        file_name = src.split('/')[-1].split('?')[0]
        key = alt or file_name.rsplit('.',1)[0]
        key = re.sub(r"[^a-z0-9]", "", key.lower()) or "logo"
        results.append({"name": key, "label": alt or file_name, "file": file_name, "url": src})
    return results[:200]

def _svg_to_png(svg_bytes, out_path, size=400):
    """Convertit SVG → PNG via qlmanage (macOS built-in)."""
    with tempfile.TemporaryDirectory() as tmp:
        svg_file = Path(tmp) / "logo.svg"
        svg_file.write_bytes(svg_bytes)
        result = subprocess.run(
            ["qlmanage", "-t", "-s", str(size), "-o", tmp, str(svg_file)],
            capture_output=True, timeout=15
        )
        pngs = list(Path(tmp).glob("*.png"))
        if pngs:
            shutil.copy(str(pngs[0]), str(out_path))
            return True
    return False


def _count_supported_files(folder: Path, suffixes: set[str]) -> int:
    try:
        return sum(
            1 for f in folder.iterdir()
            if f.is_file() and f.suffix.lower() in suffixes
        )
    except Exception:
        return 0


def _browse_folder_or_default(prompt: str, default_folder: Path, suffixes: set[str]):
    """
    Ouvre un dialogue natif uniquement quand l'environnement le permet.
    Sinon, retourne le dossier par défaut du projet.

    Important: en mode web distant, un sélecteur natif côté serveur ne peut pas
    viser le disque local du navigateur. Le fallback par défaut évite de bloquer
    le dashboard sur Linux/VPS.
    """
    default_folder = Path(default_folder)
    default_folder.mkdir(parents=True, exist_ok=True)

    native_available = sys.platform == "darwin"
    if native_available:
        try:
            import shutil
            import subprocess

            if shutil.which("osascript"):
                script = (
                    f'set defaultFolder to POSIX file "{default_folder}" as alias\n'
                    f'POSIX path of (choose folder with prompt "{prompt}" '
                    f'default location defaultFolder)'
                )
                result = subprocess.run(
                    ["osascript", "-e", script],
                    capture_output=True, text=True, timeout=60
                )
                if result.returncode == 0:
                    folder = (result.stdout or "").strip()
                    if folder:
                        chosen = Path(folder)
                        return {
                            "ok": True,
                            "path": folder,
                            "count": _count_supported_files(chosen, suffixes),
                            "source": "native",
                            "native_dialog": True,
                        }

                err = (result.stderr or "").strip()
                if "User canceled" in err or "cancelled" in err.lower():
                    return {"ok": False, "error": "Annulé"}
        except Exception as e:
            # Si le dialogue natif échoue, on retombe sur le dossier du projet.
            fallback_note = str(e)
        else:
            fallback_note = ""
    else:
        fallback_note = ""

    return {
        "ok": True,
        "path": str(default_folder),
        "count": _count_supported_files(default_folder, suffixes),
        "source": "default",
        "native_dialog": False,
        "message": "Dialogue natif indisponible, dossier par défaut utilisé",
        **({"note": fallback_note} if fallback_note else {}),
    }

@app.route("/api/logos/browse-folder")
def api_logos_browse_folder():
    """Sélectionne un dossier logos, avec fallback vers le dossier du projet."""
    try:
        return jsonify(_browse_folder_or_default(
            "Choisir le dossier logos",
            BASE_DIR / "logos",
            {".png", ".svg", ".jpg", ".jpeg", ".webp"},
        ))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/logos/scan")
def api_logos_scan():
    logos_dir = BASE_DIR / "logos"
    logos_dir.mkdir(exist_ok=True)
    existing = {f.stem.lower() for f in logos_dir.iterdir()
                if f.suffix.lower() in ('.png','.svg','.jpg','.webp')}
    return jsonify({"ok": True, "existing": list(existing)})

@app.route("/api/logos/scrape", methods=["POST"])
def api_logos_scrape():
    data   = request.get_json() or {}
    url    = (data.get("url") or "").strip()
    folder = (data.get("folder") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "URL manquante"})

    # Récupère la page
    try:
        html = _logos_fetch(url).decode("utf-8", errors="replace")
    except Exception as e:
        return jsonify({"ok": False, "error": f"Impossible de charger la page : {e}"})

    # Parse selon la source
    if "probikeshop.fr" in url:
        logos = _probikeshop_logos(html)
    else:
        logos = _generic_logos(html, url)

    if not logos:
        return jsonify({"ok": False, "error": "Aucun logo trouvé sur cette page"})

    # Compare avec logos existants dans le dossier choisi
    logos_dir = Path(folder) if folder else BASE_DIR / "logos"
    logos_dir.mkdir(parents=True, exist_ok=True)
    existing = {f.stem.lower() for f in logos_dir.iterdir()
                if f.suffix.lower() in ('.png','.svg','.jpg','.webp')}

    for l in logos:
        l["exists"]      = l["name"] in existing
        l["preview_url"] = l["url"]  # aperçu direct depuis CDN

    return jsonify({"ok": True, "logos": logos, "total": len(logos),
                    "existing": sum(1 for l in logos if l["exists"])})

@app.route("/api/logos/download-zip", methods=["POST"])
def api_logos_download_zip():
    data   = request.get_json() or {}
    logos  = data.get("logos", [])
    folder = (data.get("folder") or "").strip()
    if not logos:
        return jsonify({"ok": False, "error": "Aucun logo sélectionné"})

    logos_dir = Path(folder) if folder else BASE_DIR / "logos"
    logos_dir.mkdir(parents=True, exist_ok=True)

    zip_buf = io.BytesIO()
    ok = fail = 0

    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in logos:
            name = re.sub(r"[^a-z0-9]", "", (item.get("name") or "logo").lower())
            url  = item.get("url", "")
            file = item.get("file", "")
            if not url or not name:
                continue

            try:
                raw = _logos_fetch(url)
            except Exception:
                fail += 1
                continue

            is_svg = file.lower().endswith(".svg") or raw[:200].lstrip().startswith(b"<")
            out_png = logos_dir / f"{name}.png"

            if is_svg:
                # Essaie de convertir en PNG via qlmanage
                converted = False
                try:
                    converted = _svg_to_png(raw, out_png)
                except Exception:
                    pass

                if converted and out_png.exists():
                    zf.write(str(out_png), f"{name}.png")
                    ok += 1
                else:
                    # Fallback : garder le SVG dans le ZIP
                    svg_path = logos_dir / f"{name}.svg"
                    svg_path.write_bytes(raw)
                    zf.write(str(svg_path), f"{name}.svg")
                    ok += 1
            else:
                out_png.write_bytes(raw)
                zf.write(str(out_png), f"{name}.png")
                ok += 1

    zip_buf.seek(0)
    return send_file(
        zip_buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name="logos_freeride.zip"
    )


# ── Riders Manager ────────────────────────────────────────────────────────────

def _riders_find_photo(handle: str, search_dir: Path):
    """Fuzzy-match un handle Instagram dans un dossier. Retourne (Path|None, str|None)."""
    if not search_dir.exists():
        return None, None
    h = handle.lstrip("@").lower()
    h_strip = h.replace(".", "").replace("-", "").replace("_", "")
    # Match exact avec ou sans @
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        for stem in (f"@{h}", h):
            p = search_dir / (stem + ext)
            if p.exists():
                return p, p.name
    # Fuzzy match sur tous les fichiers
    for f in sorted(search_dir.iterdir()):
        if f.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue
        stem = f.stem.lower().lstrip("@")
        stem_s = stem.replace(".", "").replace("-", "").replace("_", "").replace(" ", "")
        if h in stem or stem in h:
            return f, f.name
        if h_strip and (h_strip in stem_s or stem_s in h_strip):
            return f, f.name
    return None, None


def _riders_load_csv():
    """Charge les handles riders depuis la source active, avec fallback CSV historique."""
    try:
        _, _, profiles = get_engine()
        handles = []
        seen = set()
        for p in profiles:
            ig = (p.get("instagram") or "").strip()
            key = ig.lstrip("@").lower()
            if ig and key not in seen:
                handles.append(ig)
                seen.add(key)
        if handles:
            return handles
    except Exception:
        pass

    riders = []
    seen = set()
    for fname in ("equipment_men.csv", "equipment_women.csv"):
        p = BASE_DIR / fname
        if not p.exists():
            continue
        import csv as _csv
        with open(p, newline="", encoding="utf-8") as f:
            for row in _csv.DictReader(f):
                ig = (row.get("Instagram") or "").strip()
                key = ig.lstrip("@").lower()
                if ig and key not in seen:
                    riders.append(ig)
                    seen.add(key)
    return riders

def _riders_display_name(handle):
    key = str(handle or "").lstrip("@").lower()
    try:
        _, _, profiles = get_engine()
        profile = next((p for p in profiles if (p.get("instagram") or "").lstrip("@").lower() == key), None)
        if profile:
            return f"{profile.get('prenom', '')} {profile.get('nom', '')}".strip() or key.replace("_", " ").title()
    except Exception:
        pass
    return key.replace("_", " ").title()


@app.route("/api/riders/browse-folder")
def api_riders_browse_folder():
    rtype = request.args.get("type", "pp")  # 'pp' ou 'pic'
    default_sub = "PPRiders" if rtype == "pp" else "PictureRiders"
    label = "portraits (PPRiders)" if rtype == "pp" else "photos action (PictureRiders)"
    try:
        return jsonify(_browse_folder_or_default(
            f"Choisir le dossier {label}",
            BASE_DIR / default_sub,
            {".jpg", ".jpeg", ".png", ".webp"},
        ))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/riders/scan-photos", methods=["POST"])
def api_riders_scan_photos():
    data       = request.get_json() or {}
    pp_folder  = (data.get("pp_folder")  or "").strip()
    pic_folder = (data.get("pic_folder") or "").strip()

    pp_dir  = Path(pp_folder)  if pp_folder  else BASE_DIR / "PPRiders"
    pic_dir = Path(pic_folder) if pic_folder else BASE_DIR / "PictureRiders"

    handles = _riders_load_csv()
    if not handles:
        return jsonify({"ok": False, "error": "Aucun rider trouvé dans les CSV"})

    result = []
    for ig in handles:
        pp_path,  pp_file  = _riders_find_photo(ig, pp_dir)
        pic_path, pic_file = _riders_find_photo(ig, pic_dir)
        display = _riders_display_name(ig)
        result.append({
            "instagram":   ig,
            "display_name": display,
            "pp_found":    pp_path is not None,
            "pp_path":     str(pp_path)  if pp_path  else "",
            "pp_file":     pp_file       or "",
            "pic_found":   pic_path is not None,
            "pic_path":    str(pic_path) if pic_path else "",
            "pic_file":    pic_file      or "",
        })

    return jsonify({"ok": True, "riders": result})


@app.route("/api/riders/thumb")
def api_riders_thumb():
    """Sert une miniature depuis un chemin absolu (sécurisé : doit être dans le projet)."""
    path_str = (request.args.get("path") or "").strip()
    if not path_str:
        return ("", 404)
    p = Path(path_str)
    # Sécurité : limité aux dossiers autorisés
    allowed_parents = [
        BASE_DIR / "PPRiders",
        BASE_DIR / "PictureRiders",
        BASE_DIR / "PPRIDERS",
    ]
    try:
        resolved = p.resolve()
        ok = any(str(resolved).startswith(str(par.resolve())) for par in allowed_parents)
        # Accepte aussi les dossiers custom s'ils sont sur le même Mac (sous /Users)
        if not ok and str(resolved).startswith("/Users/"):
            ok = True
    except Exception:
        return ("", 403)
    if not ok or not resolved.exists():
        return ("", 404)
    suffix = resolved.suffix.lower()
    if suffix == ".png":
        mime = "image/png"
    elif suffix == ".webp":
        mime = "image/webp"
    else:
        mime = "image/jpeg"
    return send_file(str(resolved), mimetype=mime)


# ── Instaloader session ───────────────────────────────────────────────────────
_ig_L        = None   # instance instaloader partagée
_ig_username = None   # username connecté (None = anonyme)

def _ig_loader():
    """Retourne l'instance instaloader (charge la session si dispo)."""
    global _ig_L, _ig_username
    import instaloader as _il
    if _ig_L is None:
        _ig_L = _il.Instaloader(
            download_pictures=False, download_videos=False,
            download_video_thumbnails=False, download_geotags=False,
            download_comments=False, save_metadata=False, quiet=True,
        )
        # Charge la 1ère session trouvée dans ~/.config/instaloader/
        session_dir = Path.home() / ".config" / "instaloader"
        if session_dir.exists():
            for f in sorted(session_dir.glob("session-*")):
                uname = f.name[len("session-"):]
                try:
                    _ig_L.load_session_from_file(uname, str(f))
                    _ig_username = uname
                    break
                except Exception:
                    pass
    return _ig_L


def _ig_is_logged_in() -> bool:
    try:
        return bool(_ig_username and _ig_loader().context.is_logged_in)
    except Exception:
        return False


def _ig_fetch_profile_pic_url(handle: str) -> str:
    """Récupère l'URL HD de la PP d'un profil Instagram."""
    import instaloader as _il
    L = _ig_loader()
    profile = _il.Profile.from_username(L.context, handle.lstrip("@"))
    url = profile.profile_pic_url
    if not url:
        raise ValueError("Pas d'URL de photo dans la réponse")
    return url


@app.route("/api/riders/download-pp", methods=["POST"])
def api_riders_download_pp():
    """Télécharge la PP Instagram d'un rider via l'API mobile (sans login)."""
    data   = request.get_json() or {}
    handle = data.get("handle", "").strip().lstrip("@")
    folder = (data.get("pp_folder") or "").strip()
    if not handle:
        return jsonify({"ok": False, "error": "Handle manquant"})

    pp_dir = Path(folder) if folder else BASE_DIR / "PPRiders"
    pp_dir.mkdir(exist_ok=True)

    try:
        pic_url = _ig_fetch_profile_pic_url(handle)

        # Télécharge l'image depuis le CDN
        req = urllib.request.Request(pic_url, headers={
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                          "AppleWebKit/605.1.15",
            "Referer": "https://www.instagram.com/",
        })
        with urllib.request.urlopen(req, context=_logos_ssl, timeout=20) as resp:
            raw = resp.read()

        out_path = pp_dir / f"@{handle}.jpg"
        out_path.write_bytes(raw)
        return jsonify({"ok": True, "handle": handle, "file": out_path.name,
                        "thumb": f"/api/riders/thumb?path={out_path}"})

    except urllib.error.HTTPError as e:
        if e.code == 401:
            return jsonify({"ok": False, "error": "Instagram exige un login — voir README"})
        if e.code == 404:
            return jsonify({"ok": False, "error": f"@{handle} introuvable ou compte privé"})
        if e.code == 429:
            return jsonify({"ok": False, "error": "Rate limit — attends quelques minutes"})
        return jsonify({"ok": False, "error": f"HTTP {e.code}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:150]})


def _ig_shortcode_to_id(shortcode: str) -> int:
    ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    media_id = 0
    for char in shortcode:
        if char in ALPHABET:
            media_id = media_id * 64 + ALPHABET.index(char)
    return media_id


def _ig_extract_images_from_info(info: dict) -> list:
    """Parse la réponse JSON de l'API mobile Instagram."""
    images = []
    item = (info.get("items") or [{}])[0]

    def best_and_thumb(versions):
        cands = (versions or {}).get("candidates") or []
        cands_sorted = sorted(cands, key=lambda c: c.get("width", 0) * c.get("height", 0), reverse=True)
        if not cands_sorted:
            return None, None
        return cands_sorted[0]["url"], cands_sorted[-1]["url"]

    if "carousel_media" in item:
        for i, slide in enumerate(item["carousel_media"]):
            if "image_versions2" in slide:
                full_url, thumb_url = best_and_thumb(slide["image_versions2"])
                if full_url:
                    images.append({"index": i, "full_url": full_url, "thumb_url": thumb_url or full_url})
    elif "image_versions2" in item:
        full_url, thumb_url = best_and_thumb(item["image_versions2"])
        if full_url:
            images.append({"index": 0, "full_url": full_url, "thumb_url": thumb_url or full_url})

    return images


def _ig_get_post_images_direct(shortcode: str) -> list:
    """Récupère les images d'un post via l'API mobile Instagram (HTTP direct)."""
    import json as _json
    media_id = _ig_shortcode_to_id(shortcode)
    api_url  = f"https://i.instagram.com/api/v1/media/{media_id}/info/"
    req = urllib.request.Request(api_url, headers={
        "User-Agent": "Instagram 275.0.0.27.98 Android (33/13; 420dpi; 1080x2400; "
                      "samsung; SM-G991B; o1s; exynos2100; en_US; 458229237)",
        "x-ig-app-id": "936619743392459",
        "Accept-Language": "en-US",
        "Accept": "*/*",
    })
    with urllib.request.urlopen(req, context=_logos_ssl, timeout=15) as resp:
        info = _json.loads(resp.read())
    return _ig_extract_images_from_info(info)


def _ytdlp_extract_images(post_url: str) -> list:
    """Utilise yt-dlp avec les cookies du navigateur pour extraire les images d'un post."""
    import subprocess, json as _json, shutil

    ytdlp = shutil.which("yt-dlp")
    if not ytdlp:
        raise RuntimeError("yt-dlp non installé (pip3 install yt-dlp)")

    images = []
    for browser in ("chrome", "safari", "firefox"):
        try:
            res = subprocess.run(
                [ytdlp, "--dump-json", "--cookies-from-browser", browser,
                 "--no-warnings", "--quiet", post_url],
                capture_output=True, text=True, timeout=30
            )
            raw = res.stdout.strip()
            if not raw:
                continue

            # yt-dlp peut sortir plusieurs lignes JSON (une par slide de carrousel)
            entries = []
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = _json.loads(line)
                except Exception:
                    continue
                # Si c'est une playlist (carrousel), on déplie les entries
                if obj.get("_type") == "playlist":
                    entries.extend(obj.get("entries") or [])
                else:
                    entries.append(obj)

            for i, entry in enumerate(entries):
                if not entry:
                    continue
                ext = (entry.get("ext") or "").lower()
                if ext in ("mp4", "webm"):
                    continue  # on ignore les vidéos

                # Meilleure URL : d'abord les formats triés par résolution, sinon url directe
                best_url  = None
                thumb_url = None

                formats = [f for f in (entry.get("formats") or [])
                           if f.get("ext", "") not in ("mp4", "webm", "m3u8")]
                if formats:
                    formats_sorted = sorted(
                        formats,
                        key=lambda f: (f.get("width") or 0) * (f.get("height") or 0),
                        reverse=True
                    )
                    best_url  = formats_sorted[0].get("url")
                    thumb_url = formats_sorted[-1].get("url") or best_url

                if not best_url:
                    best_url = entry.get("url")

                if not thumb_url:
                    thumbs = sorted(
                        entry.get("thumbnails") or [],
                        key=lambda t: (t.get("width") or 0) * (t.get("height") or 0),
                        reverse=True
                    )
                    thumb_url = thumbs[-1]["url"] if thumbs else best_url

                if best_url:
                    images.append({"index": i, "full_url": best_url,
                                   "thumb_url": thumb_url or best_url})

            if images:
                return images   # succès avec ce navigateur, on arrête

        except subprocess.TimeoutExpired:
            continue
        except Exception:
            continue

    raise RuntimeError("yt-dlp n'a pas pu extraire les images (vérifie que tu es connecté à Instagram dans Chrome/Safari)")


def _ig_get_post_images(post_url: str) -> list:
    """Retourne toutes les images d'un post.
    Priorité : yt-dlp (cookies navigateur) → instaloader (session) → API mobile directe.
    """
    import re as _re
    m = _re.search(r"instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)", post_url)
    if not m:
        raise ValueError("URL invalide — doit contenir /p/, /reel/ ou /tv/")
    shortcode = m.group(1)

    # ── 1. yt-dlp + cookies navigateur ──
    try:
        images = _ytdlp_extract_images(post_url)
        if images:
            return images
    except Exception:
        pass

    # ── 2. instaloader (session sauvegardée) ──
    try:
        import instaloader as _il
        L    = _ig_loader()
        post = _il.Post.from_shortcode(L.context, shortcode)
        images = []
        media_count = getattr(post, 'mediacount', 1) or 1
        if post.typename in ("GraphSidecar", "XDTGraphSidecar") or media_count > 1:
            for i, node in enumerate(post.get_sidecar_nodes()):
                if not node.is_video:
                    url = node.display_url
                    if url:
                        images.append({"index": i, "full_url": url, "thumb_url": url})
        else:
            if not post.is_video:
                url = post.url
                if url:
                    images.append({"index": 0, "full_url": url, "thumb_url": url})
        if images:
            return images
    except Exception:
        pass

    # ── 3. API mobile directe (fallback sans auth) ──
    return _ig_get_post_images_direct(shortcode)


@app.route("/api/riders/inspect-pic", methods=["POST"])
def api_riders_inspect_pic():
    """Inspecte un post Instagram et retourne toutes les images (carrousel inclus)."""
    data = request.get_json() or {}
    url  = (data.get("url") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "URL manquante"})
    try:
        images = _ig_get_post_images(url)
        if not images:
            return jsonify({"ok": False, "error": "Aucune image trouvée (post vidéo ou URL invalide ?)"})
        return jsonify({"ok": True, "images": images, "count": len(images)})
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return jsonify({"ok": False, "error": "Instagram bloque la requête — connecte-toi via le bouton 🔐"})
        return jsonify({"ok": False, "error": f"Erreur HTTP {e.code}"})
    except Exception as e:
        err = str(e)
        if any(k in err.lower() for k in ("login", "checkpoint", "unauthorized", "forbidden")):
            return jsonify({"ok": False, "error": "Instagram bloque la requête — connecte-toi via le bouton 🔐"})
        return jsonify({"ok": False, "error": err[:200]})


@app.route("/api/riders/ig-status")
def api_riders_ig_status():
    """Retourne le statut de connexion Instagram."""
    try:
        logged = _ig_is_logged_in()
        return jsonify({"ok": True, "logged_in": logged, "username": _ig_username if logged else None})
    except Exception as e:
        return jsonify({"ok": False, "logged_in": False, "username": None, "error": str(e)})


@app.route("/api/riders/ig-login", methods=["POST"])
def api_riders_ig_login():
    """Connexion Instagram via instaloader (mot de passe via dialog natif macOS)."""
    import subprocess, instaloader as _il
    global _ig_L, _ig_username
    data     = request.get_json() or {}
    username = (data.get("username") or "").strip().lstrip("@")
    if not username:
        return jsonify({"ok": False, "error": "Nom d'utilisateur manquant"})

    # Demande le mot de passe via dialog natif macOS (invisible pour Flask)
    script_pwd = f'''
    set pwd to text returned of (display dialog "Mot de passe Instagram pour @{username}" ¬
        default answer "" with hidden answer ¬
        with title "Freeride Fanatics — Instagram" ¬
        buttons {{"Annuler","Connexion"}} default button "Connexion")
    return pwd
    '''
    try:
        res = subprocess.run(["osascript", "-e", script_pwd],
                             capture_output=True, text=True, timeout=60)
        if res.returncode != 0:
            return jsonify({"ok": False, "error": "Annulé"})
        password = res.stdout.strip()
        if not password:
            return jsonify({"ok": False, "error": "Mot de passe vide"})
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "Timeout dialog"})

    # Connexion
    try:
        _ig_L = None  # force recréation
        L = _ig_loader()
        L.login(username, password)
        # Sauvegarde session
        session_dir = Path.home() / ".config" / "instaloader"
        session_dir.mkdir(parents=True, exist_ok=True)
        L.save_session_to_file(str(session_dir / f"session-{username}"))
        _ig_username = username
        return jsonify({"ok": True, "username": username})
    except _il.TwoFactorAuthRequiredException:
        # Demande le code 2FA
        script_2fa = f'''
        set code to text returned of (display dialog "Code d'authentification 2FA pour @{username}" ¬
            default answer "" ¬
            with title "Freeride Fanatics — Instagram 2FA" ¬
            buttons {{"Annuler","Valider"}} default button "Valider")
        return code
        '''
        res2 = subprocess.run(["osascript", "-e", script_2fa],
                              capture_output=True, text=True, timeout=60)
        if res2.returncode != 0:
            return jsonify({"ok": False, "error": "2FA annulé"})
        code = res2.stdout.strip().replace(" ", "")
        try:
            L.two_factor_login(code)
            session_dir = Path.home() / ".config" / "instaloader"
            session_dir.mkdir(parents=True, exist_ok=True)
            L.save_session_to_file(str(session_dir / f"session-{username}"))
            _ig_username = username
            return jsonify({"ok": True, "username": username})
        except Exception as e2:
            return jsonify({"ok": False, "error": f"2FA échoué : {e2}"})
    except Exception as e:
        err = str(e)
        if "checkpoint" in err.lower():
            return jsonify({"ok": False, "error": "Vérification Instagram requise — connecte-toi sur instagram.com depuis ton navigateur"})
        if "bad password" in err.lower() or "incorrect" in err.lower():
            return jsonify({"ok": False, "error": "Mot de passe incorrect"})
        return jsonify({"ok": False, "error": err[:200]})


@app.route("/api/riders/ig-logout", methods=["POST"])
def api_riders_ig_logout():
    """Déconnexion Instagram."""
    global _ig_L, _ig_username
    _ig_L = None
    _ig_username = None
    return jsonify({"ok": True})


@app.route("/api/riders/proxy-img")
def api_riders_proxy_img():
    """Proxy une image Instagram CDN pour contourner CORS."""
    img_url = (request.args.get("url") or "").strip()
    if not img_url:
        return ("", 400)
    # Sécurité : seulement les CDN Instagram/Facebook
    allowed = ("scontent", "cdninstagram.com", "fbcdn.net", "instagram.f")
    if not any(d in img_url for d in allowed):
        return ("", 403)
    try:
        req = urllib.request.Request(img_url, headers={
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
            "Referer": "https://www.instagram.com/",
        })
        with urllib.request.urlopen(req, context=_logos_ssl, timeout=15) as resp:
            raw  = resp.read()
            mime = resp.headers.get("Content-Type", "image/jpeg")
        return send_file(io.BytesIO(raw), mimetype=mime)
    except Exception as e:
        return (str(e), 502)


@app.route("/api/riders/download-pic", methods=["POST"])
def api_riders_download_pic():
    """Télécharge une image Instagram via son URL directe CDN."""
    data      = request.get_json() or {}
    img_url   = (data.get("img_url")    or "").strip()
    handle    = (data.get("handle")     or "").strip().lstrip("@")
    folder    = (data.get("pic_folder") or "").strip()

    if not img_url or not handle:
        return jsonify({"ok": False, "error": "img_url et rider requis"})

    pic_dir = Path(folder) if folder else BASE_DIR / "PictureRiders"
    pic_dir.mkdir(exist_ok=True)

    try:
        req = urllib.request.Request(img_url, headers={
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
            "Referer": "https://www.instagram.com/",
        })
        with urllib.request.urlopen(req, context=_logos_ssl, timeout=20) as resp:
            raw = resp.read()
    except Exception as e:
        return jsonify({"ok": False, "error": f"Téléchargement échoué : {e}"})

    out_path = pic_dir / f"@{handle}.jpg"
    out_path.write_bytes(raw)
    return jsonify({"ok": True, "handle": handle, "file": out_path.name,
                    "thumb": f"/api/riders/thumb?path={out_path}"})


# ── Google OAuth ──────────────────────────────────────────────────────────────

@app.route('/api/auth/google/status')
def api_auth_google_status():
    if not _GOOGLE_SECRET_FILE.exists():
        return jsonify({'configured': False, 'connected': False})
    if not _GOOGLE_TOKEN_FILE.exists():
        return jsonify({'configured': True, 'connected': False})
    try:
        data = _json.loads(_GOOGLE_TOKEN_FILE.read_text())
        return jsonify({'configured': True, 'connected': True,
                        'email': data.get('email', ''),
                        'name':  data.get('name', '')})
    except Exception as e:
        return jsonify({'configured': True, 'connected': False, 'error': str(e)})


@app.route('/api/auth/google')
def api_auth_google():
    import os
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'  # localhost HTTP OK
    if not _GOOGLE_SECRET_FILE.exists():
        return (
            '<h3 style="font-family:sans-serif;padding:20px">⚠️ Fichier introuvable.<br>'
            f'Place ton <b>client_secret.json</b> Google ici :<br>'
            f'<code>{_GOOGLE_SECRET_FILE}</code></h3>'
        ), 400
    try:
        from google_auth_oauthlib.flow import Flow
    except ImportError:
        return '<h3>pip install google-auth-oauthlib</h3>', 500
    redirect_uri = request.host_url.rstrip('/') + '/api/auth/google/callback'
    flow = Flow.from_client_secrets_file(
        str(_GOOGLE_SECRET_FILE),
        scopes=_GOOGLE_SCOPES,
        redirect_uri=redirect_uri
    )
    auth_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='select_account'
    )
    session['google_oauth_state'] = state
    return flask_redirect(auth_url)


@app.route('/api/auth/google/callback')
def api_auth_google_callback():
    import os
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    try:
        from google_auth_oauthlib.flow import Flow
    except ImportError:
        return '<h3>pip install google-auth-oauthlib</h3>', 500
    redirect_uri = request.host_url.rstrip('/') + '/api/auth/google/callback'
    flow = Flow.from_client_secrets_file(
        str(_GOOGLE_SECRET_FILE),
        scopes=_GOOGLE_SCOPES,
        state=session.get('google_oauth_state'),
        redirect_uri=redirect_uri
    )
    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials

    # Récupère l'email/nom via userinfo
    try:
        req = urllib.request.Request(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {creds.token}'}
        )
        with urllib.request.urlopen(req) as resp:
            user_info = _json.loads(resp.read())
    except Exception:
        user_info = {}

    token_data = {
        'token':         creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri':     creds.token_uri,
        'client_id':     creds.client_id,
        'client_secret': creds.client_secret,
        'scopes':        list(creds.scopes or []),
        'email':         user_info.get('email', ''),
        'name':          user_info.get('name', ''),
        'picture':       user_info.get('picture', ''),
    }
    _GOOGLE_TOKEN_FILE.write_text(_json.dumps(token_data, indent=2))

    return '''<!DOCTYPE html><html><body style="font-family:sans-serif;text-align:center;padding:40px;background:#0a0a0a;color:#eee">
<h2>✅ Connexion Google réussie !</h2>
<p>Tu peux fermer cet onglet.</p>
<script>
  if (window.opener) {
    window.opener.postMessage({type:"google_oauth_success"}, "*");
    setTimeout(() => window.close(), 800);
  }
</script>
</body></html>'''


@app.route('/api/auth/google/logout', methods=['POST'])
def api_auth_google_logout():
    if _GOOGLE_TOKEN_FILE.exists():
        _GOOGLE_TOKEN_FILE.unlink()
    return jsonify({'ok': True})


# ── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="0.0.0.0",  help="IP d'écoute (0.0.0.0 pour VPS)")
    p.add_argument("--port", default=5000, type=int)
    args = p.parse_args()

    print(f"\n🏔️  Freeride Fanatics — Card Generator")
    print(f"   http://localhost:{args.port}")
    print(f"   http://<VPS-IP>:{args.port}\n")

    get_engine()  # précharge tout au démarrage
    app.run(host=args.host, port=args.port, debug=False)
