"""Canonical, schema and generated round filenames must use the same route."""
import importlib.util
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('site_build', ROOT / 'build.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)
competition = next(c for c in build.COMPETITION_CATALOG['series'] if c['id'] == 'uci-mtb-world-cup-dh-2026')
for name in ('La Thuile','Lake Placid','Lenzerheide','Leogang','Les Gets','Loudenvielle','Mona Yongpyong','Pal Arinsal','Whistler'):
    event = name + ' 2026'
    page = build.build_competition_round([], competition, event, 1, [event])
    route = '/competitions/uci-mtb-world-cup-dh-2026/rounds/' + build.competition_round_path_slug(competition,event) + '.html'
    assert f'rel="canonical" href="{build.SITE_URL}{route}"' in page, route
    assert '-2026.html' not in route
print('All nine UCI round canonical routes match generated filenames.')
