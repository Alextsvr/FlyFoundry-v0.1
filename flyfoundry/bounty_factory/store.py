"""SQLite store. Raw observations are kept (bounded by a retention policy) as evidence; opportunity records are merged,
deduplicated and diffed; per-fact freshness and history are preserved (nothing is silently overwritten)."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .model import Opportunity, Fact, HUMAN, MAX_HISTORY, canonical_url

SCHEMA_VERSION = 3          # 2: observation evidence columns, keys rebuilt; 3: fact origin back-fill (legacy facts without origin)
RAW_CAP = 400_000          # bytes of raw text stored per observation (hash always covers the full text)
SCHEMA = """
CREATE TABLE IF NOT EXISTS source_runs(id INTEGER PRIMARY KEY, source TEXT, started_at TEXT, finished_at TEXT,
  status TEXT, http_status INTEGER, n_records INTEGER, complete INTEGER, requests INTEGER, error TEXT);
CREATE TABLE IF NOT EXISTS observations(id INTEGER PRIMARY KEY, run_id INTEGER, source TEXT, source_key TEXT, url TEXT,
  fetched_at TEXT, raw_hash TEXT, raw_text TEXT, kind TEXT, http_status INTEGER, parser_version TEXT, truncated INTEGER DEFAULT 0, pruned INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS opportunities(id TEXT PRIMARY KEY, canonical TEXT, record TEXT, first_seen TEXT, last_seen TEXT);
CREATE TABLE IF NOT EXISTS keys(key TEXT, opp_id TEXT, PRIMARY KEY(key, opp_id));
CREATE TABLE IF NOT EXISTS changes(id INTEGER PRIMARY KEY, opp_id TEXT, at TEXT, field TEXT, old TEXT, new TEXT);
"""
NO_LOG = {"description_text"}


def _parse(ts: str):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


LIST_FACTS = {"prize_amount", "prize_currency", "prize_count", "deadline_date", "deadline_precision", "deadline_tz", "location", "invite_only",
              "themes", "registrations_count", "submission_method"}
APP_TABLES = {
    "source_runs": {"id", "source", "started_at", "finished_at", "status", "n_records", "complete", "error"},
    "observations": {"id", "run_id", "source", "source_key", "url", "fetched_at", "raw_hash", "raw_text"},
    "opportunities": {"id", "canonical", "record", "first_seen", "last_seen"},
    "keys": {"key", "opp_id"},
    "changes": {"id", "opp_id", "at", "field", "old", "new"},
}
OBS_V2_COLS = {"kind", "http_status", "parser_version", "truncated", "pruned"}


def backfill_origins(o: Opportunity) -> int:
    """Legacy facts (written before `origin` existed) get their origin from what the record itself proves:
    list facts carry 'Devpost list API' evidence, manual/human facts come from their basis. A legacy detail-page value whose page
    (overview vs rules), observation and date cannot be established is NOT kept as a current fact: it becomes status
    'historical_unverified' (value moved to last_value, history entry added) and takes no part in eligibility or ranking.
    Nothing is invented: observed_at/observation_id are left as they were. Returns the number of facts touched."""
    n = 0
    for name, f in list(o.facts.items()):
        if f.origin:
            continue
        origin = ""
        if f.basis in HUMAN:
            origin = "manual" if o.source == "manual" else "human"
        elif o.source == "devpost" and ((f.evidence or "").startswith("Devpost list API") or (name in LIST_FACTS and (f.basis == "unknown" or "list gives a calendar date" in (f.evidence or "")))):
            origin = "list"
        elif o.source == "manual":
            origin = "manual"
        if origin:
            f.origin = origin
            n += 1
        elif f.known():
            f.history = (f.history + [{"value": f.value, "basis": f.basis, "evidence": (f.evidence or "")[:200], "from": f.changed_at or f.observed_at, "to": "", "end": "historical_unverified"}])[-MAX_HISTORY:]
            f.last_value, f.value, f.status, f.origin = f.value, None, "historical_unverified", "legacy_unverified"
            n += 1
        else:
            f.origin = "legacy_unverified"
    return n


def inspect_db(path) -> dict:
    """READ-ONLY inspection of an existing state database (never creates, migrates or repairs anything).
    status: absent | empty_file | not_sqlite | corrupt | foreign | incomplete | invalid_records | newer | legacy | current.
    legacy = a valid older version that needs migration; current = ready to use. Only legacy/current are usable."""
    p = Path(path)
    r = {"status": "absent", "version": None, "problems": [], "opportunities": 0, "bytes": 0}
    if not p.exists():
        return r
    r["bytes"] = p.stat().st_size
    if r["bytes"] == 0:
        r.update(status="empty_file", problems=["bounty.sqlite3 is empty (0 bytes)"])
        return r
    with open(p, "rb") as fh:
        if fh.read(16) != b"SQLite format 3\x00":
            r.update(status="not_sqlite", problems=["file is not an SQLite database"])
            return r
    try:
        db = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True)
    except sqlite3.Error as e:
        r.update(status="corrupt", problems=[f"cannot open read-only: {e}"])
        return r
    try:
        res = [x[0] for x in db.execute("PRAGMA integrity_check").fetchall()]
        if res != ["ok"]:
            r.update(status="corrupt", problems=["integrity_check: " + "; ".join(res[:3])])
            return r
        ver = db.execute("PRAGMA user_version").fetchone()[0]
        r["version"] = ver
        have = {t[0] for t in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not (have & set(APP_TABLES)):
            r.update(status="foreign", problems=["no Bounty Factory tables: not a state database"])
            return r
        probs = []
        for t, cols in APP_TABLES.items():
            if t not in have:
                probs.append(f"missing table {t}")
                continue
            got = {c[1] for c in db.execute(f"PRAGMA table_info({t})")}
            if cols - got:
                probs.append(f"table {t} lacks columns {sorted(cols - got)}")
            if t == "observations" and ver >= 2 and OBS_V2_COLS - got:
                probs.append(f"observations lacks columns {sorted(OBS_V2_COLS - got)}")
        if probs:
            r.update(status="incomplete", problems=probs)
            return r
        if ver > SCHEMA_VERSION:
            r.update(status="newer", problems=[f"database version {ver} is newer than this code ({SCHEMA_VERSION})"])
            return r
        n = bad = 0
        for (rec,) in db.execute("SELECT record FROM opportunities"):
            n += 1
            try:
                d = json.loads(rec)
                if not isinstance(d, dict) or not d.get("id") or not isinstance(d.get("facts", {}), dict):
                    bad += 1
            except ValueError:
                bad += 1
        r["opportunities"] = n
        if bad:
            r.update(status="invalid_records", problems=[f"{bad} of {n} opportunity records are not valid"])
            return r
        r["status"] = "current" if ver == SCHEMA_VERSION else "legacy"
        return r
    except sqlite3.Error as e:
        r.update(status="corrupt", problems=[f"{type(e).__name__}: {e}"])
        return r
    finally:
        db.close()


USABLE = ("legacy", "current")


def migrate_file(path, backup_suffix: str = ".premigration.bak") -> dict:
    """Explicit, safe migration of an existing legacy database: the original is copied to a backup, the COPY is migrated and verified
    (integrity, same record count), and only then atomically replaces the original. On any failure the original is untouched."""
    p = Path(path)
    before = inspect_db(p)
    if before["status"] != "legacy":
        return {"migrated": False, "status": before["status"], "backup": None}
    bak = p.with_name(p.name + backup_suffix)
    shutil.copy2(p, bak)
    work = p.with_name(p.name + ".migrating")
    if work.exists():
        work.unlink()
    shutil.copy2(p, work)
    try:
        s = Store(work)
        probs = s.integrity()
        n = len(s.all())
        s.close()
        if probs or n != before["opportunities"]:
            raise RuntimeError(f"migration check failed: problems={probs} records {before['opportunities']}->{n}")
        after = inspect_db(work)
        if after["status"] != "current":
            raise RuntimeError(f"migrated copy is not current: {after}")
        os.replace(work, p)
    except Exception:
        if work.exists():
            work.unlink()
        raise
    return {"migrated": True, "from_version": before["version"], "to_version": SCHEMA_VERSION, "records": n, "backup": str(bak)}


class Store:
    def __init__(self, path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.duplicates_merged = 0
        self.possible_duplicates_flagged = 0
        self.raw_records_seen = 0
        self._migrate()

    def _migrate(self):
        ver = self.db.execute("PRAGMA user_version").fetchone()[0]
        has_obs = self.db.execute("SELECT 1 FROM sqlite_master WHERE name='observations'").fetchone()
        if ver < 2 and self.db.execute("SELECT 1 FROM sqlite_master WHERE name='keys'").fetchone():
            self.db.execute("DROP TABLE keys")          # old single-id key table; rebuilt below with the corrected normalization
        self.db.executescript(SCHEMA)
        if has_obs:
            cols = {r[1] for r in self.db.execute("PRAGMA table_info(observations)")}
            for name, ddl in (("kind", "TEXT"), ("http_status", "INTEGER"), ("parser_version", "TEXT"), ("truncated", "INTEGER DEFAULT 0"), ("pruned", "INTEGER DEFAULT 0")):
                if name not in cols:
                    self.db.execute(f"ALTER TABLE observations ADD COLUMN {name} {ddl}")
            self.db.execute("UPDATE observations SET kind='list' WHERE kind IS NULL AND source='devpost'")
        if ver < SCHEMA_VERSION:
            for o in self.all():
                backfill_origins(o)
                self._write(o)
            self.db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        self.db.commit()

    def close(self):
        self.db.commit()
        self.db.close()

    # ---- runs / observations
    def start_run(self, source: str, now: str) -> int:
        return self.db.execute("INSERT INTO source_runs(source,started_at,status) VALUES(?,?,?)", (source, now, "running")).lastrowid

    def finish_run(self, run_id, now, status, http_status=None, n_records=0, complete=False, requests=0, error=""):
        self.db.execute("UPDATE source_runs SET finished_at=?,status=?,http_status=?,n_records=?,complete=?,requests=?,error=? WHERE id=?",
                        (now, status, http_status, n_records, int(complete), requests, error[:500], run_id))
        self.db.commit()

    def add_observation(self, run_id, source, source_key, url, fetched_at, raw_text, kind="list", http_status=None, parser_version="") -> int:
        raw = raw_text or ""
        h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        trunc = int(len(raw) > RAW_CAP)
        return self.db.execute("INSERT INTO observations(run_id,source,source_key,url,fetched_at,raw_hash,raw_text,kind,http_status,parser_version,truncated) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                               (run_id, source, source_key, url, fetched_at, h, raw[:RAW_CAP], kind, http_status, parser_version, trunc)).lastrowid

    def observation(self, obs_id):
        r = self.db.execute("SELECT id,source,url,fetched_at,raw_hash,kind,http_status,parser_version,truncated,pruned FROM observations WHERE id=?", (obs_id,)).fetchone()
        return dict(zip(("id", "source", "url", "fetched_at", "raw_hash", "kind", "http_status", "parser_version", "truncated", "pruned"), r)) if r else None

    def raw(self, obs_id):
        """Stored raw response text of an observation (None if pruned by the retention policy; the hash stays)."""
        r = self.db.execute("SELECT raw_text FROM observations WHERE id=?", (obs_id,)).fetchone()
        return r[0] if r else None

    def last_runs(self) -> dict:
        rows = self.db.execute("SELECT source,started_at,finished_at,status,http_status,n_records,complete,requests,error FROM source_runs "
                               "WHERE id IN (SELECT MAX(id) FROM source_runs GROUP BY source)").fetchall()
        keys = ("source", "started_at", "finished_at", "status", "http_status", "n_records", "complete", "requests", "error")
        return {r[0]: dict(zip(keys, r)) for r in rows}

    def last_ok_run(self, source: str):
        r = self.db.execute("SELECT finished_at FROM source_runs WHERE source=? AND status='ok' AND complete=1 ORDER BY id DESC LIMIT 1", (source,)).fetchone()
        return r[0] if r else None

    # ---- lookup
    def find_strong(self, opp: Opportunity):
        r = self.db.execute("SELECT opp_id FROM keys WHERE key=?", ("u:" + canonical_url(opp.url),)).fetchone()
        return r[0] if r else None

    def find_candidates(self, opp: Opportunity) -> list:
        ks = [k for k in opp.dedupe_keys() if k.startswith("t:")]
        if not ks:
            return []
        return [r[0] for r in self.db.execute("SELECT opp_id FROM keys WHERE key=?", (ks[0],)).fetchall()]

    def find(self, opp: Opportunity):
        return self.find_strong(opp)

    def get(self, opp_id: str):
        r = self.db.execute("SELECT record FROM opportunities WHERE id=?", (opp_id,)).fetchone()
        return Opportunity.from_dict(json.loads(r[0])) if r else None

    def all(self) -> list:
        return [Opportunity.from_dict(json.loads(r[0])) for r in self.db.execute("SELECT record FROM opportunities ORDER BY id")]

    def _log(self, opp_id, now, fld, old, new):
        if fld in NO_LOG:
            return
        self.db.execute("INSERT INTO changes(opp_id,at,field,old,new) VALUES(?,?,?,?,?)", (opp_id, now, fld, json.dumps(old, default=str), json.dumps(new, default=str)))

    # ---- fact merge (per-fact freshness, history, human protection)
    def _apply(self, old: Opportunity, newfacts: dict, origins: set, now: str, fill_only: bool = False) -> list:
        changed = []
        names = set(newfacts) | {n for n, f in old.facts.items() if f.origin in origins}
        for name in sorted(names):
            nf, cur = newfacts.get(name), old.facts.get(name)
            nf_known = nf is not None and nf.known()
            if cur is not None and cur.basis in HUMAN and not (nf_known and nf.basis in HUMAN):
                # human facts are never overwritten or withdrawn by a source; a contradicting source claim is stored beside them
                if nf_known and nf.value != cur.value:
                    c = {"value": nf.value, "basis": nf.basis, "evidence": (nf.evidence or "")[:300], "strength": nf.strength, "observed_at": now, "observation_id": nf.observation_id}
                    if not any(x["value"] == c["value"] and x["evidence"] == c["evidence"] for x in cur.conflicts):
                        cur.conflicts.append(c)
                        self._log(old.id, now, "conflict:" + name, cur.value, nf.value)
                        changed.append(name)
                elif nf_known and nf.value == cur.value:
                    pass
                elif cur.origin == "manual" and "manual" in origins and cur.known():
                    self._withdraw(old, cur, name, now)
                    changed.append(name)
                continue
            if not nf_known:
                if cur is not None and cur.known() and cur.origin in origins and not fill_only:
                    self._withdraw(old, cur, name, now)
                    changed.append(name)
                elif cur is None and nf is not None:
                    old.facts[name] = nf
                continue
            if cur is None or not cur.known():
                f = Fact.from_dict(nf.to_dict())
                f.observed_at = f.changed_at = now
                if cur is not None:
                    f.history = cur.history
                old.facts[name] = f
                self._log(old.id, now, name, cur.last_value if cur is not None else None, f.value)
                changed.append(name)
            elif fill_only:
                continue
            elif cur.value == nf.value:
                cur.observed_at = now
                cur.evidence, cur.strength = nf.evidence or cur.evidence, nf.strength
                cur.observation_id = nf.observation_id if nf.observation_id is not None else cur.observation_id
                cur.parser_version = nf.parser_version or cur.parser_version
            else:
                f = Fact.from_dict(nf.to_dict())
                f.history = (cur.history + [{"value": cur.value, "basis": cur.basis, "evidence": cur.evidence[:200], "from": cur.changed_at, "to": now, "end": "changed"}])[-MAX_HISTORY:]
                f.observed_at = f.changed_at = now
                old.facts[name] = f
                self._log(old.id, now, name, cur.value, f.value)
                changed.append(name)
        return changed

    def _withdraw(self, old, cur, name, now):
        cur.history = (cur.history + [{"value": cur.value, "basis": cur.basis, "evidence": cur.evidence[:200], "from": cur.changed_at, "to": now, "end": "withdrawn"}])[-MAX_HISTORY:]
        self._log(old.id, now, name, cur.value, None)
        cur.last_value, cur.value, cur.status = cur.value, None, "withdrawn"
        cur.changed_at = now

    def apply_facts(self, opp_id: str, facts: dict, origins: set, now: str) -> list:
        """Used by the detail pass: merge facts extracted from freshly read pages (origins = pages that were read successfully)."""
        old = self.get(opp_id)
        changed = self._apply(old, facts, origins, now)
        self._write(old)
        return changed

    def set_detail_state(self, opp_id: str, page: str, state: dict, now: str):
        old = self.get(opp_id)
        old.detail[page] = state
        if state.get("ok"):
            old.detail_fetched_at = now
        self._write(old)

    # ---- upsert
    def upsert(self, new: Opportunity, now: str, obs_id: int | None = None) -> tuple:
        """Returns (opportunity_id, 'new'|'updated'|'duplicate_merged'|'unchanged').
        Identity: same canonical URL = same record. title|organizer alone is only a CANDIDATE: it merges only when both records
        have the same known deadline date; otherwise both are kept and flagged possible_duplicates."""
        self.raw_records_seen += 1
        existing_id, matched_by, possible = self.find_strong(new), "url", []
        if existing_id is None:
            for cid in self.find_candidates(new):
                other = self.get(cid)
                d1, d2 = new.fact("deadline_date"), other.fact("deadline_date")
                if d1.known() and d2.known() and d1.value == d2.value:
                    existing_id, matched_by = cid, "title+organizer+deadline"
                    break
                possible.append(cid)
        origins = {f.origin for f in new.facts.values() if f.origin}
        if existing_id is None:
            new.first_seen = new.last_seen = now
            new.status = "listed"
            for n_, f in new.facts.items():
                if f.known():
                    f.observed_at = f.changed_at = now
            if obs_id:
                new.observation_ids = [obs_id]
            for cid in possible:
                new.possible_duplicates.append(cid)
                other = self.get(cid)
                if new.id not in other.possible_duplicates:
                    other.possible_duplicates.append(new.id)
                    self._write(other)
                self._log(new.id, now, "possible_duplicate", None, cid)
                self.possible_duplicates_flagged += 1
            self._write(new)
            return new.id, "new"
        old = self.get(existing_id)
        outcome = "unchanged"
        same_ref = (old.source == new.source and old.source_key == new.source_key) or \
                   any(a.get("source") == new.source and a.get("source_key") == new.source_key for a in old.aliases)
        if not same_ref:
            old.aliases.append({"source": new.source, "source_key": new.source_key, "url": new.url, "matched_by": matched_by, "merged_at": now})
            self.duplicates_merged += 1
            outcome = "duplicate_merged"
        if self._apply(old, new.facts, origins, now, fill_only=not same_ref) and outcome == "unchanged":
            outcome = "updated"
        for fld in (("title", "organizer") if same_ref else ()):
            if getattr(new, fld) and getattr(old, fld) != getattr(new, fld):
                self._log(old.id, now, fld, getattr(old, fld), getattr(new, fld))
                setattr(old, fld, getattr(new, fld))
                if outcome == "unchanged":
                    outcome = "updated"
        if old.status != "listed":
            self._log(old.id, now, "status", old.status, "listed")
            old.status = "listed"
        old.last_seen = now
        if obs_id:
            old.observation_ids = (old.observation_ids + [obs_id])[-20:]
        self._write(old)
        return old.id, outcome

    def _write(self, o: Opportunity):
        from .model import canonical_url as cu
        self.db.execute("INSERT OR REPLACE INTO opportunities(id,canonical,record,first_seen,last_seen) VALUES(?,?,?,?,?)",
                        (o.id, o.dedupe_keys()[0], json.dumps(o.to_dict(), sort_keys=True), o.first_seen, o.last_seen))
        self.db.execute("DELETE FROM keys WHERE opp_id=?", (o.id,))
        for k in o.dedupe_keys():
            self.db.execute("INSERT OR IGNORE INTO keys(key,opp_id) VALUES(?,?)", (k, o.id))
        for a in o.aliases:
            if a.get("url"):
                self.db.execute("INSERT OR IGNORE INTO keys(key,opp_id) VALUES(?,?)", ("u:" + cu(a["url"]), o.id))
        self.db.commit()

    def mark_unlisted(self, source: str, seen_ids: set, now: str, max_fraction: float = 0.5, min_guard: int = 5) -> tuple:
        """Only call after a COMPLETE, schema-validated listing. Returns (n_marked, skipped_reason). A shrink larger than
        max(min_guard, max_fraction * previously listed) is treated as a suspicious listing and nothing is marked."""
        listed = [o for o in self.all() if o.source == source and o.status == "listed"]
        gone = [o for o in listed if o.id not in seen_ids]
        if len(gone) > max(min_guard, max_fraction * len(listed)):
            return 0, f"suspicious shrink: {len(gone)} of {len(listed)} previously listed records missing; nothing marked unlisted"
        for o in gone:
            o.status = "unlisted"
            self._log(o.id, now, "status", "listed", "unlisted")
            self._write(o)
        return len(gone), ""

    def changes_since(self, since: str) -> list:
        rows = self.db.execute("SELECT opp_id,at,field,old,new FROM changes WHERE at>=? ORDER BY at,id", (since,)).fetchall()
        return [dict(zip(("opp_id", "at", "field", "old", "new"), r)) for r in rows]

    def all_changes(self) -> list:
        return self.changes_since("")

    # ---- retention
    def prune(self, now: datetime, keep_raw_per_url: int = 2, raw_days: int = 30, meta_days: int = 180, max_changes: int = 20000) -> dict:
        """Bounded growth: old raw bodies are dropped (hash + metadata kept); unreferenced metadata older than meta_days is deleted;
        the change log is capped. Observations still referenced by a current fact/record are never deleted."""
        referenced = set()
        for o in self.all():
            referenced.update(x for x in o.observation_ids if x)
            for f in o.facts.values():
                if f.observation_id:
                    referenced.add(f.observation_id)
            for d in o.detail.values():
                if d.get("observation_id"):
                    referenced.add(d["observation_id"])
        raw_cut = (now - timedelta(days=raw_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        meta_cut = (now - timedelta(days=meta_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows = self.db.execute("SELECT id,COALESCE(kind,''),url,fetched_at FROM observations WHERE raw_text IS NOT NULL ORDER BY id DESC").fetchall()
        kept, dropped_raw = {}, 0
        for oid, kind, url, ts in rows:
            k = (kind, url)
            kept[k] = kept.get(k, 0) + 1
            if kept[k] > keep_raw_per_url and ts < raw_cut and oid not in referenced:
                self.db.execute("UPDATE observations SET raw_text=NULL, pruned=1 WHERE id=?", (oid,))
                dropped_raw += 1
        old_ids = [r[0] for r in self.db.execute("SELECT id FROM observations WHERE fetched_at<?", (meta_cut,)).fetchall() if r[0] not in referenced]
        for i in old_ids:
            self.db.execute("DELETE FROM observations WHERE id=?", (i,))
        n_ch = self.db.execute("SELECT COUNT(*) FROM changes").fetchone()[0]
        cut = 0
        if n_ch > max_changes:
            cut = n_ch - max_changes
            self.db.execute("DELETE FROM changes WHERE id IN (SELECT id FROM changes ORDER BY id LIMIT ?)", (cut,))
        self.db.commit()
        if dropped_raw or old_ids or cut:
            self.db.execute("VACUUM")
        return {"raw_dropped": dropped_raw, "observations_deleted": len(old_ids), "changes_deleted": cut}

    def integrity(self) -> list:
        """Problems found by `PRAGMA integrity_check` and basic consistency checks (empty list = ok)."""
        problems = [r[0] for r in self.db.execute("PRAGMA integrity_check").fetchall() if r[0] != "ok"]
        for t in ("source_runs", "observations", "opportunities", "keys", "changes"):
            if not self.db.execute("SELECT 1 FROM sqlite_master WHERE name=?", (t,)).fetchone():
                problems.append(f"missing table {t}")
        return problems
