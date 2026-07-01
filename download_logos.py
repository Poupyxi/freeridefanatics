#!/usr/bin/env python3
"""
Télécharge les logos depuis probikeshop.fr, Brandfetch CDN et sites officiels,
puis les convertit en PNG.
Aucune dépendance externe requise — utilise Python + qlmanage (macOS intégré).

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

# ── Logos existants (probikeshop.fr) ─────────────────────────────────────────
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
    # ── Marques manquantes — multiples sources (essayées dans l'ordre) ────────
    "hope":          [
        "https://cdn.brandfetch.io/hopetechnology.com/w/512/h/512/logo",
        "https://logo.clearbit.com/hopetechnology.com",
        "https://www.hopetechnology.com/wp-content/themes/hope/img/hope-logo.svg",
    ],
    "renthal":       [
        "https://cdn.brandfetch.io/renthal.com/w/512/h/512/logo",
        "https://logo.clearbit.com/renthal.com",
        "https://www.renthal.com/wp-content/themes/renthal/images/logo.svg",
    ],
    "crankbrothers": [
        "https://cdn.brandfetch.io/crankbrothers.com/w/512/h/512/logo",
        "https://logo.clearbit.com/crankbrothers.com",
        "https://www.crankbrothers.com/cdn/shop/files/cb-logo-light.svg",
    ],
    "ethirteen":     [
        "https://cdn.brandfetch.io/ethirteen.com/w/512/h/512/logo",
        "https://logo.clearbit.com/ethirteen.com",
        "https://www.ethirteen.com/wp-content/uploads/2021/01/e13-logo.png",
    ],
    "deity":         [
        "https://cdn.brandfetch.io/deitybikes.com/w/512/h/512/logo",
        "https://logo.clearbit.com/deitybikes.com",
        "https://deitybikes.com/wp-content/themes/deity/img/logo.svg",
    ],
    "raceface":      [
        "https://cdn.brandfetch.io/raceface.com/w/512/h/512/logo",
        "https://logo.clearbit.com/raceface.com",
        "https://www.raceface.com/cdn/shop/files/RF_Logo_White.svg",
    ],
    "magura":        [
        "https://cdn.brandfetch.io/magura.com/w/512/h/512/logo",
        "https://logo.clearbit.com/magura.com",
        "https://www.magura.com/fileadmin/templates/magura/images/logo.svg",
    ],
    "pinion":        [
        "https://cdn.brandfetch.io/pinion.eu/w/512/h/512/logo",
        "https://logo.clearbit.com/pinion.eu",
        "https://pinion.eu/wp-content/uploads/2020/03/pinion-logo.svg",
    ],
    "enve":          [
        "https://cdn.brandfetch.io/enve.com/w/512/h/512/logo",
        "https://logo.clearbit.com/enve.com",
        "https://www.enve.com/cdn/shop/files/ENVE-wordmark-white.svg",
    ],
    "nukeproof":     [
        "https://cdn.brandfetch.io/nukeproof.com/w/512/h/512/logo",
        "https://logo.clearbit.com/nukeproof.com",
        "https://www.nukeproof.com/cdn/shop/files/nukeproof-logo-white.svg",
    ],
    "canecreek":     [
        "https://cdn.brandfetch.io/canecreek.com/w/512/h/512/logo",
        "https://logo.clearbit.com/canecreek.com",
        "https://www.canecreek.com/wp-content/themes/canecreek/img/logo.svg",
    ],
    "wolftooth":     [
        "https://cdn.brandfetch.io/wolftoothcomponents.com/w/512/h/512/logo",
        "https://logo.clearbit.com/wolftoothcomponents.com",
        "https://www.wolftoothcomponents.com/cdn/shop/files/wolf-tooth-logo.svg",
    ],
    "spank":         [
        "https://cdn.brandfetch.io/spankind.com/w/512/h/512/logo",
        "https://logo.clearbit.com/spankind.com",
        "https://spankind.com/wp-content/themes/spank/img/logo.svg",
    ],
}

# Logos à NE PAS écraser (déjà des vrais logos)
SKIP_IF_EXISTS = {"fox.png", "canyon.png"}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Referer': 'https://probikeshop.fr/pages/marques',
}

def download_url(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as r:
        return r.read()

def download_svg(url):
    return download_url(url)

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

MANUAL_FALLBACK = {
    "hope":         "https://brandfetch.com/hopetechnology.com",
    "renthal":      "https://brandfetch.com/renthal.com",
    "crankbrothers":"https://brandfetch.com/crankbrothers.com",
    "ethirteen":    "https://brandfetch.com/ethirteen.com",
    "deity":        "https://brandfetch.com/deitybikes.com",
    "raceface":     "https://brandfetch.com/raceface.com",
    "magura":       "https://brandfetch.com/magura.com",
    "pinion":       "https://brandfetch.com/pinion.eu",
    "enve":         "https://brandfetch.com/enve.com",
    "nukeproof":    "https://brandfetch.com/nukeproof.com",
    "canecreek":    "https://brandfetch.com/canecreek.com",
    "wolftooth":    "https://brandfetch.com/wolftoothcomponents.com",
    "spank":        "https://brandfetch.com/spankind.com",
}

def try_download_and_convert(name, urls, png_path):
    """Essaie chaque URL dans l'ordre, retourne True si succès."""
    if isinstance(urls, str):
        urls = [urls]
    for url in urls:
        try:
            data = download_url(url)
            is_svg = b"<svg" in data[:500] or url.lower().endswith(".svg")
            if is_svg:
                with tempfile.NamedTemporaryFile(suffix='.svg', delete=False) as f:
                    f.write(data)
                    tmp_svg = Path(f.name)
                converted = False
                try:
                    svg_to_png_qlmanage(tmp_svg, png_path)
                    converted = True
                except Exception:
                    try:
                        svg_to_png_pillow(data, png_path)
                        converted = True
                    except Exception:
                        svg_dest = LOGOS_DIR / f"{name}.svg"
                        shutil.copy(tmp_svg, svg_dest)
                tmp_svg.unlink(missing_ok=True)
                if converted:
                    return True, url
            else:
                # PNG direct
                import io
                from PIL import Image
                img = Image.open(io.BytesIO(data)).convert("RGBA")
                img.save(png_path, "PNG")
                return True, url
        except Exception:
            continue
    return False, None

