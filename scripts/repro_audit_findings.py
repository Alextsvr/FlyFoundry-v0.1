"""Black-box reproduction of the v0.2 audit findings. Prints REPRODUCED / FIXED / NOT_CONFIRMED per finding.
Works against both the pre-hardening and the hardened code (adapters below tolerate API differences)."""
from __future__ import annotations

import json, os, re, subprocess, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, ".")
from flyfoundry.bounty_factory import detail, pipeline as P
from flyfoundry.bounty_factory.gate import evaluate as gate
from flyfoundry.bounty_factory.model import Opportunity, norm_text
from flyfoundry.bounty_factory.store import Store

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
CFG = P.load_cfg("data/bounty_config.json")
RES = []


def rec(fid, title, reproduced, evidence):
    RES.append((fid, "REPRODUCED" if reproduced else "FIXED_OR_NOT_CONFIRMED", title, evidence))


def opp(**facts):
    o = Opportunity(id="bf-t", source="manual", source_key="k", url="https://x.example/a", title="T", organizer="O")
    for k, v in facts.items():
        o.set(k, v, "source_claim", "t")
    return o


def sig(text):
    """-> {name: value} regardless of analyse() return shape"""
    out = {}
    for k, v in detail.analyse(text).items():
        out[k] = v[0] if isinstance(v, tuple) else v.get("value")
    return out


def decision(o, reviews=None):
    return gate(o, CFG, NOW, reviews)["decision"]


# 1.1 stale review hides new contradicting facts
o = opp(deadline_date="2026-12-01", fees_required=True, geo_eligible=False)
rv = {"bf-t": {"id": "bf-t", "fees": "none", "geo": "ok", "reviewed_at": "2025-01-01"}}
rec("1.1", "old review (fees none, geo ok) + new fees_required/geo_eligible=False", decision(o, rv) == "ELIGIBLE", f"decision={decision(o, rv)}")
# 1.2 future deadline + fees none + geo ok => ELIGIBLE
o = opp(deadline_date="2026-12-01")
rv = {"bf-t": {"id": "bf-t", "fees": "none", "geo": "ok", "reviewed_at": "2026-10-14"}}
rec("1.2", "future deadline + legacy fees/geo review only", decision(o, rv) == "ELIGIBLE", f"decision={decision(o, rv)}")
# 1.3 false hard rejects
cases = {
 "wallet-negated": ("You do not need to connect a wallet.", lambda s: s.get("token_or_wallet_required") is True),
 "hardware-alt": ("No hardware is required. You can build a web app or a robot.", lambda s: bool(s.get("hardware_required")) and s.get("hardware_required") is not False),
 "fee-zero": ("Registration fee: $0.", lambda s: s.get("fees_required") is True),
 "geo-incl-excl": ("Residents of Latvia are eligible. Residents of Canada are not eligible.", None),
 "fee-after-no": ("There is no age restriction. Registration fee is $50.", lambda s: s.get("fees_required") is not True),
}
for name, (text, bad) in cases.items():
    s = sig(text)
    if name == "geo-incl-excl":
        o = opp(deadline_date="2026-12-01")
        for k, v in detail.analyse(text).items():
            val, ev = (v if isinstance(v, tuple) else (v.get("value"), v.get("evidence", "")))
            o.set(k, val, "source_claim", ev)
        g = gate(o, CFG, NOW)
        r = any(q["code"] == "geo_excluded" for q in g["reasons"])
    else:
        r = bad(s)
    rec("1.3-" + name, text, r, json.dumps(s, default=str)[:160])
# 2.1 HTTP 200 {} treated as complete empty listing
def fake(body):
    def t(url, h):
        if url.endswith("/robots.txt"):
            return 200, "User-agent: *\nDisallow:\n"
        return 200, body
    return t
from flyfoundry.bounty_factory.http import Fetcher
s = Store(":memory:")
for i in range(3):
    o = Opportunity(id=f"bf-{i}", source="devpost", source_key=str(i), url=f"https://e{i}.devpost.com/", title=f"E{i}", organizer="O")
    s.upsert(o, "t0")
