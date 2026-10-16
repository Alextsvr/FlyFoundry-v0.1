"""Compare the ORIGINAL run-1 output with a re-evaluation of the SAME stored records by the hardened code (no refetching).
Usage: python scripts/compare_reeval.py <old_opportunities.json> <new_opportunities.json> <out_dir>"""
import csv, json, sys
from collections import Counter
from pathlib import Path

old = {r["id"]: r for r in json.load(open(sys.argv[1], encoding="utf-8"))}
new = {r["id"]: r for r in json.load(open(sys.argv[2], encoding="utf-8"))}
out = Path(sys.argv[3]); out.mkdir(parents=True, exist_ok=True)
codes = lambda r: sorted({x["code"] if isinstance(x, dict) else str(x) for x in r.get("reasons", [])})
rows = []
for i, n in sorted(new.items(), key=lambda kv: (kv[1].get("rank_review") or 999, kv[0])):
    o = old.get(i, {})
    rows.append({"id": i, "title": n["title"][:70], "old_decision": o.get("decision"), "new_decision": n["decision"],
                 "old_rank_b": o.get("rank_b"), "new_rank_b": n.get("rank_b"), "new_rank_review": n.get("rank_review"),
                 "old_est": f"{o.get('est_hours')} h ({o.get('est_class')}, {o.get('est_confidence')})",
                 "new_est": f"{n.get('est_hours_low')}-{n.get('est_hours_high')} h (mid {n.get('est_hours')}, {n.get('est_confidence')}, read={n.get('requirements_read')})",
                 "old_criteria_coverage": (o.get("score_b") or {}).get("coverage") if isinstance(o.get("score_b"), dict) else None,
                 "new_criteria_fill": n.get("criteria_fill"), "conditions_confirmed": f"{n.get('conditions_confirmed')}/{n.get('conditions_total')}",
                 "reasons_removed": ";".join(sorted(set(codes(o)) - set(codes(n)))), "reasons_added": ";".join(sorted(set(codes(n)) - set(codes(o))))})
with open(out / "comparison.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
trans = Counter((r["old_decision"], r["new_decision"]) for r in rows)
added = Counter(c for r in rows for c in r["reasons_added"].split(";") if c)
removed = Counter(c for r in rows for c in r["reasons_removed"].split(";") if c)
top = lambda d, k, key: [d[i]["title"][:50] for i in sorted((i for i in d if d[i].get(key)), key=lambda i: d[i][key])[:k]]
summary = {"records_old": len(old), "records_new": len(new), "decision_transitions": {f"{a}->{b}": n for (a, b), n in sorted(trans.items(), key=str)},
           "reasons_added_counts": dict(added), "reasons_removed_counts": dict(removed),
           "conditions_confirmed_distribution_new": dict(Counter(r["conditions_confirmed"] for r in rows)),
           "top5_old_rank_b": top(old, 5, "rank_b"), "top5_new_rank_b": top(new, 5, "rank_b"), "top5_new_rank_review": top(new, 5, "rank_review"),
           "changed_decisions": [{"id": r["id"], "title": r["title"], "from": r["old_decision"], "to": r["new_decision"], "added": r["reasons_added"], "removed": r["reasons_removed"]} for r in rows if r["old_decision"] != r["new_decision"]]}
json.dump(summary, open(out / "summary.json", "w", indent=1) if False else open(out / "summary.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps(summary, indent=1, ensure_ascii=False))
