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
from pathlib import Path
from flask import Flask, jsonify, request, send_file, Response, session, redirect as flask_redirect

# ── Import du moteur de génération ───────────────────────────────────────────
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))
import generate_cards as gc

app = Flask(__name__)

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
]

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
    _cache.clear()
    get_engine()

def get_equipment():
    if "equipment" not in _cache:
        _cache["equipment"] = gc.load_equipment_from_gsheet() or {}
    return _cache["equipment"]

# ── HTML ──────────────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Freeride Fanatics — Card Generator</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', sans-serif; background: #1a1a1a; color: #eee; min-height: 100vh; }

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

  /* ── Tab nav ── */
  .tab-nav {
    display: flex;
    gap: 3px;
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    padding: 3px;
    border-radius: 8px;
    margin-left: 8px;
  }
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
    width: 240px;
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
    grid-template-columns: 380px 1fr;
    gap: 0;
    height: calc(100vh - 65px);
  }

  /* ── PANNEAU GAUCHE ── */
  .panel-wrapper {
    display: flex;
    flex-direction: column;
    background: #222;
    border-right: 1px solid #333;
    overflow: hidden;
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
  .sponsor-chip span {
    font-size: 0.58rem;
    color: #777;
    text-align: center;
    line-height: 1.1;
    letter-spacing: 0.5px;
  }
  .sponsor-chip.active span { color: #C8D400; }

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
  .slider-row.locked input[type=range] { opacity: 0.3; pointer-events: none; }
  .slider-row.locked input.slider-val  { opacity: 0.5; pointer-events: none; }

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
     RESPONSIVE MOBILE
  ══════════════════════════════════════════ */
  @media (max-width: 768px) {

    /* ── Header ── */
    header {
      flex-wrap: wrap;
      padding: 10px 14px 8px;
      gap: 8px;
      row-gap: 6px;
    }
    header h1 { font-size: 0.95rem; letter-spacing: 1px; }

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
    #page-reel { height: auto; }
    #page-reel .layout { height: auto; }
    #page-publish { height: auto; }
    #page-publish .layout { height: auto; }
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
    }
    .preview-area img {
      max-height: 80vw;
      max-width: 96%;
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
    .action-grid,
    .action-grid.two,
    .action-grid.four { grid-template-columns: 1fr; }

    /* ── Boutons : zones de touch plus grandes ── */
    .btn { padding: 14px; }
    .btn-generate { font-size: 0.92rem; }

    /* ── Barre équipements ── */
    .eq-page-bar { flex-wrap: wrap; }
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
  <div style="font-size:2rem">⛰️</div>
  <div style="color:#C8D400;font-family:'BebasNeue-Regular',sans-serif;font-size:1.6rem;letter-spacing:2px">
    FREERIDE FANATICS
  </div>
  <div id="app-loading-msg" style="color:#666;font-size:0.8rem">Chargement des données…</div>
  <div style="width:200px;height:3px;background:#222;border-radius:2px;overflow:hidden">
    <div id="app-loading-bar" style="height:100%;background:#C8D400;width:0%;transition:width .3s ease"></div>
  </div>
</div>

<header>
  <h1>⛰️ Freeride Fanatics</h1>

  <!-- Nav principale (gauche) -->
  <nav class="tab-nav" id="main-tab-nav">
    <button class="tab-btn active" onclick="switchTab('cards')" id="tab-cards">🏔️ Riders</button>
    <button class="tab-btn" onclick="switchTab('equipment')" id="tab-equipment">🔧 Équipements</button>
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
        <button class="dashboard-menu-btn" id="tab-audit" onclick="switchTab('audit'); closeDashboard()">
          📋 Audit Équipements
        </button>
        <div class="dashboard-section-label" style="margin-top:6px">Settings</div>
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
    <button class="burger-item" id="burger-reel" onclick="switchTab('reel'); closeBurger()">🎬 Reel</button>
    <button class="burger-item" id="burger-publish" onclick="switchTab('publish'); closeBurger()">
      📣 Publish <span id="burger-publish-badge" style="display:none;background:#C8D400;color:#000;
        border-radius:10px;font-size:0.65rem;padding:1px 5px;margin-left:4px;font-weight:700"></span>
    </button>
    <div class="burger-divider">Assets Management</div>
    <button class="burger-item" id="burger-riders" onclick="switchTab('riders'); closeBurger()">👤 Riders</button>
    <button class="burger-item" id="burger-logos" onclick="switchTab('logos'); closeBurger()">🖼 Logos</button>
    <button class="burger-item" id="burger-audit" onclick="switchTab('audit'); closeBurger()">📋 Audit Équipements</button>
    <div class="burger-divider">Settings</div>
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
          <input type="range" id="logo_h" min="20" max="200" value="38" onmousedown="captureHistory()" oninput="updateSlider(this,'val_lh')">
          <input type="text" class="slider-val" id="val_lh" value="38" onfocus="this.select()" onchange="syncVal('val_lh','logo_h')">
          <button class="lock-btn" id="lock_logo_h" onclick="toggleLock('lock_logo_h','logo_h')" title="Verrouiller">🔓</button>
        </div>
        <div class="slider-row">
          <span class="slider-label">Position Y</span>
          <input type="range" id="logo_y" min="900" max="1340" value="1280" onmousedown="captureHistory()" oninput="updateSlider(this,'val_ly')">
          <input type="text" class="slider-val" id="val_ly" value="1280" onfocus="this.select()" onchange="syncVal('val_ly','logo_y')">
          <button class="lock-btn" id="lock_logo_y" onclick="toggleLock('lock_logo_y','logo_y')" title="Verrouiller">🔓</button>
        </div>
        <div class="slider-row">
          <span class="slider-label">Position X</span>
          <input type="range" id="logo_x" min="-1" max="1060" value="-1" onmousedown="captureHistory()" oninput="updateSlider(this,'val_lx',true)">
          <input type="text" class="slider-val" id="val_lx" value="Auto" onfocus="this.select()" onchange="syncVal('val_lx','logo_x',true)">
          <button class="lock-btn" id="lock_logo_x" onclick="toggleLock('lock_logo_x','logo_x')" title="Verrouiller">🔓</button>
        </div>
      </div>
    </div>

  </div><!-- fin .panel -->

  <!-- Actions fixées en bas -->
  <div class="panel-actions sticky">
    <button class="btn btn-generate" onclick="generate()">▶ Générer la carte</button>
    <div class="action-grid four">
      <button class="btn btn-download" id="btn-dl" disabled onclick="download()">⬇ Télécharger</button>
      <button class="btn btn-secondary" id="cards-add-publish-btn" disabled onclick="addRiderCardToPublish()">
        ＋ Publish
      </button>
      <button class="btn btn-secondary" id="cards-add-reel-btn" disabled onclick="addRiderCardToReel()">
        ＋ Reel
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

    <!-- Rider -->
    <div class="collapsible open" id="eqcol-rider">
      <div class="collapsible-header" onclick="toggleCol('eqcol-rider')">
        <span class="section-title">Rider</span><span class="collapsible-arrow">▼</span>
      </div>
      <div class="collapsible-body">
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

    <!-- Équipements -->
    <div class="collapsible open" id="eqcol-items">
      <div class="collapsible-header" onclick="toggleCol('eqcol-items')">
        <span class="section-title">🔧 Équipement</span><span class="collapsible-arrow">▼</span>
      </div>
      <div class="collapsible-body">
        <div class="eq-list" id="eq-page-list">
          <div class="eq-empty">Sélectionne un rider</div>
        </div>
        <!-- Variantes couleur -->
        <div id="eq-color-variants" style="display:none;margin-top:10px">
          <div style="font-size:11px;color:#888;margin-bottom:6px;text-transform:uppercase;letter-spacing:.05em">🎨 Variante</div>
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
            <input type="checkbox" id="eq_use_v2" onchange="eqDebouncedGenerate()">
            <span class="eq-toggle-label" style="color:#C8D400;font-weight:bold">Background V2 <span style="font-size:10px;opacity:.7;font-weight:normal">beta</span></span>
          </label>
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
      <button class="btn btn-secondary" id="eq-add-publish-btn" disabled onclick="addEqCardToPublish()">
        ＋ Publish
      </button>
      <button class="btn btn-secondary" id="eq-add-reel-btn" disabled onclick="addToReel()">
        ＋ Reel
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
<!-- PAGE REEL                                                               -->
<!-- ═══════════════════════════════════════════════════════════════════════ -->
<div id="page-reel">
<div class="layout">

  <div class="panel-wrapper">
  <div class="panel">

    <div class="collapsible open" id="reelcol-items">
      <div class="collapsible-header" onclick="toggleCol('reelcol-items')">
        <span class="section-title">🎬 Cartes du reel</span><span class="collapsible-arrow">▼</span>
      </div>
      <div class="collapsible-body">
        <div id="reel-item-list">
          <div class="reel-empty">Aucune carte ajoutée.<br>Génère une carte dans l'onglet Équipements<br>et clique <b>＋ Reel</b>.</div>
        </div>
      </div>
    </div>

    <div class="collapsible open" id="reelcol-settings">
      <div class="collapsible-header" onclick="toggleCol('reelcol-settings')">
        <span class="section-title">⚙ Paramètres</span><span class="collapsible-arrow">▼</span>
      </div>
      <div class="collapsible-body">
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
      <button class="btn btn-secondary" id="reel-add-publish-btn" disabled onclick="addEqReelToPublish()">
        ＋ Publish
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
          <button class="btn btn-secondary" onclick="publishCopyCaption()">📋 Caption</button>
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
          <button class="btn btn-secondary publish-copy-mini" id="publish-preview-copy-btn" onclick="publishCopyCaption()" disabled>📋 Copier</button>
        </div>
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
  const row = btn.closest('.slider-row');
  if (lockedSliders.has(rangeId)) {
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
    _app.sponsors        = data.sponsors         || [];
    _app.eqVariants      = data.eq_variants      || [];
    _app.categoryFolders = data.category_folders || {};

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
  lastSlug = null;
  document.getElementById('btn-dl').disabled = true;
  if (!slug) return;

  // Lookup local — pas de fetch
  const profile = _app.profiles.find(p => p.slug === slug);
  if (!profile) return;
  _originalProfile = profile;
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
  document.querySelectorAll('.sponsor-chip').forEach(c => {
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
  logos: { logo_h: 38, logo_y: 1280, logo_x: -1, logo_dir: 'row' },
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
  document.getElementById('error-msg').style.display = 'none';

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
    document.getElementById('cards-add-publish-btn').disabled = false;
    document.getElementById('cards-add-reel-btn').disabled = false;
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

// ── Tab navigation ────────────────────────────────────────────────────────
const _DASHBOARD_TABS = ['logos', 'riders', 'connections', 'audit'];

function switchTab(tab) {
  // Tabs principaux
  ['cards','equipment','reel','publish'].forEach(t => {
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
  document.getElementById('page-logos').style.display       = tab === 'logos'       ? 'block' : 'none';
  document.getElementById('page-riders').style.display      = tab === 'riders'      ? 'block' : 'none';
  document.getElementById('page-reel').style.display        = tab === 'reel'        ? 'block' : 'none';
  document.getElementById('page-publish').style.display     = tab === 'publish'     ? 'block' : 'none';
  document.getElementById('page-connections').style.display = tab === 'connections' ? 'block' : 'none';
  document.getElementById('page-audit').style.display       = tab === 'audit'       ? 'block' : 'none';

  if (tab === 'equipment' && !_eqRidersLoaded) initEqPage();
  if (tab === 'reel') { renderReelPage(); _initReelRiderList(); }
  if (tab === 'publish') publishInit();
  if (tab === 'connections') connRefreshGoogle();
  if (tab === 'audit') loadEqAudit();
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
      statusEl.innerHTML = '<span class="dot" style="background:#f90"></span>client_secret.json requis';
      btn.textContent = 'Configurer ↗';
      btn.style.background = '';
      btn.onclick = () => window.open('https://console.cloud.google.com/apis/credentials', '_blank');
    } else if (d.connected) {
      statusEl.innerHTML = `<span class="dot" style="background:#4CAF50"></span>${d.email || 'Connecté'}`;
      btn.textContent = 'Déconnecter';
      btn.style.background = '#2a2a2a';
      btn.onclick = async () => {
        await fetch('/api/auth/google/logout', {method:'POST'});
        btn.onclick = () => connClick('google');
        connRefreshGoogle();
      };
    } else {
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
  if (btn) { btn.textContent = orig || '↺ Actualiser le Sheet'; btn.disabled = false; }
  if (_eqSelectedSlug) onEqRiderChange(_eqSelectedSlug);
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
      <span>${r.genre === 'F' ? '♀' : '♂'} ${r.prenom} ${r.nom}</span>
    </div>`).join('');
}

let _eqSelectedRider = null;  // profil complet du rider sélectionné (pour badge reel)

// ── Checks statut par item d'équipement ──────────────────────────────────────
function _eqCheckPhoto(it) {
  const norm = s => (s || '').toLowerCase().replace(/[\s\-_\/\.]/g, '');
  const bNorm = norm(it.brand);
  const rNorm = norm(it.reference);
  const words = (it.reference || '').toLowerCase().split(/\s+/)
    .filter(w => w.length > 2).map(norm);
  const catFolders = (_app.categoryFolders[it.category] || [it.category]).map(norm);
  return _app.eqVariants.some(f => {
    if (!catFolders.includes(norm(f.folder || ''))) return false;
    const s = norm(f.name);
    if (bNorm && rNorm && s.includes(bNorm) && s.includes(rNorm)) return true;
    if (bNorm && s.includes(bNorm)) return true;
    if (words.length && words.some(w => s.includes(w))) return true;
    return false;
  });
}

function _eqCheckLogo(brand) {
  if (!brand) return false;
  const norm = s => s.toLowerCase().replace(/[\s\-_\/]/g, '');
  const b = norm(brand);
  return _app.sponsors.some(s => {
    const k = norm(s.key || s.label || '');
    return k && (k.includes(b) || b.includes(k));
  });
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
  const varBox   = document.getElementById('eq-color-variants');
  const swatches = document.getElementById('eq-color-swatches');
  varBox.style.display = 'none';
  swatches.innerHTML = '';

  // Lookup local — dossier catégorie d'abord, puis score de pertinence
  const cacheKey = `${it.brand||''}|${it.reference||''}|${it.category||''}`;
  let variants = _app.varCache[cacheKey];
  if (!variants) {
    const norm = s => (s||'').toLowerCase().replace(/[\s\-\_\/\.]/g, '');
    const bNorm = norm(it.brand);
    const rNorm = norm(it.reference);
    // Dossiers valides pour cette catégorie
    const catFolders = (_app.categoryFolders[it.category] || [it.category])
      .map(f => norm(f));

    // 1. Filtrer par dossier catégorie
    const inFolder = _app.eqVariants.filter(f => {
      if (!f.folder) return false;
      return catFolders.includes(norm(f.folder));
    });

    const score = f => {
      const s = norm(f.name);
      if (bNorm && rNorm && s.includes(bNorm) && s.includes(rNorm)) return 0;  // marque + modèle
      if (bNorm && s.includes(bNorm)) return 1;                                  // marque seule
      const words = (it.reference||'').toLowerCase().split(/\s+/).filter(Boolean);
      if (words.some(w => w.length > 2 && s.includes(norm(w)))) return 2;       // mot-clé ref
      return 3;                                                                   // hors sujet
    };

    if (inFolder.length === 0) {
      // Fallback : racine Equipment/ si aucun dossier matche
      variants = _app.eqVariants.filter(f => !f.folder && score(f) < 3);
    } else {
      // Garder marque OU modèle (scores 0, 1, 2) — exclure les hors-sujet (score 3)
      const matched = inFolder.filter(f => score(f) < 3).sort((a, b) => score(a) - score(b));
      if (matched.length > 0) {
        variants = matched;
      } else {
        // Aucun match — afficher tout le dossier avec un avertissement
        variants = [...inFolder];
        variants._noMatch = true;
      }
    }
    _app.varCache[cacheKey] = variants;
  }

  if (variants.length > 0) {
    varBox.style.display = 'block';
    if (variants._noMatch) {
      swatches.insertAdjacentHTML('beforebegin',
        `<div style="color:#f90;font-size:11px;margin-bottom:6px">
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
      };
      const lbl = document.createElement('div');
      lbl.className = 'eq-swatch-label';
      const base = ((it.brand||'') + (it.reference||'')).replace(/\s/g,'');
      lbl.textContent = v.name.replace(new RegExp('^'+base, 'i'), '') || v.name;
      wrap.appendChild(sw); wrap.appendChild(lbl);
      swatches.appendChild(wrap);
      if (i === 0) _eqSelectedPhotoPath = v.path;
    });
  }
}

// Debounce live preview
let _eqDebTimer = null;
function toggleEqLogoControls() {
  const show = document.getElementById('eq_show_logo')?.checked;
  const ctrl = document.getElementById('eq-logo-controls');
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
  const use_v2         = g('eq_use_v2')?.checked         ?? false;
  const brand_text     = g('eq_brand_text')?.value     || it.brand     || '';
  const reference_text = g('eq_reference_text')?.value || it.reference || '';
  const details_text   = g('eq_details_text')?.value   || it.details   || '';
  const photo_bg       = _hexToRgb(g('eq_photo_bg')?.value || '#ffffff');

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
        photo_bg, use_v2,
      }),
    });
    if (!res.ok) { const e = await res.json(); throw new Error(e.error); }
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const name = `${it.brand}_${it.reference || it.category}`.replace(/\s+/g,'_') + '.png';
    _lastEqCard = { url, name };
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
    document.getElementById('eq-add-publish-btn').disabled = false;
    document.getElementById('eq-add-reel-btn').disabled = false;
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
  btn.textContent = '✓ Ajouté';
  btn.style.background = '#C8D400'; btn.style.color = '#000';
  setTimeout(() => { btn.textContent = '＋ Reel'; btn.style.background=''; btn.style.color=''; }, 1200);
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

  const item = {
    id,
    label:           `${it.category} · ${it.brand || ''} ${it.reference || ''}`.trim(),
    sub:             g('eq_brand_text')?.value || it.brand || '',
    preview_url:     _lastEqCard.url,
    photo_path:      _eqSelectedPhotoPath || '',
    rider_instagram: _eqSelectedRider?.instagram || '',
    is_selection:    false,
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
      use_v2:         g('eq_use_v2')?.checked           ?? false,
    },
  };

  _reelItems.push(item);
  _updateReelBadge();

  // Flash du bouton
  const btn = document.getElementById('eq-add-reel-btn');
  btn.textContent = '✓ Ajouté';
  btn.style.background = '#C8D400'; btn.style.color = '#000';
  setTimeout(() => { btn.textContent = '＋ Reel'; btn.style.background=''; btn.style.color=''; }, 1200);
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

  if (_reelItems.length === 0) {
    list.innerHTML = '<div class="reel-empty">Aucune carte ajoutée.<br>Génère une carte dans l\'onglet Équipements<br>et clique <b>＋ Reel</b>.</div>';
    if (grid) grid.innerHTML = '';
    return;
  }

  list.innerHTML = _reelItems.map(it => `
    <div class="reel-item ${it.is_selection ? 'is-selection' : ''}"
         draggable="true" data-id="${it.id}">
      <img class="reel-thumb" src="${it.preview_url}" alt="">
      <div class="reel-info">
        <div class="reel-label">${it.label}</div>
        <div class="reel-sub">${it.rider_instagram ? '@' + it.rider_instagram.replace(/^@/,'') : '—'}</div>
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
    _reelLog('❌ Ajoute au moins une carte via ＋ Reel', true); return;
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
      if (it.type === 'rider' && it.preview_url) {
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

    _reelLog(`⚙ Génération du MP4 (${items_payload.length} frames)…`);
    const badgeRiderIg  = document.getElementById('reel-rider-select')?.value || '';
    const badgeRadius   = parseInt(g('reel_badge_radius')?.value || 58);
    const res = await fetch('/api/generate-eq-reel', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items: items_payload, dur_per_card: dur,
                             crossfade: cf, show_rider_badge: showBadge,
                             badge_rider_ig: badgeRiderIg,
                             badge_radius: badgeRadius }),
    });

    if (!res.ok) {
      let errMsg = `HTTP ${res.status}`;
      try { errMsg = (await res.json()).error || errMsg; } catch {}
      throw new Error(errMsg);
    }

    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    _lastEqReel = { url, name: 'reel_equipment.mp4' };
    _lastPublishSource = {
      kind: 'reel',
      url,
      name: 'reel_equipment.mp4',
      mime: 'video/mp4',
    };
    g('reel-dl-btn').disabled = false;
    g('reel-add-publish-btn').disabled = false;

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
  const lead = parts.filter(Boolean).join(' · ');
  const tags = '#freeridefanatics #mtb #downhill';
  return lead ? `${lead}\n\n${tags}` : tags;
}

function _publishBrandHandle(item) {
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
  if (ctx.equipmentName) bits.push(ctx.equipmentName);
  if (ctx.category && !ctx.equipmentName) bits.push(ctx.category);
  return bits.length ? bits.join(' · ') : 'Full setup on Freeride Fanatics.';
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
  if (status) status.textContent = '';
}

function publishAutoFill(force = false) {
  const kind = _publishState.kind || _publishDraftKind || (_publishAvailable('reel') ? 'reel' : _publishAvailable('equipment') ? 'equipment' : 'rider');
  if (!kind || !_publishAvailable(kind)) {
    publishRender();
    return;
  }

  const title = document.getElementById('publish-title');
  const caption = document.getElementById('publish-caption');
  const location = document.getElementById('publish-location');
  const hashtags = document.getElementById('publish-hashtags');
  const firstComment = document.getElementById('publish-first-comment');
  const alt = document.getElementById('publish-alt');
  const musicSel = document.getElementById('publish-music-select');
  const musicNote = document.getElementById('publish-music-note');
  const music = _publishDefaultMusic(kind);

  if (title && (force || !title.value.trim())) title.value = _publishDefaultTitle(kind);
  if (caption && (force || !caption.value.trim())) caption.value = _publishDefaultCaption(kind);
  if (location && (force || !location.value.trim())) location.value = _publishDefaultLocation(kind);
  if (hashtags && (force || !hashtags.value.trim())) hashtags.value = _publishDefaultHashtags(kind);
  if (firstComment && (force || !firstComment.value.trim())) firstComment.value = _publishDefaultFirstComment(kind);
  if (alt && (force || !alt.value.trim())) alt.value = _publishDefaultAlt(kind);
  if (musicSel && (force || !musicSel.value)) musicSel.value = music.value;
  if (musicNote && (force || !musicNote.value.trim())) musicNote.value = music.note;
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
    document.getElementById('publish-status').textContent = '✅ Caption copiée';
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
      await navigator.share({
        title: document.getElementById('publish-title')?.value || 'Freeride Fanatics',
        text,
        files,
      });
      status.textContent = '✅ Partagé vers le téléphone';
      if (openInstagram) {
        setTimeout(() => { _publishLaunchInstagramApp(); }, 400);
      }
      return;
    }
    await publishDownload();
    if (text) await navigator.clipboard.writeText(text);
    status.textContent = '⚠️ Partage natif indisponible, média téléchargé + caption copiée';
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
    from flask import send_from_directory
    return send_from_directory(str(gc.LOGOS_DIR), filename)


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
            profile = {**profile, **{k: v for k, v in overrides.items() if v != ""}}

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

        # Retourner l'image en mémoire
        buf = io.BytesIO()
        card.save(buf, "JPEG", quality=92)
        buf.seek(0)
        return send_file(buf, mimetype="image/jpeg",
                         download_name=f"{slug}.jpg")

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


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
        output = tmpdir / "reel.mp4"

        if n == 1:
            cmd = ["ffmpeg","-y","-r","30","-loop","1","-t",str(dur),"-i",str(png_paths[0]),
                   "-vf","format=yuv420p",
                   "-c:v","libx264","-r","30",str(output)]
        else:
            inputs = []
            for p in png_paths:
                inputs += ["-r","30","-loop","1","-t",str(dur + crossfade),"-i",str(p)]
            # format=yuv420p sur chaque input (les PNG sont RGBA, xfade ne supporte pas RGBA)
            fmt_parts = [f"[{i}:v]format=yuv420p[f{i}]" for i in range(n)]
            xfade_parts, prev = [], "[f0]"
            for i in range(1, n):
                out_lbl = f"[x{i}]" if i < n-1 else "[vout]"
                offset  = round(i * (dur - crossfade), 3)
                xfade_parts.append(f"{prev}[f{i}]xfade=transition=fade:duration={crossfade}:offset={offset}{out_lbl}")
                prev = out_lbl
            fc = ";".join(fmt_parts + xfade_parts)
            cmd = ["ffmpeg","-y"] + inputs + [
                "-filter_complex", fc,
                "-map","[vout]","-c:v","libx264","-r","30",str(output)]

        cmd[0] = ffmpeg_bin
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode()[-600:])

        buf = io.BytesIO(output.read_bytes())
        return send_file(buf, mimetype="video/mp4", download_name="reel_equipment.mp4")
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/equipment-audit")
def api_equipment_audit():
    """Audit croisé : pour chaque rider, vérifie données Sheet + photo dossier."""
    import re as _re
    eq  = get_equipment()
    _, _, profiles = get_engine()

    # Index des fichiers par catégorie : category → list of filenames (lower)
    eq_photos_dir = BASE_DIR / "Equipment"
    cat_files = {}
    if eq_photos_dir.exists():
        for sub in eq_photos_dir.iterdir():
            if sub.is_dir():
                cat_files[sub.name] = [
                    f.name for f in sub.iterdir()
                    if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
                ]

    def _norm(s):
        return _re.sub(r'[\s\-_/\.]', '', (s or '').lower())

    import generate_equipment_card as _gec
    def _has_photo(cat, brand, reference):
        # Chercher dans tous les alias de dossiers pour cette catégorie
        folder_names = _gec.CATEGORY_FOLDERS.get(cat, [cat])
        files = []
        for fn in folder_names:
            files.extend(cat_files.get(fn, []))
        if not files:
            return False
        b = _norm(brand)
        r = _norm(reference)
        words = [_norm(w) for w in (reference or '').split() if len(w) > 2]
        for fname in files:
            s = _norm(fname)
            if b and r and b in s and r in s:
                return True   # match exact
            if b and b in s:
                return True   # match marque
            if words and any(w in s for w in words):
                return True   # match mot-clé modèle
        return False

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
                if _has_photo(cat, brand, ref):
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
        "sponsors":         sponsors,
        "eq_variants":      eq_variants,
        "category_folders": gec.CATEGORY_FOLDERS,
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
    for ext in (".jpg", ".jpeg", ".png"):
        for stem in (f"@{h}", h):
            p = search_dir / (stem + ext)
            if p.exists():
                return p, p.name
    # Fuzzy match sur tous les fichiers
    for f in sorted(search_dir.iterdir()):
        if f.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue
        stem = f.stem.lower().lstrip("@")
        stem_s = stem.replace(".", "").replace("-", "").replace("_", "").replace(" ", "")
        if h in stem or stem in h:
            return f, f.name
        if h_strip and (h_strip in stem_s or stem_s in h_strip):
            return f, f.name
    return None, None


def _riders_load_csv():
    """Charge les riders depuis equipment_men.csv + equipment_women.csv."""
    riders = []
    for fname in ("equipment_men.csv", "equipment_women.csv"):
        p = BASE_DIR / fname
        if not p.exists():
            continue
        import csv as _csv
        with open(p, newline="", encoding="utf-8") as f:
            for row in _csv.DictReader(f):
                ig = (row.get("Instagram") or "").strip()
                if ig:
                    riders.append(ig)
    return riders


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
        display = ig.lstrip("@").replace("_", " ").title()
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
    mime = "image/png" if resolved.suffix.lower() == ".png" else "image/jpeg"
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
    flow = Flow.from_client_secrets_file(
        str(_GOOGLE_SECRET_FILE),
        scopes=_GOOGLE_SCOPES,
        redirect_uri='http://localhost:5000/api/auth/google/callback'
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
    flow = Flow.from_client_secrets_file(
        str(_GOOGLE_SECRET_FILE),
        scopes=_GOOGLE_SCOPES,
        state=session.get('google_oauth_state'),
        redirect_uri='http://localhost:5000/api/auth/google/callback'
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
