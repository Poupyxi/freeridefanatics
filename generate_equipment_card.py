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
import sys, textwrap, subprocess, tempfile

# ── Chemins ───────────────────────────────────────────────────────────────────
BASE_DIR     = Path(__file__).parent
BG_PATH      = BASE_DIR / "equipment_card_bg.png"
BG_V2_PATH   = BASE_DIR / "background equipementv2.png"  # fond avec encoche catégorie
FONTS_DIR    = BASE_DIR / "fonts"
LOGOS_DIR    = BASE_DIR / "logos"
EQ_PHOTOS    = BASE_DIR / "Equipment"   # sous-dossiers par catégorie
PPRIDERS_DIR = BASE_DIR / "PPRiders"    # PP dédiées au badge reel/équipement

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
# Utilise les dimensions du fond v2 si disponible (1080×1350), sinon fallback
if BG_V2_PATH.exists():
    _bg_img   = Image.open(BG_V2_PATH).convert("RGBA")
    W, H      = _bg_img.size          # 1080 × 1350
    PANEL_Y   = 1051                  # où commence le panel texte (après bordure lime)
    NOTCH_X1  = 10                    # encoche catégorie : bord gauche
    NOTCH_X2  = 220                   # bord droit de l'encoche
    NOTCH_Y1  = 992                   # haut de l'encoche (sous la bordure lime)
    NOTCH_Y2  = 1040                  # bas de l'encoche (avant la bordure lime du panel)
    # Pré-calculer l'overlay : la zone photo (alpha=102 dans le PNG) → transparent
    # pour qu'on puisse coller photo_bg en dessous
    import numpy as _np
    _arr = _np.array(_bg_img)
    _photo_zone_mask = (_arr[:,:,3] > 0) & (_arr[:,:,3] < 200)  # semi-transparent = zone photo
    _bg_arr = _np.array(_bg_img.copy())
    _bg_arr[_photo_zone_mask, 3] = 0   # rendre transparent la zone photo
    _BG_OVERLAY = Image.fromarray(_bg_arr)  # fond : bordure + panel + encoche opaques, zone photo transparente
    del _np, _arr, _bg_arr
else:
    _bg_img    = None
    _BG_OVERLAY = None
    W, H      = 970, 1250
    PANEL_Y   = int(H * 0.72)
    NOTCH_X1  = NOTCH_X2 = NOTCH_Y1 = NOTCH_Y2 = 0

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

