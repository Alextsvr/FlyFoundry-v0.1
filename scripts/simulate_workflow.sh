#!/usr/bin/env bash
# LOCAL simulation of the experiment workflow's shell logic against a local bare "origin".
# It is NOT a GitHub Actions run. It proves that state survives independent, fresh checkouts.
set -euo pipefail
SRC="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-python3}"
W="$(mktemp -d)"; ORIGIN="$W/origin.git"
git init -q --bare -b main "$ORIGIN"
git -C "$SRC" push -q "$ORIGIN" HEAD:refs/heads/main
for run in 1 2 3; do
  rm -rf "$W/clone$run"; git clone -q "$ORIGIN" "$W/clone$run"; cd "$W/clone$run"
  export PYTHONPATH="$PWD"
  scripts/state_restore.sh origin state
  if [ -f state/manifest.json ]; then ARGS=(); else ARGS=(--allow-fresh); fi
  $PY -m flyfoundry run --config configs/nightly.json --state-dir state --out reports/latest --generations ${GENS:-6} --seeds ${SEEDS:-2} --pop-size ${POP:-30} "${ARGS[@]}" --scheduled
  $PY -m flyfoundry validate --state-dir state > /dev/null
  scripts/state_save.sh origin state "simulated run $run"
  echo "== run $run: generation $($PY -c "import json;print(json.load(open('reports/latest/results.json'))['generation'])")"
done
# tamper test: corrupt the newest checkpoint on the branch, expect recovery from the older one
rm -rf "$W/clone4"; git clone -q "$ORIGIN" "$W/clone4"; cd "$W/clone4"; export PYTHONPATH="$PWD"
scripts/state_restore.sh origin state
newest=$(ls state/ckpt_*.json.gz | sort | tail -1); printf 'corrupt' > "$newest"
$PY -m flyfoundry run --config configs/nightly.json --state-dir state --out reports/latest --generations 2 2>&1 | grep -E "WARNING|restored|advanced" || true
# missing-state test: an empty remote branch must NOT silently restart
rm -rf "$W/emptystate"; mkdir "$W/emptystate"
set +e; $PY -m flyfoundry run --config configs/nightly.json --state-dir "$W/emptystate" --out "$W/o" --generations 1 >/dev/null 2>&1; rc=$?; set -e
echo "== missing state without --allow-fresh -> exit code $rc (expected 4)"
rm -rf "$W"
