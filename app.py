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
from flask import Flask, jsonify, request, send_file, Response

# ── Import du moteur de génération ───────────────────────────────────────────
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))
import generate_cards as gc

app = Flask(__name__)

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

  /* ── Equipment page ── */
  #page-equipment {
    display: none;  /* montré via JS → display:block */
  }
  #page-equipment .layout {
    height: calc(100vh - 65px);
  }
  .eq-page-bar {
    background: #161616;
    border-bottom: 1px solid #2a2a2a;
    padding: 10px 20px;
    display: flex;
    gap: 10px;
    align-items: center;
    flex-shrink: 0;
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
</style>
</head>
<body>

<header>
  <h1>⛰️ Freeride Fanatics</h1>
  <nav class="tab-nav">
    <button class="tab-btn active" onclick="switchTab('cards')" id="tab-cards">🎴 Cards</button>
    <button class="tab-btn" onclick="switchTab('equipment')" id="tab-equipment">🔧 Équipements</button>
  </nav>
  <div style="flex:1"></div>
  <button class="btn btn-reload" onclick="reloadExcel()">↺ Recharger</button>
</header>

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
  <div class="panel-actions">
    <button class="btn btn-generate" onclick="generate()">▶ Générer la carte</button>
    <div style="display:flex;gap:8px">
      <button class="btn btn-download" id="btn-dl" disabled onclick="download()" style="flex:1">⬇ Télécharger</button>
      <button class="btn-undo" id="btn-undo" disabled onclick="undo()" title="Ctrl+Z">↩ Annuler</button>
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
        <select id="eq-rider-select" onchange="onEqRiderChange()" size="8"
          style="height:160px;border-radius:6px;padding:4px 0"></select>
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
            <input type="checkbox" id="eq_show_logo" onchange="eqDebouncedGenerate()">
            <span class="eq-toggle-label">Logo marque</span>
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
      </div>
    </div>

  </div><!-- fin .panel -->

  <div class="panel-actions">
    <button class="btn btn-generate" onclick="generateEqCard()">▶ Générer la carte</button>
    <div style="display:flex;gap:8px">
      <button class="btn btn-download" id="eq-page-dl-btn" disabled onclick="downloadEqCard()" style="flex:1;margin-top:0">⬇ Télécharger</button>
      <button class="btn-undo" onclick="reloadEqData()" title="↺ Recharger Sheet">↺ Sheet</button>
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

<script>
// ── Collapsible ───────────────────────────────────────────────────────────
function toggleCol(id) {
  document.getElementById(id).classList.toggle('open');
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

// ── État ──────────────────────────────────────────────────────────────────
let riders = [];
let selectedSponsors = new Set();  // vide = auto
let lastSlug = null;
let genderFilter = 'all';  // 'all' | 'F' | 'M'

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

// ── Init ──────────────────────────────────────────────────────────────────
async function init() {
  const res = await fetch('/api/riders');
  riders = await res.json();
  renderRiderList();

  // Sponsors disponibles — affichage avec vrais logos
  const sr = await fetch('/api/sponsors');
  const sponsors = await sr.json();
  const grid = document.getElementById('sponsors-grid');
  sponsors.forEach(s => {
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

let _originalProfile = null;

async function onRiderChange() {
  const slug = document.getElementById('rider').value;
  lastSlug = null;
  document.getElementById('btn-dl').disabled = true;
  if (!slug) return;

  const res = await fetch(`/api/profile/${slug}`);
  if (!res.ok) return;
  const profile = await res.json();
  _originalProfile = profile;
  _fillEditFields(profile);
  const editCol = document.getElementById('col-edit');
  editCol.style.display = 'block';
  editCol.classList.add('open');
  debouncedGenerate(100);

  // Charger les équipements
  const instagram = profile.instagram || '';
  if (instagram) loadEquipment(instagram);
}

async function loadEquipment(instagram) {
  const handle = instagram.replace(/^@/, '');
  const res = await fetch(`/api/equipment/${handle}`);
  if (!res.ok) return;
  const items = await res.json();

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
function switchTab(tab) {
  document.getElementById('tab-cards').classList.toggle('active', tab === 'cards');
  document.getElementById('tab-equipment').classList.toggle('active', tab === 'equipment');
  document.getElementById('page-cards').style.display      = (tab === 'cards')     ? 'grid' : 'none';
  document.getElementById('page-equipment').style.display  = (tab === 'equipment') ? 'block': 'none';
  if (tab === 'equipment' && !_eqRidersLoaded) initEqPage();
}

// ── Equipment page ────────────────────────────────────────────────────────
let _eqRidersLoaded = false;
let _eqRiders       = [];
let _eqGender       = 'all';
let _eqSelectedItem = null;
let _eqSelectedPhotoPath = '';
let _eqItemsData    = [];
let _lastEqCard     = null;

async function initEqPage() {
  _eqRiders = riders;
  _eqRidersLoaded = true;
  renderEqRiderList();
  fetch('/api/reload-equipment', { method: 'POST' });
}

async function reloadEqData() {
  const btn = event.currentTarget;
  btn.textContent = '⏳'; btn.disabled = true;
  await fetch('/api/reload-equipment', { method: 'POST' });
  btn.textContent = '↺ Sheet'; btn.disabled = false;
  const slug = document.getElementById('eq-rider-select').value;
  if (slug) onEqRiderChange();
}

function setEqGender(g) {
  _eqGender = (_eqGender === g) ? 'all' : g;
  document.getElementById('eq-btn-f').className = 'gender-btn' + (_eqGender === 'F' ? ' active-f' : '');
  document.getElementById('eq-btn-m').className = 'gender-btn' + (_eqGender === 'M' ? ' active-m' : '');
  renderEqRiderList();
}

function renderEqRiderList() {
  const query = (document.getElementById('eq-rider-search').value || '').trim().toLowerCase();
  const sel = document.getElementById('eq-rider-select');
  const prev = sel.value;
  sel.innerHTML = '';
  const filtered = _eqRiders.filter(r => {
    if (_eqGender !== 'all' && r.genre !== _eqGender) return false;
    if (query && !`${r.prenom} ${r.nom}`.toLowerCase().includes(query)) return false;
    return true;
  });
  filtered.forEach(r => {
    const opt = document.createElement('option');
    opt.value = r.slug;
    opt.textContent = `${r.genre === 'F' ? '♀' : '♂'}  ${r.prenom} ${r.nom}`;
    sel.appendChild(opt);
  });
  if (prev && filtered.find(r => r.slug === prev)) sel.value = prev;
}

async function onEqRiderChange() {
  const slug = document.getElementById('eq-rider-select').value;
  if (!slug) return;
  const res = await fetch(`/api/profile/${slug}`);
  if (!res.ok) return;
  const profile = await res.json();
  const instagram = (profile.instagram || '').replace(/^@/, '');
  if (!instagram) return;

  const eqRes = await fetch(`/api/equipment/${instagram}`);
  if (!eqRes.ok) return;
  const items = await eqRes.json();

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
  list.innerHTML = items.map((it, i) => `
    <div class="eq-item" id="eq-page-item-${i}" onclick="selectEqItem(${i})">
      <span class="eq-cat">${it.category}</span>
      <span class="eq-brand">${it.brand || '—'}</span>
      <span class="eq-ref">${it.reference || ''}</span>
    </div>
  `).join('');
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
}

async function loadColorVariants(it) {
  const varBox   = document.getElementById('eq-color-variants');
  const swatches = document.getElementById('eq-color-swatches');
  varBox.style.display = 'none';
  swatches.innerHTML = '';

  const params = new URLSearchParams({ brand: it.brand||'', reference: it.reference||'', category: it.category||'' });
  const res  = await fetch(`/api/equipment-photos?${params}`);
  if (!res.ok) return;
  const data = await res.json();
  const variants = data.variants || [];

  if (variants.length > 0) {
    varBox.style.display = 'block';
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
function eqDebouncedGenerate(delay = 500) {
  clearTimeout(_eqDebTimer);
  _eqDebTimer = setTimeout(() => generateEqCard(true), delay);
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
  const brand_text     = g('eq_brand_text')?.value     || it.brand     || '';
  const reference_text = g('eq_reference_text')?.value || it.reference || '';
  const details_text   = g('eq_details_text')?.value   || it.details   || '';

  try {
    const res = await fetch('/api/generate-eq-card', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        category: it.category,
        brand: brand_text, reference: reference_text, details: details_text,
        photo_path: _eqSelectedPhotoPath || '',
        zoom, photo_x, photo_y,
        panel_y: 900, text_x: 0, text_y: 0,
        show_brand, show_reference, show_details, show_logo,
      }),
    });
    if (!res.ok) { const e = await res.json(); throw new Error(e.error); }
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const name = `${it.brand}_${it.reference || it.category}`.replace(/\s+/g,'_') + '.png';
    _lastEqCard = { url, name };
    const img = document.getElementById('eq-preview-img');
    img.onload = () => area.classList.remove('loading');
    img.src = url; img.style.display = 'block';
    document.getElementById('eq-placeholder').style.display = 'none';
    document.getElementById('eq-page-dl-btn').disabled = false;
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


@app.route("/api/sponsors")
def api_sponsors():
    """Liste tous les logos présents dans logos/ — dédupliqués par nom de stem (PNG > SVG)."""
    seen_stems = {}   # stem → fichier retenu
    if gc.LOGOS_DIR.exists():
        # Premier passage : PNG (fallback)
        for f in sorted(gc.LOGOS_DIR.iterdir()):
            if f.suffix.lower() == ".png":
                seen_stems[f.stem.lower()] = f
        # Deuxième passage : SVG écrase PNG si disponible (priorité SVG)
        for f in sorted(gc.LOGOS_DIR.iterdir()):
            if f.suffix.lower() == ".svg":
                seen_stems[f.stem.lower()] = f

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
        "nationality":  profile.get("nationality", ""),
        "hometown":     profile.get("hometown", ""),
        "age":          profile.get("age", ""),
        "achievements": profile.get("achievements", ""),
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
        panel_y    = int(data.get("panel_y",   900))
        text_x     = int(data.get("text_x",    0))
        text_y     = int(data.get("text_y",    0))
        show_brand     = bool(data.get("show_brand",     True))
        show_reference = bool(data.get("show_reference", True))
        show_details   = bool(data.get("show_details",   True))
        show_logo      = bool(data.get("show_logo",      False))
        fonts      = gec.load_eq_fonts()
        photo_path = Path(photo_path_str) if photo_path_str else None
        card       = gec.generate_equipment_card(
            category, brand, reference, details,
            fonts=fonts, photo_path=photo_path,
            zoom=zoom, photo_x=photo_x, photo_y=photo_y,
            panel_y=panel_y, text_x=text_x, text_y=text_y,
            show_brand=show_brand, show_reference=show_reference,
            show_details=show_details, show_logo=show_logo,
        )
        buf = io.BytesIO()
        card.save(buf, "PNG")   # PNG pour conserver la transparence
        buf.seek(0)
        fname = f"{brand}_{reference or category}".replace(" ", "_") + ".png"
        return send_file(buf, mimetype="image/png", download_name=fname)
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


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
