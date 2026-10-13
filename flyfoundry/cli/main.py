"""Command line interface: smoke | fresh | resume | run | merge | report | validate | export | schedule-guard | islands."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import traceback
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ..config import ExperimentConfig
from ..reporting import html_report, summary
from ..research import analysis
from ..research.experiment import Experiment, shard_seeds
from ..research.opportunities import build_hypotheses
from ..storage.checkpoint import CheckpointCorrupt, CheckpointError, CheckpointMissing, CheckpointStore
from ..storage.serialize import state_hash

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "configs" / "default.json"


def _cfg(args) -> ExperimentConfig:
    path = Path(args.config) if getattr(args, "config", None) else DEFAULT_CONFIG
    cfg = ExperimentConfig.from_file(path) if path.exists() else ExperimentConfig()
    return cfg.with_overrides(gens_per_run=getattr(args, "generations", None), n_seeds=getattr(args, "seeds", None),
                              pop_size=getattr(args, "pop_size", None))


def _parse_shard(args):
    """--shard i/N -> (index, n) or None. Shard index is 0-based."""
    spec = getattr(args, "shard", None)
    if not spec:
        return None
    try:
        i, n = (int(x) for x in spec.split("/"))
    except ValueError:
        raise SystemExit(f"invalid --shard {spec!r}: expected i/N, e.g. 0/10") from None
    if n < 1 or not 0 <= i < n:
        raise SystemExit(f"invalid --shard {spec!r}: need N >= 1 and 0 <= i < N")
    return i, n


def _new_experiment(cfg, args):
    sh = _parse_shard(args)
    return Experiment(cfg, shard_seeds(cfg.n_seeds, *sh) if sh else None)


def _info(entry, problems=None):
    return {"version": entry.get("version"), "sha256": entry.get("sha256"), "file": entry.get("file"),
            "bytes": entry.get("bytes"), "problems": list(problems or [])}


def _write_outputs(exp, out: Path, ckpt_info: dict, resume_test: dict) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    res = analysis.analyze(exp)
    hyps = build_hypotheses(exp)
    (out / "index.html").write_text(html_report.render(exp, res, ckpt_info, hyps), encoding="utf-8")
    (out / "summary.md").write_text(summary.markdown_summary(exp, res, ckpt_info, resume_test, hyps), encoding="utf-8")
    (out / "results.json").write_text(summary.results_json(exp, res, ckpt_info, resume_test), encoding="utf-8")
    (out / "history.csv").write_text(summary.history_csv(exp), encoding="utf-8")
    (out / "hypotheses.json").write_text(json.dumps(hyps, indent=1, default=float), encoding="utf-8")
    return res


def _advance_save_report(exp, store, args, ckpt_load_info=None, run_note=None) -> int:
    gens_before = exp.generation
    run = exp.advance(args.generations or exp.cfg.gens_per_run,
                      time_budget_s=getattr(args, "time_budget_s", None), run_note=run_note)
    print(f"advanced {gens_before} -> {exp.generation} generations in {run['wall_s']}s (cpu {run['cpu_s']}s)")
    payload = exp.payload()
    extra = {}
    if getattr(args, "scheduled", False):
        extra["last_scheduled_local_date"] = datetime.now(ZoneInfo("Europe/Riga")).date().isoformat()
    entry = store.save(payload, {"generation": exp.generation, "total_evals": exp.total_evals,
                                 "config_hash": exp.cfg.identity_hash(), "code_revision": payload["meta"]["code_revision"]}, extra)
    # resume test: reload what was written and verify it is bit-identical to the in-memory state
    reloaded = store.load_latest()
    exp2 = Experiment.from_payload(reloaded.payload, exp.cfg)
    equal = state_hash(exp2.payload()["runners"]) == state_hash(payload["runners"])
    resume_test = {"loaded_from_version": (ckpt_load_info or {}).get("version"), "gens_before": gens_before,
                   "saved_version": entry["version"], "reload_roundtrip_identical": equal, "generation_after_reload": exp2.generation}
    if not equal:
        print("ERROR: checkpoint round trip is not identical", file=sys.stderr)
        return 6
    info = _info(entry, (ckpt_load_info or {}).get("problems"))
    if not exp.is_full:
        # a shard holds only some seeds: statistics over seeds are meaningless here, so write a small status file only
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "shard.json").write_text(json.dumps({
            "seeds": exp.seeds, "generation": exp.generation, "total_evals": exp.total_evals, "checkpoint": info,
            "resume_test": resume_test, "note": "shard of a larger experiment; run `flyfoundry merge` to build the report"},
            indent=1), encoding="utf-8")
        print(f"checkpoint v{entry['version']} saved ({entry['bytes']:,} bytes); shard seeds {exp.seeds[0]}..{exp.seeds[-1]}")
        return 0
    _write_outputs(exp, Path(args.out), info, resume_test)
    print(f"checkpoint v{entry['version']} saved ({entry['bytes']:,} bytes); report written to {args.out}")
    return 0


def cmd_fresh(args) -> int:
    cfg = _cfg(args)
    store = CheckpointStore(args.state_dir, cfg.checkpoints_keep)
    if store.exists() and not args.overwrite:
        print("state directory already holds a checkpoint; use `resume`, or pass --overwrite to start a new experiment", file=sys.stderr)
        return 2
    return _advance_save_report(_new_experiment(cfg, args), store, args, run_note={"mode": "fresh"})


def cmd_resume(args, allow_fresh=False) -> int:
    cfg = _cfg(args)
    store = CheckpointStore(args.state_dir, cfg.checkpoints_keep)
    try:
        loaded = store.load_latest()
    except CheckpointMissing as e:
        if not allow_fresh:
            raise
        print(f"NOTICE: {e}; --allow-fresh given, starting experiment from generation 0")
        return _advance_save_report(_new_experiment(cfg, args), store, args, run_note={"mode": "fresh (explicitly allowed)"})
    if loaded.recovered:
        print("WARNING: newest checkpoint(s) invalid, recovered from older one:", *loaded.problems, sep="\n  ")
    exp = Experiment.from_payload(loaded.payload, cfg)
    sh = _parse_shard(args)
    want = shard_seeds(cfg.n_seeds, *sh) if sh else list(range(cfg.n_seeds))
    if exp.seeds != want:
        raise CheckpointCorrupt(f"state directory holds seeds {exp.seeds[0]}..{exp.seeds[-1]} ({len(exp.seeds)}), "
                                f"but this invocation asks for {want[0]}..{want[-1]} ({len(want)}); refusing to mix shards")
    print(f"restored checkpoint v{loaded.entry['version']} at generation {exp.generation} ({exp.total_evals:,} evals)")
    if exp.generation >= exp.cfg.max_total_generations:
        print("experiment already at max_total_generations; regenerating report only")
        info = _info(loaded.entry, loaded.problems)
        _write_outputs(exp, Path(args.out), info, {"note": "no new generations (experiment complete)"})
        return 0
    return _advance_save_report(exp, store, args, _info(loaded.entry, loaded.problems), {"mode": "resume"})


def cmd_run(args) -> int:
    if args.overwrite_state:
        if not args.allow_fresh:
            print("--overwrite-state requires --allow-fresh", file=sys.stderr)
            return 2
        for f in Path(args.state_dir).glob("ckpt_*.json.gz"):
            f.unlink()
        mp = Path(args.state_dir) / "manifest.json"
        if mp.exists():
            mp.unlink()
        print("NOTICE: previous state removed by explicit --overwrite-state; starting a NEW experiment")
    return cmd_resume(args, allow_fresh=args.allow_fresh)


def cmd_merge(args) -> int:
    """Combine shard state directories into one full experiment checkpoint and write the report."""
    payloads, infos = [], []
    for d in args.shard_dir:
        loaded = CheckpointStore(d).load_latest()
        if loaded.recovered:
            print(f"WARNING: {d}: newest checkpoint(s) invalid, recovered from older one:", *loaded.problems, sep="\n  ")
        payloads.append(loaded.payload)
        infos.append(_info(loaded.entry, loaded.problems))
    exp = Experiment.merge(payloads)
    store = CheckpointStore(args.state_dir)
    if store.exists() and not args.overwrite:
        print("merge target already holds a checkpoint; pass --overwrite to replace it", file=sys.stderr)
        return 2
    payload = exp.payload()
    entry = store.save(payload, {"generation": exp.generation, "total_evals": exp.total_evals,
                                 "config_hash": exp.cfg.identity_hash(), "code_revision": payload["meta"]["code_revision"]},
                       {"merged_from_shards": len(payloads)})
    exp2 = Experiment.from_payload(store.load_latest().payload, exp.cfg)
    if state_hash(exp2.payload()["runners"]) != state_hash(payload["runners"]):
        print("ERROR: merged checkpoint round trip is not identical", file=sys.stderr)
        return 6
    info = _info(entry)
    _write_outputs(exp, Path(args.out), info, {"note": f"merged from {len(payloads)} shards", "shards": infos,
                                               "reload_roundtrip_identical": True})
    print(f"merged {len(payloads)} shards ({len(exp.seeds)} seeds, generation {exp.generation}, {exp.total_evals:,} evals); "
          f"checkpoint v{entry['version']} saved; report written to {args.out}")
    return 0


def cmd_report(args) -> int:
    cfg = _cfg(args)
    store = CheckpointStore(args.state_dir, cfg.checkpoints_keep)
    loaded = store.load_latest()
    exp = Experiment.from_payload(loaded.payload)
    _write_outputs(exp, Path(args.out), _info(loaded.entry, loaded.problems), {"note": "report regenerated from checkpoint"})
    print(f"report written to {args.out}")
    return 0


def cmd_validate(args) -> int:
    rep = CheckpointStore(args.state_dir).validate()
    print(json.dumps(rep.to_dict(), indent=1))
    return 0 if rep.ok else 3


def cmd_export(args) -> int:
    store = CheckpointStore(args.state_dir)
    loaded = store.load_latest()
    exp = Experiment.from_payload(loaded.payload)
    _write_outputs(exp, Path(args.out), _info(loaded.entry, loaded.problems), {"note": "export"})
    print(f"exported results.json, history.csv, hypotheses.json, summary.md, index.html to {args.out}")
    return 0


def cmd_guard(args) -> int:
    """For scheduled runs: allow only inside --window (local hours, inclusive) and only once per local date."""
    now = datetime.now(ZoneInfo(args.tz))
    lo, hi = (int(x) for x in args.window.split("-"))
    if not (lo <= now.hour <= hi):
        print(f"skip: local time {now:%H:%M} outside window {lo}-{hi}h")
        return 10
    last = CheckpointStore(args.state_dir).read_manifest_extra().get("last_scheduled_local_date")
    if last == now.date().isoformat():
        print(f"skip: scheduled run already completed for local date {last}")
        return 10
    print(f"run: local time {now:%Y-%m-%d %H:%M} ({args.tz})")
    return 0


def cmd_smoke(args) -> int:
    """Fast end-to-end self-check: tiny experiment, checkpoint round trip, resume determinism, report."""
    base = ExperimentConfig().with_overrides(n_seeds=2, pop_size=20, survivors=6, elites=2, gens_per_run=4)
    cfg = ExperimentConfig.from_dict({**base.to_dict(), "pop_size": 20, "survivors": 6, "elites": 2})
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        a = Experiment(cfg); a.advance(4, log=lambda *_: None); a.advance(4, log=lambda *_: None)
        b = Experiment(cfg); b.advance(8, log=lambda *_: None)
        h_a = state_hash({k: r.get_state()["arm"] for k, r in a.runners.items()})
        h_b = state_hash({k: r.get_state()["arm"] for k, r in b.runners.items()})
        store = CheckpointStore(td / "state")
        store.save(a.payload(), {"generation": a.generation, "total_evals": a.total_evals})
        c = Experiment.from_payload(store.load_latest().payload, cfg); c.advance(4, log=lambda *_: None)
        d = Experiment(cfg); d.advance(12, log=lambda *_: None)
        h_c = state_hash({k: r.get_state()["arm"] for k, r in c.runners.items()})
        h_d = state_hash({k: r.get_state()["arm"] for k, r in d.runners.items()})
        checks = {"deterministic_rerun": h_a == h_b, "resume_equals_uninterrupted": h_c == h_d,
                  "budget_matched": len({r.evaluator.n_evals for r in c.runners.values()}) == 1,
                  "validate_ok": store.validate().ok}
        _write_outputs(c, td / "report", {"version": 1, "sha256": "smoke"}, {"note": "smoke"})
        checks["report_written"] = (td / "report" / "index.html").stat().st_size > 10_000
    print(json.dumps(checks, indent=1))
    return 0 if all(checks.values()) else 6


def build_parser():
    p = argparse.ArgumentParser(prog="flyfoundry")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp, state=True, out=True, run=False):
        sp.add_argument("--config")
        if state:
            sp.add_argument("--state-dir", default="state")
        if out:
            sp.add_argument("--out", default="reports/latest")
        if run:
            sp.add_argument("--generations", type=int)
            sp.add_argument("--seeds", type=int)
            sp.add_argument("--pop-size", type=int)
            sp.add_argument("--time-budget-s", type=float)
            sp.add_argument("--scheduled", action="store_true")
            sp.add_argument("--shard", help="i/N: run only shard i (0-based) of N seed blocks; combine later with `merge`")
    sp = sub.add_parser("smoke"); sp.set_defaults(fn=cmd_smoke)
    sp = sub.add_parser("fresh", help="start a new benchmark experiment"); common(sp, run=True)
    sp.add_argument("--overwrite", action="store_true"); sp.set_defaults(fn=cmd_fresh)
    sp = sub.add_parser("resume", help="continue from the latest valid checkpoint (fails if none)"); common(sp, run=True); sp.set_defaults(fn=cmd_resume)
    sp = sub.add_parser("run", help="resume; start fresh only with --allow-fresh"); common(sp, run=True)
    sp.add_argument("--allow-fresh", action="store_true")
    sp.add_argument("--overwrite-state", action="store_true", help="discard existing state first (needs --allow-fresh)")
    sp.set_defaults(fn=cmd_run)
    sp = sub.add_parser("merge", help="merge shard state directories into one full experiment"); common(sp)
    sp.add_argument("--shard-dir", action="append", required=True, help="state directory of one shard (repeat for each shard)")
    sp.add_argument("--overwrite", action="store_true"); sp.set_defaults(fn=cmd_merge)
    sp = sub.add_parser("report", help="regenerate the HTML dashboard from the latest checkpoint"); common(sp); sp.set_defaults(fn=cmd_report)
    sp = sub.add_parser("validate", help="validate checkpoint integrity"); sp.add_argument("--state-dir", default="state"); sp.set_defaults(fn=cmd_validate)
    sp = sub.add_parser("export", help="export results.json/history.csv/hypotheses.json"); common(sp); sp.set_defaults(fn=cmd_export)
    sp = sub.add_parser("islands", help="v0.2 E2: island model vs single pool (one shard of repeats)")
    sp.add_argument("--config", default=None); sp.add_argument("--out", default="e2_out")
    sp.add_argument("--repeats", type=int, default=30); sp.add_argument("--generations", type=int, default=60)
    sp.add_argument("--shard", default=None); sp.add_argument("--arms", nargs="+", default=["B_evolved_ann", "C_genetic"])
    sp.set_defaults(fn=cmd_islands)
    sp = sub.add_parser("probe", help="Phase 1: run free public-API probes (network)")
    sp.add_argument("--ideas", default="data/ideas.csv"); sp.add_argument("--cache", required=True)
    sp.add_argument("--sources", nargs="+", default=["hn", "github", "stackexchange"]); sp.add_argument("--max-requests", type=int, default=3000)
    sp.set_defaults(fn=cmd_probe)
    sp = sub.add_parser("calibrate", help="Phase 1: calibrate layer F against the H01-H12 reference (offline)")
    sp.add_argument("--facts", required=True); sp.add_argument("--compare", default=None)
    sp.add_argument("--reference", default="data/calibration_reference.csv"); sp.add_argument("--out", default="reports/phase1")
    sp.set_defaults(fn=cmd_calibrate)
    sp = sub.add_parser("schedule-guard"); sp.add_argument("--state-dir", default="state")
    sp.add_argument("--tz", default="Europe/Riga"); sp.add_argument("--window", default="1-3"); sp.set_defaults(fn=cmd_guard)
    return p


def cmd_islands(args) -> int:
    """v0.2 E2: one shard of swarm repeats (island model vs single pool). Writes e2_shard_<i>.json."""
    import time
    from ..environments.benchmark import BenchmarkWorld
    from ..research import islands as isl
    from ..research.tournament import final_tournament
    cfg = _cfg(args)
    if cfg.drift_amp > 0:
        raise SystemExit("E2 is defined for the stationary world only")
    i, n = _parse_shard(args) or (0, 1)
    reps = shard_seeds(args.repeats, i, n)
    world = BenchmarkWorld(cfg)
    rows, t0 = [], time.time()
    for rep in reps:
        for arm in args.arms:
            for cond in ("islands_mig", "islands_nomig", "single_pool"):
                if cond == "single_pool":
                    pops = isl.run_pool(arm, cfg, world, rep, args.generations)
                else:
                    pops = isl.run_islands(arm, cfg, world, rep, args.generations, migrate=cond == "islands_mig")
                rows.append({"rep": int(rep), "arm": arm, "condition": cond, **final_tournament(pops, world)})
            print(f"rep {rep} {arm} done ({time.time() - t0:.0f}s)", flush=True)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    payload = {"config_hash": cfg.identity_hash(), "world_fingerprint": world.fingerprint(), "generations": args.generations,
               "repeats": args.repeats, "shard": [i, n], "n_islands": isl.N_ISLANDS, "migrate_every": isl.MIGRATE_EVERY,
               "n_migrants": isl.N_MIGRANTS, "pool_factor": isl.POOL_FACTOR, "rows": rows}
    (out / f"e2_shard_{i}.json").write_text(json.dumps(payload))
    return 0


def cmd_probe(args) -> int:
    """Phase 1 layer F: run the free public-API probes (live network; meant for GitHub Actions). Resumable via the cache."""
    from ..phase1 import probes
    ideas = probes.load_ideas(args.ideas)
    cache = probes.ProbeCache(args.cache)
    facts = probes.run_probes(ideas, cache, sources=tuple(args.sources), max_requests=args.max_requests)
    st = {}
    for f in facts:
        st[f["status"]] = st.get(f["status"], 0) + 1
    print(json.dumps({"ideas": len(ideas), "facts": len(facts), "status": st, "cache": str(args.cache)}))
    return 0


def cmd_calibrate(args) -> int:
    """Phase 1 calibration of the automated layer-F score against the manual H01-H12 verdicts (offline, from the cache)."""
    from ..phase1 import calibration, probes, scoring
    facts = list(probes.ProbeCache(args.facts).facts.values())
    scores = scoring.f_scores(facts)
    y = calibration.load_reference(args.reference)
    res = {"calibration": calibration.calibrate(scores, y), "scores": scores,
           "negative_control": calibration.calibrate(scoring.f_scores(scoring.shuffle_facts(facts, 0)), y),
           "n_facts": len(facts), "facts_ok": sum(f["status"] == "ok" for f in facts)}
    if args.compare:
        other = scoring.f_scores(list(probes.ProbeCache(args.compare).facts.values()))
        res["stability"] = calibration.stability(scores, other)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "calibration.json").write_text(json.dumps(res, indent=1))
    c, n = res["calibration"], res["negative_control"]
    L = ["## Phase 1 calibration (automated layer F vs manual H01-H12 verdicts)", "",
         f"Facts: {res['facts_ok']} ok of {res['n_facts']}. n = {c['n']} ideas.", "",
         f"**Verdict: {c['verdict']}** - Spearman rho = {c['rho']:+.3f} (95% CI {c['ci95'][0]:+.2f}..{c['ci95'][1]:+.2f}), "
         f"one-sided permutation p = {c['p_one_sided']:.4f}; pass needs rho >= 0.5 and p <= 0.05 (n = 12: low power).", "",
         f"Negative control (probe results shuffled across ideas): rho = {n['rho']:+.3f}, p = {n['p_one_sided']:.3f}."]
    if "stability" in res:
        L += ["", f"Stability vs second run: rho = {res['stability']['rho']:+.3f} -> {res['stability']['verdict']} (needs >= 0.8)."]
    (out / "calibration.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))
    return 0


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except CheckpointError as e:
        print(f"CHECKPOINT ERROR ({type(e).__name__}): {e}", file=sys.stderr)
        _error_report(args, e)
        return e.exit_code
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        _error_report(args, e)
        return 6


def _error_report(args, e) -> None:
    out = getattr(args, "out", None)
    if not out:
        return
    try:
        Path(out).mkdir(parents=True, exist_ok=True)
        (Path(out) / "error.md").write_text(
            f"# FlyFoundry run FAILED\n\n- Error: `{type(e).__name__}: {e}`\n- No experiment state was modified after the error "
            f"(checkpoints are written atomically).\n- Recovery: run `flyfoundry validate --state-dir <dir>`; a missing state "
            f"is never silently replaced by a fresh start.\n", encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    sys.exit(main())
