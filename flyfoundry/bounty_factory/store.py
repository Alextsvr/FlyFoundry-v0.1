"""SQLite store: raw observations are kept verbatim (evidence); opportunity records are merged, deduplicated and diffed."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from .model import Opportunity, Fact

SCHEMA = """
CREATE TABLE IF NOT EXISTS source_runs(id INTEGER PRIMARY KEY, source TEXT, started_at TEXT, finished_at TEXT,
  status TEXT, http_status INTEGER, n_records INTEGER, complete INTEGER, requests INTEGER, error TEXT);
CREATE TABLE IF NOT EXISTS observations(id INTEGER PRIMARY KEY, run_id INTEGER, source TEXT, source_key TEXT, url TEXT,
  fetched_at TEXT, raw_hash TEXT, raw_text TEXT);
CREATE TABLE IF NOT EXISTS opportunities(id TEXT PRIMARY KEY, canonical TEXT, record TEXT, first_seen TEXT, last_seen TEXT);
CREATE TABLE IF NOT EXISTS keys(key TEXT PRIMARY KEY, opp_id TEXT);
CREATE TABLE IF NOT EXISTS changes(id INTEGER PRIMARY KEY, opp_id TEXT, at TEXT, field TEXT, old TEXT, new TEXT);
"""


class Store:
    def __init__(self, path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.executescript(SCHEMA)
        self.duplicates_merged = 0
        self.raw_records_seen = 0

    def close(self):
        self.db.commit()
        self.db.close()

    # ---- runs / observations
    def start_run(self, source: str, now: str) -> int:
        cur = self.db.execute("INSERT INTO source_runs(source,started_at,status) VALUES(?,?,?)", (source, now, "running"))
        return cur.lastrowid

    def finish_run(self, run_id, now, status, http_status=None, n_records=0, complete=False, requests=0, error=""):
        self.db.execute("UPDATE source_runs SET finished_at=?,status=?,http_status=?,n_records=?,complete=?,requests=?,error=? WHERE id=?",
                        (now, status, http_status, n_records, int(complete), requests, error[:500], run_id))
        self.db.commit()

    def add_observation(self, run_id, source, source_key, url, fetched_at, raw_text) -> int:
        h = hashlib.sha256(raw_text.encode()).hexdigest()
        cur = self.db.execute("INSERT INTO observations(run_id,source,source_key,url,fetched_at,raw_hash,raw_text) VALUES(?,?,?,?,?,?,?)",
                              (run_id, source, source_key, url, fetched_at, h, raw_text))
        return cur.lastrowid

    def last_runs(self) -> dict:
        rows = self.db.execute("SELECT source,started_at,finished_at,status,http_status,n_records,complete,requests,error FROM source_runs "
                               "WHERE id IN (SELECT MAX(id) FROM source_runs GROUP BY source)").fetchall()
        keys = ("source", "started_at", "finished_at", "status", "http_status", "n_records", "complete", "requests", "error")
        return {r[0]: dict(zip(keys, r)) for r in rows}

    # ---- opportunities
    def find(self, opp: Opportunity):
        for k in opp.dedupe_keys():
            r = self.db.execute("SELECT opp_id FROM keys WHERE key=?", (k,)).fetchone()
            if r:
                return r[0]
        return None

    def get(self, opp_id: str):
        r = self.db.execute("SELECT record FROM opportunities WHERE id=?", (opp_id,)).fetchone()
        return Opportunity.from_dict(json.loads(r[0])) if r else None

    def all(self) -> list:
        return [Opportunity.from_dict(json.loads(r[0])) for r in self.db.execute("SELECT record FROM opportunities ORDER BY id")]

    def upsert(self, new: Opportunity, now: str, obs_id: int | None = None) -> tuple:
        """Returns (opportunity_id, 'new'|'updated'|'duplicate_merged'|'unchanged'). Facts with basis human_* are never overwritten
        by source claims; every changed fact is logged."""
        self.raw_records_seen += 1
        existing_id = self.find(new)
        if existing_id is None:
            new.first_seen = new.last_seen = now
            new.status = "listed"
            if obs_id:
                new.observation_ids = [obs_id]
            self._write(new)
            return new.id, "new"
        old = self.get(existing_id)
        outcome = "unchanged"
        same_ref = (old.source == new.source and old.source_key == new.source_key) or \
                   any(a.get("source") == new.source and a.get("source_key") == new.source_key for a in old.aliases)
        if not same_ref:
            old.aliases.append({"source": new.source, "source_key": new.source_key, "url": new.url})
            self.duplicates_merged += 1
            outcome = "duplicate_merged"
        for name, fact in new.facts.items():
            cur = old.facts.get(name)
            if cur and cur.basis in ("human_confirmed", "human_entered") and fact.basis not in ("human_confirmed", "human_entered"):
                continue
            if not same_ref and cur is not None and cur.known():
                continue        # a secondary source only fills gaps; it never overwrites the primary record
            if cur is None or cur.value != fact.value:
                if not (cur is None and fact.value is None) and name != "description_text":
                    self.db.execute("INSERT INTO changes(opp_id,at,field,old,new) VALUES(?,?,?,?,?)",
                                    (old.id, now, name, json.dumps(cur.value if cur else None), json.dumps(fact.value)))
                    if outcome == "unchanged":
                        outcome = "updated"
            if fact.known() or cur is None:
                old.facts[name] = fact
        for fld in (("title", "organizer") if same_ref else ()):
            if getattr(new, fld) and getattr(old, fld) != getattr(new, fld):
                self.db.execute("INSERT INTO changes(opp_id,at,field,old,new) VALUES(?,?,?,?,?)",
                                (old.id, now, fld, json.dumps(getattr(old, fld)), json.dumps(getattr(new, fld))))
                setattr(old, fld, getattr(new, fld))
                if outcome == "unchanged":
                    outcome = "updated"
        if old.status != "listed":
            self.db.execute("INSERT INTO changes(opp_id,at,field,old,new) VALUES(?,?,?,?,?)", (old.id, now, "status", json.dumps(old.status), json.dumps("listed")))
            old.status = "listed"
        old.last_seen = now
        if obs_id:
            old.observation_ids = (old.observation_ids + [obs_id])[-20:]
        self._write(old)
        return old.id, outcome

    def _write(self, o: Opportunity):
        self.db.execute("INSERT OR REPLACE INTO opportunities(id,canonical,record,first_seen,last_seen) VALUES(?,?,?,?,?)",
                        (o.id, o.dedupe_keys()[0], json.dumps(o.to_dict(), sort_keys=True), o.first_seen, o.last_seen))
        for k in o.dedupe_keys():
            self.db.execute("INSERT OR IGNORE INTO keys(key,opp_id) VALUES(?,?)", (k, o.id))
        for a in o.aliases:
            if a.get("url"):
                from .model import canonical_url
                self.db.execute("INSERT OR IGNORE INTO keys(key,opp_id) VALUES(?,?)", ("u:" + canonical_url(a["url"]), o.id))
        self.db.commit()

    def mark_unlisted(self, source: str, seen_ids: set, now: str) -> int:
        n = 0
        for o in self.all():
            if o.source == source and o.status == "listed" and o.id not in seen_ids:
                o.status = "unlisted"
                self.db.execute("INSERT INTO changes(opp_id,at,field,old,new) VALUES(?,?,?,?,?)", (o.id, now, "status", json.dumps("listed"), json.dumps("unlisted")))
                self._write(o)
                n += 1
        return n

    def changes_since(self, since: str) -> list:
        rows = self.db.execute("SELECT opp_id,at,field,old,new FROM changes WHERE at>=? ORDER BY at,id", (since,)).fetchall()
        return [dict(zip(("opp_id", "at", "field", "old", "new"), r)) for r in rows]

    def all_changes(self) -> list:
        return self.changes_since("")
