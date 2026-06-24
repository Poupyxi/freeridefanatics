#!/usr/bin/env python3
"""
Télécharge les logos depuis probikeshop.fr et les convertit en PNG.
Aucune dépendance externe requise — utilise uniquement Python + qlmanage (macOS intégré).

Lance : python3 download_logos.py
"""

import urllib.request
import ssl
import os
import subprocess
import tempfile
import shutil
from pathlib import Path

# SSL — contourne la vérification (certificats racine manquants sur macOS)
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

BASE_DIR  = Path(__file__).parent
LOGOS_DIR = BASE_DIR / "logos"
LOGOS_DIR.mkdir(exist_ok=True)

# Logos trouvés sur probikeshop.fr/pages/marques
LOGO_URLS = {
    "100percent":    "https://probikeshop.fr/cdn/shop/files/centpourcent-logo.svg",
    "burgtec":       "https://probikeshop.fr/cdn/shop/files/Burgtec-logo.svg",
    "continental":   "https://probikeshop.fr/cdn/shop/files/continental-logo.svg",
    "cushcore":      "https://probikeshop.fr/cdn/shop/files/Cushcore-logo.svg",
    "dtswiss":       "https://probikeshop.fr/cdn/shop/files/dtswiss-logo.svg",
    "rockshox":      "https://probikeshop.fr/cdn/shop/files/rockshox-logo.svg",
    "industrynine":  "https://probikeshop.fr/cdn/shop/files/industrynine-logo_761cbefc-dd05-496e-a642-b7a8998af436.svg",
    "marzocchi":     "https://probikeshop.fr/cdn/shop/files/Marzocchi-logo.svg",
    "maxxis":        "https://probikeshop.fr/cdn/shop/files/maxxis-logo.svg",
    "michelin":      "https://probikeshop.fr/cdn/shop/files/michelin-logo.svg",
    "oakley":        "https://probikeshop.fr/cdn/shop/files/Oakley-logo.svg",
    "poc":           "https://probikeshop.fr/cdn/shop/files/Poc-logo.svg",
    "schwalbe":      "https://probikeshop.fr/cdn/shop/files/schwalbe-logo.svg",
    "shimano":       "https://probikeshop.fr/cdn/shop/files/shimano-logo.svg",
    "sram":          "https://probikeshop.fr/cdn/shop/files/sram-logo.svg",
    "troyleedesigns":"https://probikeshop.fr/cdn/shop/files/troyleedesigns-logo.svg",
    "trp":           "https://probikeshop.fr/cdn/shop/files/TRP-logo.svg",
    "yeti":          "https://probikeshop.fr/cdn/shop/files/yeti-logo.svg",
}

# Logos à NE PAS écraser (déjà des vrais logos)
SKIP_IF_EXISTS = {"fox.png", "canyon.png"}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Referer': 'https://probikeshop.fr/pages/marques',
}

def download_svg(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as r:
        return r.read()

def svg_to_png_qlmanage(svg_path, out_png, size=300):
    """Convertit SVG → PNG via qlmanage (outil macOS intégré, aucun pip requis)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        result = subprocess.run(
            ["qlmanage", "-t", "-s", str(size), "-o", tmp_dir, str(svg_path)],
            capture_output=True, timeout=15
        )
        # qlmanage génère un fichier nomfichier.svg.png
        candidates = list(Path(tmp_dir).glob("*.png"))
        if not candidates:
            raise RuntimeError(f"qlmanage n'a rien généré (code {result.returncode})")
        shutil.copy(candidates[0], out_png)

def svg_to_png_pillow(svg_bytes, out_png):
    """Fallback : tente de lire le SVG comme image via Pillow (fonctionne pour certains SVGs simples)."""
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(svg_bytes))
    img.save(out_png, "PNG")

# ─────────────────────────────────────────────────────────────
print(f"📂 Dossier logos : {LOGOS_DIR}\n")

ok = skip = fail = 0

for name, url in LOGO_URLS.items():
    png_path = LOGOS_DIR / f"{name}.png"

    if png_path.name in SKIP_IF_EXISTS and png_path.exists():
        print(f"  ⏭️  {name}.png — conservé")
        skip += 1
        continue

    print(f"  ⬇️  {name}...", end=" ", flush=True)
    try:
        svg_bytes = download_svg(url)

        # Sauvegarde le SVG temporairement
        with tempfile.NamedTemporaryFile(suffix='.svg', delete=False) as f:
            f.write(svg_bytes)
            tmp_svg = Path(f.name)

        converted = False
        try:
            svg_to_png_qlmanage(tmp_svg, png_path)
            converted = True
        except Exception as e1:
            # Fallback Pillow
            try:
                svg_to_png_pillow(svg_bytes, png_path)
                converted = True
            except Exception as e2:
                # Dernier recours : sauvegarde le SVG directement
                svg_dest = LOGOS_DIR / f"{name}.svg"
                shutil.copy(tmp_svg, svg_dest)
                print(f"⚠️  SVG sauvegardé (conversion échouée : {e1})")
                fail += 1

        tmp_svg.unlink(missing_ok=True)

        if converted:
            size = png_path.stat().st_size
            print(f"✅ ({size//1024}KB)")
            ok += 1

    except Exception as e:
        print(f"❌ {e}")
        fail += 1

print(f"\n✅ {ok} convertis en PNG, {skip} conservés, {fail} en SVG (remplacement manuel possible)")
print(f"📁 {LOGOS_DIR}")
