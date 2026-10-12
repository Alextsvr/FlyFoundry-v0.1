"""Self-contained HTML dashboard (no external requests)."""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone

import numpy as np

from ..evolution.lineage import OP_NAMES
from ..research import analysis, provenance
from ..research.opportunities import build_hypotheses
from . import charts
from .charts import ARM_LABEL

E = html.escape

CSS = """
:root{color-scheme:light;--surface:#fcfcfb;--panel:#f4f3f0;--text:#0b0b0b;--text2:#52514e;--muted:#6b6a65;--line:#dcdad3;
--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#eda100;--s5:#e87ba4;--s6:#008300;--bad:#c0392b;--ok:#1d7a3a;--warn:#9a6700}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){color-scheme:dark;--surface:#1a1a19;--panel:#242422;--text:#f0efec;--text2:#c3c2b7;--muted:#a09f96;--line:#3a3935;
--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#d55181;--s6:#008300;--bad:#e66767;--ok:#4cc27a;--warn:#e0a526}}
:root[data-theme="dark"]{color-scheme:dark;--surface:#1a1a19;--panel:#242422;--text:#f0efec;--text2:#c3c2b7;--muted:#a09f96;--line:#3a3935;
--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#d55181;--s6:#008300;--bad:#e66767;--ok:#4cc27a;--warn:#e0a526}
*{box-sizing:border-box}body{margin:0;background:var(--surface);color:var(--text);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
header{padding:20px 16px 8px;max-width:1200px;margin:0 auto}h1{font-size:22px;margin:0 0 4px}h2{font-size:18px;margin:26px 0 8px}h3{font-size:15px;margin:18px 0 6px}h4{margin:0}
main{max-width:1200px;margin:0 auto;padding:0 16px 60px}.muted{color:var(--muted)}small{color:var(--text2)}
nav{position:sticky;top:0;background:var(--surface);border-bottom:1px solid var(--line);z-index:5}nav div{max-width:1200px;margin:0 auto;padding:0 16px;display:flex;gap:4px;flex-wrap:wrap}
nav button{background:none;border:0;border-bottom:3px solid transparent;color:var(--text2);padding:10px 12px;font:inherit;cursor:pointer}
nav button[aria-selected=true]{color:var(--text);border-color:var(--s1);font-weight:600}section.tab{display:none}section.tab.on{display:block}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}.kpi{background:var(--panel);border-radius:8px;padding:10px 12px}
.kpi b{display:block;font-size:20px}.kpi span{color:var(--text2);font-size:12px}
table{border-collapse:collapse;width:100%;font-size:13px;margin:6px 0}th,td{border-bottom:1px solid var(--line);padding:5px 8px;text-align:left;vertical-align:top}
th{color:var(--text2);font-weight:600;background:var(--panel)}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.tablewrap{overflow-x:auto}.pill{display:inline-block;border-radius:10px;padding:1px 8px;font-size:12px;border:1px solid var(--line)}
.pill.ok{color:var(--ok)}.pill.bad{color:var(--bad)}.pill.warn{color:var(--warn)}
.banner{border-left:4px solid var(--warn);background:var(--panel);padding:8px 12px;margin:10px 0;border-radius:4px}.banner.bad{border-color:var(--bad)}
.charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(380px,1fr));gap:14px}
figure.chart{margin:0;background:var(--panel);border-radius:8px;padding:10px;position:relative}figcaption{font-weight:600;font-size:13px;margin-bottom:4px}
svg.plot{width:100%;height:auto;display:block}.grid{stroke:var(--line);stroke-width:1}.tick,.axl{fill:var(--text2);font-size:11px}.val{fill:var(--text);font-size:11px}
.whisk{stroke:var(--text2);stroke-width:1.5}.xh{stroke:var(--text2);stroke-width:1;opacity:0}
.tip{position:absolute;pointer-events:none;background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:6px 8px;font-size:12px;box-shadow:0 2px 8px #0003;z-index:3;white-space:nowrap}
.legend{display:flex;flex-wrap:wrap;gap:6px 16px;margin:8px 0;font-size:12.5px;color:var(--text2)}.lg{display:inline-flex;align-items:center;gap:6px}
.panels{display:flex;gap:6px;flex-wrap:wrap}.grid4{display:grid;grid-template-columns:repeat(4,16px);gap:2px}.c{display:block;width:16px;height:16px;border-radius:2px}.c.empty{background:var(--surface);border:1px dashed var(--line)}
.hyp{background:var(--panel);border-radius:8px;padding:10px 14px;margin:10px 0}.hyp h4{font-size:14px}dl{display:grid;grid-template-columns:200px 1fr;gap:3px 12px;margin:6px 0;font-size:13px}dt{color:var(--text2)}dd{margin:0}
code{background:var(--panel);padding:0 4px;border-radius:3px;font-size:12px;word-break:break-all}
@media(max-width:640px){dl{grid-template-columns:1fr}.charts{grid-template-columns:1fr}}
"""

