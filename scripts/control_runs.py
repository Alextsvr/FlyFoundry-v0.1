"""SYNTHETIC control runs of the real CLI (`bounty run`) against a fake transport. Not real data; documents behaviour.
Usage: python scripts/control_runs.py <out_dir>"""
import json, shutil, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, "tests"); sys.path.insert(0, ".")
from _bounty_common import item, page, make_transport, fetcher
from flyfoundry.bounty_factory import cli as C

root = Path(sys.argv[1]); shutil.rmtree(root, ignore_errors=True); root.mkdir(parents=True)
base = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
(root / "reviews.json").write_text('{"reviews": []}'); (root / "manual.json").write_text('{"entries": []}')
pages = lambda prize=5000: [page([item(i, f"Synthetic Hack {i}", prize=f"${prize + i}") for i in range(1, 9)])]
scen = [("01_first_run_no_state", pages(), {}, 0), ("02_second_run_restored_state_prize_change", pages(9000), {}, 0),
        ("03_source_http_503_prior_data", [], {"list_status": 503}, 4), ("04_http200_wrong_schema_prior_data", [], {"list_body": "{}"}, 4),
        ("05_partial_listing_total_mismatch", [page([item(1, "Synthetic Hack 1")], total=60, per_page=1), page([], total=60, per_page=1, current=2)], {}, 3),
        ("06_recovery_after_outage", pages(9000), {}, 0)]
log = []
for k, (name, pg, kw, expect) in enumerate(scen):
    t = make_transport(pg, **kw)
    C.Fetcher = lambda **a: fetcher(t)
    out = root / name
    now = (base + timedelta(days=k)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rc = C.main_bounty(["run", "--state-dir", str(root / "state"), "--out", str(out), "--reviews", str(root / "reviews.json"), "--manual", str(root / "manual.json"),
                        "--now", now, "--no-detail", "--provisional-briefs", "2"])
    m = json.loads((out / "manifest.json").read_text())
    log.append({"scenario": name, "exit_code": rc, "expected": expect, "run_status": m["run_status"]["run_status"], "manifest_ok": C.verify_manifest(out) == [],
                "files": len(m["files"]), "briefs": len(m["briefs"]), "run_id": m["run_id"]})
(root / "control_runs_summary.json").write_text(json.dumps(log, indent=1))
print(json.dumps(log, indent=1)); sys.exit(0 if all(l["exit_code"] == l["expected"] and l["manifest_ok"] for l in log) else 1)
