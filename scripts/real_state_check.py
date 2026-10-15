"""Restore a copy of a REAL stored state (written by earlier code), run the real CLI against a replay of the REAL Devpost list pages that are
stored in that state (with three deliberate mutations: one prize and one deadline disappear, one record disappears), and report what happened.
Usage: python scripts/real_state_check.py <state_dir_with_bounty.sqlite3> <work_dir> <out.json>"""
import json, shutil, sqlite3, sys, hashlib
from pathlib import Path
sys.path.insert(0, "."); sys.path.insert(0, "tests")
from _bounty_common import fetcher
from flyfoundry.bounty_factory import cli as C
from flyfoundry.bounty_factory.store import Store, inspect_db

src, work, outp = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
state = work / "state"; shutil.copytree(src, state)
db = state / "bounty.sqlite3"
sha0 = hashlib.sha256(db.read_bytes()).hexdigest()
info0 = inspect_db(db)
raw = {}
for url, txt in sqlite3.connect(db).execute("select url, raw_text from observations where url like '%/api/hackathons%'"):
    if txt and "/api/hackathons" in url:
        raw[int(url.split("page=")[1].split("&")[0])] = json.loads(txt)
pages = [raw[k] for k in sorted(raw)]
n_before = info0['opportunities']             # never open the input with Store(): that would migrate it before the run
first_ids = [h["url"] for h in pages[0]["hackathons"]]
pages[0]["hackathons"][0]["prize_amount"] = None
pages[0]["hackathons"][1]["submission_period_dates"] = None
dropped = pages[-1]["hackathons"].pop()
pages[-1]["meta"]["total_count"] -= 1
mut = {"prize_removed": pages[0]["hackathons"][0]["url"], "deadline_removed": pages[0]["hackathons"][1]["url"], "record_dropped": dropped["url"]}
from _bounty_common import make_transport
t = make_transport(pages)
C.Fetcher = lambda **kw: fetcher(t)
(work / "reviews.json").write_text('{"reviews": []}'); (work / "manual.json").write_text('{"entries": []}')
rc = C.main_bounty(["run", "--state-dir", str(state), "--out", str(work / "out"), "--reviews", str(work / "reviews.json"), "--manual", str(work / "manual.json"), "--now", "2026-10-16T09:00:00Z", "--no-detail"])
s = Store(db)
from flyfoundry.bounty_factory.model import stable_id
after = {o.id: o for o in s.all()}
def f(o, n): x = o.fact(n); return {"known": x.known(), "value": x.value, "status": x.status, "origin": x.origin, "last_value": x.last_value, "history": [h["end"] for h in x.history]}
rep = {"input_state": {"sha256": sha0, "inspect": info0}, "exit_code": rc, "mutations": mut, "records_before": n_before, "records_after": len(after),
       "prize_removed": f(after[stable_id(mut["prize_removed"])], "prize_amount"), "deadline_removed": f(after[stable_id(mut["deadline_removed"])], "deadline_date"),
       "dropped_record_status": after[stable_id(mut["record_dropped"])].status, "unchanged_record_prize": f(after[stable_id(first_ids[2])], "prize_amount"),
       "facts_without_origin_after": sum(1 for o in after.values() for x in o.facts.values() if x.known() and not x.origin),
       "db_after": inspect_db(db), "integrity": s.integrity(), "backup_present": (state / "bounty.sqlite3.premigration.bak").exists(),
       "manifest_ok": C.verify_manifest(work / "out") == [], "verify_state_exit": C.main_bounty(["verify-state", "--state-dir", str(state)])}
json.dump(rep, open(outp, "w"), indent=1, default=str)
print(json.dumps(rep, indent=1, default=str))
