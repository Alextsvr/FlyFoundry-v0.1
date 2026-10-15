"""Orchestration: discover -> detail -> gate -> estimate -> score -> metrics. `evaluate` is a pure function of store content,
config, reviews and `now`, so rankings are reproducible.

Run status semantics (see docs/BOUNTY_FACTORY.md): success (exit 0) | partial (3) | source_unavailable (4) | no_data (5) | internal error (6)."""
from __future__ import annotations

import json
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import detail as detail_mod
from .feasibility import estimate
from .gate import evaluate as gate_eval, deadline_status, ELIGIBLE, INELIGIBLE, NEEDS_REVIEW
from .http import Fetcher, RobotsDenied, BudgetExceeded, HostBlocked
from .model import canonical_url
from .scoring import criteria, score_b, baseline_a, rank, sensitivity, kendall_tau, prize_usd, review_priority, effort_scenarios, A_DEFINITION
from .sources import SOURCES
from .sources import devpost
from .sources.manual import load_manual
from .store import Store

EXIT = {"success": 0, "partial": 3, "source_unavailable": 4, "no_data": 5, "internal_error": 6}


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_cfg(path="data/bounty_config.json") -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def discover(store: Store, cfg: dict, fetcher: Fetcher, now: datetime, manual_path="data/bounty_manual_intake.json", log=print) -> dict:
    summary, now_s = {}, iso(now)
    # ---- devpost (live)
    run = store.start_run("devpost", now_s)
    seen_ids, seen_urls = set(), set()
    n = dup_items = invalid = pages = 0
    status, err, complete, last_http, total = "ok", "", False, None, None
    try:
        for url, http, body, data, is_last in devpost.fetch_all(fetcher, cfg["max_list_pages"]):
            last_http, pages = http, pages + 1
            obs = store.add_observation(run, "devpost", url, url, now_s, body, kind="list", http_status=http, parser_version=devpost.PARSER_VERSION)
            if http != 200:
                status, err = "failed", f"HTTP {http} at {url}"
                break
            try:
                items, meta = devpost.validate_page(data)
            except devpost.SchemaError as e:
                status, err = "schema_error", f"{e} (HTTP 200 at {url}); not treated as an empty listing"
                break
            total = meta.get("total_count", total)
            new_this_page = 0
            for item in items:
                o = devpost.to_opportunity(item, url)
                if o is None:
                    invalid += 1
                    continue
                cu = canonical_url(o.url)
                if cu in seen_urls:
                    dup_items += 1
                    continue
                seen_urls.add(cu)
                oid, _ = store.upsert(o, now_s, obs)
                seen_ids.add(oid)
                n += 1
                new_this_page += 1
            if items and new_this_page == 0 and pages > 1:
                status, err = "partial", "pagination repeated the same records; stopping"
                break
            complete = is_last
        if status == "ok" and not complete:
            status, err = "partial", "listing incomplete (page cap reached)"
        if status == "ok" and total is not None and len(seen_urls) < total:
            status, complete = "partial", False
            err = f"listing returned {len(seen_urls)} distinct records but meta.total_count={total}"
        if status == "ok" and pages == 0:
            status, err = "failed", "no page was fetched"
    except RobotsDenied as e:
        status, err = "blocked_by_robots", str(e)
    except HostBlocked as e:
        status, err = "host_blocked", str(e)
    except BudgetExceeded as e:
        status, err = "partial", str(e)
    except Exception as e:  # noqa: BLE001 - one source failing must not stop the others
        status, err = "failed", f"{type(e).__name__}: {e}"
    skipped = ""
    if status == "ok" and complete:
        _, skipped = store.mark_unlisted("devpost", seen_ids, now_s)
        if skipped:
            status, err = "partial", skipped
    store.finish_run(run, now_s, status, last_http, n, complete and status == "ok", fetcher.requests, err)
    summary["devpost"] = {"status": status, "records": n, "complete": complete and status == "ok", "error": err, "pages": pages,
                          "total_count_claimed": total, "duplicate_items_in_listing": dup_items, "invalid_items": invalid}
    log(f"devpost: {status} records={n} complete={summary['devpost']['complete']} {err}")
    # ---- manual intake
    run = store.start_run("manual", now_s)
    entries = load_manual(manual_path)
    for o in entries:
        store.upsert(o, now_s)
    store.finish_run(run, now_s, "ok", None, len(entries), True, 0, "")
    summary["manual"] = {"status": "ok", "records": len(entries), "complete": True, "error": ""}
    for name, info in SOURCES.items():          # registry entries that are not implemented are recorded, not faked
        if info.status in ("unsupported", "manual_review"):
            r = store.start_run(name, now_s)
            store.finish_run(r, now_s, info.status, None, 0, False, 0, info.reason[:300])
            summary[name] = {"status": info.status, "records": 0, "complete": False, "error": info.reason}
    return summary


