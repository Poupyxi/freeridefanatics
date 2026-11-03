"""Verify that every retained or generated preview page stays ad-network free."""
from pathlib import Path
import re
root = Path(__file__).resolve().parents[1]
checked = 0
for page in root.rglob('*.html'):
    if any(part in {'.git', 'node_modules'} for part in page.parts):
        continue
    source = page.read_text()
    assert not re.search(r'<script[^>]+src=["\'][^"\']*pagead2\.googlesyndication\.com', source), page
    if '<footer>' in source:
        assert source.count('class="rider-ad rider-ad-preview"') == 1, page
        assert source.index('class="rider-ad rider-ad-preview"') < source.index('<footer>'), page
        assert '<ins class="adsbygoogle' not in source, page
        checked += 1
assert checked > 10
print(f'{checked} pages: one preview before footer; no external ad loader or live unit.')