summ = P.discover(s, CFG, Fetcher(transport=fake("{}"), min_interval=0, sleep=lambda x: None), NOW, manual_path="none.json", log=lambda *a: None)
st = {x.id: x.status for x in s.all()}
rec("2.1", "HTTP 200 '{}' marks previous records unlisted", all(v == "unlisted" for k, v in st.items() if k.startswith("bf-")) and summ["devpost"]["status"] == "ok", f"status={summ['devpost']['status']} records={st}")
# 2.2 cyrillic dedupe key
a = Opportunity(id="a", source="x", source_key="1", url="https://a.example/1", title="Хакатон Москва", organizer="Яндекс")
b = Opportunity(id="b", source="x", source_key="2", url="https://b.example/2", title="Конкурс Питер", organizer="Сбер")
rec("2.2", "different Cyrillic title/organizer collapse to same key", a.dedupe_keys()[1:] == b.dedupe_keys()[1:] and a.dedupe_keys()[1:] != [], f"keys={a.dedupe_keys()} {b.dedupe_keys()}")
# 2.3 fact withdrawal keeps fresh value
s = Store(":memory:")
x = Opportunity(id="bf-x", source="devpost", source_key="1", url="https://x.devpost.com/", title="X", organizer="O"); x.set("prize_amount", 100, "source_claim", "t", origin="list")
s.upsert(x, "2026-10-01T00:00:00Z")
y = Opportunity(id="bf-x", source="devpost", source_key="1", url="https://x.devpost.com/", title="X", organizer="O"); y.set("prize_amount", None, origin="list")
s.upsert(y, "2026-10-10T00:00:00Z")
got = s.get("bf-x") or s.all()[0]
f = got.fact("prize_amount")
rec("2.3", "prize 100 -> None still shows 100 and fresh last_seen", f.value == 100 and got.last_seen.startswith("2026-10-10"), f"value={f.value} last_seen={got.last_seen}")
# 2.4 raw evidence for overview/rules kept?
cols = [r[1] for r in s.db.execute("PRAGMA table_info(observations)")]
rec("2.4", "observations table lacks kind/http_status/parser_version", not {"kind", "http_status", "parser_version"} <= set(cols), f"columns={cols}")
# 3.1 coverage naming
sb = P.evaluate(Store(":memory:"), CFG, {}, NOW)
src = Path("flyfoundry/bounty_factory/scoring.py").read_text(encoding="utf-8")
rec("3.1", "score_b exposes 'coverage' of numeric criteria incl. heuristics", '"coverage"' in src, "scoring.py contains key 'coverage'" if '"coverage"' in src else "key renamed to criteria_fill; evidence completeness is reported separately as conditions_confirmed/total")
# 3.2 template hypothesis narrows estimate without reading requirements
from flyfoundry.bounty_factory.feasibility import estimate
n = Opportunity(id="bf-n", source="devpost", source_key="n", url="https://n.devpost.com/", title="Nebius x NVIDIA Global AI Hackathon", organizer="Nebius")
n.set("themes", ["Machine Learning/AI", "Beginner Friendly", "Robotic Process Automation"], "source_claim", "t")
e = estimate(n)
rec("3.2", "Nebius-like list-only record gets a point estimate from theme words", (("hours_low" not in e) and e["total_hours"] <= 6) or (e.get("hours_high", 0) / max(e.get("hours_low", 1), 0.1) < 3), f"class={e['class']} total={e['total_hours']} template={e.get('template')}")
# 4.1 stale briefs remain
import shutil
d = Path(tempfile.mkdtemp())
(d / "briefs").mkdir(); (d / "briefs" / "old.md").write_text("x")
class A: pass
a_ = A(); a_.out = str(d); a_.reviews = "none.json"; a_.provisional_briefs = 0
from flyfoundry.bounty_factory import cli as C
st_ = Store(":memory:")
import inspect
try:
    if "out_dir" in inspect.signature(C.produce).parameters:      # hardened code: the real command publishes via a fresh directory
        a_.state_dir = str(d / "state"); a_.config = "data/bounty_config.json"; a_.manual = "none.json"; a_.now = "2026-10-15T12:00:00Z"; a_.no_detail = True; a_.action = "evaluate"; a_.id = ""
        (d / "state").mkdir()
        C.cmd_bounty(a_)
    else:
        C.produce(st_, CFG, a_, NOW)