def enrich_details(store: Store, cfg: dict, fetcher: Fetcher, now: datetime, log=print) -> dict:
    now_s = iso(now)
    run = store.start_run("devpost_detail", now_s)
    cands = []
    for o in store.all():
        if o.source != "devpost" or o.status != "listed" or deadline_status(o, now) == "expired":
            continue
        if any(detail_mod.due(o.detail.get(p), now) for p in detail_mod.PAGES):
            cands.append((-(prize_usd(o, cfg) or 0), str(o.fact("deadline_date").value or "9999"), o.id))
    cands.sort()
    tot = {"events_attempted": 0, "pages_ok": 0, "pages_failed": [], "blocked": False}
    for _, _, oid in cands[: cfg["detail_limit_per_run"]]:
        o = store.get(oid)
        r = detail_mod.fetch_detail(store, o, fetcher, run, now, cfg.get("participant"))
        if r["attempted"]:
            tot["events_attempted"] += 1
        tot["pages_ok"] += r["ok"]
        tot["pages_failed"] += r["failed"]
        tot["blocked"] = tot["blocked"] or r["blocked"]
        if r["blocked"] and any(h for h in fetcher.denied_hosts):
            tot["pages_failed"].append("host answered 401/403 (or robots denied): remaining pages skipped this run, not bypassed")
            break
    status = "ok" if tot["pages_ok"] and not tot["blocked"] else ("blocked" if tot["blocked"] else ("nothing_due" if not cands else "failed"))
    store.finish_run(run, now_s, status, None, tot["pages_ok"], False, fetcher.requests, "; ".join(tot["pages_failed"][:3]))
    tot["status"] = status
    tot["pages_failed"] = tot["pages_failed"][:20]
    log(f"detail pass: {status}; events attempted {tot['events_attempted']}, pages ok {tot['pages_ok']}, failures {len(tot['pages_failed'])}")
    return tot


def run_status(summary: dict, store: Store, cfg: dict) -> dict:
    """Primary-source semantics: success only if every primary source finished ok AND complete."""
    prim = cfg.get("primary_sources", ["devpost"])
    bad = {s: summary.get(s, {}).get("status", "missing") for s in prim}
    n_opps = len(store.all())
    if any(v in ("failed", "blocked_by_robots", "host_blocked", "schema_error", "missing") for v in bad.values()):
        state = "source_unavailable" if n_opps else "no_data"
        msg = f"primary source(s) unavailable: {bad}; " + ("report built from OLDER stored data" if n_opps else "no data at all")
    elif any(v == "partial" for v in bad.values()):
        state, msg = "partial", f"primary source(s) returned a partial result: {bad}"
    elif n_opps == 0:
        state, msg = "no_data", "primary source ok but the store is empty"
    else:
        state, msg = "success", "all primary sources ok and complete"
    last_ok = {s: store.last_ok_run(s) for s in prim}
    return {"run_status": state, "exit_code": EXIT[state], "message": msg, "primary_sources": bad, "last_complete_success": last_ok}


