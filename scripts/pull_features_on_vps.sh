#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/hotcut/freeridefanatics"
REPO_URL="https://github.com/Poupyxi/freeridefanatics.git"

log() {
  printf '[features] %s\n' "$1"
}

cd "$APP_DIR"

if ! command -v git >/dev/null 2>&1; then
  log "git missing; installing"
  apt-get update -qq
  apt-get install -y -qq git
fi

git config --global --add safe.directory "$APP_DIR" >/dev/null 2>&1 || true

if [ ! -d .git ]; then
  log "bootstrap git repo"
  git init -b main
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  log "configure origin remote"
  git remote add origin "$REPO_URL"
fi

log "fetch latest from GitHub"
git fetch --prune origin main
git reset --hard origin/main

log "rebuild docker stack"
docker compose up -d --build

log "done"
