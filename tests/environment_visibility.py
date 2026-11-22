#!/usr/bin/env python3
"""Assert that generated content matches the selected deployment environment."""
import os
import re
from pathlib import Path


def ad_placement_count(source):
    """Count the placement section in both preview and production markup."""
    return len(re.findall(r'class="rider-ad(?:\s|")', source))

root = Path(__file__).resolve().parent.parent
environment = os.environ.get("RF_BUILD_ENV", "production")
home = (root / "index.html").read_text(encoding="utf-8")
robots = (root / "robots.txt").read_text(encoding="utf-8")
ads = (root / "ads.txt").read_text(encoding="utf-8")
red_bull = root / "competitions" / "redbull-2026.html"
red_bull_rounds = root / "competitions" / "redbull-2026" / "rounds"
assert (root / "advertise.html").is_file()
assert (root / "assets" / "js" / "promo-pool.js").is_file()
assert "assets/js/promo-pool.js" in home
assert "google.com, pub-6372404738608947, DIRECT, f08c47fec0942fa0" in ads
assert 'class="direct-ad promo-strip"' in home
assert 1 <= home.count('<article class="promo-card') <= 3
assert "Common equipment" in home
assert 'class="direct-ad-shell"' not in home
assert "Reach downhill fans at the point of discovery." not in home
ad_marker = 'rider-ad-preview' if (environment == "preprod" or os.environ.get("RF_ADS_MODE", "preview") != "live") else 'data-ad-slot="7556439197"'
cmp_marker = "fundingchoicesmessages.google.com/i/pub-6372404738608947"
assert ad_marker in home
rider_pages = list((root / "riders").glob("*.html"))
assert rider_pages
rider_source = rider_pages[0].read_text(encoding="utf-8")
assert ad_marker in rider_source
assert rider_source.index('>Results</h2>') < rider_source.index('class="rider-ad')
assert rider_source.index('class="rider-ad') < rider_source.index('<footer>')
assert ad_placement_count(rider_source) == 1

# Every complete generated page gets exactly one placement. Redirect-only files
# without the shared footer are intentionally excluded.
complete_pages = []
for page in root.rglob("*.html"):
    if any(part in {".git", "node_modules"} for part in page.parts):
        continue
    source = page.read_text(encoding="utf-8")
    if "<footer>" not in source:
        continue
    complete_pages.append(page)
    assert ad_marker in source, f"Missing ad placement: {page.relative_to(root)}"
    assert ad_placement_count(source) == 1, f"Duplicate ad placement: {page.relative_to(root)}"
    assert source.index('class="rider-ad') < source.index('<footer>'), f"Ad must precede footer: {page.relative_to(root)}"
assert complete_pages
if red_bull.is_file():
    # Legacy umbrella layout: Red Bull is one competition with three rounds.
    assert red_bull_rounds.joinpath("cerroabajo-2026.html").is_file()
    assert red_bull_rounds.joinpath("rampage-2026.html").is_file()
    assert red_bull_rounds.joinpath("hardline-2026.html").is_file()
else:
    # Current Notion layout: each Red Bull discipline is an independent
    # competition. Keep the environment contract compatible with both layouts
    # while still requiring all three public competition pages.
    competition_pages = list((root / "competitions").glob("*.html"))
    for tokens in (("cerro", "abajo"), ("rampage",), ("hardline",)):
        assert any(all(token in page.stem.lower() for token in tokens)
                   for page in competition_pages), tokens

if environment == "preprod":
    assert "noindex,nofollow,noarchive" in home
    assert "Disallow: /" in robots
    assert "sibforms.com" not in home
    assert "pagead2.googlesyndication.com" not in home
    assert cmp_marker not in home
    assert (root / "winter" / "riders.html").is_file()
    assert (root / "winter" / "competitions.html").is_file()
    assert (root / "winter" / "equipment.html").is_file()
else:
    assert "Allow: /" in robots
    assert "pagead2.googlesyndication.com/pagead/js/adsbygoogle.js" not in home
    assert cmp_marker in home
    # The promoted site exposes the validated Winter season alongside Summer.
    for marker in (
        'class="season-switch"',
        'seasonal-home.css',
        'seasonal-home.js',
        'season-routing.js',
        'data-season-scope="winter"',
        'href="winter/',
    ):
        assert marker in home, f"Winter production marker is missing: {marker}"
    for route in (
        root / "winter" / "riders.html",
        root / "winter" / "competitions.html",
        root / "winter" / "equipment.html",
        root / "winter" / "competitions" / "freerideworldtour-2027.html",
        root / "winter" / "competitions" / "kings-queens-of-corbet-s-2027.html",
        root / "winter" / "competitions" / "natural-selection-2027.html",
        root / "winter" / "competitions" / "scandinavian-big-mountain-championships-2027.html",
    ):
        assert route.is_file(), f"Winter production route is missing: {route.relative_to(root)}"

print(f"Environment visibility checks passed for {environment}.")