for name, urls in LOGO_URLS.items():
    png_path = LOGOS_DIR / f"{name}.png"

    if png_path.name in SKIP_IF_EXISTS and png_path.exists():
        print(f"  ⏭️  {name}.png — conservé")
        skip += 1
        continue

    if png_path.exists() and isinstance(urls, str):
        # Logos déjà présents (ancienne version) — on ne ré-écrase pas
        print(f"  ⏭️  {name}.png — déjà présent")
        skip += 1
        continue

    print(f"  ⬇️  {name}...", end=" ", flush=True)
    success, used_url = try_download_and_convert(name, urls, png_path)
    if success:
        size = png_path.stat().st_size if png_path.exists() else 0
        source = used_url.split("/")[2] if used_url else "?"
        print(f"✅  ({source}, {size//1024}KB)")
        ok += 1
    else:
        print(f"❌  toutes sources échouées")
        fail += 1

print(f"\n✅ {ok} téléchargés, ⏭️  {skip} conservés, ❌ {fail} échoués")
if fail:
    print("\n  Logos manquants — télécharge manuellement depuis Brandfetch :")
    for name in MANUAL_FALLBACK:
        if not (LOGOS_DIR / f"{name}.png").exists():
            print(f"    {name:15s} → {MANUAL_FALLBACK[name]}")
print(f"\n📁 {LOGOS_DIR}")