def evaluate(store: Store, cfg: dict, reviews: dict, now: datetime) -> dict:
    rows = []
    for o in store.all():
        g = gate_eval(o, cfg, now, reviews)
        est = estimate(o, cfg)
        crit = criteria(o, est, cfg, now)
        sb = score_b(crit, cfg["weights"])
        prov = {}
        for f in o.facts.values():
            if f.known():
                key = f.basis + ("/weak" if f.strength == "weak" else "")
                prov[key] = prov.get(key, 0) + 1
        rows.append({"opp": o, "gate": g, "est": est, "crit": crit, "score_b": sb, "score_a": baseline_a(o, est, cfg), "provenance": prov,
                     "review_priority": review_priority(o, est, g, cfg, now),
                     "development_priority": sb["score"] if g["decision"] == ELIGIBLE else None})
    cand = [r for r in rows if r["gate"]["decision"] != INELIGIBLE]
    rb = rank({r["opp"].id: r["score_b"]["score"] for r in cand})
    ra = rank({r["opp"].id: r["score_a"] for r in cand})
    rr = rank({r["opp"].id: r["review_priority"]["value"] for r in cand})
    for r in rows:
        i = r["opp"].id
        r["rank_b"] = rb.index(i) + 1 if i in rb else None
        r["rank_a"] = ra.index(i) + 1 if i in ra else None
        r["rank_review"] = rr.index(i) + 1 if i in rr else None
    sens = sensitivity({r["opp"].id: r["crit"] for r in cand}, cfg["weights"])
    scen = effort_scenarios({r["opp"].id: (r["opp"], r["est"]) for r in cand}, cfg, now)
    k = min(5, len(cand))
    return {"rows": rows, "rank_a": ra, "rank_b": rb, "rank_review": rr, "sensitivity": sens, "effort_scenarios": scen, "a_definition": A_DEFINITION,
            "a_vs_b": {"kendall_tau": kendall_tau(ra, rb), "top_k": k, "top_k_overlap": (len(set(ra[:k]) & set(rb[:k])) / k) if k else None}}


def metrics(store: Store, ev: dict, reviews: dict, history: dict, now: datetime) -> dict:
    rows = ev["rows"]
    runs = store.last_runs()
    ok_src = sum(1 for r in runs.values() if r["status"] == "ok")
    ages = []
    for r in rows:
        for n in ("prize_amount", "deadline_date"):
            f = r["opp"].fact(n)
            try:
                ages.append((now - datetime.fromisoformat(f.observed_at.replace("Z", "+00:00"))).total_seconds() / 3600)
            except (ValueError, AttributeError):
                pass
    labelled = [(r["gate"]["decision"], reviews[r["opp"].id].get("label")) for r in rows if r["opp"].id in reviews and reviews[r["opp"].id].get("label")]
    est_act = [(p["estimated_hours"], p["actual_hours"]) for p in history.get("projects", []) if p.get("estimated_hours") and p.get("actual_hours")]
    dec = {d: sum(1 for r in rows if r["gate"]["decision"] == d) for d in (ELIGIBLE, NEEDS_REVIEW, INELIGIBLE)}
    return {
        "records_total": len(rows),
        "decisions": dec,
        "eligible_confirmed": dec[ELIGIBLE],
        "needs_review_candidates": dec[NEEDS_REVIEW],
        "rejected": dec[INELIGIBLE],
        "candidates_note": "NEEDS_REVIEW candidates are NOT confirmed suitable opportunities; only eligible_confirmed counts as confirmed",
        "source_coverage": {"sources_registered": len(SOURCES), "sources_ok_last_run": ok_src, "supported": sum(1 for s in SOURCES.values() if s.status == "supported")},
        "duplicate_rate": round(store.duplicates_merged / max(store.raw_records_seen, 1), 4) if store.raw_records_seen else None,
        "duplicate_rate_note": "merged duplicates in THIS process run / records seen in this run",
        "possible_duplicates_flagged": sum(1 for r in rows if r["opp"].possible_duplicates),
        "evidence_freshness_hours": {"basis": "age of per-fact observation (prize, deadline)", "median": round(statistics.median(ages), 2) if ages else None, "max": round(max(ages), 2) if ages else None},
        "conditions_confirmed_distribution": {str(k): sum(1 for r in rows if r["gate"]["conditions_confirmed"] == k) for k in range(0, 11)},
        "eligibility_precision": (round(sum(1 for d, l in labelled if d == l) / len(labelled), 3) if labelled else None),
        "eligibility_precision_n": len(labelled),
        "eligibility_precision_note": "agreement with human labels in data/bounty_reviews.json; n/a until labels exist. Small n: no significance claimed.",
        "estimated_vs_actual_hours": est_act or None,
        "human_review_minutes_total": sum(r.get("minutes_spent", 0) for r in reviews.values()) or None,
        "ranking_stability_top3_weights_only": ev["sensitivity"].get("stable_top"),
        "effort_scenarios_top_set_stable": ev["effort_scenarios"].get("top_set_stable"),
        "ranking_a_vs_b": ev["a_vs_b"],
    }
