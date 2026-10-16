#!/usr/bin/env bash
# Restore durable state (orphan branch) into a plain directory, safely.
# Usage: state_restore.sh <remote> <state_dir>
# Env:   STATE_BRANCH  (default flyfoundry-state)
#        STATE_VERIFY  optional shell command; run as `bash -c "$STATE_VERIFY" _ <restored_dir>`; non-zero = state is invalid
# Writes <state_dir>.base_sha ("none" if the branch does not exist) = the remote head this run is based on; state_save.sh uses it
# as a compare-and-swap lease so a concurrent change of the remote branch is never overwritten.
# Exit 0: state restored AND verified, or the branch verifiably does not exist.  Exit 1: anything else (nothing is left in <state_dir>).
set -uo pipefail
REMOTE="${1:-origin}"; DIR="${2:-state}"
BRANCH="${STATE_BRANCH:-flyfoundry-state}"
fail() { echo "ERROR: $*" >&2; [ -n "${TMP:-}" ] && rm -rf "$TMP"; exit 1; }
TMP="$(mktemp -d)" || fail "mktemp failed"

ls_out="$(git ls-remote --heads "$REMOTE" "refs/heads/$BRANCH" 2>&1)"; rc=$?
[ $rc -eq 0 ] || fail "could not query $REMOTE (git ls-remote exit $rc): $ls_out; refusing to guess"
if [ -z "$ls_out" ]; then
  echo "state branch $BRANCH does not exist on $REMOTE (verified by ls-remote)"
  rm -rf "$DIR"; mkdir -p "$DIR"
  echo "none" > "${DIR}.base_sha"
  [ -n "${GITHUB_OUTPUT:-}" ] && echo "state_exists=false" >> "$GITHUB_OUTPUT"
  rm -rf "$TMP"; exit 0
fi
git fetch --quiet --depth 1 "$REMOTE" "refs/heads/$BRANCH" || fail "fetch of $BRANCH failed"
SHA="$(git rev-parse FETCH_HEAD)" || fail "cannot resolve FETCH_HEAD"
git archive FETCH_HEAD > "$TMP/state.tar" || fail "git archive failed"
mkdir -p "$TMP/x"
tar -x -f "$TMP/state.tar" -C "$TMP/x" || fail "tar extraction failed (corrupt archive)"
[ -n "$(ls -A "$TMP/x")" ] || fail "restored state is empty"
if [ -n "${STATE_VERIFY:-}" ]; then
  bash -c "$STATE_VERIFY" _ "$TMP/x" || fail "state verification failed; not using it, not overwriting the remote"
fi
rm -rf "$DIR"
mkdir -p "$(dirname "$DIR")"
mv "$TMP/x" "$DIR" || fail "could not move restored state into place"
echo "$SHA" > "${DIR}.base_sha"
echo "state restored from $BRANCH @ ${SHA:0:12} ($(ls "$DIR" | wc -l) entries), verified"
[ -n "${GITHUB_OUTPUT:-}" ] && echo "state_exists=true" >> "$GITHUB_OUTPUT"
rm -rf "$TMP"
exit 0
