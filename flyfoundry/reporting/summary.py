"""Markdown summary for the GitHub Actions run summary and exports (CSV / JSON)."""
from __future__ import annotations

import csv
import io
import json

from ..research import analysis
from .charts import ARM_LABEL


def markdown_summary(exp, res: dict, ckpt_info: dict, resume_test: dict, hyps: list) -> str:
    run = exp.runs[-1] if exp.runs else {}
    L = ["# FlyFoundry run summary", "",
         f"- **Status:** {run.get('status', 'n/a')}  |  **Run:** `{run.get('run_id')}`",
         f"- **Generations:** {run.get('gen_start')} -> {run.get('gen_end')} (cumulative {exp.generation})",
         f"- **Fitness evaluations:** {exp.total_evals:,} total, {run.get('evals_added', 0):,} this run "
         f"({exp.cfg.pop_size} agents x {len(exp.cfg.arms)} arms x {exp.cfg.n_seeds} seeds)",
         f"- **Resources this run:** CPU {run.get('cpu_s')} s, wall {run.get('wall_s')} s, peak RSS {run.get('peak_rss_mb')} MB",
         f"- **Code revision:** `{(run.get('code_revision') or '')[:12]}`  |  **Checkpoint:** v{ckpt_info.get('version')} "
         f"(sha256 `{str(ckpt_info.get('sha256', ''))[:12]}`)",
         f"- **Checkpoint recovery problems:** {'; '.join(ckpt_info.get('problems', [])) or 'none'}",
         f"- **Resume test:** {json.dumps(resume_test)}",
         f"- **Arm E (LLM baseline):** {exp.llm['status']} - {exp.llm['reason']}", "",
         "| Arm | Held-out QD (mean [95% CI]) | Held-out best | Train best | Peaks found | QD / 1k evals | QD / CPU-s |",
         "|---|---|---|---|---|---|---|"]
    for a in exp.cfg.arms:
        d = res["arms"][a]
        m = d["metrics"]
        L.append(f"| {ARM_LABEL.get(a, a)} | {m['heldout_qd']['mean']:.3f} [{m['heldout_qd']['lo']:.3f}, {m['heldout_qd']['hi']:.3f}] "
                 f"| {m['heldout_best']['mean']:.3f} | {m['f_best']['mean']:.3f} | {m['discovered']['mean']:.1f} "
                 f"| {d['heldout_qd_per_1k_evals']:.4f} | {d['heldout_qd_per_cpu_s']:.3f} |")
    L += ["", "## Conclusions (conservative, auto-generated)", ""]
    for it in res["conclusions"]:
        L.append(f"**{it['title']}**  ")
        if "text" in it:
            L.append(it["text"])
        for x in it.get("list", []):
            L.append(f"- {x}")
        L.append("")
    L += ["## Top hypotheses (synthetic benchmark only; not real-world evidence)", ""]
    for h in hyps[:5]:
        d = h["decoded"]
        L.append(f"- `{h['id']}` {d['customer']} / {d['problem']} / {d['solution']} / {d['revenue_mechanism']} "
                 f"(held-out fixed score {h['heldout_fixed_score']:.3f}, EUR {d['required_capital_eur_model_estimate']} est.)")
    return "\n".join(L) + "\n"


def history_csv(exp) -> str:
    buf = io.StringIO()
    keys = None
    w = None
    for r in exp.runners.values():
        for h in r.history:
            row = {"arm": r.arm_name, "seed": r.seed_idx, **h}
            if w is None:
                keys = list(row)
                w = csv.DictWriter(buf, fieldnames=keys)
                w.writeheader()
            w.writerow(row)
    return buf.getvalue()


def results_json(exp, res: dict, ckpt_info: dict, resume_test: dict) -> str:
    out = {"generation": exp.generation, "total_evals": exp.total_evals, "config": exp.cfg.to_dict(),
           "config_hash": exp.cfg.identity_hash(), "world_fingerprint": exp.world.fingerprint(),
           "runs": exp.runs, "llm": exp.llm, "checkpoint": ckpt_info, "resume_test": resume_test,
           "analysis": {"arms": res["arms"], "paired": res["paired"], "conclusions": res["conclusions"]}}
    return json.dumps(out, indent=1, default=float)
