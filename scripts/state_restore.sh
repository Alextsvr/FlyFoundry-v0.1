#!/usr/bin/env bash
# Restore the durable experiment state (orphan branch `flyfoundry-state`) into a plain directory.
# Usage: state_restore.sh <remote> <state_dir>
# Exit 0 always on success; reports presence via stdout and $GITHUB_OUTPUT (state_exists=true|false).
# Network/auth errors abort (exit 1) so a transient failure can never be mistaken for "no state".
set -uo pipefail
REMOTE="${1:-origin}"; DIR="${2:-state}"
BRANCH="flyfoundry-state"
git ls-remote --exit-code --heads "$REMOTE" "$BRANCH" >/dev/null 2>&1
rc=$?
mkdir -p "$DIR"
if [ $rc -eq 0 ]; then
  git fetch --quiet --depth 1 "$REMOTE" "$BRANCH" || { echo "ERROR: fetch of $BRANCH failed" >&2; exit 1; }
  git archive FETCH_HEAD | tar -x -C "$DIR"
  echo "state restored from $BRANCH ($(ls "$DIR" | wc -l) files)"
  [ -n "${GITHUB_OUTPUT:-}" ] && echo "state_exists=true" >> "$GITHUB_OUTPUT"
  exit 0
elif [ $rc -eq 2 ]; then
  echo "state branch $BRANCH does not exist on $REMOTE"
  [ -n "${GITHUB_OUTPUT:-}" ] && echo "state_exists=false" >> "$GITHUB_OUTPUT"
  exit 0
else
  echo "ERROR: could not query $REMOTE (git ls-remote exit $rc); refusing to guess" >&2
  exit 1
fi
