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
  --include='/.htaccess' \
  $([[ "$BUILD_ENV" == "production" ]] && printf '%s' "--include=/contact-submit.php") \
  --exclude='*'

if [[ "$BUILD_ENV" == "preprod" ]]; then
  cp "$SOURCE_DIR/deploy/preprod.htaccess" "$PUBLIC_DIR/.htaccess"
fi
