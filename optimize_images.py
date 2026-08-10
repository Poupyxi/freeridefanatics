#!/usr/bin/env python3
"""Generate modern image variants and enrich generated HTML image markup.

The source JPG/PNG files remain the universal fallback. Browsers that support
WebP receive a smaller image through a ``picture`` source, with a 480 px
variant for cards and narrow screens when the source is large enough.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parent
IMAGE_ROOT = ROOT / "assets" / "img"
RASTER_SUFFIXES = {".jpg", ".jpeg", ".png"}
LOCAL_IMAGE_SUFFIXES = RASTER_SUFFIXES | {".svg"}
SMALL_WIDTH = 480

IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
SRC_RE = re.compile(r"\bsrc=(['\"])(.*?)\1", re.IGNORECASE)
PICTURE_RE = re.compile(
    r'<picture class="optimized-picture">\s*<source\b[^>]*>\s*(<img\b[^>]*>)\s*</picture>',
    re.IGNORECASE,
)


def _variant_path(source: Path, small: bool = False) -> Path:
    suffix = f"-{SMALL_WIDTH}.webp" if small else ".webp"
    return source.with_name(source.stem + suffix)


def _save_webp(image: Image.Image, destination: Path, *, lossless: bool) -> None:
    image.save(
        destination,
        "WEBP",
        quality=84,
        method=6,
        lossless=lossless,
        exact=lossless,
    )


def generate_webp_variants() -> dict[str, int]:
    """Create WebP files only when they are smaller than their fallback."""
    created = updated = skipped = 0
    originals = [
        path
        for path in IMAGE_ROOT.rglob("*")
        if path.suffix.lower() in RASTER_SUFFIXES
        and not path.stem.endswith(f"-{SMALL_WIDTH}")
    ]

    for source in originals:
        source_mtime = source.stat().st_mtime
        with Image.open(source) as opened:
            image = ImageOps.exif_transpose(opened)
            image.load()
            lossless = source.suffix.lower() == ".png"

            full = _variant_path(source)
            needs_full = not full.exists() or full.stat().st_mtime < source_mtime
            if needs_full:
                existed = full.exists()
                _save_webp(image, full, lossless=lossless)
                if full.stat().st_size >= source.stat().st_size:
                    full.unlink()
                    skipped += 1
                elif existed:
                    updated += 1
                else:
                    created += 1

            small = _variant_path(source, small=True)
            if image.width > SMALL_WIDTH:
                needs_small = not small.exists() or small.stat().st_mtime < source_mtime
                if needs_small:
                    ratio = SMALL_WIDTH / image.width
                    resized = image.resize(
                        (SMALL_WIDTH, max(1, round(image.height * ratio))),
                        Image.Resampling.LANCZOS,
                    )
                    existed = small.exists()
                    _save_webp(resized, small, lossless=lossless)
                    if small.stat().st_size >= source.stat().st_size:
                        small.unlink()
                        skipped += 1
                    elif existed:
                        updated += 1
                    else:
                        created += 1
            elif small.exists():
                small.unlink()

    return {"created": created, "updated": updated, "skipped": skipped}


def _local_source(html_path: Path, src: str) -> Path | None:
    clean = src.split("?", 1)[0]
    if not clean or clean.startswith(("http://", "https://", "//", "data:")):
        return None
    candidate = (ROOT / clean.lstrip("/")) if clean.startswith("/") else (html_path.parent / clean)
    candidate = candidate.resolve()
    try:
        candidate.relative_to(ROOT)
    except ValueError:
        return None
    return candidate if candidate.suffix.lower() in LOCAL_IMAGE_SUFFIXES and candidate.exists() else None


def _image_dimensions(source: Path) -> tuple[int, int] | None:
    if source.suffix.lower() in RASTER_SUFFIXES:
        with Image.open(source) as image:
            return image.size

    svg = source.read_text(encoding="utf-8")[:4096]
    viewbox = re.search(
        r"\bviewBox\s*=\s*(['\"])\s*[-\d.]+\s+[-\d.]+\s+([\d.]+)\s+([\d.]+)\s*\1",
        svg,
        re.IGNORECASE,
    )
    if viewbox:
        return max(1, round(float(viewbox.group(2)))), max(1, round(float(viewbox.group(3))))
    width = re.search(r"\bwidth\s*=\s*(['\"])([\d.]+)(?:px)?\1", svg, re.IGNORECASE)
    height = re.search(r"\bheight\s*=\s*(['\"])([\d.]+)(?:px)?\1", svg, re.IGNORECASE)
    if width and height:
        return max(1, round(float(width.group(2)))), max(1, round(float(height.group(2))))
    return None


def _add_intrinsic_attributes(tag: str, width: int, height: int) -> str:
    attributes = []
    if not re.search(r"\bwidth\s*=", tag, re.IGNORECASE):
        attributes.append(f'width="{width}"')
    if not re.search(r"\bheight\s*=", tag, re.IGNORECASE):
        attributes.append(f'height="{height}"')
    if not re.search(r"\bdecoding\s*=", tag, re.IGNORECASE):
        attributes.append('decoding="async"')
    if not attributes:
        return tag
    close = " />" if tag.rstrip().endswith("/>") else ">"
    body = tag.rstrip()[:-2].rstrip() if close == " />" else tag.rstrip()[:-1].rstrip()
    return f'{body} {" ".join(attributes)}{close}'


def optimize_html_file(html_path: Path) -> int:
    """Add dimensions and WebP sources to every local raster image."""
    source_html = html_path.read_text(encoding="utf-8")
    # Make the operation safe to run repeatedly without nesting pictures.
    source_html = PICTURE_RE.sub(r"\1", source_html)
    changed = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal changed
        tag = match.group(0)
        src_match = SRC_RE.search(tag)
        if not src_match:
            return tag
        src = src_match.group(2)
        local = _local_source(html_path, src)
        if not local:
            return tag

        dimensions = _image_dimensions(local)
        if not dimensions:
            return tag
        width, height = dimensions
        enriched = _add_intrinsic_attributes(tag, width, height)
        if local.suffix.lower() == ".svg":
            changed += enriched != tag
            return enriched
        webp = _variant_path(local)
        if not webp.exists():
            changed += enriched != tag
            return enriched

        query = ("?" + src.split("?", 1)[1]) if "?" in src else ""
        webp_src = src.split("?", 1)[0].rsplit(".", 1)[0] + ".webp" + query
        small = _variant_path(local, small=True)
        if small.exists():
            small_src = src.split("?", 1)[0].rsplit(".", 1)[0] + f"-{SMALL_WIDTH}.webp" + query
            srcset = f"{small_src} {SMALL_WIDTH}w, {webp_src} {width}w"
            sizes = (
                "(max-width: 800px) 100vw, 50vw"
                if not re.search(r"\bloading\s*=", tag, re.IGNORECASE)
                else "(max-width: 520px) 100vw, 480px"
            )
            source_tag = f'<source type="image/webp" srcset="{srcset}" sizes="{sizes}">'
        else:
            source_tag = f'<source type="image/webp" srcset="{webp_src}">'
        changed += 1
        return (
            '<picture class="optimized-picture">'
            f"{source_tag}"
            f"{enriched}</picture>"
        )

    optimized = IMG_RE.sub(replace, source_html)
    if optimized != html_path.read_text(encoding="utf-8"):
        html_path.write_text(optimized, encoding="utf-8")
    return changed


def optimize_generated_html() -> dict[str, int]:
    pages = images = 0
    for html_path in ROOT.rglob("*.html"):
        if any(part in {".git", "tmp"} for part in html_path.parts):
            continue
        count = optimize_html_file(html_path)
        if count:
            pages += 1
            images += count
    return {"pages": pages, "images": images}


def main() -> None:
    variants = generate_webp_variants()
    markup = optimize_generated_html()
    print(
        "Optimized images: "
        f"{variants['created']} variants created, {variants['updated']} updated, "
        f"{variants['skipped']} larger variants skipped; "
        f"{markup['images']} image tags across {markup['pages']} pages enriched."
    )


if __name__ == "__main__":
    main()
