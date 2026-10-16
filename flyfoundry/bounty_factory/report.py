"""Daily report: self-contained HTML + JSON + CSV. Unverified opportunities are always labelled UNVERIFIED."""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timedelta
from html import escape as e

from .gate import deadline_status
from .scoring import prize_usd
from .sources import source_status_table

CSS = """body{font:15px/1.45 system-ui,sans-serif;margin:0 auto;max-width:1100px;padding:16px;color:#1b1f23;background:#fff}
h1{font-size:22px}h2{font-size:17px;margin-top:28px;border-bottom:1px solid #ddd;padding-bottom:4px}
table{border-collapse:collapse;width:100%;font-size:13px}td,th{border:1px solid #ddd;padding:4px 6px;text-align:left;vertical-align:top}th{background:#f4f5f7}
.card{border:1px solid #ccd;border-radius:6px;padding:10px 14px;margin:8px 0}.b{display:inline-block;padding:1px 7px;border-radius:9px;font-size:12px;color:#fff}
.ELIGIBLE{background:#1a7f37}.NEEDS_REVIEW{background:#9a6700}.INELIGIBLE{background:#a40e26}.unv{background:#6e7781}.note{color:#57606a;font-size:13px}
@media (prefers-color-scheme:dark){body{background:#0d1117;color:#e6edf3}th{background:#161b22}td,th,.card,h2{border-color:#30363d}.note{color:#9da7b3}a{color:#58a6ff}}"""


def money(o, cfg):
    a, c = o.fact("prize_amount"), o.fact("prize_currency")
    if not a.known():
        return "unknown"
    return f"{a.value:,.0f} {c.value or '(currency unknown)'}"


def badge(row):
    d, g = row["gate"]["decision"], row["gate"]
    v = "VERIFIED" if g["verified"] else f"UNVERIFIED: {g['conditions_confirmed']}/{g['conditions_total']} required conditions confirmed"
    return f'<span class="b {d}">{d}</span> <span class="b unv">{e(v)}</span>'


def summary_json(ev, cfg, now) -> list:
    out = []
    for r in ev["rows"]:
        o = r["opp"]
        out.append({"id": o.id, "title": o.title, "url": o.url, "source": o.source, "organizer": o.organizer, "status": o.status,
                    "first_seen": o.first_seen, "last_seen": o.last_seen, "decision": r["gate"]["decision"], "verified": r["gate"]["verified"],
                    "reasons": r["gate"]["reasons"], "prize_amount": o.fact("prize_amount").value, "prize_currency": o.fact("prize_currency").value,
                    "prize_usd_planning": prize_usd(o, cfg), "deadline_date": o.fact("deadline_date").value, "deadline_status": deadline_status(o, now),
                    "est_class": r["est"]["class_range"], "est_hours": r["est"]["hours_mid"], "est_hours_low": r["est"]["hours_low"], "est_hours_high": r["est"]["hours_high"],
                    "est_confidence": r["est"]["confidence"], "requirements_read": r["est"]["requirements_read"],
                    "score_b": r["score_b"], "criteria_fill": r["score_b"]["criteria_fill"], "score_a_prize_pool_per_hour": r["score_a"], "rank_a": r["rank_a"], "rank_b": r["rank_b"],
                    "review_priority": r["review_priority"], "rank_review": r["rank_review"], "development_priority": r["development_priority"],
                    "conditions_confirmed": r["gate"]["conditions_confirmed"], "conditions_total": r["gate"]["conditions_total"], "review_status": r["gate"]["review_status"],
                    "conditions": r["gate"]["conditions"], "provenance": r["provenance"], "possible_duplicates": o.possible_duplicates,
                    "prize_attainable_to_participant": None,
                    "facts": {k: v.to_dict() for k, v in o.facts.items() if k != "description_text"}, "aliases": o.aliases})
    return out


def to_csv(summary: list) -> str:
    buf = io.StringIO()
    cols = ["id", "title", "url", "source", "decision", "verified", "conditions_confirmed", "conditions_total", "prize_amount", "prize_currency", "prize_usd_planning", "deadline_date",
            "deadline_status", "est_class", "est_hours_low", "est_hours", "est_hours_high", "est_confidence", "criteria_fill", "rank_review", "rank_a", "rank_b", "first_seen", "last_seen"]
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for r in summary:
        w.writerow({**r, "reasons": ""})
    return buf.getvalue()


def _tbl(headers, rows):
    h = "".join(f"<th>{e(x)}</th>" for x in headers)
    b = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows) or f'<tr><td colspan="{len(headers)}">none</td></tr>'
    return f"<table><tr>{h}</tr>{b}</table>"


def link(o):
    return f'<a href="{e(o.url)}" rel="noopener nofollow">{e(o.title)}</a>'


