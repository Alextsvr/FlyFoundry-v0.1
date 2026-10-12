"""Dependency-free inline SVG charts (themeable via CSS variables) with a small hover layer."""
from __future__ import annotations

import html
import json
import math

import numpy as np

ARM_STYLE = {  # fixed entity->colour map (never repainted when arms are filtered)
    "A_fly_plastic": ("var(--s1)", ""),
    "B_evolved_ann": ("var(--s2)", "6 3"),
    "A_fly_noplast": ("var(--s3)", "2 3"),
    "C_genetic": ("var(--s4)", "8 3 2 3"),
    "A_fly_shuffled": ("var(--s5)", "4 4"),
    "D_random": ("var(--s6)", "1 3"),
}
ARM_LABEL = {
    "A_fly_plastic": "A fly-inspired + plasticity", "A_fly_noplast": "A fly-inspired, no plasticity",
    "A_fly_shuffled": "A fly-inspired, shuffled wiring", "B_evolved_ann": "B evolved ANN",
    "C_genetic": "C genetic algorithm", "D_random": "D random search", "E_llm_baseline": "E LLM baseline (NOT RUN)",
}


def legend(arms) -> str:
    items = []
    for a in arms:
        col, dash = ARM_STYLE.get(a, ("var(--muted)", ""))
        items.append(f'<span class="lg"><svg width="26" height="10"><line x1="0" y1="5" x2="26" y2="5" stroke="{col}" '
                     f'stroke-width="2.5" stroke-dasharray="{dash}"/></svg>{html.escape(ARM_LABEL.get(a, a))}</span>')
    return '<div class="legend">' + "".join(items) + "</div>"


def _nice_ticks(lo, hi, n=5):
    if hi - lo < 1e-9:
        hi = lo + 1.0
    raw = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(raw))
    step = min((s * mag for s in (1, 2, 2.5, 5, 10) if s * mag >= raw), default=raw)
    start = math.floor(lo / step) * step
    ticks, v = [], start
    while v <= hi + step * 0.5:
        ticks.append(round(v, 10))
        v += step
    return ticks


def line_chart(title: str, series: dict, xs, ylabel: str = "", ci: dict | None = None, w=640, h=270,
               yfmt="{:.2f}", xlabel="generation") -> str:
    """series: name -> list of y; ci: name -> (lo list, hi list)."""
    ml, mr, mt, mb = 52, 14, 14, 36
    xs = list(xs)
    allv = [v for ys in series.values() for v in ys if v is not None and not np.isnan(v)]
    if ci:
        allv += [v for lo, hi in ci.values() for v in list(lo) + list(hi) if not np.isnan(v)]
    if not allv or len(xs) < 1:
        return f'<div class="chart empty"><h4>{html.escape(title)}</h4><p class="muted">No observations available.</p></div>'
    ticks = _nice_ticks(min(allv), max(allv))
    y0, y1 = ticks[0], ticks[-1]
    x0, x1 = xs[0], xs[-1] if len(xs) > 1 else xs[0] + 1

    def px(x):
        return ml + (x - x0) / (x1 - x0) * (w - ml - mr)

    def py(y):
        return mt + (1 - (y - y0) / (y1 - y0)) * (h - mt - mb)

    g = [f'<svg viewBox="0 0 {w} {h}" class="plot" role="img" aria-label="{html.escape(title)}">']
    for t in ticks:
        g.append(f'<line x1="{ml}" x2="{w - mr}" y1="{py(t):.1f}" y2="{py(t):.1f}" class="grid"/>'
                 f'<text x="{ml - 6}" y="{py(t) + 4:.1f}" class="tick" text-anchor="end">{yfmt.format(t)}</text>')
    for t in _nice_ticks(x0, x1, 6):
        if x0 <= t <= x1:
            g.append(f'<text x="{px(t):.1f}" y="{h - mb + 16}" class="tick" text-anchor="middle">{t:g}</text>')
    g.append(f'<text x="{(ml + w - mr) / 2:.0f}" y="{h - 4}" class="axl" text-anchor="middle">{xlabel}</text>')
    if ylabel:
        g.append(f'<text x="12" y="{(mt + h - mb) / 2:.0f}" class="axl" text-anchor="middle" '
                 f'transform="rotate(-90 12 {(mt + h - mb) / 2:.0f})">{html.escape(ylabel)}</text>')
    for name, ys in series.items():
        col, dash = ARM_STYLE.get(name, ("var(--s1)", ""))
        if ci and name in ci:
            lo, hi = ci[name]
            if not any(np.isnan(lo)) and not any(np.isnan(hi)):
                top = " ".join(f"{px(x):.1f},{py(v):.1f}" for x, v in zip(xs, hi))
                bot = " ".join(f"{px(x):.1f},{py(v):.1f}" for x, v in zip(reversed(xs), reversed(list(lo))))
                g.append(f'<polygon points="{top} {bot}" fill="{col}" opacity="0.13"/>')
        pts = " ".join(f"{px(x):.1f},{py(v):.1f}" for x, v in zip(xs, ys) if v is not None and not np.isnan(v))
        g.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="2" '
                 f'stroke-dasharray="{dash}" stroke-linejoin="round"/>')
    g.append(f'<line class="xh" x1="0" x2="0" y1="{mt}" y2="{h - mb}"/>')
    g.append("</svg>")
    data = {"xs": xs, "series": [{"name": ARM_LABEL.get(n, n), "color": ARM_STYLE.get(n, ("var(--s1)", ""))[0],
                                  "y": [None if (v is None or np.isnan(v)) else round(float(v), 4) for v in ys]}
                                 for n, ys in series.items()],
            "ml": ml, "mr": mr, "w": w, "x0": x0, "x1": x1, "fmt": yfmt}
    return (f'<figure class="chart" data-chart=\'{html.escape(json.dumps(data), quote=True)}\'>'
            f'<figcaption>{html.escape(title)}</figcaption>{"".join(g)}<div class="tip" hidden></div></figure>')


