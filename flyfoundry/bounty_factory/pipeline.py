"""Orchestration: discover -> detail -> gate -> estimate -> score -> metrics. `evaluate` is a pure function of store content,
config, reviews and `now`, so rankings are reproducible."""
from __future__ import annotations

import json
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import detail as detail_mod
from .feasibility import estimate
from .gate import evaluate as gate_eval, load_reviews, deadline_status, ELIGIBLE, INELIGIBLE, NEEDS_REVIEW
from .http import Fetcher, RobotsDenied, BudgetExceeded
from .scoring import criteria, score_b, baseline_a, rank, sensitivity, kendall_tau, prize_usd
from .sources import SOURCES
from .sources import devpost
from .sources.manual import load_manual
from .store import Store


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_cfg(path="data/bounty_config.json") -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def discover(store: Store, cfg: dict, fetcher: Fetcher, now: datetime, manual_path="data/bounty_manual_intake.json", log=print) -> dict:
    summary = {}
    now_s = iso(now)
    # ---- devpost (live)
    run = store.start_run("devpost", now_s)
    seen, n, status, err, complete, last_http = set(), 0, "ok", "", False, None
    try:
        for url, http, body, data, is_last in devpost.fetch_all(fetcher, cfg["max_list_pages"]):
            last_http = http
            obs = store.add_observation(run, "devpost", url, url, now_s, body)
            if http != 200 or data is None:
                status, err = "failed", f"HTTP {http} or unparsable JSON at {url}"
                break
            for item in data.get("hackathons", []):
                o = devpost.to_opportunity(item, url)
                if o is None:
                    continue
                oid, _ = store.upsert(o, now_s, obs)
                seen.add(oid)
                n += 1
            complete = is_last
        if status == "ok" and not complete:
            status = "partial"
            err = "listing incomplete (page cap reached)"
    except RobotsDenied as e:
        status, err = "blocked_by_robots", str(e)
    except BudgetExceeded as e:
        status, err = "partial", str(e)
    except Exception as e:  # noqa: BLE001 - one source failing must not stop the others
        status, err = "failed", f"{type(e).__name__}: {e}"
    if status == "ok" and complete:
        store.mark_unlisted("devpost", seen, now_s)
    store.finish_run(run, now_s, status, last_http, n, complete, fetcher.requests, err)
    summary["devpost"] = {"status": status, "records": n, "complete": complete, "error": err}
    log(f"devpost: {status} records={n} complete={complete} {err}")
    # ---- manual intake
    run = store.start_run("manual", now_s)
    entries = load_manual(manual_path)
    for o in entries:
        store.upsert(o, now_s)
    store.finish_run(run, now_s, "ok", None, len(entries), True, 0, "")
    summary["manual"] = {"status": "ok", "records": len(entries), "complete": True, "error": ""}
    # ---- registry entries that are not implemented are recorded, not faked
    for name, info in SOURCES.items():
        if info.status in ("unsupported", "manual_review"):
            r = store.start_run(name, now_s)
            store.finish_run(r, now_s, info.status, None, 0, False, 0, info.reason[:300])
            summary[name] = {"status": info.status, "records": 0, "complete": False, "error": info.reason}
    return summary


def enrich_details(store: Store, cfg: dict, fetcher: Fetcher, now: datetime, log=print) -> dict:
    now_s = iso(now)
    cands = []
    for o in store.all():
        if o.source != "devpost" or o.status != "listed" or deadline_status(o, now) == "expired":
            continue
        age_ok = (not o.detail_fetched_at) or (now - datetime.fromisoformat(o.detail_fetched_at.replace("Z", "+00:00"))) > timedelta(days=7)
        if age_ok:
            usd = prize_usd(o, cfg) or 0
            cands.append((-usd, o.fact("deadline_date").value or "9999", o.id, o))
    cands.sort(key=lambda x: x[:3])
    done, errs = 0, []
    for _, _, _, o in cands[: cfg["detail_limit_per_run"]]:
        try:
            r = detail_mod.enrich(o, fetcher, now_s)
        except BudgetExceeded as e:
            errs.append(str(e))
            break
        errs += r["errors"]
        store.upsert(o, now_s)    # same record: facts diffed and persisted
        stored = store.get(o.id)
        stored.detail_fetched_at = o.detail_fetched_at
        store._write(stored)
        done += 1
    log(f"detail pass: {done} pages-sets fetched, {len(errs)} issues")
    return {"fetched": done, "issues": errs[:20]}


