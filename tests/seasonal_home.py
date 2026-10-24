#!/usr/bin/env python3
"""Keep the seasonal visual experiment limited to the preproduction homepage."""
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build


def render(preprod):
    with patch.object(build, 'IS_PREPROD', preprod), \
         patch.object(build, 'build_rankings_section', return_value='<section id="rankings">Rankings</section>'), \
         patch.object(build, 'build_best_equipment_carousel', return_value='<section id="equipment">Equipment</section>'):
        riders = [{'slug': 'fixture-rider', 'equipment': []}]
        return build.build_index(
            riders, 0, 1,
            winter_counts={'ski': 4, 'snowboard': 3, 'winter': 6},
        ), build.header_html('../', seasonal=False)


preprod, other_header = render(True)
production, _ = render(False)
for marker in ('seasonal-home.css', 'seasonal-home.js', 'class="season-switch"', 'class="season-panorama"', 'class="season-destinations"', 'freeride-fanatics-winter.png'):
    assert marker in preprod, marker
    assert marker not in production, marker
    assert marker not in other_header, marker
assert 'body class="home-page seasonal-home"' in preprod
assert 'body class="home-page"' in production
assert 'noindex,nofollow,noarchive' in preprod
assert preprod.count('role="switch"') == 1
assert preprod.count('class="season-peak') == 3
assert preprod.count('class="season-tree"') == 5
for marker in ('id="rankings"', 'id="equipment"', 'id="faq"', 'class="cta-dark"', 'data-random-rider=', 'compare.html', 'promo-pool.js', 'assets/js/site.js'):
    assert marker in preprod and marker in production, marker
assert 'aria-describedby="season-appearance-status"' in preprod
assert 'id="season-appearance-status" role="status"' in preprod
for marker in ('data-season-scope="summer"', 'data-season-scope="winter"',
               'id="winter-ski"', 'id="winter-snowboard"',
               '4 riders', '3 riders', '6 Winter riders'):
    assert marker in preprod, marker
    assert marker not in production, marker
assert 'Explore Bike Downhill' in preprod
assert 'Bike Downhill content stays in Summer.' in preprod
for asset in ('css/seasonal-home.css', 'js/seasonal-home.js', 'img/brand/freeride-fanatics-winter.png'):
    assert (ROOT / 'assets' / asset).is_file(), asset
css = (ROOT / 'assets/css/seasonal-home.css').read_text()
assert '@media(prefers-reduced-motion:reduce)' in css
assert '.season-switch[hidden]{display:none}' in css
script = (ROOT / 'assets/js/seasonal-home.js').read_text()
assert 'rf-preprod-home-appearance-v1' in script
assert not any(term in script for term in ('fetch(', 'XMLHttpRequest', 'location.href', 'RF_DATA_SOURCE', 'innerHTML'))
print('Seasonal homepage: preprod-only scope, destinations and existing features preserved.')
