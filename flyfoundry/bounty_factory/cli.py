"""CLI: `python -m flyfoundry bounty <run|discover|evaluate|report|brief>`. Sequential defaults, no secrets needed."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import pipeline as P
from .brief import build_brief, build_prompt
from .gate import load_reviews
from .http import Fetcher
from .report import render_html, summary_json, to_csv
from .store import Store


def _now(args):
    return datetime.fromisoformat(args.now.replace("Z", "+00:00")) if getattr(args, "now", None) else datetime.now(timezone.utc)


def _history(path="data/bounty_history.json"):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"projects": []}


def produce(store, cfg, args, now, discovery=None) -> dict:
    reviews = load_reviews(args.reviews)
    ev = P.evaluate(store, cfg, reviews, now)
    history = _history()
    m = P.metrics(store, ev, reviews, history, now)
    out = Path(args.out)
    (out / "briefs").mkdir(parents=True, exist_ok=True)
    (out / "prompts").mkdir(parents=True, exist_ok=True)
    summ = summary_json(ev, cfg, now)
    first_run = store.db.execute("SELECT COUNT(*) FROM source_runs WHERE source='devpost'").fetchone()[0] <= 1
    html = render_html(ev, cfg, store, m, history, now, store.last_runs(), store.all_changes(), first_run)
    (out / "report.html").write_text(html, encoding="utf-8")
    (out / "opportunities.json").write_text(json.dumps(summ, indent=1, default=str), encoding="utf-8")
    (out / "opportunities.csv").write_text(to_csv(summ), encoding="utf-8")
    (out / "ranking.json").write_text(json.dumps({"rank_a": ev["rank_a"], "rank_b": ev["rank_b"], "sensitivity": ev["sensitivity"], "a_vs_b": ev["a_vs_b"], "weights": cfg["weights"]}, indent=1), encoding="utf-8")
    (out / "metrics.json").write_text(json.dumps({"metrics": m, "discovery": discovery, "sources": {k: v for k, v in store.last_runs().items()}}, indent=1, default=str), encoding="utf-8")
    # briefs: ELIGIBLE above threshold; provisional NEEDS_REVIEW only on request (top N by rank)
    made = []
    for r in ev["rows"]:
        d = r["gate"]["decision"]
        ok = d == "ELIGIBLE" and r["score_b"]["score"] >= cfg["min_priority_for_brief"]
        prov = d == "NEEDS_REVIEW" and args.provisional_briefs and r["rank_b"] and r["rank_b"] <= args.provisional_briefs
        if ok or prov:
            (out / "briefs" / f"{r['opp'].id}.md").write_text(build_brief(r, P.iso(now), provisional=not ok), encoding="utf-8")
            (out / "prompts" / f"{r['opp'].id}.claude-prompt.md").write_text(build_prompt(r), encoding="utf-8")
            made.append(r["opp"].id)
    print(f"report written to {out}/report.html; decisions={m['decisions']}; briefs={len(made)}")
    return {"metrics": m, "briefs": made}


def cmd_bounty(args) -> int:
    cfg = P.load_cfg(args.config)
    now = _now(args)
    Path(args.state_dir).mkdir(parents=True, exist_ok=True)
    store = Store(Path(args.state_dir) / "bounty.sqlite3")
    discovery = None
    try:
        if args.action in ("run", "discover"):
            fetcher = Fetcher(min_interval=cfg["min_interval_seconds"], max_seconds=cfg["max_run_seconds"])
            discovery = P.discover(store, cfg, fetcher, now, args.manual)
            if args.action == "run" and not args.no_detail:
                discovery["detail"] = P.enrich_details(store, cfg, fetcher, now)
        if args.action in ("run", "evaluate", "report", "brief"):
            produce(store, cfg, args, now, discovery)
        if discovery and all(v["status"] in ("failed", "blocked_by_robots") for k, v in discovery.items() if k == "devpost"):
            print("WARNING: devpost produced no data this run (recorded in metrics.json)", file=sys.stderr)
    finally:
        store.close()
    return 0


def add_parser(sub):
    sp = sub.add_parser("bounty", help="Bounty Factory: discover/evaluate/report/brief (no paid APIs)")
    sp.add_argument("action", choices=["run", "discover", "evaluate", "report", "brief"])
    sp.add_argument("--state-dir", default="state_bounty")
    sp.add_argument("--out", default="out/bounty")
    sp.add_argument("--config", default="data/bounty_config.json")
    sp.add_argument("--reviews", default="data/bounty_reviews.json")
    sp.add_argument("--manual", default="data/bounty_manual_intake.json")
    sp.add_argument("--now", default=None, help="ISO timestamp override for reproducible evaluation")
    sp.add_argument("--no-detail", action="store_true")
    sp.add_argument("--provisional-briefs", type=int, default=0, help="also write PROVISIONAL briefs for the top N NEEDS_REVIEW items")
    sp.set_defaults(fn=cmd_bounty)
