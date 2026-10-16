"""CLI: `python -m flyfoundry bounty <action>`. Standard library only (works on Windows).

Exit codes of `run` / `discover`: 0 success | 3 partial | 4 source_unavailable | 5 no_data | 6 internal error | 7 invalid state (verify-state).
Outputs are generated into a fresh directory, verified against a manifest and published by swapping directories, so a failed or
partial run never leaves a mixture of old and new files (stale briefs disappear) and never destroys the last complete set."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from . import pipeline as P
from . import detail as detail_mod
from .brief import build_brief, build_prompt
from .gate import load_reviews, participant_hash, SCHEMA as REVIEW_SCHEMA, REQUIRED
from .http import Fetcher
from .report import render_html, summary_json, to_csv
from .sources import devpost, source_status_table
from .store import Store, inspect_db, migrate_file, USABLE

PACKAGE_VERSION = "0.2.2"
EXIT_INVALID_STATE = 7


def _now(args):
    return datetime.fromisoformat(args.now.replace("Z", "+00:00")) if getattr(args, "now", None) else datetime.now(timezone.utc)


def _history(path="data/bounty_history.json"):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"projects": []}


def code_version() -> dict:
    sha = os.environ.get("GITHUB_SHA", "")
    if not sha:
        try:
            sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10).stdout.strip()
        except Exception:  # noqa: BLE001
            sha = ""
    return {"git_sha": sha or "unknown", "package": PACKAGE_VERSION, "parsers": {"devpost_list": devpost.PARSER_VERSION, "detail": detail_mod.PARSER_VERSION}}


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def write_manifest(d: Path, run_id: str, now, status: dict, briefs: list, runs: dict) -> dict:
    files = [{"path": str(f.relative_to(d)).replace("\\", "/"), "sha256": sha256_file(f), "bytes": f.stat().st_size} for f in sorted(d.rglob("*")) if f.is_file() and f.name != "manifest.json"]
    m = {"run_id": run_id, "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "evaluated_at": P.iso(now), "code_version": code_version(),
         "run_status": status, "briefs": briefs, "files": files, "source_runs": runs, "complete": True}
    (d / "manifest.json").write_text(json.dumps(m, indent=1, default=str), encoding="utf-8")
    return m


def verify_manifest(d: Path) -> list:
    """Problems found (empty = the directory is a complete, untampered set described by its manifest)."""
    mp = d / "manifest.json"
    if not mp.exists():
        return ["manifest.json missing"]
    m = json.loads(mp.read_text(encoding="utf-8"))
    problems = []
    listed = {f["path"] for f in m.get("files", [])}
    for f in m.get("files", []):
        fp = d / f["path"]
        if not fp.exists():
            problems.append(f"missing {f['path']}")
        elif sha256_file(fp) != f["sha256"]:
            problems.append(f"hash mismatch {f['path']}")
    actual = {str(f.relative_to(d)).replace("\\", "/") for f in d.rglob("*") if f.is_file() and f.name != "manifest.json"}
    problems += [f"unlisted file {x}" for x in sorted(actual - listed)]
    return problems


def recover_dir(final: Path):
    """If a crash happened between the two renames of publish_dir, bring the previous complete set back."""
    old = final.with_name(final.name + ".old")
    if not final.exists() and old.exists():
        os.replace(old, final)


def publish_dir(new: Path, final: Path):
    """Replace `final` by `new` (a complete directory). The previous set is kept as `.old` until the swap succeeded."""
    final, new = Path(final), Path(new)
    old = final.with_name(final.name + ".old")
    recover_dir(final)
    if old.exists():
        shutil.rmtree(old)
    had = final.exists()
    if had:
        os.replace(final, old)
    try:
        os.replace(new, final)
    except Exception:
        if had:
            os.replace(old, final)
        raise
    if had:
        shutil.rmtree(old, ignore_errors=True)


def produce(store, cfg, args, now, out_dir: Path, status: dict, discovery=None, run_id="local") -> dict:
    reviews = load_reviews(args.reviews)
    ev = P.evaluate(store, cfg, reviews, now)
    history = _history()
    m = P.metrics(store, ev, reviews, history, now)
    out = Path(out_dir)
    if out.exists():
        shutil.rmtree(out)
    (out / "briefs").mkdir(parents=True)
    (out / "prompts").mkdir()
    summ = summary_json(ev, cfg, now)
    first_run = store.db.execute("SELECT COUNT(*) FROM source_runs WHERE source='devpost'").fetchone()[0] <= 1
    (out / "report.html").write_text(render_html(ev, cfg, store, m, history, now, store.last_runs(), store.all_changes(), first_run, status), encoding="utf-8")
    (out / "opportunities.json").write_text(json.dumps(summ, indent=1, default=str), encoding="utf-8")
    (out / "opportunities.csv").write_text(to_csv(summ), encoding="utf-8")
    (out / "ranking.json").write_text(json.dumps({"rank_a": ev["rank_a"], "rank_b": ev["rank_b"], "rank_review": ev["rank_review"], "a_definition": ev["a_definition"], "sensitivity": ev["sensitivity"],
                                                  "effort_scenarios": ev["effort_scenarios"], "a_vs_b": ev["a_vs_b"], "weights": cfg["weights"]}, indent=1), encoding="utf-8")
    (out / "metrics.json").write_text(json.dumps({"metrics": m, "discovery": discovery, "status": status, "sources": store.last_runs()}, indent=1, default=str), encoding="utf-8")
    (out / "status.json").write_text(json.dumps(status, indent=1, default=str), encoding="utf-8")
    made = []
    for r in ev["rows"]:
        d = r["gate"]["decision"]
        ok = d == "ELIGIBLE" and r["development_priority"] is not None and r["development_priority"] >= cfg["min_priority_for_brief"]
        prov = d == "NEEDS_REVIEW" and args.provisional_briefs and r["rank_review"] and r["rank_review"] <= args.provisional_briefs
        if ok or prov:
            (out / "briefs" / f"{r['opp'].id}.md").write_text(build_brief(r, P.iso(now), provisional=not ok), encoding="utf-8")
            (out / "prompts" / f"{r['opp'].id}.claude-prompt.md").write_text(build_prompt(r), encoding="utf-8")
            made.append(r["opp"].id)
    write_manifest(out, run_id, now, status, made, store.last_runs())
    bad = verify_manifest(out)
    if bad:
        raise RuntimeError("generated set failed manifest verification: " + "; ".join(bad[:5]))
    print(f"report generated; decisions={m['decisions']}; briefs={len(made)}; run_status={status['run_status']}")
    return {"metrics": m, "briefs": made}


def write_diagnostics(out_dir: Path, exc: BaseException, now, status: str = "internal_error", code: int | None = None):
    d = Path(str(out_dir) + "-diagnostics")
    d.mkdir(parents=True, exist_ok=True)
    (d / "error.md").write_text(f"# Bounty Factory run FAILED\n\n- time: {P.iso(now)}\n- error: `{type(exc).__name__}: {exc}`\n- the last complete output set (if any) was left untouched\n\n```\n{traceback.format_exc()[-3000:]}\n```\n", encoding="utf-8")
    (d / "status.json").write_text(json.dumps({"run_status": status, "exit_code": P.EXIT["internal_error"] if code is None else code, "message": f"{type(exc).__name__}: {exc}"}, indent=1), encoding="utf-8")


def cmd_bounty(args) -> int:
    if args.action == "verify-state":                  # needs neither config nor clock: it must work from any directory
        return cmd_verify_state(args)
    cfg = P.load_cfg(args.config)
    now = _now(args)
    if args.action == "review-template":
        return cmd_review_template(args, cfg, now)
    out = Path(args.out)
    state = Path(args.state_dir)
    state.mkdir(parents=True, exist_ok=True)
    recover_dir(out)
    recover_dir(state / "latest")
    run_id = os.environ.get("GITHUB_RUN_ID") or "local-" + now.strftime("%Y%m%dT%H%M%SZ")
    tmp = out.with_name(out.name + ".new")
    dbp = state / "bounty.sqlite3"
    info = inspect_db(dbp)
    if info["status"] not in ("absent",) + USABLE:        # never convert a damaged/foreign/empty file into a "fresh" state
        print(f"STATE REJECTED ({info['status']}): {'; '.join(info['problems'])}; nothing was changed", file=sys.stderr)
        write_diagnostics(out, RuntimeError(f"state database rejected: {info['status']}: {'; '.join(info['problems'])}"), now, "invalid_state", EXIT_INVALID_STATE)
        return EXIT_INVALID_STATE
    migrated = None
    if info["status"] == "legacy":
        migrated = migrate_file(dbp)
        print(f"state database migrated: {json.dumps(migrated)}")
    store = Store(dbp)
    rc = 0
    try:
        discovery = None
        if args.action in ("run", "discover"):
            fetcher = Fetcher(min_interval=cfg["min_interval_seconds"], max_seconds=cfg["max_run_seconds"])
            discovery = P.discover(store, cfg, fetcher, now, args.manual)
            if args.action == "run" and not args.no_detail:
                discovery["detail"] = P.enrich_details(store, cfg, fetcher, now)
            status = P.run_status(discovery, store, cfg)
            rc = status["exit_code"]
        else:
            status = {"run_status": "evaluate_only", "exit_code": 0, "message": "stored data re-evaluated; nothing was fetched", "primary_sources": {}, "last_complete_success": {s: store.last_ok_run(s) for s in cfg.get("primary_sources", ["devpost"])}}
        if args.action != "discover":
            produce(store, cfg, args, now, tmp, status, discovery, run_id)
            publish_dir(tmp, out)
            if args.action == "run":
                latest_new = state / "latest.new"
                if latest_new.exists():
                    shutil.rmtree(latest_new)
                shutil.copytree(out, latest_new)
                publish_dir(latest_new, state / "latest")
        if args.action == "run" and migrated is None and rc in (0, 3):
            bak = dbp.with_name(dbp.name + ".premigration.bak")
            if bak.exists():
                bak.unlink()                                # the backup lives until the first successful run after the migration
        if args.action == "run":
            print(f"RUN STATUS: {status['run_status']} (exit {rc}): {status['message']}")
            if rc:
                print(f"::warning::bounty run status={status['run_status']}: {status['message']}", file=sys.stderr)
            print(json.dumps(store.prune(now)))
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        write_diagnostics(out, e, now)
        rc = P.EXIT["internal_error"]
    finally:
        store.close()
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
    return rc


def cmd_verify_state(args) -> int:
    """Integrity gate used before state is used or published: SQLite integrity + tables + (if present) the latest/ manifest."""
    d = Path(args.state_dir)
    problems = []
    db = d / "bounty.sqlite3"
    info = inspect_db(db)                                  # READ-ONLY: never creates, migrates or repairs the checked object
    if info["status"] == "absent":
        problems.append("bounty.sqlite3 missing")
    elif info["status"] not in USABLE:
        problems += [f"bounty.sqlite3 rejected ({info['status']}): {x}" for x in info["problems"]]
    warnings_db = [f"bounty.sqlite3 is a legacy version {info['version']}; it is migrated (with a backup) at the start of the next run"] if info["status"] == "legacy" else []
    warnings = list(warnings_db)
    if (d / "latest").exists():
        if not (d / "latest" / "manifest.json").exists():
            warnings.append("latest/ has no manifest.json (written by a pre-0.2.1 run); it is replaced by the next successful run")
        else:
            problems += [f"latest/{p}" for p in verify_manifest(d / "latest")]
    size = db.stat().st_size if db.exists() else 0
    if size > 90_000_000:
        problems.append(f"sqlite is {size} bytes (> 90 MB): retention policy failed")
    print(json.dumps({"state_dir": str(d), "ok": not problems, "problems": problems, "warnings": warnings, "db_status": info["status"], "sqlite_bytes": size}))
    return 0 if not problems else 7


def cmd_review_template(args, cfg, now) -> int:
    """Print a schema-2 review skeleton bound to the current participant configuration (a human fills and commits it)."""
    store = Store(Path(args.state_dir) / "bounty.sqlite3")
    o = store.get(args.id)
    store.close()
    if o is None:
        print(f"unknown id {args.id}", file=sys.stderr)
        return 2
    rules = o.fact("rules_hash")
    print(json.dumps({"id": o.id, "schema": REVIEW_SCHEMA, "reviewed_at": P.iso(now)[:10], "reviewer": "", "evidence_url": "", "rules_ref": ("sha256:" + rules.value) if rules.known() else "",
                      "participant_hash": participant_hash(cfg), "minutes_spent": 0, "label": "",
                      "conditions": {c: {"status": "", "note": ""} for c in REQUIRED}, "acknowledged_signals": [],
                      "_help": "status: ok | not_applicable (needs a note) | excluded. rules_ref: rules hash or the version/date of the rules you read. Fill every condition from the OFFICIAL rules."}, indent=1))
    return 0


def _build_parser(sp):
    sp.add_argument("action", choices=["run", "discover", "evaluate", "report", "brief", "verify-state", "review-template"])
    sp.add_argument("--state-dir", default="state_bounty")
    sp.add_argument("--out", default="out/bounty")
    sp.add_argument("--config", default="data/bounty_config.json")
    sp.add_argument("--reviews", default="data/bounty_reviews.json")
    sp.add_argument("--manual", default="data/bounty_manual_intake.json")
    sp.add_argument("--now", default=None, help="ISO timestamp override for reproducible evaluation")
    sp.add_argument("--no-detail", action="store_true")
    sp.add_argument("--id", default="", help="opportunity id (review-template)")
    sp.add_argument("--provisional-briefs", type=int, default=0, help="also write PROVISIONAL briefs for the top N NEEDS_REVIEW items by review priority")
    sp.set_defaults(fn=cmd_bounty)
    return sp


def add_parser(sub):
    return _build_parser(sub.add_parser("bounty", help="Bounty Factory: discover/evaluate/report/brief (no paid APIs)"))


def main_bounty(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="flyfoundry bounty", description="Bounty Factory (stdlib only)")
    args = _build_parser(ap).parse_args(argv)
    return args.fn(args)