def evaluate(store: Store, cfg: dict, reviews: dict, now: datetime) -> dict:
    rows = []
    for o in store.all():
        g = gate_eval(o, cfg, now, reviews)
        est = estimate(o)
        crit = criteria(o, est, cfg, now)
        sb = score_b(crit, cfg["weights"])
        rows.append({"opp": o, "gate": g, "est": est, "crit": crit, "score_b": sb, "score_a": baseline_a(o, est, cfg)})
    cand = [r for r in rows if r["gate"]["decision"] != INELIGIBLE]
    rb = rank({r["opp"].id: r["score_b"]["score"] for r in cand})
    ra = rank({r["opp"].id: r["score_a"] for r in cand})
    for r in rows:
        i = r["opp"].id
        r["rank_b"] = rb.index(i) + 1 if i in rb else None
        r["rank_a"] = ra.index(i) + 1 if i in ra else None
    sens = sensitivity({r["opp"].id: r["crit"] for r in cand}, cfg["weights"])
    k = min(5, len(cand))
    top_overlap = len(set(ra[:k]) & set(rb[:k])) / k if k else None
    return {"rows": rows, "rank_a": ra, "rank_b": rb, "sensitivity": sens,
            "a_vs_b": {"kendall_tau": kendall_tau(ra, rb), "top_k": k, "top_k_overlap": top_overlap}}


def metrics(store: Store, ev: dict, reviews: dict, history: dict, now: datetime) -> dict:
    rows = ev["rows"]
    runs = store.last_runs()
    total_src = len(SOURCES)
    ok_src = sum(1 for r in runs.values() if r["status"] == "ok")
    ages = []
    for r in rows:
        try:
            ages.append((now - datetime.fromisoformat(r["opp"].last_seen.replace("Z", "+00:00"))).total_seconds() / 3600)
        except ValueError:
            pass
    labelled = [(r["gate"]["decision"], reviews[r["opp"].id].get("label")) for r in rows if r["opp"].id in reviews and reviews[r["opp"].id].get("label")]
    correct = sum(1 for d, l in labelled if d == l)
    est_act = [(p["estimated_hours"], p["actual_hours"]) for p in history.get("projects", []) if p.get("estimated_hours") and p.get("actual_hours")]
    seen = max(store.raw_records_seen, 1)
    return {
        "valid_opportunities_found": sum(1 for r in rows if r["gate"]["decision"] != INELIGIBLE),
        "total_records": len(rows),
        "decisions": {d: sum(1 for r in rows if r["gate"]["decision"] == d) for d in (ELIGIBLE, NEEDS_REVIEW, INELIGIBLE)},
        "source_coverage": {"sources_registered": total_src, "sources_ok_last_run": ok_src,
                            "supported": sum(1 for s in SOURCES.values() if s.status == "supported")},
        "duplicate_rate": round(store.duplicates_merged / seen, 4) if store.raw_records_seen else None,
        "duplicate_rate_note": "duplicates merged in THIS process run / records seen in this run",
        "evidence_freshness_hours": {"median": round(statistics.median(ages), 2) if ages else None, "max": round(max(ages), 2) if ages else None},
        "eligibility_precision": (round(correct / len(labelled), 3) if labelled else None),
        "eligibility_precision_n": len(labelled),
        "eligibility_precision_note": "agreement with human labels in data/bounty_reviews.json; n/a until labels exist. Small n: no significance claimed.",
        "estimated_vs_actual_hours": est_act or None,
        "human_review_minutes_total": sum(r.get("minutes_spent", 0) for r in reviews.values()) or None,
        "ranking_stability_top3": ev["sensitivity"].get("stable_top"),
        "ranking_a_vs_b": ev["a_vs_b"],
    }
