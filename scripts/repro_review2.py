"""Black-box reproduction of the second independent review (P1 x3, P2). Prints REPRODUCED / NOT_REPRODUCED with evidence.
Usage: python scripts/repro_review2.py <out.json>   (run from the repo root; uses tests/fixtures/bounty_v1_state.sqlite3, a trimmed REAL v1 state)"""
import json, shutil, subprocess, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, "."); sys.path.insert(0, "tests")
from flyfoundry.bounty_factory import detail, pipeline as P
from flyfoundry.bounty_factory.gate import evaluate as gate, participant_hash, REQUIRED
from flyfoundry.bounty_factory.model import Opportunity
from flyfoundry.bounty_factory.store import Store

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
CFG = P.load_cfg("data/bounty_config.json")
RES = []
rec = lambda i, t, rep, ev: RES.append(dict(id=i, result="REPRODUCED" if rep else "NOT_REPRODUCED", title=t, evidence=ev))
tmp = Path(tempfile.mkdtemp())


def verify(d):
    r = subprocess.run([sys.executable, "-m", "flyfoundry", "bounty", "verify-state", "--state-dir", str(d)], capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()[-200:]

# P1-1 verify-state accepts / rewrites junk
d = tmp / "zero"; d.mkdir(); (d / "bounty.sqlite3").write_bytes(b"")
rc, out = verify(d)
rec("P1-1a", "0-byte bounty.sqlite3 accepted and rewritten by verify-state", rc == 0 and (d / "bounty.sqlite3").stat().st_size > 0, f"exit={rc} size_after={(d / 'bounty.sqlite3').stat().st_size}")
import sqlite3
d = tmp / "foreign"; d.mkdir(); c = sqlite3.connect(d / "bounty.sqlite3"); c.execute("create table other(x)"); c.commit(); c.close()
before = (d / "bounty.sqlite3").read_bytes()
rc, out = verify(d)
rec("P1-1b", "foreign SQLite accepted (tables added) by verify-state", rc == 0 or (d / "bounty.sqlite3").read_bytes() != before, f"exit={rc} modified={(d / 'bounty.sqlite3').read_bytes() != before}")
d = tmp / "v1"; d.mkdir(); shutil.copy("tests/fixtures/bounty_v1_state.sqlite3", d / "bounty.sqlite3")
h0 = (d / "bounty.sqlite3").read_bytes()
rc, out = verify(d)
rec("P1-1c", "verify-state modifies (migrates) the checked v1 database", (d / "bounty.sqlite3").read_bytes() != h0, f"exit={rc} modified={(d / 'bounty.sqlite3').read_bytes() != h0}")

# P1-2 migration leaves vanished facts current
d = tmp / "mig"; d.mkdir(); shutil.copy("tests/fixtures/bounty_v1_state.sqlite3", d / "bounty.sqlite3")
s = Store(d / "bounty.sqlite3")
o0 = s.all()[0]
old_prize = o0.fact("prize_amount").value
n = Opportunity(id=o0.id, source=o0.source, source_key=o0.source_key, url=o0.url, title=o0.title, organizer=o0.organizer)
n.set("prize_amount", None, origin="list"); n.set("deadline_date", None, origin="list")
s.upsert(n, "2026-10-16T00:00:00Z")
s.close()
s = Store(d / "bounty.sqlite3"); o1 = s.get(o0.id)
pa, dl = o1.fact("prize_amount"), o1.fact("deadline_date")
rec("P1-2", "after migration + update a vanished prize/deadline stays current", pa.known() or dl.known(), f"old_prize={old_prize} prize_known={pa.known()} value={pa.value} status={pa.status} origin={pa.origin!r}; deadline_known={dl.known()}")

# P1-3 false firm signals
def decide(text, extra=None):
    o = Opportunity(id="bf-t", source="manual", source_key="k", url="https://x.example/a", title="T", organizer="O")
    o.set("deadline_date", "2026-12-01", "source_claim", "t", origin="list")
    for k, v in detail.analyse(text, CFG["participant"]).items():
        o.set(k, v["value"], "source_claim", v["evidence"], strength=v["strength"], origin="rules")
    g = gate(o, CFG, NOW, {})
    return g["decision"], [r["code"] for r in g["reasons"] if r["level"] == "hard"]
for i, t in (("P1-3a", "No registration fee is required; prizes total $5000."), ("P1-3b", "Residents of Latvia are eligible; residents of Canada are not eligible."),
             ("P1-3c", "You must submit a video about how to connect a wallet.")):
    dec, hard = decide(t)
    rec(i, t, dec == "INELIGIBLE", f"decision={dec} hard={hard}")

# P2 future-dated review
o = Opportunity(id="bf-t", source="manual", source_key="k", url="https://x.example/a", title="T", organizer="O")
o.set("deadline_date", "2026-12-01", "source_claim", "t", origin="list"); o.set("location", "Online", "source_claim", "t", origin="list"); o.set("invite_only", False, "source_claim", "t", origin="list")
rv = {o.id: {"id": o.id, "schema": 2, "reviewed_at": "2099-01-01", "reviewer": "x", "evidence_url": "https://x", "rules_ref": "v1", "participant_hash": participant_hash(CFG),
             "conditions": {c: {"status": "ok", "note": "checked the official rules text"} for c in REQUIRED}}}
dec = gate(o, CFG, NOW, rv)["decision"]
rec("P2", "review dated 2099-01-01 gives ELIGIBLE on 2026-10-15", dec == "ELIGIBLE", f"decision={dec}")
for r in RES:
    print(f"{r['id']:<7} {r['result']:<15} {r['title'][:80]}\n{'':<7} evidence: {r['evidence']}")
json.dump(RES, open(sys.argv[1], "w"), indent=1)