def bar_ci(title: str, rows: list[tuple[str, float, float, float]], w=640, fmt="{:.3f}") -> str:
    """rows: (arm, mean, lo, hi) horizontal bars with CI whiskers."""
    if not rows:
        return ""
    ml, mr, bh, gap = 190, 40, 18, 10
    h = len(rows) * (bh + gap) + 30
    vmax = max(max(r[1], r[3] if not np.isnan(r[3]) else r[1]) for r in rows) * 1.08 or 1.0
    vmin = min(0.0, min(r[1] for r in rows))
    g = [f'<svg viewBox="0 0 {w} {h}" class="plot" role="img" aria-label="{html.escape(title)}">']

    def px(v):
        return ml + (v - vmin) / (vmax - vmin) * (w - ml - mr)

    for i, (arm, m, lo, hi) in enumerate(rows):
        y = 10 + i * (bh + gap)
        col = ARM_STYLE.get(arm, ("var(--s1)", ""))[0]
        g.append(f'<text x="{ml - 8}" y="{y + 13}" class="tick" text-anchor="end">{html.escape(ARM_LABEL.get(arm, arm))}</text>')
        x_a, x_b = sorted((px(0), px(m)))
        g.append(f'<path d="M{x_a:.1f},{y} H{x_b - 4 if x_b - x_a > 6 else x_b:.1f} a4,4 0 0 1 4,4 v{bh - 8} a4,4 0 0 1 -4,4 H{x_a:.1f} Z" fill="{col}"><title>{html.escape(arm)}: {fmt.format(m)}</title></path>')
        if not (np.isnan(lo) or np.isnan(hi)):
            g.append(f'<line x1="{px(lo):.1f}" x2="{px(hi):.1f}" y1="{y + bh / 2}" y2="{y + bh / 2}" class="whisk"/>'
                     f'<line x1="{px(lo):.1f}" x2="{px(lo):.1f}" y1="{y + 4}" y2="{y + bh - 4}" class="whisk"/>'
                     f'<line x1="{px(hi):.1f}" x2="{px(hi):.1f}" y1="{y + 4}" y2="{y + bh - 4}" class="whisk"/>')
        tx = (px(hi) if not np.isnan(hi) else px(m)) + 6
        g.append(f'<text x="{tx:.1f}" y="{y + 13}" class="val">{fmt.format(m)}</text>')
    g.append("</svg>")
    return f'<figure class="chart"><figcaption>{html.escape(title)} <span class="muted">(mean, 95% bootstrap CI over seeds)</span></figcaption>{"".join(g)}</figure>'


def heat_grid(title: str, fit: np.ndarray, bins: int, vmax: float = 0.8) -> str:
    """3-D archive (bins^3) shown as `bins` small bins x bins panels (dims 0,1,3 -> panel=dim1)."""
    n = bins
    cells = fit.reshape(n, n, n)  # [d0][d1][d3]
    panels = []
    for j in range(n):
        rows = []
        for i in range(n):
            for k in range(n):
                v = cells[i, j, k]
                if not np.isfinite(v):
                    rows.append('<i class="c empty" title="empty niche"></i>')
                else:
                    pct = int(np.clip(v / vmax, 0.04, 1.0) * 100)
                    rows.append(f'<i class="c" style="background:color-mix(in srgb,var(--s1) {pct}%,var(--surface))" '
                                f'title="niche d0={i} d1={j} d3={k}: train fitness {v:.2f}"></i>')
        panels.append(f'<div class="panel"><div class="grid{n}">{"".join(rows)}</div></div>')
    return f'<figure class="chart heat"><figcaption>{html.escape(title)}</figcaption><div class="panels">{"".join(panels)}</div></figure>'
