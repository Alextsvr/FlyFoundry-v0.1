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
    d = row["gate"]["decision"]
    v = "VERIFIED" if row["gate"]["verified"] else "UNVERIFIED (list data only)"
    return f'<span class="b {d}">{d}</span> <span class="b unv">{e(v)}</span>'


def summary_json(ev, cfg, now) -> list:
    out = []
    for r in ev["rows"]:
        o = r["opp"]
        out.append({"id": o.id, "title": o.title, "url": o.url, "source": o.source, "organizer": o.organizer, "status": o.status,
                    "first_seen": o.first_seen, "last_seen": o.last_seen, "decision": r["gate"]["decision"], "verified": r["gate"]["verified"],
                    "reasons": r["gate"]["reasons"], "prize_amount": o.fact("prize_amount").value, "prize_currency": o.fact("prize_currency").value,
                    "prize_usd_planning": prize_usd(o, cfg), "deadline_date": o.fact("deadline_date").value, "deadline_status": deadline_status(o, now),
                    "est_class": r["est"]["class"], "est_hours": r["est"]["total_hours"], "est_confidence": r["est"]["confidence"],
                    "score_b": r["score_b"], "score_a": r["score_a"], "rank_a": r["rank_a"], "rank_b": r["rank_b"],
                    "facts": {k: v.to_dict() for k, v in o.facts.items() if k != "description_text"}, "aliases": o.aliases})
    return out


def to_csv(summary: list) -> str:
    buf = io.StringIO()
    cols = ["id", "title", "url", "source", "decision", "verified", "prize_amount", "prize_currency", "prize_usd_planning", "deadline_date",
            "deadline_status", "est_class", "est_hours", "est_confidence", "rank_a", "rank_b", "first_seen", "last_seen"]
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