def _make_bg_with_panel(panel_y: int = None,
                        photo_bg: tuple = (255, 255, 255),
                        use_v2: bool = False) -> Image.Image:
    """
    Crée le fond RGBA.
    use_v2=True  → utilise background equipementv2.png (si disponible)
    use_v2=False → fond programmatique classique (V1)
    """
    if panel_y is None:
        panel_y = PANEL_Y if use_v2 else int(H * 0.72)

    if _BG_OVERLAY is not None and use_v2:
        # ── Fond v2 : coller photo_bg sous l'overlay (zone photo transparente) ──
        base = Image.new("RGBA", (W, H), (*photo_bg, 255))
        return Image.alpha_composite(base, _BG_OVERLAY)

    # ── V1 programmatique ──
    img  = Image.new("RGBA", (W, H), TRANSPARENT)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([(0, 0), (W-1, panel_y)],
                            radius=RADIUS, fill=(*photo_bg, 255))
    draw.rounded_rectangle([(BORDER, panel_y), (W-BORDER-1, H-BORDER-1)],
                            radius=RADIUS-4, fill=DARK_A)
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
                         panel_y: int = None, photo_bg: tuple = (255, 255, 255)):
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

    # Layer initialisé avec photo_bg — les pixels hors-photo gardent la bonne couleur
    photo_layer = Image.new("RGBA", (W, H), (*photo_bg, 0))
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
                     show_details: bool = True, use_v2: bool = False):
    """Dessine Category / Brand / Model / Details dans la zone grise."""
    if panel_y is None:
        panel_y = PANEL_Y if use_v2 else int(H * 0.72)
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

    # Catégorie : affichée dans le panel en V1, dans l'encoche en V2
    if category and not use_v2:
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
    photo_bg: tuple      = (255, 255, 255),
    use_v2: bool         = False,
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
        panel_y = PANEL_Y if use_v2 else int(H * 0.72)

    card = _make_bg_with_panel(panel_y, photo_bg=photo_bg, use_v2=use_v2)

    # ── Image produit ──
    if photo_path is None:
        photo_path = find_eq_photo(brand, reference, category)

    if photo_path and photo_path.exists():
        card = _place_product_image(card, photo_path,
                                    zoom=zoom, offset_x=photo_x, offset_y=photo_y,
                                    panel_y=panel_y, photo_bg=photo_bg)
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
                     show_details=show_details, use_v2=use_v2)

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

    if _BG_OVERLAY is not None and use_v2:
        # ── V2 : bordure déjà dans le fond PNG, écrire catégorie dans l'encoche ──
        if category:
            font_notch = _font("BebasNeue-Regular.ttf", 36)
            bbox = draw.textbbox((0, 0), category.upper(), font=font_notch)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            notch_cx = (NOTCH_X1 + NOTCH_X2) // 2
            notch_cy = (NOTCH_Y1 + NOTCH_Y2) // 2
            draw.text((notch_cx - tw // 2, notch_cy - th // 2 - bbox[1]),
                      category.upper(), font=font_notch, fill=LIME_A)
    else:
        # ── V1 : redessiner la bordure lime + clip arrondi ──
        draw.rounded_rectangle([(0, 0), (W-1, H-1)], radius=RADIUS, outline=LIME_A, width=BORDER)
        card.putalpha(_rounded_clip_mask((W, H), RADIUS))

    return card   # RGBA → sauvegarder en PNG


# ── Rider photo lookup ────────────────────────────────────────────────────────
def find_rider_photo(instagram: str) -> "Path | None":
    """Cherche la PP du rider dans PPRIDERS/ par handle Instagram."""
    if not PPRIDERS_DIR.exists():
        return None
    handle = instagram.lstrip("@").lower()
    # version sans ponctuation (pour les noms de fichiers qui ont supprimé les points/tirets)
    handle_stripped = handle.replace(".", "").replace("-", "")
    for ext in [".jpg", ".jpeg", ".png"]:
        for stem in [f"@{handle}", handle]:
            p = PPRIDERS_DIR / (stem + ext)
            if p.exists():
                return p
    for f in sorted(PPRIDERS_DIR.iterdir()):
        if f.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue
        stem = f.stem.lower().lstrip("@")
        stem_stripped = stem.replace(".", "").replace("-", "")
        if handle in stem or stem in handle:
            return f
        if handle_stripped and (handle_stripped in stem_stripped or stem_stripped in handle_stripped):
            return f
    return None


# ── Badge "Rider's Selection" ─────────────────────────────────────────────────
def draw_rider_badge(card: Image.Image, rider_photo_path: Path,
                     panel_y: int = None,
                     badge_radius: int = 58,
                     instagram: str = "") -> Image.Image:
    """
    Dessine un badge circulaire avec la PP du rider, centré sur la jointure
    photo/panel, côté droit de la carte.
    badge_radius : rayon du cercle en px (slider côté UI)
    instagram    : handle affiché en vert sous le cercle
    """
    if panel_y is None:
        panel_y = PANEL_Y

    R       = max(20, badge_radius)
    BORDER  = max(3, R // 12)
    PILL_H  = 32
    cx      = W - R - 28
    cy      = panel_y

    badge_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(badge_layer)

    # ── Cercle liseré lime ──
    bd.ellipse([(cx - R - BORDER, cy - R - BORDER),
                (cx + R + BORDER, cy + R + BORDER)],
               fill=LIME_A)

    # ── Photo rider en cercle ──
    try:
        pp = Image.open(rider_photo_path).convert("RGBA")
        s  = min(pp.width, pp.height)
        pp = pp.crop(((pp.width - s) // 2, (pp.height - s) // 2,
                      (pp.width + s) // 2, (pp.height + s) // 2))
        pp = pp.resize((R * 2, R * 2), Image.LANCZOS)
        circ = Image.new("L", (R * 2, R * 2), 0)
        ImageDraw.Draw(circ).ellipse([(0, 0), (R * 2 - 1, R * 2 - 1)], fill=255)
        pp.putalpha(circ)
        badge_layer.paste(pp, (cx - R, cy - R), mask=pp.split()[3])
    except Exception:
        pass

    card = Image.alpha_composite(card, badge_layer)
    draw = ImageDraw.Draw(card)

    # ── Pastille "RIDER'S SELECTION" à gauche du cercle ──
    font_pill = _font("BebasNeue-Regular.ttf", 30)
    text      = "RIDER'S SELECTION"
    tw_val    = draw.textbbox((0, 0), text, font=font_pill)[2]
    px  = cx - R - BORDER - tw_val - 32
    py  = cy - PILL_H // 2
    draw.rounded_rectangle([(px - 10, py), (px + tw_val + 10, py + PILL_H)],
                            radius=8, fill=LIME_A)
    draw.text((px, py), text, font=font_pill, fill=(15, 15, 15, 255))

    # ── Handle Instagram en vert sous le cercle ──
    if instagram:
        handle = ("@" + instagram.lstrip("@")).lower()
        font_ig = _font("BebasNeue-Regular.ttf", max(24, R // 2))
        tw_ig   = draw.textbbox((0, 0), handle, font=font_ig)[2]
        ix = cx - tw_ig // 2
        iy = cy + R + BORDER + 6
        draw.text((ix, iy), handle, font=font_ig, fill=LIME_A)

    return card


# ── Génération reel MP4 ────────────────────────────────────────────────────────
def generate_equipment_reel(
    variant_photos:    list,        # [Path, ...]  — tous les coloris
    selected_photo:    "Path|None", # coloris du rider (reçoit le badge)
    rider_instagram:   str  = "",   # handle pour trouver la PP
    card_params:       dict = None, # kwargs transmis à generate_equipment_card
    total_duration:    float = 6.0, # durée totale du MP4 en secondes
    crossfade:         float = 0.5, # durée du fondu entre cartes
    fps:               int   = 30,
    show_rider_badge:  bool  = True,
    bg_color:          tuple = (20, 20, 20),
) -> bytes:
    """
    Génère un MP4 animé (crossfade) depuis plusieurs variantes de couleur.
    Retourne les bytes du MP4.
    """
    if not variant_photos:
        raise ValueError("Aucune photo fournie")

    params = card_params or {}
    fonts  = params.pop("fonts", None) or load_eq_fonts()
    panel_y = params.get("panel_y", PANEL_Y)
    n      = len(variant_photos)
    dur    = total_duration / n          # durée par coloris

    # ── Trouver PP rider ──
    rider_photo = None
    if show_rider_badge and rider_instagram:
        rider_photo = find_rider_photo(rider_instagram)

    tmpdir = Path(tempfile.mkdtemp())
    png_paths = []

    for i, photo_path in enumerate(variant_photos):
        is_selected = (Path(photo_path) == Path(selected_photo)) if selected_photo else (i == 0)
        card = generate_equipment_card(
            **params, fonts=fonts,
            photo_path=Path(photo_path) if photo_path else None,
        )
        # Composite RGBA sur fond sombre
        bg = Image.new("RGBA", (W, H), (*bg_color, 255))
        bg = Image.alpha_composite(bg, card)

        # Badge rider sur le coloris sélectionné
        if is_selected and rider_photo and rider_photo.exists():
            bg = draw_rider_badge(bg, rider_photo, panel_y)

        frame = bg.convert("RGB")
        p = tmpdir / f"card_{i:04d}.png"
        frame.save(p, "PNG")
        png_paths.append(p)

    output = tmpdir / "reel.mp4"

    if n == 1:
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-t", str(total_duration), "-i", str(png_paths[0]),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
            str(output),
        ]
    else:
        inputs = []
        for p in png_paths:
            inputs += ["-loop", "1", "-t", str(dur + crossfade), "-i", str(p)]

        # xfade filter chain
        parts = []
        prev  = "[0]"
        for i in range(1, n):
            out_lbl = f"[v{i}]" if i < n - 1 else "[out]"
            offset  = round(i * dur - crossfade * (n - i) / n, 3)
            offset  = round(i * (dur - crossfade / n), 3)
            parts.append(
                f"{prev}[{i}]xfade=transition=fade:duration={crossfade}:offset={offset}{out_lbl}"
            )
            prev = out_lbl

        cmd = [
            "ffmpeg", "-y",
        ] + inputs + [
            "-filter_complex", ";".join(parts),
            "-map", "[out]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
            str(output),
        ]

    # Cherche ffmpeg dans les emplacements courants macOS / Linux
    import shutil
    ffmpeg_bin = shutil.which("ffmpeg") or next(
        (p for p in [
            "/opt/homebrew/bin/ffmpeg",   # Homebrew Apple Silicon
            "/usr/local/bin/ffmpeg",       # Homebrew Intel
            "/usr/bin/ffmpeg",
        ] if Path(p).exists()), None
    )
    if not ffmpeg_bin:
        raise RuntimeError(
            "ffmpeg introuvable. Installe-le avec : brew install ffmpeg"
        )
    cmd[0] = ffmpeg_bin

    result = subprocess.run(cmd, capture_output=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode()[-800:])

    data = output.read_bytes()
    # Nettoyage
    for p in png_paths:
        p.unlink(missing_ok=True)
    return data


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
