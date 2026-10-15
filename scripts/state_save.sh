#!/usr/bin/env bash
# Persist the state directory as a single-commit orphan branch (bounded size), with a compare-and-swap lease.
# Usage: state_save.sh <remote> <state_dir> <message>
# Env:   STATE_BRANCH       (default flyfoundry-state)
#        STATE_VERIFY       optional command run on <state_dir> BEFORE pushing (non-zero = refuse to publish)
#        STATE_REQUIRE_BASE if "1", refuse unless <state_dir>.base_sha exists (written by state_restore.sh)
# If <state_dir>.base_sha exists the push uses --force-with-lease against that sha ("none" = branch must still be absent), so a
# change made to the remote branch after the restore is never overwritten (the push fails; nothing is lost, rerun the job).
set -euo pipefail
REMOTE="${1:-origin}"; DIR="${2:-state}"; MSG="${3:-state update}"
BRANCH="${STATE_BRANCH:-flyfoundry-state}"
BASE_FILE="${DIR}.base_sha"
if [ "${STATE_REQUIRE_BASE:-0}" = "1" ] && [ ! -f "$BASE_FILE" ]; then echo "ERROR: $BASE_FILE missing: restore did not complete; refusing to publish" >&2; exit 1; fi
if [ -n "${STATE_VERIFY:-}" ]; then bash -c "$STATE_VERIFY" _ "$DIR" || { echo "ERROR: state failed verification; not publishing" >&2; exit 1; }; fi
ROOT="$(git rev-parse --show-toplevel)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cp -a "$DIR"/. "$TMP"/
git -C "$TMP" init -q
git -C "$TMP" checkout -q --orphan state
git -C "$TMP" add -A
git -C "$TMP" -c user.name="flyfoundry-bot" -c user.email="flyfoundry-bot@users.noreply.github.com" -c commit.gpgsign=false commit -q -m "$MSG"
git -C "$ROOT" fetch -q "$TMP" "state:refs/heads/_flyfoundry_state_tmp" --force
if [ -f "$BASE_FILE" ]; then
  BASE="$(cat "$BASE_FILE")"
  if [ "$BASE" = "none" ]; then LEASE="--force-with-lease=refs/heads/$BRANCH:"; else LEASE="--force-with-lease=refs/heads/$BRANCH:$BASE"; fi
else
  LEASE="--force"
fi
if ! git -C "$ROOT" push -q $LEASE "$REMOTE" "_flyfoundry_state_tmp:refs/heads/$BRANCH"; then
  git -C "$ROOT" branch -q -D _flyfoundry_state_tmp || true
  echo "ERROR: push refused (the remote state branch changed after it was restored, or the push failed); nothing was overwritten" >&2
  exit 1
fi
git -C "$ROOT" branch -q -D _flyfoundry_state_tmp
echo "state persisted to $BRANCH: $(git -C "$TMP" rev-parse --short HEAD)"
