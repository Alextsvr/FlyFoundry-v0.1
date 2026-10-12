#!/usr/bin/env bash
# Persist the state directory as a single-commit orphan branch `flyfoundry-state` (force-pushed, bounded size).
# Usage: state_save.sh <remote> <state_dir> <message>
set -euo pipefail
REMOTE="${1:-origin}"; DIR="${2:-state}"; MSG="${3:-state update}"
BRANCH="flyfoundry-state"
ROOT="$(git rev-parse --show-toplevel)"
TMP="$(mktemp -d)"
cp -a "$DIR"/. "$TMP"/
git -C "$TMP" init -q
git -C "$TMP" checkout -q --orphan state
git -C "$TMP" add -A
git -C "$TMP" -c user.name="flyfoundry-bot" -c user.email="flyfoundry-bot@users.noreply.github.com" \
    -c commit.gpgsign=false commit -q -m "$MSG"
git -C "$ROOT" fetch -q "$TMP" "state:refs/heads/_flyfoundry_state_tmp" --force
git -C "$ROOT" push -q --force "$REMOTE" "_flyfoundry_state_tmp:refs/heads/$BRANCH"
git -C "$ROOT" branch -q -D _flyfoundry_state_tmp
echo "state persisted to $BRANCH: $(git -C "$TMP" rev-parse --short HEAD)"
rm -rf "$TMP"