JS = """
const tabs=[...document.querySelectorAll('nav button')];
function show(id){tabs.forEach(b=>b.setAttribute('aria-selected',b.dataset.t===id));
document.querySelectorAll('section.tab').forEach(s=>s.classList.toggle('on',s.id===id));history.replaceState(null,'','#'+id)}
tabs.forEach(b=>b.onclick=()=>show(b.dataset.t));show((location.hash||'#overview').slice(1)||'overview');
document.querySelectorAll('figure[data-chart]').forEach(f=>{const d=JSON.parse(f.dataset.chart),svg=f.querySelector('svg'),tip=f.querySelector('.tip'),xh=svg.querySelector('.xh');
svg.addEventListener('mousemove',e=>{const r=svg.getBoundingClientRect(),sx=d.w/r.width,x=(e.clientX-r.left)*sx;
let t=(x-d.ml)/(d.w-d.ml-d.mr);t=Math.min(1,Math.max(0,t));const gx=d.x0+t*(d.x1-d.x0);
let i=0,b=1e18;d.xs.forEach((v,k)=>{if(Math.abs(v-gx)<b){b=Math.abs(v-gx);i=k}});
const px=d.ml+(d.xs[i]-d.x0)/((d.x1-d.x0)||1)*(d.w-d.ml-d.mr);xh.setAttribute('x1',px);xh.setAttribute('x2',px);xh.style.opacity=1;
tip.hidden=false;tip.innerHTML='<b>generation '+d.xs[i]+'</b><br>'+d.series.map(s=>'<span style="color:'+s.color+'">&#9632;</span> '+s.name+': '+(s.y[i]==null?'n/a':s.y[i].toFixed(3))).join('<br>');
const fr=f.getBoundingClientRect();let l=e.clientX-fr.left+14;if(l>fr.width-260)l=e.clientX-fr.left-250;tip.style.left=l+'px';tip.style.top=(e.clientY-fr.top+8)+'px'});
svg.addEventListener('mouseleave',()=>{tip.hidden=true;xh.style.opacity=0})});
"""


def _curve(exp, arm, key, n_res=400, seed=0):
    s = analysis.series(exp, arm, key)
    mean = s.mean(axis=0)
    if s.shape[0] < 2:
        return mean, np.full_like(mean, np.nan), np.full_like(mean, np.nan)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, s.shape[0], (n_res, s.shape[0]))
    bm = s[idx].mean(axis=1)  # (R, T)
    return mean, np.quantile(bm, 0.025, axis=0), np.quantile(bm, 0.975, axis=0)


def _curves(exp, key, title, ylabel, yfmt="{:.2f}"):
    xs = [h["gen"] for h in next(iter(exp.runners.values())).history]
    ser, ci = {}, {}
    for arm in exp.cfg.arms:
        m, lo, hi = _curve(exp, arm, key)
        ser[arm], ci[arm] = list(m), (lo, hi)
    return charts.line_chart(title, ser, xs, ylabel, ci, yfmt=yfmt)


def _fmt(v, d=3):
    return "n/a" if v is None or (isinstance(v, float) and np.isnan(v)) else f"{v:.{d}f}"


