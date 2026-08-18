#!/usr/bin/env python3
"""Assert that generated content matches the selected deployment environment."""
import os
from pathlib import Path

root = Path(__file__).resolve().parent.parent
environment = os.environ.get("RF_BUILD_ENV", "production")
home = (root / "index.html").read_text(encoding="utf-8")
robots = (root / "robots.txt").read_text(encoding="utf-8")
ads = (root / "ads.txt").read_text(encoding="utf-8")
red_bull = root / "competitions" / "red-bull"
assert (root / "advertise.html").is_file()
assert (root / "assets" / "js" / "promo-pool.js").is_file()
assert "assets/js/promo-pool.js" in home
assert "google.com, pub-6372404738608947, DIRECT, f08c47fec0942fa0" in ads
assert 'class="direct-ad promo-strip"' in home
assert home.count('<article class="promo-card') == 3
assert "Top 1 Women · Last race" in home
assert "Common equipment" in home
assert "Top 1 Men · Last race" in home
assert 'class="direct-ad-shell"' in home

if environment == "preprod":
    assert red_bull.joinpath("index.html").is_file()
    assert red_bull.joinpath("rampage", "index.html").is_file()
    assert red_bull.joinpath("hardline", "index.html").is_file()
    assert "noindex,nofollow,noarchive" in home
    assert "Disallow: /" in robots
    assert "sibforms.com" not in home
    assert "pagead2.googlesyndication.com" not in home
else:
    assert not red_bull.exists()
    assert "Red Bull Rampage" not in "".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in root.rglob("*.html")
    )
    assert "Allow: /" in robots
    assert "pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-6372404738608947" in home

print(f"Environment visibility checks passed for {environment}.")
