#!/usr/bin/env python3
"""Assert that generated content matches the selected deployment environment."""
import os
from pathlib import Path

root = Path(__file__).resolve().parent.parent
environment = os.environ.get("RF_BUILD_ENV", "production")
home = (root / "index.html").read_text(encoding="utf-8")
robots = (root / "robots.txt").read_text(encoding="utf-8")
red_bull = root / "competitions" / "red-bull"
assert (root / "advertise.html").is_file()
assert (root / "data" / "public" / "promo-pool.json").is_file()
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
else:
    assert not red_bull.exists()
    assert "Red Bull Rampage" not in "".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in root.rglob("*.html")
    )
    assert "Allow: /" in robots

print(f"Environment visibility checks passed for {environment}.")