def _lineage_summary(exp, arm):
    r = next(r for r in exp.runners.values() if r.arm_name == arm and r.seed_idx == 0)
    lin = r.arm.lineage
    living = [int(i) for i in r.arm.ids]
    founders_total = exp.cfg.pop_size
    if arm == "D_random":
        return r, None
    fs = {lin.founder_of(i) for i in living}
    depth = [len(lin.ancestry(i)) for i in living]
    champ = r.arm.champions[-1][1] if r.arm.champions else None
    chain = []
    for aid in (lin.ancestry(champ)[:12] if champ is not None else []):
        row = lin.rows[aid]
        chain.append((aid, row[2], OP_NAMES.get(row[3], "?"), row[4], row[6]))
    return r, {"surviving": len(fs), "total": founders_total, "extinct": founders_total - len(fs),
               "mean_depth": float(np.mean(depth)), "max_depth": int(max(depth)), "champ": champ, "chain": chain,
               "pruned": lin.pruned}


def render(exp, res: dict, ckpt_info: dict | None = None, hypotheses: list | None = None) -> str:
    cfg = exp.cfg
    arms = list(cfg.arms)
    run = exp.runs[-1] if exp.runs else {}
    ckpt_info = ckpt_info or {}
    hyps = hypotheses if hypotheses is not None else build_hypotheses(exp)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    status_ok = run.get("status", "").startswith("completed") and not ckpt_info.get("problems")
    status = "COMPLETED" if run.get("status") == "completed" else (run.get("status", "no run").upper())
    parts = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
             f"<title>FlyFoundry dashboard</title><style>{CSS}</style></head><body>"]
    parts.append(f"<header><h1>FlyFoundry v0.1 &mdash; evolutionary venture discovery lab</h1>"
                 f"<small>Experimental search system on a <b>synthetic</b> benchmark. Not a claim of digital organisms, and not evidence of real revenue. "
                 f"Report generated {now}.</small></header>")
    parts.append("<nav><div>" + "".join(f"<button data-t='{t}'>{n}</button>" for t, n in (
        ("overview", "Overview"), ("comparison", "Experimental comparison"), ("evolution", "Evolutionary history"),
        ("opportunities", "Opportunity discovery"), ("conclusions", "Conclusions"), ("repro", "Provenance &amp; model cards"))) + "</div></nav><main>")

    # ------------------------------------------------------------ overview
    gens_total = exp.generation
    parts.append("<section class='tab' id='overview'><h2>Overview</h2>")
    parts.append(f"<div class='banner {'bad' if not status_ok else ''}'><b>Actual status:</b> {E(status)}"
                 f"{' &mdash; ' + E(run.get('stopped_early_reason', '')) if run.get('stopped_early_reason') else ''}. "
                 f"Checkpoint recovery problems: {E('; '.join(ckpt_info.get('problems', [])) or 'none')}.</div>")
    kp = [("Run ID", run.get("run_id", "n/a")), ("Run finished (UTC)", run.get("finished_utc", "n/a")),
          ("Generations completed (cumulative)", f"{gens_total} (this run: {run.get('gens_done', 0)})"),
          ("Agents evaluated (= fitness evaluations)", f"{exp.total_evals:,} (this run: {run.get('evals_added', 0):,})"),
          ("Active arms x seeds", f"{len(arms)} x {cfg.n_seeds} (+E not run)"),
          ("CPU time this run", f"{run.get('cpu_s', 0)} s"), ("Wall time this run", f"{run.get('wall_s', 0)} s"),
          ("Peak RAM (process RSS)", f"{run.get('peak_rss_mb', 0)} MB"),
          ("Code revision", (run.get("code_revision") or "unknown")[:12]),
          ("Checkpoint", f"v{ckpt_info.get('version', '?')} sha256 {str(ckpt_info.get('sha256', ''))[:12]}")]
    parts.append("<div class='kpis'>" + "".join(f"<div class='kpi'><b>{E(str(v))}</b><span>{E(k)}</span></div>" for k, v in kp) + "</div>")
    parts.append("<h3>Evidence ladder (what is actually established)</h3><table><tr><th>Level</th><th class='n'>Count</th><th>Note</th></tr>"
                 "<tr><td>Synthetic benchmark score</td><td class='n'>all candidates</td><td>Scores on a hidden synthetic landscape.</td></tr>"
                 "<tr><td>Evidence-supported real-world hypothesis</td><td class='n'>0</td><td>No public evidence dataset wired in (v0.1).</td></tr>"
                 "<tr><td>Validated customer demand</td><td class='n'>0</td><td>None.</td></tr>"
                 "<tr><td>Actual paying customer</td><td class='n'>0</td><td>None.</td></tr>"
                 "<tr><td>Real collected revenue</td><td class='n'>EUR 0 / unknown</td><td>No independent proof of any revenue.</td></tr></table>")
    parts.append("<h3>Experiment arms &mdash; observed vs missing</h3><div class='tablewrap'><table><tr><th>Arm</th><th>Status</th><th class='n'>Seeds</th>"
                 "<th class='n'>Evals / seed</th><th class='n'>CPU s / seed (search)</th><th class='n'>CPU s / seed (monitoring)</th><th class='n'>Transient peak alloc (KB)</th></tr>")
    for a in arms:
        d = res["arms"][a]
        parts.append(f"<tr><td>{E(ARM_LABEL.get(a, a))}</td><td><span class='pill ok'>RAN</span></td><td class='n'>{cfg.n_seeds}</td>"
                     f"<td class='n'>{d['evals_per_seed']:,}</td><td class='n'>{d['cpu_search_s_mean']:.2f}</td>"
                     f"<td class='n'>{d['cpu_monitor_s_mean']:.2f}</td><td class='n'>{d['mem_peak_kb_max']:.0f}</td></tr>")
    parts.append(f"<tr><td>{E(ARM_LABEL['E_llm_baseline'])}</td><td><span class='pill warn'>{E(exp.llm['status'])}</span></td>"
                 f"<td class='n'>0</td><td class='n'>0</td><td class='n'>-</td><td class='n'>-</td><td class='n'>-</td></tr></table></div>"
                 f"<p class='muted'>Arm E: {E(exp.llm['reason'])}. No LLM output is simulated.</p>")
    parts.append("<h3>Run history</h3><div class='tablewrap'><table><tr><th>Run</th><th>Status</th><th class='n'>Gens</th><th class='n'>Evals</th>"
                 "<th class='n'>CPU s</th><th class='n'>Wall s</th><th>Revision</th><th>GitHub run</th></tr>")
    for r_ in exp.runs[-12:][::-1]:
        url = (r_.get("environment") or {}).get("github_run_url")
        parts.append(f"<tr><td>{E(r_['run_id'])}</td><td>{E(r_['status'])}</td><td class='n'>{r_['gen_start']}&rarr;{r_['gen_end']}</td>"
                     f"<td class='n'>{r_['evals_added']:,}</td><td class='n'>{r_['cpu_s']}</td><td class='n'>{r_['wall_s']}</td>"
                     f"<td><code>{E((r_.get('code_revision') or '')[:10])}</code></td><td>{('<a href=' + chr(34) + E(url) + chr(34) + '>link</a>') if url else 'local'}</td></tr>")
    parts.append("</table></div></section>")

    # ----------------------------------------------------------- comparison
    parts.append("<section class='tab' id='comparison'><h2>Experimental comparison</h2>"
                 "<p class='muted'>Curves: mean over seeds with 95% bootstrap band. Held-out metrics use contexts never used for selection. "
                 "All arms received the identical evaluation budget per generation.</p>" + charts.legend(arms) + "<div class='charts'>")
    for key, title, yl in (("heldout_qd", "Held-out quality-diversity score", "score"), ("heldout_best", "Held-out best candidate score", "score"),
                           ("heldout_discovery", "Held-out peak discovery rate", "rate"), ("f_best", "Train best-of-generation fitness", "fitness"),
                           ("f_mean", "Train mean fitness", "fitness"), ("f_median", "Train median fitness", "fitness"),
                           ("diversity", "Population diversity (phenotype)", "mean pairwise dist."), ("novelty", "Novelty (5-NN distance)", "dist."),
                           ("niches_viable", "Niche coverage: viable archive niches", "niches"), ("pop_niches", "Niches occupied by current population", "niches"),
                           ("discovered", "Distinct real peaks discovered (train, cumulative)", "peaks")):
        parts.append(_curves(exp, key, title, yl))
    parts.append("</div><h3>Final held-out score per arm</h3><div class='charts'>")
    for key, label, *_ in analysis.METRICS[:3]:
        rows = [(a, res["arms"][a]["metrics"][key]["mean"], res["arms"][a]["metrics"][key]["lo"], res["arms"][a]["metrics"][key]["hi"]) for a in arms]
        parts.append(charts.bar_ci(label, rows))
    parts.append("</div><h3>Metric table (mean of last 5 generations, 95% bootstrap CI over seeds)</h3><div class='tablewrap'><table><tr><th>Metric</th>"
                 + "".join(f"<th class='n'>{E(ARM_LABEL.get(a, a))}</th>" for a in arms) + "</tr>")
    for key, label, *_ in analysis.METRICS:
        parts.append(f"<tr><td>{E(label)}</td>" + "".join(
            f"<td class='n'>{_fmt(res['arms'][a]['metrics'][key]['mean'])}<br><small>[{_fmt(res['arms'][a]['metrics'][key]['lo'])}, {_fmt(res['arms'][a]['metrics'][key]['hi'])}]</small></td>"
            for a in arms) + "</tr>")
    parts.append("<tr><td>Held-out QD per 1k evaluations</td>" + "".join(f"<td class='n'>{res['arms'][a]['heldout_qd_per_1k_evals']:.4f}</td>" for a in arms) + "</tr>")
    parts.append("<tr><td>Held-out QD per search CPU-second</td>" + "".join(f"<td class='n'>{res['arms'][a]['heldout_qd_per_cpu_s']:.3f}</td>" for a in arms) + "</tr>")
    parts.append("<tr><td>Held-out QD, mean over whole run (learning-curve AUC)</td>" + "".join(f"<td class='n'>{res['arms'][a]['auc_heldout_qd']:.3f}</td>" for a in arms) + "</tr></table></div>")
    parts.append("<h3>Paired differences (seeds paired by index)</h3><div class='tablewrap'><table><tr><th>A</th><th>B</th><th>Metric</th><th class='n'>mean(A-B)</th><th class='n'>95% CI</th><th>Reading</th></tr>")
    for p in res["paired"]:
        ex = analysis._ci_excludes_zero(p)
        parts.append(f"<tr><td>{E(p['a'])}</td><td>{E(p['b'])}</td><td>{E(p['metric'])}</td><td class='n'>{p['diff']:+.3f}</td>"
                     f"<td class='n'>[{p['lo']:+.3f}, {p['hi']:+.3f}]</td><td>{'CI excludes 0 (preliminary)' if ex else 'CI includes 0'}</td></tr>")
    parts.append("</table></div></section>")

    # ------------------------------------------------------------ evolution
    parts.append("<section class='tab' id='evolution'><h2>Evolutionary history</h2><p class='muted'>Seed 0 shown for per-agent views; "
                 "genealogy is pruned to the ancestry of living agents, archive elites and recent champions.</p>")
    parts.append("<h3>Generation-by-generation comparison (held-out QD, mean over seeds)</h3><div class='tablewrap'><table><tr><th>Generation</th>"
                 + "".join(f"<th class='n'>{E(a)}</th>" for a in arms) + "</tr>")
    T = gens_total
    marks = sorted({max(1, round(T * k / 10)) for k in range(1, 11)})
    for g in marks:
        parts.append(f"<tr><td>{g}</td>" + "".join(f"<td class='n'>{analysis.series(exp, a, 'heldout_qd')[:, g - 1].mean():.3f}</td>" for a in arms) + "</tr>")
    parts.append("</table></div><h3>Population fitness distribution over generations (seed 0)</h3><div class='charts'>")
    xs = [h["gen"] for h in next(iter(exp.runners.values())).history]
    for a in arms:
        r = next(r for r in exp.runners.values() if r.arm_name == a and r.seed_idx == 0)
        ser = {a: [h["f_median"] for h in r.history]}
        ci = {a: (np.array([h["f_q10"] for h in r.history]), np.array([h["f_q90"] for h in r.history]))}
        parts.append(charts.line_chart(f"{ARM_LABEL[a]} - median and 10-90% band", ser, xs, "train fitness", ci, h=200))
    parts.append("</div><h3>Mutation history (mean mutated genes per offspring, seed 0)</h3><div class='charts'>")
    ser = {}
    for a in arms:
        if a == "D_random":
            continue
        r = next(r for r in exp.runners.values() if r.arm_name == a and r.seed_idx == 0)
        ser[a] = [h["n_mut"] for h in r.history]
    parts.append(charts.line_chart("Mutated genes per offspring", ser, xs, "genes", None, yfmt="{:.1f}"))
    parts.append("</div><h3>Niche / species evolution: archive occupancy (seed 0, final)</h3>"
                 "<p class='muted'>Each 4x4 panel is one bin of dimension 1; rows = dim 0, columns = dim 3. Darker = higher training fitness; dashed = empty niche.</p><div class='charts'>")
    for a in arms:
        r = next(r for r in exp.runners.values() if r.arm_name == a and r.seed_idx == 0)
        parts.append(charts.heat_grid(ARM_LABEL[a], r.arm.archive.fit, cfg.archive_bins))
    parts.append("</div><h3>Winning and extinct lineages (seed 0)</h3><div class='tablewrap'><table><tr><th>Arm</th><th class='n'>Founder lineages alive</th>"
                 "<th class='n'>Extinct</th><th class='n'>Mean / max ancestry depth</th><th class='n'>Pruned records</th><th>Latest champion</th></tr>")
    champ_tables = []
    for a in arms:
        r, ls = _lineage_summary(exp, a)
        if ls is None:
            parts.append(f"<tr><td>{E(a)}</td><td colspan='5'>n/a &mdash; random search has no inheritance (every candidate is a founder)</td></tr>")
            continue
        parts.append(f"<tr><td>{E(a)}</td><td class='n'>{ls['surviving']} / {ls['total']}</td><td class='n'>{ls['extinct']}</td>"
                     f"<td class='n'>{ls['mean_depth']:.1f} / {ls['max_depth']}</td><td class='n'>{ls['pruned']}</td><td>agent {ls['champ']}</td></tr>")
        rows = "".join(f"<tr><td>{aid}</td><td class='n'>{born}</td><td>{E(op)}</td><td class='n'>{nm}</td><td class='n'>{bf:.2f}</td></tr>" for aid, born, op, nm, bf in ls["chain"])
        champ_tables.append(f"<h4>Champion genealogy &mdash; {E(ARM_LABEL[a])} (agent {ls['champ']}, newest ancestor first)</h4>"
                            f"<div class='tablewrap'><table><tr><th>Agent</th><th class='n'>Born gen</th><th>Created by</th><th class='n'>Genes mutated</th><th class='n'>Best fitness</th></tr>{rows}</table></div>")
    parts.append("</table></div>" + "".join(champ_tables) + "</section>")

    # --------------------------------------------------------- opportunities
    parts.append("<section class='tab' id='opportunities'><h2>Opportunity discovery</h2>"
                 "<div class='banner'><b>These are synthetic-benchmark HYPOTHESES.</b> Customer and problem names are labels from a synthetic taxonomy "
                 "(<code>data/taxonomy.json</code>), not market findings. No sources, competitors, customers or revenue are claimed. "
                 "Ranked by fixed-candidate score on held-out contexts; training score shown separately.</div>")
    for i, h in enumerate(hyps[:15], 1):
        d = h["decoded"]
        parts.append(f"<div class='hyp'><h4>#{i} <code>{E(h['id'])}</code> &mdash; {E(d['customer'])}: {E(d['problem'])}</h4><dl>"
                     f"<dt>Originating arm / seed</dt><dd>{E(ARM_LABEL.get(h['arm'], h['arm']))} / seed {h['seed_idx']}</dd>"
                     f"<dt>Agent lineage</dt><dd>agent {h['agent_id']} (found gen {h['generation_found']}), parent {h['parent_agent_id']}, created by {E(str(h['creation_operator']))}, ancestry depth {h['ancestry_chain_length']}</dd>"
                     f"<dt>Business model</dt><dd>{E(d['solution'])}; revenue: {E(d['revenue_mechanism'])}; channel: {E(d['channel'])}</dd>"
                     f"<dt>Scores</dt><dd>train fitness {h['train_fitness']:.3f}; held-out fixed-candidate {h['heldout_fixed_score']:.3f} (synthetic)</dd>"
                     f"<dt>Supporting sources</dt><dd>{E(h['sources'])}</dd><dt>Novelty assessment</dt><dd>{E(h['novelty_assessment'])}</dd>"
                     f"<dt>Competition</dt><dd>{E(h['competition'])}</dd>"
                     f"<dt>Upfront cost</dt><dd>EUR {d['required_capital_eur_model_estimate']} (model estimate, unverified)</dd>"
                     f"<dt>Maintenance effort</dt><dd>{d['operational_effort_hours_per_week_model_estimate']} h/week (model estimate), automation share {d['automation_share_pct']}%</dd>"
                     f"<dt>Testable assumptions</dt><dd>{'<br>'.join(E(x) for x in d['testable_assumptions'])}</dd>"
                     f"<dt>Principal risks</dt><dd>{'; '.join(E(x) for x in d['principal_risks'])}</dd>"
                     f"<dt>Next validation step</dt><dd>{E(h['next_validation_step'])}</dd>"
                     f"<dt>Confidence</dt><dd>{E(h['confidence'])}</dd><dt>Hypothesis vs fact</dt><dd>{E(h['hypothesis_vs_fact'])}</dd></dl></div>")
    parts.append("</section>")

    # ----------------------------------------------------------- conclusions
    parts.append("<section class='tab' id='conclusions'><h2>Conclusions (auto-generated, conservative)</h2>")
    for it in res["conclusions"]:
        parts.append(f"<h3>{E(it['title'])}</h3>")
        if "text" in it:
            parts.append(f"<p>{E(it['text'])}</p>")
        if "list" in it:
            parts.append("<ul>" + "".join(f"<li>{E(x)}</li>" for x in it["list"]) + "</ul>")
    parts.append("</section>")

    # ----------------------------------------------------------------- repro
    parts.append("<section class='tab' id='repro'><h2>Provenance &amp; model cards</h2><div class='tablewrap'><table>")
    for k, v in (("Config identity hash", cfg.identity_hash()), ("Benchmark world fingerprint", exp.world.fingerprint()),
                 ("Taxonomy sha256", provenance.taxonomy_hash()), ("Code revision", run.get("code_revision", "unknown")),
                 ("Environment", json.dumps(run.get("environment", {}))), ("Config", json.dumps(cfg.to_dict()))):
        parts.append(f"<tr><th>{E(k)}</th><td><code>{E(str(v))}</code></td></tr>")
    parts.append("</table></div><h3>Biological fidelity (honest statement)</h3>")
    for a in ("A_fly_plastic",):
        mc = exp.model_cards.get(a, {})
        parts.append(f"<pre style='white-space:pre-wrap;background:var(--panel);padding:10px;border-radius:8px;font-size:12px'>{E(json.dumps(mc, indent=2))}</pre>")
    parts.append("<h3>Other arm model cards</h3>")
    for a in arms:
        if a != "A_fly_plastic":
            parts.append(f"<p><b>{E(a)}</b>: <code>{E(json.dumps(exp.model_cards.get(a, {})))}</code></p>")
    parts.append("</section></main><script>" + JS + "</script></body></html>")
    return "".join(parts)
