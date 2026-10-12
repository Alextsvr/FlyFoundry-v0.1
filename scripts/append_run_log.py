"""Append one row per workflow run to runs.csv (kept in the state branch) so the history is readable without artifacts."""
import csv
import json
import sys
from pathlib import Path

res = json.loads(Path(sys.argv[1]).read_text())
out = Path(sys.argv[2])
run = res["runs"][-1]
arms = res["analysis"]["arms"]
row = {
    "run_id": run["run_id"], "finished_utc": run.get("finished_utc"), "event": (run.get("mode") or ""),
    "gen_start": run["gen_start"], "gen_end": run["gen_end"], "total_evals": res["total_evals"],
    "cpu_s": run["cpu_s"], "wall_s": run["wall_s"], "peak_rss_mb": run["peak_rss_mb"],
    "code_revision": (run.get("code_revision") or "")[:10],
    "github_run_url": (run.get("environment") or {}).get("github_run_url") or "",
}
for a, d in arms.items():
    row[f"heldout_qd__{a}"] = round(d["metrics"]["heldout_qd"]["mean"], 4)
new = not out.exists()
with out.open("a", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(row))
    if new:
        w.writeheader()
    w.writerow(row)
print(f"appended run {row['run_id']} to {out}")
