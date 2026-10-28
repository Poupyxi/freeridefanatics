#!/usr/bin/env python3
"""Assert that generated content matches the selected deployment environment."""
import os
from pathlib import Path

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
assert 'class="direct-ad-shell"' in home
ad_marker = 'rider-ad-preview' if environment == "preprod" else 'data-ad-slot="7556439197"'
assert ad_marker in home
rider_pages = list((root / "riders").glob("*.html"))
assert rider_pages
rider_source = rider_pages[0].read_text(encoding="utf-8")
assert ad_marker in rider_source
assert rider_source.index('class="rider-ad') < rider_source.index('>Results</h2>')
assert rider_source.count('class="rider-ad ') == 1

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
    assert source.count('class="rider-ad ') == 1, f"Duplicate ad placement: {page.relative_to(root)}"
assert complete_pages
assert red_bull.is_file()
assert red_bull_rounds.joinpath("cerroabajo-2026.html").is_file()
assert red_bull_rounds.joinpath("rampage-2026.html").is_file()
assert red_bull_rounds.joinpath("hardline-2026.html").is_file()

if environment == "preprod":
    assert "noindex,nofollow,noarchive" in home
    assert "Disallow: /" in robots
    assert "sibforms.com" not in home
    assert "pagead2.googlesyndication.com" not in home
else:
    assert "Allow: /" in robots
    assert "pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-6372404738608947" in home

print(f"Environment visibility checks passed for {environment}.")
