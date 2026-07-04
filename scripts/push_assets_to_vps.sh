#!/usr/bin/env bash
set -euo pipefail

LOCAL_REPO="/Users/marcgreteau/Desktop/freeride"
VPS_HOST="root@76.13.149.25"
VPS_DIR="/opt/hotcut/freeridefanatics"

log() {
  printf '[assets] %s\n' "$1"
}

mkdir -p "$LOCAL_REPO"

sync_dir() {
  local src="$1"
  if [ -d "$LOCAL_REPO/$src" ]; then
    log "sync $src"
    rsync -a --delete "$LOCAL_REPO/$src/" "$VPS_HOST:$VPS_DIR/$src/"
  fi
}

sync_file() {
  local src="$1"
  if [ -f "$LOCAL_REPO/$src" ]; then
    log "sync $src"
    rsync -a "$LOCAL_REPO/$src" "$VPS_HOST:$VPS_DIR/"
  fi
}

sync_dir "PPRiders"
sync_dir "PictureRiders"
sync_dir "Equipment"
sync_dir "flags"
sync_dir "logos"
sync_dir "hotcut-landing"

sync_file "config.py"
sync_file "background.png"
sync_file "background equipementv2.png"
sync_file "equipment_card_bg.png"
sync_file "AntonSC-Regular.ttf"
sync_file "BebasNeue-Regular.ttf"

log "rebuild container on VPS"
ssh "$VPS_HOST" "cd '$VPS_DIR' && docker compose up -d --build"

log "verify public endpoint"
ssh "$VPS_HOST" "curl -fsS https://freeridefanatics.hotcut.xyz/api/preload >/dev/null"

log "done"
