#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
PUBLIC_DIR="${2:-/var/www/ridersfanatics-public}"
BUILD_ENV="${3:-production}"

if [[ "$BUILD_ENV" != "production" && "$BUILD_ENV" != "preprod" ]]; then
  echo "Unknown build environment: $BUILD_ENV" >&2
  exit 2
fi

case "$PUBLIC_DIR" in
  /|/var|/var/www) echo "Refusing unsafe public directory: $PUBLIC_DIR" >&2; exit 2 ;;
esac

mkdir -p "$PUBLIC_DIR"

# Publish only files that belong on the public website. Source code, Git
# metadata, tests and private working documents never enter the web root.
rsync -a --delete "$SOURCE_DIR/assets/" "$PUBLIC_DIR/assets/"
for directory in riders equipment competitions guides; do
  rsync -a --delete "$SOURCE_DIR/$directory/" "$PUBLIC_DIR/$directory/"
done
rsync -a "$SOURCE_DIR/" "$PUBLIC_DIR/" \
  --include='/*.html' \
  --include='/robots.txt' \
  --include='/sitemap.xml' \
  --include='/ads.txt' \
  --include='/.htaccess' \
  $([[ "$BUILD_ENV" == "production" ]] && printf '%s' "--include=/contact-submit.php") \
  --exclude='*'

if [[ "$BUILD_ENV" == "preprod" ]]; then
  cp "$SOURCE_DIR/deploy/preprod.htaccess" "$PUBLIC_DIR/.htaccess"

  # Pages intentionally hidden while the next site version is reviewed.
  # Keep this at publish time so production sources and deployment stay intact.
  for hidden_page in \
    methodology.html \
    data-license.html \
    advertise.html \
    affiliate-disclosure.html
  do
    find "$PUBLIC_DIR" -maxdepth 1 -type f -name "$hidden_page" -delete
    sed -i.bak "\\|<loc>https://ridersfanatics.com/$hidden_page</loc>|d" "$PUBLIC_DIR/sitemap.xml"
  done
  find "$PUBLIC_DIR" -type f -name '*.html' -exec perl -0pi -e \
    's{<a\b[^>]*href="[^"]*(?:methodology|data-license|advertise|affiliate-disclosure)\.html"[^>]*>(.*?)</a>}{$1}gis;
     s{,\s*"license"\s*:\s*"https://ridersfanatics\.com/data-license\.html"}{}gis;
     s{,\s*"license"\s*:\s*\{[^{}]*"https://ridersfanatics\.com/data-license\.html"[^{}]*\}}{}gis' {} +
  find "$PUBLIC_DIR" -type f -name '*.bak' -delete
fi
