#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="${1:?source directory required}"
PUBLIC_DIR="${2:?public directory required}"
WORK_DIR="${3:-${RUNNER_TEMP:-/tmp}/ridersfanatics-preprod-variants}"

case "$PUBLIC_DIR" in
  /|/var|/var/www|"") echo "Refusing unsafe public directory: $PUBLIC_DIR" >&2; exit 2 ;;
esac
case "$WORK_DIR" in
  /|/var|/var/www|"") echo "Refusing unsafe work directory: $WORK_DIR" >&2; exit 2 ;;
esac

rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR/google-public" "$PUBLIC_DIR"

# Google remains the stable root build and also gets an isolated comparison URL.
RF_BUILD_ENV=preprod \
RF_DATA_SOURCE=google \
RF_SITE_URL=https://preprod.ridersfanatics.com \
RF_SKIP_IMAGE_OPTIMIZER="${RF_SKIP_IMAGE_OPTIMIZER:-1}" \
python3 "$SOURCE_DIR/build.py"
python3 "$SOURCE_DIR/scripts/validate_rider_snapshot.py" "$SOURCE_DIR/data/riders.json"
"$SOURCE_DIR/deploy/publish-static.sh" "$SOURCE_DIR" "$WORK_DIR/google-public" preprod
rsync -a --delete "$WORK_DIR/google-public/" "$PUBLIC_DIR/"
mkdir -p "$PUBLIC_DIR/google"
rsync -a --delete "$WORK_DIR/google-public/" "$PUBLIC_DIR/google/"
rm -f "$PUBLIC_DIR/google/.htaccess"

NOTION_SNAPSHOT="$SOURCE_DIR/data/notion/riders.json"
if [[ -f "$NOTION_SNAPSHOT" ]]; then
  python3 "$SOURCE_DIR/scripts/validate_rider_snapshot.py" "$NOTION_SNAPSHOT"
  mkdir -p "$WORK_DIR/notion-build" "$WORK_DIR/notion-public"
  rsync -a --exclude='.git' "$SOURCE_DIR/" "$WORK_DIR/notion-build/"
  (
    cd "$WORK_DIR/notion-build"
    RF_BUILD_ENV=preprod \
    RF_DATA_SOURCE=notion \
    RF_DATA_PATH=data/notion/riders.json \
    RF_SITE_URL=https://preprod.ridersfanatics.com/notion \
    RF_SKIP_IMAGE_OPTIMIZER="${RF_SKIP_IMAGE_OPTIMIZER:-1}" \
    python3 build.py
  )
  "$WORK_DIR/notion-build/deploy/publish-static.sh" "$WORK_DIR/notion-build" "$WORK_DIR/notion-public" preprod
  mkdir -p "$PUBLIC_DIR/notion"
  rsync -a --delete "$WORK_DIR/notion-public/" "$PUBLIC_DIR/notion/"
  rm -f "$PUBLIC_DIR/notion/.htaccess"
  notion_state="ready"
else
  mkdir -p "$PUBLIC_DIR/notion"
  cat > "$PUBLIC_DIR/notion/index.html" <<'HTML'
<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow,noarchive"><title>Notion source · Preproduction</title><style>body{margin:0;background:#f2f0ec;color:#15161a;font:16px/1.6 Arial,sans-serif}.bar{padding:12px 20px;background:#101216;color:#fff}.wrap{max-width:760px;margin:12vh auto;padding:32px}.label{font:12px monospace;letter-spacing:.12em;text-transform:uppercase;color:#b4471b}h1{font-size:clamp(36px,7vw,72px);line-height:1;margin:.3em 0}a{display:inline-block;margin-top:18px;padding:12px 16px;background:#b4471b;color:#fff;text-decoration:none}</style></head><body><div class="bar">PREPROD DATA SOURCE · NOTION</div><main class="wrap"><div class="label">Safe fallback active</div><h1>Notion is not connected yet.</h1><p>The Google Sheets build remains available and unchanged. This preview will become active only after a valid read-only Notion snapshot passes the data contract checks.</p><a href="/google/">Return to Google Sheets preview</a></main></body></html>
HTML
  notion_state="unavailable"
fi

printf 'active=google\ngoogle=ready\nnotion=%s\n' "$notion_state" > "$PUBLIC_DIR/data-source-status.txt"

echo "Preproduction variants built: google=ready notion=$notion_state"
