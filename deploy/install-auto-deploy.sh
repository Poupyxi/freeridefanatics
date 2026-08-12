#!/usr/bin/env bash
set -euo pipefail

REPOSITORY_URL="${1:-https://github.com/Poupyxi/freeridefanatics.git}"
REPO_DIR="${2:-/opt/ridersfanatics/repo}"
PUBLIC_DIR="${3:-/var/www/ridersfanatics-public}"
BRANCH="${4:-main}"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run this installer as root." >&2
  exit 2
fi

apt-get update
apt-get install -y git rsync
mkdir -p "$(dirname "$REPO_DIR")" "$PUBLIC_DIR"

if [[ -d "$REPO_DIR/.git" ]]; then
  git -C "$REPO_DIR" remote set-url origin "$REPOSITORY_URL"
else
  git clone --branch "$BRANCH" --single-branch "$REPOSITORY_URL" "$REPO_DIR"
fi

chmod +x "$REPO_DIR/deploy/auto-deploy.sh" "$REPO_DIR/deploy/publish-static.sh"
sed \
  -e "s#/opt/ridersfanatics/repo#$REPO_DIR#g" \
  -e "s#/var/www/ridersfanatics-public#$PUBLIC_DIR#g" \
  -e "s# main$# $BRANCH#" \
  "$REPO_DIR/deploy/ridersfanatics-deploy.service" \
  > /etc/systemd/system/ridersfanatics-deploy.service
cp "$REPO_DIR/deploy/ridersfanatics-deploy.timer" /etc/systemd/system/ridersfanatics-deploy.timer

systemctl daemon-reload
systemctl enable --now ridersfanatics-deploy.timer
systemctl start ridersfanatics-deploy.service
systemctl --no-pager status ridersfanatics-deploy.timer