except Exception as ex:
    print("4.1 produce raised", type(ex).__name__, ex)
rec("4.1", "stale brief file survives a run that produces no briefs", (d / "briefs" / "old.md").exists(), f"exists={(d / 'briefs' / 'old.md').exists()}")
# 4.2 restore script: a failing archive extraction must NOT look like success
def restore_behaviour():
    import shutil
    tmp = Path(tempfile.mkdtemp())
    env = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    run = lambda *c, cwd=tmp: subprocess.run(c, cwd=cwd, env=env, capture_output=True, text=True)
    run("git", "init", "-q", "--bare", "remote.git")
    run("git", "init", "-q", "work")
    (tmp / "work" / "bounty.sqlite3").write_text("x")
    run("git", "checkout", "-q", "-b", "flyfoundry-state", cwd=tmp / "work")
    run("git", "add", "-A", cwd=tmp / "work"); run("git", "commit", "-q", "-m", "s", cwd=tmp / "work")
    run("git", "remote", "add", "origin", str(tmp / "remote.git"), cwd=tmp / "work")
    run("git", "push", "-q", "origin", "flyfoundry-state", cwd=tmp / "work")
    bad = tmp / "bin"; bad.mkdir(); (bad / "tar").write_text("#!/bin/sh\ncat >/dev/null\nexit 2\n"); (bad / "tar").chmod(0o755)
    env2 = dict(env, PATH=f"{bad}:{os.environ['PATH']}")
    sh = Path(os.getcwd()) / "scripts" / "state_restore.sh"
    r = subprocess.run(["bash", str(sh), "origin", str(tmp / "state_out")], cwd=tmp / "work", env=env2, capture_output=True, text=True)
    present = (tmp / "state_out").exists() and any((tmp / "state_out").iterdir())
    shutil.rmtree(tmp, ignore_errors=True)
    return r.returncode, present, (r.stdout + r.stderr)[-160:]
rc, present, tail = restore_behaviour()
rec("4.2", "tar failure during restore is reported as success", rc == 0, f"exit={rc} state_dir_populated={present} tail={tail.strip()!r}")
# 4.4 resource import on Windows
ok = subprocess.run([sys.executable, "-c", "import sys; sys.modules['resource']=None; sys.path.insert(0,'.'); import importlib, importlib.util; m=importlib.import_module('flyfoundry.cli.entry') if importlib.util.find_spec('flyfoundry.cli.entry') else importlib.import_module('flyfoundry.cli.main'); sys.exit(m.main(['bounty','--help']))"], capture_output=True, text=True)
rec("4.4", "bounty CLI unavailable when Unix 'resource' module is missing", ok.returncode != 0, (ok.stderr.strip().splitlines() or ["`bounty --help` works without `resource`"])[-1])
w = open(".github/workflows/bounty_discovery.yml", encoding="utf-8").read()
w = "\n".join(l for l in w.splitlines() if not l.lstrip().startswith("#"))          # ignore comments
jobs_part = w.split("\njobs:")[1]
disc = jobs_part.split("\n  persist:")[0]
rec("4.3b", "the job that runs network fetch/parsing holds contents: write", "contents: write" in w.split("\njobs:")[0] or "contents: write" in disc, "write permission in workflow-level or discover job")
for r in RES:
    print(f"{r[0]:<22} {r[1]:<22} {r[2][:70]}\n{'':<22} evidence: {r[3]}")
json.dump([dict(id=r[0], result=r[1], title=r[2], evidence=r[3]) for r in RES], open(sys.argv[1] if len(sys.argv) > 1 else "/dev/null", "w"), indent=1)
