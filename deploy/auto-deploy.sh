#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${1:-/opt/ridersfanatics/repo}"
PUBLIC_DIR="${2:-/var/www/ridersfanatics-public}"
BRANCH="${3:-main}"
LOCK_FILE="${4:-/run/lock/ridersfanatics-deploy.lock}"

exec 9>"$LOCK_FILE"
flock -n 9 || exit 0

git -C "$REPO_DIR" fetch --quiet origin "$BRANCH"
CURRENT_COMMIT="$(git -C "$REPO_DIR" rev-parse HEAD)"
REMOTE_COMMIT="$(git -C "$REPO_DIR" rev-parse "origin/$BRANCH")"

if [[ "$CURRENT_COMMIT" == "$REMOTE_COMMIT" ]]; then
  exit 0
fi

# This is a dedicated deployment checkout: it never contains authored work.
git -C "$REPO_DIR" reset --hard --quiet "origin/$BRANCH"
"$REPO_DIR/deploy/publish-static.sh" "$REPO_DIR" "$PUBLIC_DIR"
chown -R www-data:www-data "$PUBLIC_DIR"
logger -t ridersfanatics-deploy "Published $REMOTE_COMMIT from $BRANCH"

