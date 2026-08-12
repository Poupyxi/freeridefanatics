#!/usr/bin/env python3
"""
RidersFanatics — image import.

Bridges the photo library on the Desktop into the site's assets, resizing and
renaming along the way. The library keeps its own conventions (files named by
Instagram handle, equipment sorted into category folders); this script maps
them onto the names build.py looks for. Nothing in the library is modified.

  ~/Desktop/freeride/PPRiders/@handle.jpg      -> assets/img/riders/{slug}.jpg
                                                  (square avatar, grid cards)
  ~/Desktop/freeride/PictureRiders/@handle.jpg -> assets/img/riders-action/{slug}.jpg
                                                  (portrait, rider page hero)
  ~/Desktop/freeride/Equipment/{Cat}/Brand;Model.webp
                                               -> assets/img/equipment/{cat}-{brand}-{model}.jpg

Riders are matched on the Instagram handle already present in riders.json, so
messy filenames (trailing spaces, capitals, a missing "@") still resolve.

Equipment is matched per category against the products actually used in
riders.json — the imported filename is derived from the *product*, not from
the source filename, so build.py's lookup stays exact. Files that can't be
matched are reported at the end rather than silently dropped.

Usage:
  python3 import_images.py                # import everything, then rebuild
  python3 import_images.py --no-build
  python3 import_images.py --force        # re-process files already imported
  python3 import_images.py --report       # match report only, writes nothing
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
from collections import defaultdict

from PIL import Image, ImageOps

import build

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

LIBRARY = os.path.expanduser("~/Desktop/freeride")
SRC_PP = os.path.join(LIBRARY, "PPRiders")
SRC_ACTION = os.path.join(LIBRARY, "PictureRiders")
SRC_EQUIP = os.path.join(LIBRARY, "Equipment")

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(ROOT, "data", "riders.json")
OUT_PP = os.path.join(ROOT, "assets", "img", "riders")
OUT_ACTION = os.path.join(ROOT, "assets", "img", "riders-action")
OUT_EQUIP = os.path.join(ROOT, "assets", "img", "equipment")
OUT_REVEAL = os.path.join(OUT_EQUIP, "reveal")

# Output sizes (px). Avatars are square-cropped; the others keep their ratio.
AVATAR_SIZE = 400
ACTION_MAX = 900
EQUIP_MAX = 600
JPEG_QUALITY = 82

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")

# Library folder name -> category key used in riders.json.
# Folders with no equivalent (Hub, Spacer, Stems) are intentionally absent:
# the site doesn't track those parts.
FOLDER_TO_CATEGORY = {
    "Frame": "Frame", "Fork": "Fork", "Rear Shock": "RearShock",
    "Handle bar": "Handlebar", "Dropper Post": "DropperPost", "Seatpost": "DropperPost",
    "Saddle": "Saddle", "Crank": "Crankset", "Derailleur": "Derailleur",
    "Brake": "BrakeLever", "Brake Lever": "BrakeLever", "Grip": "GRIP", "Chain": "CHAIN", "Disk": "Disk",
    "Wheels": "Wheels", "Tires": "Tires", "Pedals": "Pedals",
    "Shoes": "Shoes", "Helmet": "Helmet", "Protection": "Protection", "Goggles": "Goggles",
}

# Photo-library names occasionally describe a production family or use a
# shorter trade name while the sheet keeps the exact race specification.
# Keep these overrides explicit so a loose fuzzy match never shows the wrong
# component (for example alloy wheels for a carbon-wheel specification).
PHOTO_ALIASES = {
    ("Fork", "sr suntour", "rux"): ("sr suntour", "rux38 evo boost eq rc"),
    ("Fork", "sr suntour", "rux 29"): ("sr suntour", "rux38 evo boost eq rc"),
    ("Fork", "sr suntour", "rux 38"): ("sr suntour", "rux38 evo boost eq rc"),
    ("Frame", "atherton", "a 200 g"): ("atherton", "downhill200"),
    ("Frame", "giant", "glory advanced"): ("giant", "glory 2026"),
    ("Frame", "norco", "aurum hsp"): ("norco", "torrent dh"),
    ("Frame", "norco", "prototype dh"): ("norco", "torrent dh"),
    ("Frame", "norco", "dh prototype"): ("norco", "torrent dh"),
    ("Frame", "specialized", "demo"): ("s works", "demo"),
    ("RearShock", "ohlins", "prototype coil"): ("ohlins", "ttx22 m2 coil"),
    ("RearShock", "float x2 factory", ""): ("fox", "float x2 factory 2026"),
    ("Tires", "continental", "kryptotal"): ("continental", "kryptotal r"),
    ("Tires", "continental", "kryptotal dh"): ("continental", "kryptotal r"),
    ("Tires", "continental", "kryptotal f + argotal r"): ("continental", "kryptotal f"),
    ("Tires", "continental", "argotal"): ("continental", "argotal"),
    ("Tires", "continental", "argotal dh"): ("continental", "argotal"),
    ("Tires", "continental", "argotal dh supersoft"): ("continental", "argotal"),
    ("Tires", "continental", "argotal f + kryptotal r"): ("continental", "argotal"),
    ("Handlebar", "cast components", "20mm rise"): ("cast", "sfx"),
    ("Handlebar", "fsa", "gradient aluminum"): ("fsa", "gradient aluminium"),
    ("Handlebar", "burgtec", "alloy 31 8mm"): ("burgtec", "ride wide alloy downhill riser bar"),
    ("Handlebar", "renthal", "fatbar m172"): ("renthal", "fatbar carbon 20mm rise"),
    ("Handlebar", "renthal", "fatbar carbon 31 8mm"): ("renthal", "fatbar carbon 20mm rise"),
    ("Handlebar", "renthal", "fatbar 35"): ("renthal", "fatbar35 30mm rise"),
    ("Crankset", "north shore billet", "155mm"): ("north shore billet", "talon crankset"),
    ("Crankset", "sram", "x0 dh"): ("sram", "x01 dh x sync crankset"),
    ("Crankset", "sram", "x0 dh carbon"): ("sram", "x01 dh x sync crankset"),
    ("Crankset", "shimano", "saint"): ("shimano", "shimano saint fc m825 single 10 speed crankset"),
    ("BrakeLever", "brembo lever", ""): ("brembo gr pro gravity lever", ""),
    ("BrakeLever", "brembo", "prototype"): ("brembo gr pro gravity", ""),
    ("BrakeLever", "hope", "evo lever"): ("hope tech 4 evo red", ""),
    ("BrakeLever", "shimano", "saint shimano"): ("shimano", "saint 820"),
    ("BrakeLever", "shimano", "saint xtr"): ("shimano", "saint 820"),
    ("BrakeLever", "shimano", "xtr saint"): ("shimano", "saint 820"),
    ("BrakeLever", "shimano", "xtr m9120"): ("shimano", "xtr 9120"),
    ("Derailleur", "sram", "xx dh axs t type"): ("sram", "xx dh t type axs"),
    ("Derailleur", "sram", "axs eagle t type"): ("sram", "xx dh t type axs"),
    ("Derailleur", "sram", "x0 dh"): ("sram", "x01 dh"),
    ("Wheels", "crankbrothers", ""): ("crankbrother", "synthesis dh alloy 2 0 i9"),
    ("Wheels", "crankbrothers", "synthesis dh"): ("crankbrother", "synthesis dh alloy 2 0 i9"),
    ("Wheels", "dt swiss", ""): ("dtswiss", "fanatik"),
    ("Wheels", "dt swiss", "ex471 + dt swiss 240"): ("dtswiss", "fanatik"),
    ("Wheels", "reserve", "30dh carbon"): ("reserve", "30dhcarbon"),
    ("Wheels", "reserve", "carbon dh"): ("reserve", "30dhcarbon"),
}

# ---------------------------------------------------------------- helpers

def norm_handle(s, is_filename=False):
    """Collapse cosmetic handle separators so Sheet and filenames stay compatible.

    Instagram dots and underscores are often swapped in the photo library
    (`@andreas.kolb66` vs `@andreas_kolb66`), but cannot change the underlying
    letter/number identity. Only strip an extension for actual filenames."""
    if is_filename:
        stem, ext = os.path.splitext(s)
        if ext.lower() in IMAGE_EXTS:
            s = stem
    return re.sub(r"[^a-z0-9]", "", s.lower().lstrip("@").strip())

def norm_text(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii")
    s = s.lower().replace("™", "").replace("®", "")
    return re.sub(r"[^a-z0-9+]+", " ", s).strip()

def compact_text(s):
    """Comparison key for cosmetic separators only: `RUX 38` == `RUX38`."""
    return re.sub(r"[^a-z0-9]+", "", norm_text(s))

def listdir_images(path):
    if not os.path.isdir(path):
        return []
    images = []
    for f in sorted(os.listdir(path)):
        if f.startswith("."):
            continue
        full = os.path.join(path, f)
        if not os.path.isfile(full):
            continue
        if f.lower().endswith(IMAGE_EXTS):
            images.append(f)
            continue
        # Some library exports are valid JPEG/PNG files with no extension.
        # Pillow inspects the file signature, so accept those without guessing.
        if not os.path.splitext(f)[1]:
            try:
                with Image.open(full) as probe:
                    probe.verify()
                images.append(f)
            except (OSError, ValueError):
                pass
    return images

def open_library_image(path):
    """Open a library image, including AVIF exports carrying a .jpg suffix."""
    try:
        img = Image.open(path)
        img.load()
        return img
    except (OSError, ValueError) as pillow_error:
        # macOS can decode AVIF through ImageIO even when the installed Pillow
        # build cannot. Convert only a temporary copy; never touch the library.
        with tempfile.TemporaryDirectory(prefix="freeride-image-") as temp_dir:
            converted = os.path.join(temp_dir, "converted.png")
            result = subprocess.run(
                ["/usr/bin/sips", "-s", "format", "png", path, "--out", converted],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if result.returncode != 0:
                raise pillow_error
            try:
                with Image.open(converted) as decoded:
                    decoded.load()
                    return decoded.copy()
            except (OSError, ValueError):
                raise pillow_error

def load_image(path):
    img = open_library_image(path)
    img = ImageOps.exif_transpose(img)  # honour phone/camera orientation
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        flat = Image.new("RGB", img.size, (255, 255, 255))
        flat.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
        return flat
    return img.convert("RGB")

def validate_library_image(path):
    """Validate cheaply; only invoke the AVIF fallback when Pillow needs it."""
    try:
        with Image.open(path) as probe:
            probe.verify()
    except (OSError, ValueError):
        open_library_image(path)

def save_square(src, dest, size):
    img = load_image(src)
    ImageOps.fit(img, (size, size), Image.LANCZOS, centering=(0.5, 0.4)).save(
        dest, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)

def save_fitted(src, dest, max_side):
    img = load_image(src)
    img.thumbnail((max_side, max_side), Image.LANCZOS)
    img.save(dest, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)

# ---------------------------------------------------------------- riders

def import_riders(riders, src_dir, out_dir, kind, square, force, dry):
    """Match library files to riders by Instagram handle."""
    by_handle = {norm_handle(r["instagram"]): r for r in riders if r.get("instagram")}
    files = listdir_images(src_dir)
    if not files:
        print(f"{kind}: source folder empty or missing ({src_dir})")
        return [], []

    os.makedirs(out_dir, exist_ok=True)
    done, unmatched = [], []
    matched_handles = set()

    for f in files:
        rider = by_handle.get(norm_handle(f, is_filename=True))
        if not rider:
            unmatched.append(f)
            continue
        matched_handles.add(norm_handle(f, is_filename=True))
        dest = os.path.join(out_dir, f"{rider['slug']}.jpg")
        if os.path.exists(dest) and not force:
            continue
        if dry:
            done.append(rider["slug"])
            continue
        src = os.path.join(src_dir, f)
        try:
            if square:
                save_square(src, dest, AVATAR_SIZE)
            else:
                save_fitted(src, dest, ACTION_MAX)
            done.append(rider["slug"])
        except Exception as e:
            print(f"  ! {f}: {e}")
            unmatched.append(f)

    no_photo = sorted(r["slug"] for r in riders
                      if norm_handle(r.get("instagram") or "") not in matched_handles)
    verb = "would import" if dry else "imported"
    print(f"{kind}: {len(matched_handles)}/{len(riders)} riders matched, {len(done)} {verb}")
    if unmatched:
        print(f"  unmatched files ({len(unmatched)}): {', '.join(unmatched)}")
    if no_photo:
        print(f"  riders with no photo ({len(no_photo)}): {', '.join(no_photo)}")
    return done, no_photo

# ---------------------------------------------------------------- equipment

def index_library_equipment():
    """category -> [{'brand','model','full','path'}], parsed from 'Brand;Model;Variant.ext'."""
    index = defaultdict(list)
    skipped_folders = []
    if not os.path.isdir(SRC_EQUIP):
        return index, skipped_folders

    for folder in sorted(os.listdir(SRC_EQUIP)):
        path = os.path.join(SRC_EQUIP, folder)
        if not os.path.isdir(path):
            continue
        category = FOLDER_TO_CATEGORY.get(folder)
        files = listdir_images(path)
        if category is None:
            if files:
                skipped_folders.append((folder, len(files)))
            continue
        for f in files:
            source_path = os.path.join(path, f)
            try:
                validate_library_image(source_path)
            except (OSError, ValueError):
                continue
            stem = os.path.splitext(f)[0]
            parts = [p.strip() for p in stem.split(";")]
            # Some bulk catalogue exports put tyre product images in the
            # Wheels folder and mark them with a third `Pneu` field. Route
            # those by their declared product type instead of their folder.
            file_category = ("Tires" if category == "Wheels"
                             and len(parts) > 2 and norm_text(parts[2]) == "pneu"
                             else category)
            raw_brand = parts[0]
            raw_model = parts[1] if len(parts) > 1 else ""
            canonical_brand, canonical_model = build.canonical_equipment_product(
                file_category, raw_brand, raw_model)
            index[file_category].append({
                "brand": norm_text(canonical_brand),
                "model": norm_text(canonical_model),
                "full": norm_text(stem.replace(";", " ")),
                "path": source_path,
                "name": f,
            })
    return index, skipped_folders

def pick_photo(candidates, brand, model):
    """Best library file for one product, from strictest to loosest match."""
    if not candidates:
        return None
    target_full = f"{brand} {model}".strip()
    compact_brand = compact_text(brand)
    compact_model = compact_text(model)
    compact_full = compact_text(target_full)

    # 1. brand and model both match exactly
    for c in candidates:
        if c["brand"] == brand and c["model"] and c["model"] == model:
            return c
    # 2. whole filename equals "brand model" (files that don't use ';')
    for c in candidates:
        if c["full"] == target_full:
            return c
    # 3. Cosmetic separators are ignored globally. This covers spaces, dashes
    # and underscores without fuzzy-merging distinct identities such as X0/X01.
    same_brand = [c for c in candidates if compact_text(c["brand"]) == compact_brand]
    if compact_model:
        compact_exact = [c for c in same_brand
                         if c["model"] and compact_text(c["model"]) == compact_model]
        if compact_exact:
            return min(compact_exact, key=lambda c: len(c["full"]))

        # A library filename may append a tune, generation or colour after the
        # actual sheet model (`RUX38-EVO...`). Require a substantial shared
        # identity and a true compact prefix, never a similarity percentage.
        compact_prefixed = []
        if len(compact_model) >= 5:
            for c in same_brand:
                candidate_model = compact_text(c["model"])
                if candidate_model and (candidate_model.startswith(compact_model)
                                        or compact_model.startswith(candidate_model)):
                    compact_prefixed.append(c)
        if compact_prefixed:
            return min(compact_prefixed, key=lambda c: len(compact_text(c["model"])))

        compact_filename = [c for c in candidates
                            if len(compact_full) >= 8
                            and compact_text(c["full"]).startswith(compact_full)]
        if compact_filename:
            return min(compact_filename, key=lambda c: len(compact_text(c["full"])))

    # 4. same brand, model is a word-boundary prefix either way
    # ("Boxxer" vs "Boxxer Ultimate").
    if model:
        prefixed = [c for c in same_brand if c["model"] and
                    (c["model"].startswith(model + " ") or model.startswith(c["model"] + " "))]
        if prefixed:
            return max(prefixed, key=lambda c: len(os.path.commonprefix([c["model"], model])))
        loose = [c for c in same_brand if c["full"].startswith(target_full)]
        if loose:
            return min(loose, key=lambda c: len(c["full"]))
    # 5. brand-only photo, when the sheet gives no model at all
    if not model and same_brand:
        return min(same_brand, key=lambda c: len(c["full"]))
    return None

def import_equipment(riders, force, dry):
    index, skipped_folders = index_library_equipment()
    if not index:
        print(f"equipment: source folder empty or missing ({SRC_EQUIP})")
        return [], []

    # every distinct product actually used by a rider
    products = {}
    for r in riders:
        for item in r.get("equipment") or []:
            brand = item.get("brand") or ""
            detail = [p.strip() for p in (item.get("model_detail") or "").split(";") if p.strip()]
            model = detail[0] if detail else ""
            brand, model = build.canonical_equipment_product(item.get("category"), brand, model)
            if not brand and not model:
                continue
            cat = item.get("category")
            products[(cat, brand, model)] = build.equip_image_slug(cat, brand, model)

    os.makedirs(OUT_EQUIP, exist_ok=True)
    imported, missing = [], []
    used_files = set()

    for (cat, brand, model), slug in sorted(products.items()):
        photo_brand, photo_model = PHOTO_ALIASES.get(
            (cat, norm_text(brand), norm_text(model)),
            (norm_text(brand), norm_text(model)),
        )
        choice = pick_photo(index.get(cat, []), photo_brand, photo_model)
        if not choice:
            missing.append(f"{slug}  ({cat}: {brand} {model})".strip())
            continue
        used_files.add(choice["path"])
        dest = os.path.join(OUT_EQUIP, f"{slug}.jpg")
        if os.path.exists(dest) and not force:
            continue
        if dry:
            imported.append(slug)
            continue
        try:
            save_fitted(choice["path"], dest, EQUIP_MAX)
            imported.append(slug)
        except Exception as e:
            print(f"  ! {choice['name']}: {e}")
            missing.append(slug)

    # Tires are a deliberate exception: a rider product can be a front/rear
    # combo, while the library stores one file per tread. Import every tire so
    # the site generator can compose the two matching product photos.
    for choice in index.get("Tires", []):
        slug = build.equip_image_slug("Tires", choice["brand"], choice["model"])
        dest = os.path.join(OUT_EQUIP, f"{slug}.jpg")
        if os.path.exists(dest) and not force:
            continue
        if dry:
            imported.append(slug)
            continue
        try:
            save_fitted(choice["path"], dest, EQUIP_MAX)
            imported.append(slug)
            used_files.add(choice["path"])
        except Exception as e:
            print(f"  ! {choice['name']}: {e}")

    total_files = sum(len(v) for v in index.values())
    verb = "would import" if dry else "imported"
    print(f"equipment: {len(products) - len(missing)}/{len(products)} products matched, "
          f"{len(imported)} {verb}")
    print(f"  library: {total_files} files in tracked categories, {len(used_files)} used")
    if skipped_folders:
        detail = ", ".join(f"{n} ({c} files)" for n, c in skipped_folders)
        print(f"  folders not tracked by the site: {detail}")
    return imported, missing

# ---------------------------------------------------------------- frame reveal

def make_sketch(gray, blur_k=9, gamma=0.55, edge_mix=0.55):
    """Pencil-drawing render: classic dodge blend, then darkened and reinforced
    with structural edges so pale frames still read as a drawing."""
    inv = 255 - gray
    blur = cv2.GaussianBlur(inv, (blur_k, blur_k), 0)
    dodge = cv2.divide(gray, 255 - blur, scale=256).astype(np.float32) / 255.0
    dodge = np.power(dodge, 1.0 / gamma)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (3, 3), 0), 30, 90)
    edges = cv2.dilate(edges, np.ones((2, 2), np.uint8))
    edges = cv2.GaussianBlur(edges, (3, 3), 0).astype(np.float32) / 255.0
    return (np.clip(dodge * (1.0 - edges * edge_mix), 0, 1) * 255).astype(np.uint8)

def make_draw_svg(gray, w, h, duration=2.6, eps=1.1, min_len=22, max_paths=140):
    """Self-drawing outline: contours become paths whose stroke-dashoffset
    animates to 0. Delays are staggered by path length so the frame appears to
    be sketched progressively instead of every line landing at once."""
    edges = cv2.Canny(cv2.GaussianBlur(gray, (3, 3), 0), 35, 95)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = [c for c in contours if cv2.arcLength(c, False) >= min_len]
    contours.sort(key=lambda c: -cv2.arcLength(c, False))
    contours = contours[:max_paths]
    if not contours:
        return None

    total = sum(cv2.arcLength(c, False) for c in contours) or 1
    parts, acc = [], 0.0
    for c in contours:
        pts = cv2.approxPolyDP(c, eps, False).reshape(-1, 2)
        if len(pts) < 2:
            continue
        d = "M " + " L ".join(f"{x} {y}" for x, y in pts)
        delay = duration * 0.55 * (acc / total)
        acc += cv2.arcLength(c, False)
        parts.append(f'<path pathLength="1" d="{d}" style="animation-delay:{delay:.2f}s"/>')

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">'
        "<style>path{fill:none;stroke:#15161a;stroke-width:1.1;stroke-linecap:round;"
        "stroke-linejoin:round;stroke-dasharray:1;stroke-dashoffset:1;"
        f"animation:draw {duration * 0.6:.2f}s ease forwards}}"
        "@keyframes draw{to{stroke-dashoffset:0}}</style>" + "".join(parts) + "</svg>"
    )

def build_frame_reveals(force, dry):
    """Derive the two extra layers of the frame reveal from each frame photo."""
    frames = sorted(f for f in os.listdir(OUT_EQUIP)
                    if f.startswith("frame-") and f.lower().endswith(IMAGE_EXTS))
    if not frames:
        return
    if not HAS_CV2:
        print(f"frame reveal: skipped — needs opencv-python ({len(frames)} frames)")
        return

    os.makedirs(OUT_REVEAL, exist_ok=True)
    made = 0
    for f in frames:
        stem = os.path.splitext(f)[0]
        sketch_path = os.path.join(OUT_REVEAL, f"{stem}-sketch.png")
        svg_path = os.path.join(OUT_REVEAL, f"{stem}-draw.svg")
        if os.path.exists(sketch_path) and os.path.exists(svg_path) and not force:
            continue
        if dry:
            made += 1
            continue
        img = cv2.imread(os.path.join(OUT_EQUIP, f))
        if img is None:
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape[:2]
        cv2.imwrite(sketch_path, make_sketch(gray))
        svg = make_draw_svg(gray, w, h)
        if svg:
            with open(svg_path, "w", encoding="utf-8") as fh:
                fh.write(svg)
        made += 1

    verb = "would build" if dry else "built"
    print(f"frame reveal: {len(frames)} frames, {made} {verb} (sketch + self-drawing SVG)")

# ---------------------------------------------------------------- main

def main():
    args = sys.argv[1:]
    force = "--force" in args
    dry = "--report" in args
    do_build = "--no-build" not in args and not dry

    with open(DATA_PATH, encoding="utf-8") as f:
        riders = json.load(f)

    if dry:
        print("REPORT ONLY — no files written\n")

    import_riders(riders, SRC_PP, OUT_PP, "avatars", True, force, dry)
    print()
    import_riders(riders, SRC_ACTION, OUT_ACTION, "action shots", False, force, dry)
    print()
    _, missing = import_equipment(riders, force, dry)
    print()
    build_frame_reveals(force, dry)

    if missing:
        print(f"\n— Equipment products still without a photo ({len(missing)}).")
        print("  Add a file named 'Brand;Model.jpg' to the matching category folder:")
        for m in missing[:40]:
            print(f"    {m}")
        if len(missing) > 40:
            print(f"    … and {len(missing) - 40} more (run with --report for the full list)"
                  if not dry else f"    … and {len(missing) - 40} more")

    if do_build:
        print()
        build.main()

if __name__ == "__main__":
    main()
