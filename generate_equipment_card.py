#!/usr/bin/env python3
"""
generate_equipment_card.py
==========================
Génère une carte visuelle pour un item d'équipement.

Format de la carte :
  - Zone blanche (haut) : photo produit ou logo de marque
  - Zone grise (bas)    : Brand / Model / Details

Usage direct :
    python3 generate_equipment_card.py --brand "Fox Racing" --model "40 Factory" --details "RAD Prototype"
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import sys, textwrap

# ── Chemins ───────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
BG_PATH     = BASE_DIR / "equipment_card_bg.png"
FONTS_DIR   = BASE_DIR / "fonts"
LOGOS_DIR   = BASE_DIR / "logos"
EQ_PHOTOS   = BASE_DIR / "Equipment"   # sous-dossiers par catégorie : Equipment/Frame/, Equipment/Fork/, …

# Mapping noms de colonnes Sheet → noms de dossiers (essayés dans l'ordre)
CATEGORY_FOLDERS = {
    "Frame":        ["Frame"],
    "Fork":         ["Fork"],
    "Rear Shock":   ["Rear Shock", "Shock"],
    "Handlebar":    ["Handlebar", "Bars"],
    "Dropper Post": ["Dropper Post", "Dropper"],
    "Saddle":       ["Saddle"],
    "Crankset":     ["Crankset", "Cranks"],
    "Derailleur":   ["Derailleur"],
    "Brake Lever":  ["Brake Lever", "Brakes"],
    "Brake Caliper":["Brake Caliper", "Brakes"],
    "Wheels":       ["Wheels", "Wheelset"],
    "Tires":        ["Tires", "Tyres"],
    "Pedals":       ["Pedals"],
    "Shoes":        ["Shoes"],
    "Helmet":       ["Helmet"],
    "Protection":   ["Protection", "Pads"],
    "Goggles":      ["Goggles"],
}

# ── Dimensions ────────────────────────────────────────────────────────────────
W, H         = 970, 1250
PANEL_Y      = int(H * 0.72)      # début zone texte
BORDER       = 10
LIME         = (200, 212, 0)
DARK         = (60, 58, 58)
WHITE        = (255, 255, 255)
RADIUS       = 36

# ── Polices ───────────────────────────────────────────────────────────────────
def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    # Try multiple locations
    candidates = [
        FONTS_DIR / name,
        BASE_DIR / name,                          # root du projet
        Path("/System/Library/Fonts") / name,
        Path("/usr/share/fonts/truetype") / name,
    ]
    for p in candidates:
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()

def load_eq_fonts():
    return {
        "label":    _font("BebasNeue-Regular.ttf", 44),
        "value":    _font("BebasNeue-Regular.ttf", 80),
        "value_sm": _font("BebasNeue-Regular.ttf", 56),
        "cat":      _font("BebasNeue-Regular.ttf", 34),
    }

# ── Background ────────────────────────────────────────────────────────────────
TRANSPARENT = (0, 0, 0, 0)
DARK_A       = (60, 58, 58, 255)
LIME_A       = (200, 212, 0, 255)

def _rounded_clip_mask(size, radius) -> Image.Image:
    """Masque blanc en forme de rectangle arrondi — pour clipper la carte."""
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (size[0]-1, size[1]-1)],
                                            radius=radius, fill=255)
    return mask

def _make_bg_with_panel(panel_y: int = None) -> Image.Image:
    """
    Crée le fond RGBA :
      - Zone photo : fond blanc (pour le détourage futur)
      - Panel bas  : foncé opaque
      - Bordure    : lime
    """
    if panel_y is None:
        panel_y = PANEL_Y
    img  = Image.new("RGBA", (W, H), TRANSPARENT)
    draw = ImageDraw.Draw(img)

    # Zone photo : rectangle blanc arrondi en haut
    draw.rounded_rectangle([(0, 0), (W-1, panel_y)],
                            radius=RADIUS, fill=(255, 255, 255, 255))

    # Panel bas foncé (coins arrondis en bas seulement)
    draw.rounded_rectangle([(BORDER, panel_y), (W-BORDER-1, H-BORDER-1)],
                            radius=RADIUS-4, fill=DARK_A)

    # Bordure lime tout autour (dessinée en dernier pour être par-dessus)
    draw.rounded_rectangle([(0, 0), (W-1, H-1)],
                            radius=RADIUS, outline=LIME_A, width=BORDER)
    return img

def _make_bg() -> Image.Image:
    return _make_bg_with_panel(PANEL_Y)

# ── Chercher photo produit + variantes couleur ────────────────────────────────
def _eq_slug(s: str) -> str:
    """Normalise brand/référence pour comparaison : minuscules, sans espaces/tirets."""
    return s.lower().replace(" ", "").replace("-", "").replace("/", "")

def _search_dirs(category: str) -> list:
    """Retourne les dossiers à chercher pour une catégorie donnée."""
    dirs = []
    if EQ_PHOTOS.exists():
        for folder_name in CATEGORY_FOLDERS.get(category, [category]):
            d = EQ_PHOTOS / folder_name
            if d.exists():
                dirs.append(d)
        dirs.append(EQ_PHOTOS)   # fallback : racine Equipment/
    return dirs

def find_eq_photo_variants(brand: str, reference: str, category: str = "") -> list:
    """
    Retourne la liste de tous les fichiers correspondant à brand+reference
    dans le dossier Equipment/{category}/.

    Naming convention attendu : {Brand}{Model}{Color}.ext
    ex : ZerodeG3black.webp, ZerodeG3creme.webp

    Retourne : liste de Path triée par nom.
    """
    if not EQ_PHOTOS.exists():
        return []
    brand_slug = _eq_slug(brand)
    ref_slug   = _eq_slug(reference)
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    results = []
    seen = set()

    for d in _search_dirs(category):
        for f in sorted(d.iterdir()):
            if f.suffix.lower() not in exts:
                continue
            name_slug = _eq_slug(f.stem)
            # Correspond si le nom commence par brand+model (ou brand seul)
            if name_slug.startswith(brand_slug + ref_slug) or \
               (ref_slug and name_slug.startswith(brand_slug) and ref_slug in name_slug) or \
               (not ref_slug and name_slug.startswith(brand_slug)):
                if f not in seen:
                    seen.add(f)
                    results.append(f)
    return results

def find_eq_photo(brand: str, reference: str, category: str = "") -> Path | None:
    """Retourne la 1ʳᵉ photo trouvée (sans préférence de couleur)."""
    variants = find_eq_photo_variants(brand, reference, category)
    return variants[0] if variants else None

def find_logo(brand: str) -> Path | None:
    """Cherche le logo de la marque dans logos/."""
    if not LOGOS_DIR.exists():
        return None
    brand_slug = brand.lower().replace(" ", "_").replace("/", "_")
    for stem in [brand_slug, brand.lower(), brand_slug.split("_")[0]]:
        for ext in [".svg", ".png"]:
            p = LOGOS_DIR / (stem + ext)
            if p.exists():
                return p
    return None

# ── Placement image produit ───────────────────────────────────────────────────
def _place_product_image(card: Image.Image, photo_path: Path,
                         zoom: float = 1.0, offset_x: int = 0, offset_y: int = 0,
                         panel_y: int = None):
    """Place la photo en arrière-plan de la zone photo (contain + zoom), centrée."""
    if panel_y is None:
        panel_y = PANEL_Y

    # Zone photo = toute la carte au-dessus du panel
    zone_w = W - BORDER * 2
    zone_h = panel_y - BORDER
    zone_x = BORDER
    zone_y = BORDER

    photo = Image.open(photo_path).convert("RGBA")

    # Contain : scale pour tenir dans la zone (avec marge 8%)
    margin = 0.08
    max_w = int(zone_w * (1 - margin * 2))
    max_h = int(zone_h * (1 - margin * 2))
    ratio = min(max_w / photo.width, max_h / photo.height)
    base_w = max(1, int(photo.width  * ratio))
    base_h = max(1, int(photo.height * ratio))
    photo = photo.resize((base_w, base_h), Image.LANCZOS)

    # Appliquer le zoom utilisateur
    if zoom != 1.0:
        nw = max(1, int(photo.width  * zoom))
        nh = max(1, int(photo.height * zoom))
        photo = photo.resize((nw, nh), Image.LANCZOS)

    # Position centrée + offset utilisateur
    px = zone_x + (zone_w - photo.width)  // 2 + offset_x
    py = zone_y + (zone_h - photo.height) // 2 + offset_y

    # Coller via un layer intermédiaire clippé à la zone photo — ne déborde pas dans le panel
    photo_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    photo_layer.paste(photo, (px, py), mask=photo.split()[3])
    # Masque : uniquement la zone photo (au-dessus du panel)
    zone_mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(zone_mask).rectangle([(zone_x, zone_y), (zone_x + zone_w, zone_y + zone_h)], fill=255)
    photo_layer.putalpha(zone_mask)
    card = Image.alpha_composite(card, photo_layer)
    return card

def _place_logo_centered(card: Image.Image, logo_path: Path,
                          zoom: float = 1.0, offset_x: int = 0, offset_y: int = 0,
                          panel_y: int = None):
    """Centre le logo de marque en grand dans la zone transparente (fallback)."""
    if panel_y is None:
        panel_y = PANEL_Y
    zone_w = W - BORDER * 2
    zone_h = panel_y - BORDER - 20
    max_w  = int(zone_w * 0.55 * zoom)
    max_h  = int(zone_h * 0.35 * zoom)

    try:
        from cairosvg import svg2png
        import io
        logo = Image.open(io.BytesIO(svg2png(url=str(logo_path), output_width=max_w*2))).convert("RGBA")
    except Exception:
        logo = Image.open(logo_path).convert("RGBA")

    logo.thumbnail((max_w, max_h), Image.LANCZOS)
    px = BORDER + (zone_w - logo.width) // 2 + offset_x
    py = BORDER + (zone_h - logo.height) // 2 + offset_y
    card.paste(logo, (px, py), mask=logo.split()[3])

# ── Texte dans le panel ───────────────────────────────────────────────────────
def _draw_panel_text(draw: ImageDraw.Draw, fonts: dict,
                     category: str, brand: str, reference: str, details: str,
                     panel_y: int = None, text_x: int = 0, text_y: int = 0,
                     show_brand: bool = True, show_reference: bool = True,
                     show_details: bool = True):
    """Dessine Category / Brand / Model / Details dans la zone grise."""
    if panel_y is None:
        panel_y = PANEL_Y
    x   = BORDER + 40 + text_x
    y   = panel_y + 24 + text_y
    gap = 8

    GREY  = (160, 160, 160, 255)
    WHITE = (255, 255, 255, 255)
    font  = fonts["label"]   # même police pour tout
    fh    = font.size
    row_gap = 12

    def tw(text):
        return draw.textbbox((0, 0), text, font=font)[2]

    # Colonne alignée sur le label le plus large
    labels = []
    if show_brand     and brand:     labels.append("Brand")
    if show_reference and reference: labels.append("Reference")
    if show_details   and details:   labels.append("Detail")
    col_x = x + (max((tw(l) for l in labels), default=0) + 20) if labels else x

    # Catégorie (gris clair, inchangé — police cat plus petite)
    if category:
        draw.text((x, y), category.upper(), font=fonts["cat"], fill=GREY)
        y += fonts["cat"].size + gap

    # Brand
    if show_brand and brand:
        draw.text((x,     y), "Brand",       font=font, fill=LIME_A)
        draw.text((col_x, y), brand.upper(), font=font, fill=WHITE)
        y += fh + row_gap

    # Reference
    if show_reference and reference:
        draw.text((x,     y), "Reference",          font=font, fill=LIME_A)
        draw.text((col_x, y), reference.upper(),    font=font, fill=WHITE)
        y += fh + row_gap

    # Detail
    if show_details and details:
        detail_lines = textwrap.wrap(details, width=22)
        for i, line in enumerate(detail_lines[:3]):
            draw.text((x,     y), "Detail" if i == 0 else "", font=font, fill=LIME_A)
            draw.text((col_x, y), line,                        font=font, fill=WHITE)
            y += fh + 4

# ── Fonction principale ───────────────────────────────────────────────────────
def generate_equipment_card(
    category: str    = "",
    brand: str       = "",
    reference: str   = "",
    details: str     = "",
    fonts: dict      = None,
    photo_path: Path = None,
    zoom: float      = 1.0,
    photo_x: int     = 0,
    photo_y: int     = 0,
    panel_y: int     = None,
    text_x: int      = 0,
    text_y: int      = 0,
    show_brand: bool     = True,
    show_reference: bool = True,
    show_details: bool   = True,
    show_logo: bool      = False,
) -> Image.Image:
    """
    Génère et retourne une image PIL RGBA de carte équipement.

    Args:
        category   : ex. "Frame", "Fork", "Helmet"
        brand      : ex. "Zerode"
        reference  : ex. "G3"
        details    : ex. "Mid high-pivot · 29er"
        fonts      : dict de polices (chargé via load_eq_fonts si None)
        photo_path : chemin vers la photo produit (auto-détecté si None)
    """
    if fonts is None:
        fonts = load_eq_fonts()
    if panel_y is None:
        panel_y = PANEL_Y

    card = _make_bg_with_panel(panel_y)

    # ── Image produit ──
    if photo_path is None:
        photo_path = find_eq_photo(brand, reference, category)

    if photo_path and photo_path.exists():
        card = _place_product_image(card, photo_path,
                                    zoom=zoom, offset_x=photo_x, offset_y=photo_y,
                                    panel_y=panel_y)
    else:
        # Fallback : logo de marque
        logo_path = find_logo(brand)
        if logo_path and logo_path.exists() and logo_path.suffix.lower() == ".png":
            try:
                _place_logo_centered(card, logo_path,
                                     zoom=zoom, offset_x=photo_x, offset_y=photo_y,
                                     panel_y=panel_y)
            except Exception:
                pass

    # ── Texte dans le panel ──
    draw = ImageDraw.Draw(card)
    _draw_panel_text(draw, fonts, category, brand, reference, details,
                     panel_y=panel_y, text_x=text_x, text_y=text_y,
                     show_brand=show_brand, show_reference=show_reference,
                     show_details=show_details)

    # ── Logo de marque en bas du panel (optionnel) ──
    if show_logo and brand:
        logo_path = find_logo(brand)
        if logo_path and logo_path.exists() and logo_path.suffix.lower() == ".png":
            try:
                logo = Image.open(logo_path).convert("RGBA")
                logo_h = 60
                ratio  = logo_h / logo.height
                logo   = logo.resize((max(1, int(logo.width * ratio)), logo_h), Image.LANCZOS)
                lx = (W - logo.width) // 2
                ly = H - BORDER - logo_h - 20
                card.paste(logo, (lx, ly), mask=logo.split()[3])
            except Exception:
                pass

    # ── Redessiner la bordure lime par-dessus la photo ──
    draw.rounded_rectangle([(0, 0), (W-1, H-1)], radius=RADIUS, outline=LIME_A, width=BORDER)

    # ── Clip arrondi — rien ne dépasse la bordure ──
    card.putalpha(_rounded_clip_mask((W, H), RADIUS))

    return card   # RGBA → sauvegarder en PNG


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse, io
    parser = argparse.ArgumentParser()
    parser.add_argument("--category",  default="Bike")
    parser.add_argument("--brand",     default="Crestline")
    parser.add_argument("--model",     default="RS 205 VHP")
    parser.add_argument("--details",   default="Mid high-pivot DH")
    parser.add_argument("--photo",     default=None)
    parser.add_argument("--out",       default="eq_card_preview.jpg")
    args = parser.parse_args()

    fonts = load_eq_fonts()
    photo = Path(args.photo) if args.photo else None
    card  = generate_equipment_card(args.category, args.brand, args.model, args.details,
                                     fonts=fonts, photo_path=photo)
    card.save(args.out, "JPEG", quality=92)
    print(f"✓ Carte générée : {args.out}")
