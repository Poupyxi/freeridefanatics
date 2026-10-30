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
        winter_riders = [
            {'slug': 'ski-fixture', 'disciplines': ['Ski Freeride'], 'equipment': []},
            {'slug': 'snowboard-fixture', 'disciplines': ['Snowboard Freeride'], 'equipment': []},
        ]
        return build.build_index(
            riders, 0, 1,
            winter_counts={'ski': 4, 'snowboard': 3, 'winter': 6},
            source_rider_count=8,
            winter_riders=winter_riders,
        ), build.header_html('../') + build.footer_html('../')


preprod, other_page = render(True)
production, production_page = render(False)
for marker in ('seasonal-home.css', 'seasonal-home.js', 'class="season-switch"', 'class="season-panorama"', 'class="season-destinations"', 'freeride-fanatics-winter.png'):
    assert marker in preprod, marker
    assert marker not in production, marker
for marker in ('class="season-switch"', 'freeride-fanatics-winter.png', 'season-routing.js'):
    assert marker in other_page, marker
    assert marker not in production_page, marker
for marker in ('seasonal-home.css', 'seasonal-home.js', 'class="season-panorama"', 'class="season-destinations"'):
    assert marker not in other_page, marker
assert 'body class="home-page seasonal-home"' in preprod
assert 'body class="home-page"' in production
assert 'noindex,nofollow,noarchive' in preprod
assert preprod.count('role="switch"') == 1
assert preprod.count('class="season-peak') == 3
assert preprod.count('class="season-tree"') == 5
for marker in ('id="rankings"', 'id="equipment"', 'id="faq"', 'class="cta-dark"', 'data-random-rider=', 'compare.html', 'promo-pool.js', 'assets/js/site.js'):
    assert marker in preprod and marker in production, marker
assert 'aria-label="Switch to Winter season"' in preprod
assert 'id="season-appearance-status" role="status"' in preprod
for marker in ('data-season-scope="summer"', 'data-season-scope="winter"',
               'winter/competitions.html', 'winter/riders.html#grid',
               'winter/equipment.html', '6 Winter riders'):
    assert marker in preprod, marker
    assert marker not in production, marker
explore = build.seasonal_explore_html()
assert 'Explore Bike Downhill' not in explore
assert 'data-season-scope="summer"' not in explore
assert 'data-season-scope="winter" hidden' in explore
assert 'Dedicated pages coming soon' not in preprod
assert 'Explore ski' not in preprod and 'Explore snowboard' not in preprod
assert 'winter/riders/ski-fixture.html' in preprod
assert 'winter/riders/snowboard-fixture.html' in preprod
winter_intro = preprod.split('class="season-winter-intro"', 1)[1].split('</div></div>', 1)[0]
assert 'data-random-rider="ski-fixture"' in winter_intro
assert 'data-random-rider="snowboard-fixture"' in winter_intro
assert 'Random skier' in winter_intro and 'Random snowboarder' in winter_intro
assert 'Compare equipment' not in winter_intro and 'Read the FAQ' not in winter_intro
assert 'class="btn"' in winter_intro
assert '<meta name="rf-source-rider-count" content="8">' in preprod
assert 'rf-source-rider-count' not in production
header = preprod.split('</header>', 1)[0]
for href in ('competitions.html', 'riders.html#grid', 'equipment.html', './#faq'):
    assert f'href="{href}"' in header, href
header_nav = header.split('<nav class="links"', 1)[1].split('</nav>', 1)[0]
header_controls = header.split('<div class="nav-icons">', 1)[1].split('</div>', 1)[0]
assert 'class="season-switch"' in header_controls
assert header.index('<div class="nav-icons">') < header.index('class="season-switch"')
assert header_nav.count('class="dropdown" data-season-scope="summer"') == 2
assert 'data-season-route="competitions"' in header_nav
assert 'data-season-route="riders"' in header_nav
assert 'data-season-route="equipment"' in header_nav
assert 'href="#winter-ski"' not in header
assert 'href="#winter-snowboard"' not in header
for asset in ('css/seasonal-home.css', 'js/seasonal-home.js', 'img/brand/freeride-fanatics-winter.png'):
    assert (ROOT / 'assets' / asset).is_file(), asset
css = (ROOT / 'assets/css/seasonal-home.css').read_text()
assert '@media(prefers-reduced-motion:reduce)' in css
assert '.season-switch[hidden]{display:none}' in css
script = (ROOT / 'assets/js/seasonal-home.js').read_text()
assert 'rf-preprod-home-appearance-v1' in script
assert not any(term in script for term in ('fetch(', 'XMLHttpRequest', 'location.href', 'RF_DATA_SOURCE', 'innerHTML'))
print('Seasonal homepage: preprod-only scope, destinations and existing features preserved.')