def render_html(ev, cfg, store, metrics, history, now, runs, changes, first_run) -> str:
    rows = ev["rows"]
    by_id = {r["opp"].id: r for r in rows}
    cand = sorted([r for r in rows if r["gate"]["decision"] != "INELIGIBLE"], key=lambda r: (r["rank_b"] or 9999, r["opp"].id))
    top = sorted(cand, key=lambda r: (r["gate"]["decision"] != "ELIGIBLE", r["rank_b"] or 9999))[:3]
    p = []
    p.append(f"<h1>Bounty Factory daily report</h1><p class='note'>Generated {e(now.strftime('%Y-%m-%d %H:%M UTC'))}. Source claims are not verified facts: "
             f"anything marked UNVERIFIED must be checked by a human against the official rules before any work or submission. "
             f"Scores rank usefulness for planning; they are not win probabilities.</p>")
    p.append("<h2>Top 3 right now</h2>")
    if not top:
        p.append("<p>No non-rejected opportunities.</p>")
    for r in top:
        o, est = r["opp"], r["est"]
        todo = [x["detail"] for x in r["gate"]["reasons"] if x["level"] == "review"][:3]
        p.append(f"<div class='card'><b>{link(o)}</b> {badge(r)}<br>Prize: {e(money(o, cfg))} | Deadline: {e(str(o.fact('deadline_date').value or 'unknown'))} "
                 f"({e(deadline_status(o, now))}) | Work: {e(est['class'])} ~{est['total_hours']} h (confidence {e(est['confidence'])}) | score B {r['score_b']['score']:.3f} "
                 f"(evidence {r['score_b']['coverage']:.0%})<br><span class='note'>Next: {e('; '.join(todo) or 'ready for brief')}</span></div>")
    d = metrics["decisions"]
    p.append(f"<h2>Summary</h2><p>{metrics['total_records']} records: {d['ELIGIBLE']} eligible, {d['NEEDS_REVIEW']} need review, {d['INELIGIBLE']} rejected. "
             f"First run: {'yes (everything is new)' if first_run else 'no'}.</p>")
    new = [r for r in rows if first_run or r["opp"].first_seen >= (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")]
    p.append("<h2>Newly discovered (last 24 h)</h2>" + _tbl(["Opportunity", "Source", "Decision", "Prize"], [[link(r["opp"]), e(r["opp"].source), badge(r), e(money(r["opp"], cfg))] for r in new[:60]]))
    p.append("<h2>Eligible</h2>" + _tbl(["Opportunity", "Prize", "Deadline", "Work"], [[link(r["opp"]), e(money(r["opp"], cfg)), e(str(r["opp"].fact("deadline_date").value)), e(r["est"]["class"])] for r in rows if r["gate"]["decision"] == "ELIGIBLE"]))
    p.append("<h2>Needs review (nothing here is confirmed)</h2>" + _tbl(["Opportunity", "Rank B", "Prize", "Deadline", "What to verify"],
             [[link(r["opp"]), str(r["rank_b"]), e(money(r["opp"], cfg)), e(str(r["opp"].fact("deadline_date").value)), e("; ".join(x["code"] for x in r["gate"]["reasons"] if x["level"] == "review"))] for r in cand if r["gate"]["decision"] == "NEEDS_REVIEW"][:80]))
    p.append("<h2>Rejected, with reasons</h2>" + _tbl(["Opportunity", "Reasons"], [[link(r["opp"]), e("; ".join(f"{x['code']}: {x['detail'][:120]}" for x in r["gate"]["reasons"] if x["level"] == "hard"))] for r in rows if r["gate"]["decision"] == "INELIGIBLE"][:80]))
    p.append("<h2>Ranking: baseline A vs experimental B</h2>" + _tbl(["Rank B", "Rank A", "Opportunity", "Score B", "Evidence", "Top-3 stability"],
             [[str(r["rank_b"]), str(r["rank_a"] or "n/a"), link(r["opp"]), f"{r['score_b']['score']:.3f}", f"{r['score_b']['coverage']:.0%}", str(ev["sensitivity"]["per_opportunity"].get(r["opp"].id, {}).get("top_k_freq", ""))] for r in cand[:15]])
             + f"<p class='note'>A = prize per estimated hour (unknown prize ranks last). B = weighted criteria, unknown criteria excluded. Kendall tau A vs B: {ev['a_vs_b']['kendall_tau']}; top-{ev['a_vs_b']['top_k']} overlap: {ev['a_vs_b']['top_k_overlap']}. "
               f"Stability = share of {ev['sensitivity']['n']} weight perturbations (+/-{int(ev['sensitivity'].get('spread', .5) * 100)}%) in which the item stays in the top 3.</p>")
    p.append("<h2>Deadlines, prize pools, estimated work</h2>" + _tbl(["Opportunity", "Deadline", "Deadline status", "Prize", "USD planning", "Class", "Hours", "Confidence"],
             [[link(r["opp"]), e(str(r["opp"].fact("deadline_date").value)), e(deadline_status(r["opp"], now)), e(money(r["opp"], cfg)), e(f"{prize_usd(r['opp'], cfg):,.0f}" if prize_usd(r["opp"], cfg) is not None else "unknown"), e(r["est"]["class"]), str(r["est"]["total_hours"]), e(r["est"]["confidence"])]
              for r in sorted(cand, key=lambda r: str(r["opp"].fact("deadline_date").value))[:40]]))
    p.append("<h2>Source accessibility and evidence freshness</h2>" + _tbl(["Source", "Registry status", "Last run", "Run status", "Records", "Detail"],
             [[e(s["name"]), e(s["status"]), e((runs.get(s["name"]) or {}).get("started_at", "never")), e((runs.get(s["name"]) or {}).get("status", "-")), str((runs.get(s["name"]) or {}).get("n_records", "")), e((s["reason"] or "")[:160])] for s in source_status_table()])
             + f"<p class='note'>Evidence age (hours since last seen): median {metrics['evidence_freshness_hours']['median']}, max {metrics['evidence_freshness_hours']['max']}.</p>")
    p.append("<h2>Historical changes</h2>" + _tbl(["When", "Opportunity", "Field", "Old", "New"], [[e(c["at"]), e(by_id[c["opp_id"]]["opp"].title if c["opp_id"] in by_id else c["opp_id"]), e(c["field"]), e(str(c["old"])[:60]), e(str(c["new"])[:60])] for c in changes[-40:]]))
    projs = history.get("projects", [])
    p.append("<h2>Selected projects, submissions, prizes</h2>" + _tbl(["Project", "Competitions", "Status", "Outcome", "Prize received"],
             [[e(x["name"]), e(", ".join(x.get("competitions", []))), e(x.get("status", "")), e(x.get("outcome", "unknown")), e(str(x.get("prize_received_eur_or_usd", "none confirmed")))] for x in projs]))
    p.append(f"<h2>Metrics</h2><pre>{e(json.dumps({k: v for k, v in metrics.items() if k != 'ranking_a_vs_b'}, indent=1, default=str))}</pre>")
    return f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Bounty Factory report</title><style>{CSS}</style></head><body>{''.join(p)}</body></html>"
