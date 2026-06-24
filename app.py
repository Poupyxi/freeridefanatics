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
    padding: 16px 24px;
    display: flex;
    align-items: center;
    gap: 16px;
  }
  header h1 { font-size: 1.3rem; color: #C8D400; letter-spacing: 2px; text-transform: uppercase; }
  header span { color: #888; font-size: 0.85rem; }

  .layout {
    display: grid;
    grid-template-columns: 340px 1fr;
    gap: 0;
    height: calc(100vh - 65px);
  }

  /* ── PANNEAU GAUCHE ── */
  .panel {
    background: #222;
    border-right: 1px solid #333;
    overflow-y: auto;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .section-title {
    font-size: 0.7rem;
    letter-spacing: 2px;
    color: #C8D400;
    text-transform: uppercase;
    margin-bottom: 8px;
    font-weight: 700;
  }

  select, input[type=range] { width: 100%; }

  select {
    background: #333;
    color: #eee;
    border: 1px solid #444;
    border-radius: 6px;
    padding: 10px 12px;
    font-size: 0.95rem;
    cursor: pointer;
    appearance: none;
  }
  select:focus { outline: none; border-color: #C8D400; }

  .slider-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 6px;
  }
  .slider-label { font-size: 0.82rem; color: #aaa; width: 120px; flex-shrink: 0; }
  .slider-val { font-size: 0.82rem; color: #C8D400; width: 42px; text-align: right; flex-shrink: 0; }
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
</style>
</head>
<body>

<header>
  <h1>⛰️ Freeride Fanatics</h1>
  <span>Card Generator</span>
  <button class="btn btn-reload" onclick="reloadExcel()">↺ Recharger l'Excel</button>
</header>

<div class="layout">

  <!-- PANNEAU GAUCHE -->
  <div class="panel">

    <!-- Rider -->
    <div>
      <div class="section-title">Rider</div>
      <select id="rider" onchange="onRiderChange()">
        <option value="">— Sélectionne un rider —</option>
      </select>
    </div>

    <!-- Sponsors -->
    <div>
      <div class="section-title">Sponsors <span id="sponsor-mode" class="auto-badge">AUTO depuis Excel</span></div>
      <input type="text" id="sponsor-search" placeholder="🔍 Rechercher une marque..." oninput="filterSponsors(this.value)"
        style="width:100%;background:#1a1a1a;border:1px solid #3a3a3a;border-radius:6px;padding:7px 10px;color:#eee;font-size:0.82rem;margin-bottom:8px;outline:none">
      <div class="sponsors-grid" id="sponsors-grid"></div>
      <div id="sponsor-empty" style="display:none;font-size:0.8rem;color:#555;text-align:center;padding:8px">Aucun logo trouvé</div>
    </div>

    <!-- Photo -->
    <div>
      <div class="section-title">Photo</div>
      <div class="slider-row">
        <span class="slider-label">Zoom</span>
        <input type="range" id="photo_zoom" min="50" max="300" value="100" oninput="updateSliderPct(this,'val_zoom')">
        <span class="slider-val" id="val_zoom">100%</span>
      </div>
      <div class="slider-row">
        <span class="slider-label">Offset X</span>
        <input type="range" id="offset_x" min="-600" max="600" value="-200" oninput="updateSlider(this,'val_x')">
        <span class="slider-val" id="val_x">-200</span>
      </div>
      <div class="slider-row">
        <span class="slider-label">Offset Y</span>
        <input type="range" id="offset_y" min="-600" max="600" value="0" oninput="updateSlider(this,'val_y')">
        <span class="slider-val" id="val_y">0</span>
      </div>
    </div>

    <!-- Texte -->
    <div>
      <div class="section-title">Texte</div>
      <div class="slider-row">
        <span class="slider-label">Position X</span>
        <input type="range" id="text_x" min="400" max="900" value="580" oninput="updateSlider(this,'val_tx')">
        <span class="slider-val" id="val_tx">580</span>
      </div>
      <div class="slider-row">
        <span class="slider-label">Position Y</span>
        <input type="range" id="text_top" min="0" max="400" value="80" oninput="updateSlider(this,'val_tt')">
        <span class="slider-val" id="val_tt">80</span>
      </div>
      <div class="slider-row">
        <span class="slider-label">Taille titre</span>
        <input type="range" id="sz_label" min="14" max="72" value="36" oninput="updateSlider(this,'val_sl')">
        <span class="slider-val" id="val_sl">36</span>
      </div>
      <div class="slider-row">
        <span class="slider-label">Taille valeur</span>
        <input type="range" id="sz_value" min="14" max="90" value="54" oninput="updateSlider(this,'val_sv')">
        <span class="slider-val" id="val_sv">54</span>
      </div>
      <div class="slider-row">
        <span class="slider-label">Taille valeur SM</span>
        <input type="range" id="sz_value_sm" min="14" max="72" value="40" oninput="updateSlider(this,'val_ss')">
        <span class="slider-val" id="val_ss">40</span>
      </div>
      <div class="slider-row">
        <span class="slider-label">Espacement</span>
        <input type="range" id="gap" min="0" max="80" value="50" oninput="updateSlider(this,'val_gap')">
        <span class="slider-val" id="val_gap">50</span>
      </div>
    </div>

    <!-- Logos -->
    <div>
      <div class="section-title">Logos</div>
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
        <input type="range" id="logo_h" min="20" max="200" value="38" oninput="updateSlider(this,'val_lh')">
        <span class="slider-val" id="val_lh">38</span>
      </div>
      <div class="slider-row">
        <span class="slider-label">Position Y</span>
        <input type="range" id="logo_y" min="900" max="1340" value="1280" oninput="updateSlider(this,'val_ly')">
        <span class="slider-val" id="val_ly">1280</span>
      </div>
      <div class="slider-row">
        <span class="slider-label">Position X</span>
        <input type="range" id="logo_x" min="-1" max="1060" value="-1" oninput="updateSlider(this,'val_lx',true)">
        <span class="slider-val" id="val_lx">Auto</span>
      </div>
    </div>

    <!-- Actions -->
    <div>
      <button class="btn btn-generate" onclick="generate()">▶ Générer la carte</button>
      <button class="btn btn-download" id="btn-dl" disabled onclick="download()">⬇ Télécharger</button>
      <div class="error-msg" id="error-msg"></div>
    </div>

  </div>

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

<script>
// ── État ──────────────────────────────────────────────────────────────────
let riders = [];
let selectedSponsors = new Set();  // vide = auto
let lastSlug = null;

// ── Init ──────────────────────────────────────────────────────────────────
async function init() {
  const res = await fetch('/api/riders');
  riders = await res.json();
  const sel = document.getElementById('rider');
  riders.forEach(r => {
    const opt = document.createElement('option');
    opt.value = r.slug;
    opt.textContent = `${r.prenom} ${r.nom}  (${r.genre === 'F' ? 'Women' : 'Men'})`;
    sel.appendChild(opt);
  });

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

function onRiderChange() { lastSlug = null; document.getElementById('btn-dl').disabled = true; }

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
}

function updateSlider(el, valId, autoMode=false) {
  const v = parseInt(el.value);
  document.getElementById(valId).textContent = (autoMode && v === -1) ? 'Auto' : v;
}
function updateSliderPct(el, valId) {
  document.getElementById(valId).textContent = el.value + '%';
}
function switchDir() {
  const input  = document.getElementById('logo_dir');
  const toggle = document.getElementById('dir-toggle');
  const isCol  = input.value === 'col';
  input.value  = isCol ? 'row' : 'col';
  toggle.classList.toggle('on', !isCol);
  document.getElementById('dir-label').textContent = isCol ? '▶▶ LIGNE' : '▼▼ COLONNE';
}

// ── Génération ────────────────────────────────────────────────────────────
async function generate() {
  const slug = document.getElementById('rider').value;
  if (!slug) { alert('Sélectionne un rider.'); return; }

  const area = document.getElementById('preview-area');
  area.classList.add('loading');
  document.getElementById('error-msg').style.display = 'none';

  const params = {
    slug,
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

init();
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
    data = [{"slug":   f"{p['nom'].lower().replace(' ','_')}_{p['prenom'].lower()}",
             "prenom": p["prenom"],
             "nom":    p["nom"],
             "genre":  p["genre"]}
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


@app.route("/api/reload", methods=["POST"])
def api_reload():
    reload_engine()
    return jsonify({"ok": True})


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
