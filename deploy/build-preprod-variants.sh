#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="${1:?source directory required}"
PUBLIC_DIR="${2:?public directory required}"
WORK_DIR="${3:-${RUNNER_TEMP:-/tmp}/ridersfanatics-preprod-notion}"

case "$PUBLIC_DIR" in
  /|/var|/var/www|"") echo "Refusing unsafe public directory: $PUBLIC_DIR" >&2; exit 2 ;;
esac
case "$WORK_DIR" in
  /|/var|/var/www|"") echo "Refusing unsafe work directory: $WORK_DIR" >&2; exit 2 ;;
esac

NOTION_SNAPSHOT="$SOURCE_DIR/data/notion/riders.json"
NOTION_COMPETITIONS="$SOURCE_DIR/data/notion/competitions.json"
test -f "$NOTION_SNAPSHOT"
test -f "$NOTION_COMPETITIONS"
python3 "$SOURCE_DIR/scripts/validate_rider_snapshot.py" "$NOTION_SNAPSHOT"

rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR/notion-build" "$WORK_DIR/notion-public" "$PUBLIC_DIR"
rsync -a --exclude='.git' "$SOURCE_DIR/" "$WORK_DIR/notion-build/"
(
  cd "$WORK_DIR/notion-build"
  RF_BUILD_ENV=preprod \
  RF_DATA_SOURCE=notion \
  RF_DATA_PATH=data/notion/riders.json \
  RF_COMPETITIONS_PATH=data/notion/competitions.json \
  RF_SITE_URL=https://preprod.ridersfanatics.com \
  RF_SKIP_IMAGE_OPTIMIZER="${RF_SKIP_IMAGE_OPTIMIZER:-1}" \
  python3 build.py
)

test -f "$WORK_DIR/notion-build/competitions/redbull-2026.html"
test -f "$WORK_DIR/notion-build/competitions/redbull-2026/rounds/ceroabajo-2026.html"
test -f "$WORK_DIR/notion-build/competitions/redbull-2026/rounds/rampage-2026.html"
test -f "$WORK_DIR/notion-build/competitions/redbull-2026/rounds/hardline-2026.html"
test -f "$WORK_DIR/notion-build/competitions/project-17/riders.html"
grep -q 'Project 17' "$WORK_DIR/notion-build/competitions.html"
"$WORK_DIR/notion-build/deploy/publish-static.sh" "$WORK_DIR/notion-build" "$WORK_DIR/notion-public" preprod
rsync -a --delete "$WORK_DIR/notion-public/" "$PUBLIC_DIR/"

if [[ -f "$SOURCE_DIR/data/notion/sync-metadata.json" ]]; then
  cp "$SOURCE_DIR/data/notion/sync-metadata.json" "$PUBLIC_DIR/notion-sync-metadata.json"
  notion_version="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["sha256"])' "$SOURCE_DIR/data/notion/sync-metadata.json")"
  printf '%s\n' "$notion_version" > "$PUBLIC_DIR/notion-data-version.txt"
fi

echo "Preproduction built from Notion only"
