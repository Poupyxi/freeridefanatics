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