def render_html(ev, cfg, store, metrics, history, now, runs, changes, first_run, status=None) -> str:
    rows = ev["rows"]
    by_id = {r["opp"].id: r for r in rows}
    cand = sorted([r for r in rows if r["gate"]["decision"] != "INELIGIBLE"], key=lambda r: (r["rank_review"] or 9999, r["opp"].id))
    elig = sorted([r for r in rows if r["gate"]["decision"] == "ELIGIBLE"], key=lambda r: (r["rank_b"] or 9999))
    top = [r for r in cand if r["gate"]["decision"] == "NEEDS_REVIEW"][:3]
    p = []
    st = status or {"run_status": "unknown", "message": "status not provided", "last_complete_success": {}}
    cls_ = "INELIGIBLE" if st["run_status"] in ("source_unavailable", "no_data") else ("NEEDS_REVIEW" if st["run_status"] == "partial" else "ELIGIBLE")
    p.append(f"<h1>Bounty Factory daily report</h1><div class='card'><span class='b {cls_}'>RUN: {e(st['run_status'].upper())}</span> {e(st['message'])}<br>"
             f"<span class='note'>Last complete successful listing: {e(json.dumps(st.get('last_complete_success', {})))}. "
             f"{'DATA BELOW MAY BE STALE.' if st['run_status'] in ('source_unavailable', 'no_data') else ''}</span></div>")
    p.append(f"<p class='note'>Generated {e(now.strftime('%Y-%m-%d %H:%M UTC'))}. Source claims are not verified facts. 'Review priority' says where to spend review time first; "
             f"it is not a recommendation to build and not a win probability. Eligibility needs {len(next(iter(rows))['gate']['conditions']) if rows else 10} confirmed conditions.</p>")
    p.append("<h2>Check these first (top 3 by review priority; all UNVERIFIED)</h2>")
    for r in top or []:
        o, est = r["opp"], r["est"]
        todo = [x["code"] for x in r["gate"]["reasons"] if x["level"] == "review"][:6]
        p.append(f"<div class='card'><b>{link(o)}</b> {badge(r)}<br>Declared pool: {e(money(o, cfg))} | Deadline: {e(str(o.fact('deadline_date').value or 'unknown'))} "
                 f"({e(deadline_status(o, now))}) | Effort: {e(est['class_range'])}, {est['hours_low']}-{est['hours_high']} h (confidence {e(est['confidence'])}, requirements read: {e(est['requirements_read'])}) | "
                 f"review priority {r['review_priority']['value']} | criteria filled {r['score_b']['criteria_fill']:.0%}<br><span class='note'>To resolve: {e(', '.join(todo) or 'nothing flagged')}</span></div>")
    if not top:
        p.append("<p>No candidates awaiting review.</p>")
    p.append("<h2>Ready to build (ELIGIBLE with a complete, current review)</h2>" + (_tbl(["Opportunity", "Dev priority (score B)", "Prize", "Deadline", "Effort"], [[link(r["opp"]), f"{r['development_priority']:.3f}", e(money(r["opp"], cfg)), e(str(r["opp"].fact("deadline_date").value)), e(r["est"]["class_range"])] for r in elig]) if elig else "<p><b>None.</b> No opportunity has all required conditions confirmed.</p>"))
    d = metrics["decisions"]
    p.append(f"<h2>Summary</h2><p>{metrics['records_total']} records: <b>{d['ELIGIBLE']} confirmed eligible</b>, {d['NEEDS_REVIEW']} candidates needing review (NOT confirmed), {d['INELIGIBLE']} rejected. "
             f"Possible duplicates flagged: {metrics['possible_duplicates_flagged']}. First run: {'yes' if first_run else 'no'}.</p>")
    new = [r for r in rows if first_run or r["opp"].first_seen >= (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")]
    p.append("<h2>Newly discovered (last 24 h)</h2>" + _tbl(["Opportunity", "Source", "Decision", "Prize"], [[link(r["opp"]), e(r["opp"].source), badge(r), e(money(r["opp"], cfg))] for r in new[:60]]))
    p.append("<h2>Candidates needing review (unconfirmed)</h2>" + _tbl(["Review rank", "Opportunity", "Confirmed", "Prize", "Deadline", "Open items"],
             [[str(r["rank_review"]), link(r["opp"]), f"{r['gate']['conditions_confirmed']}/{r['gate']['conditions_total']}", e(money(r["opp"], cfg)), e(str(r["opp"].fact("deadline_date").value)), e("; ".join(x["code"] for x in r["gate"]["reasons"] if x["level"] == "review")[:160])] for r in cand if r["gate"]["decision"] == "NEEDS_REVIEW"][:80]))
    p.append("<h2>Rejected, with reasons</h2>" + _tbl(["Opportunity", "Reasons"], [[link(r["opp"]), e("; ".join(f"{x['code']}: {x['detail'][:120]}" for x in r["gate"]["reasons"] if x["level"] == "hard"))] for r in rows if r["gate"]["decision"] == "INELIGIBLE"][:80]))
    sc = ev["effort_scenarios"]["per_opportunity"]
    p.append("<h2>Ranking: A vs B (secondary information)</h2>" + _tbl(["Rank B", "Rank A", "Opportunity", "Score B", "Criteria filled", "Rank range (effort low-high)", "Top-3 freq (weights)"],
             [[str(r["rank_b"]), str(r["rank_a"] or "n/a"), link(r["opp"]), f"{r['score_b']['score']:.3f}", f"{r['score_b']['criteria_fill']:.0%}",
               f"{sc.get(r['opp'].id, {}).get('min_rank', '')}-{sc.get(r['opp'].id, {}).get('max_rank', '')}", str(ev["sensitivity"]["per_opportunity"].get(r["opp"].id, {}).get("top_k_freq", ""))] for r in sorted(cand, key=lambda r: r["rank_b"] or 9999)[:15]])
             + f"<p class='note'>A = {e(ev['a_definition'])}. B = weighted criteria; unknown criteria are excluded. 'Criteria filled' is the share of criteria weight that has a value (many are keyword heuristics): it is NOT evidence completeness. "
               f"Sensitivity covers weights only ({ev['sensitivity']['n']} perturbations) and effort low/mid/high; it does not validate ranking quality. Unknown eligibility conditions are not scenario-tested. "
               f"Kendall tau A vs B: {ev['a_vs_b']['kendall_tau']}; top-{ev['a_vs_b']['top_k']} overlap: {ev['a_vs_b']['top_k_overlap']}; top-3 stable across effort scenarios: {ev['effort_scenarios'].get('top_set_stable')}.</p>")
    p.append("<h2>Deadlines, prize pools, estimated work</h2>" + _tbl(["Opportunity", "Deadline", "Status", "Declared pool", "USD planning", "Effort range", "Hours (low-high)", "Confidence"],
             [[link(r["opp"]), e(str(r["opp"].fact("deadline_date").value)), e(deadline_status(r["opp"], now)), e(money(r["opp"], cfg)), e(f"{prize_usd(r['opp'], cfg):,.0f}" if prize_usd(r["opp"], cfg) is not None else "unknown"), e(r["est"]["class_range"]), f"{r['est']['hours_low']}-{r['est']['hours_high']}", e(r["est"]["confidence"])]
              for r in sorted(cand, key=lambda r: str(r["opp"].fact("deadline_date").value))[:40]])
             + "<p class='note'>Pools are declared totals; what a given participant can actually win (tracks, regional or sponsor-only prizes) is unknown.</p>")
    p.append("<h2>Source accessibility and evidence freshness</h2>" + _tbl(["Source", "Registry status", "Last run", "Run status", "Records", "Detail"],
             [[e(s["name"]), e(s["status"]), e((runs.get(s["name"]) or {}).get("started_at", "never")), e((runs.get(s["name"]) or {}).get("status", "-")), str((runs.get(s["name"]) or {}).get("n_records", "")), e(((runs.get(s["name"]) or {}).get("error") or s["reason"] or "")[:160])] for s in source_status_table()])
             + f"<p class='note'>Per-fact observation age (hours; prize and deadline): median {metrics['evidence_freshness_hours']['median']}, max {metrics['evidence_freshness_hours']['max']}.</p>")
    p.append("<h2>Historical changes</h2>" + _tbl(["When", "Opportunity", "Field", "Old", "New"], [[e(c["at"]), e(by_id[c["opp_id"]]["opp"].title if c["opp_id"] in by_id else c["opp_id"]), e(c["field"]), e(str(c["old"])[:60]), e(str(c["new"])[:60])] for c in changes[-40:]]))
    projs = history.get("projects", [])
    p.append("<h2>Selected projects, submissions, prizes</h2>" + _tbl(["Project", "Competitions", "Status", "Outcome", "Prize received"],
             [[e(x["name"]), e(", ".join(x.get("competitions", []))), e(x.get("status", "")), e(x.get("outcome", "unknown")), e(str(x.get("prize_received_eur_or_usd", "none confirmed")))] for x in projs]))
    p.append(f"<h2>Metrics</h2><pre>{e(json.dumps({k: v for k, v in metrics.items() if k != 'ranking_a_vs_b'}, indent=1, default=str))}</pre>")
    return f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Bounty Factory report</title><style>{CSS}</style></head><body>{''.join(p)}</body></html>"
