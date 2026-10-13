"""Phase 1 layer F: free, official, rate-limited probes with a response cache (docs/PHASE1_SPEC.md section 3).

Sources: Hacker News Algolia API (pain mentions), GitHub search API (free open-source alternatives),
Stack Exchange API (question volume). A blocked or failing source is recorded as such and never worked around.
The transport is injectable so tests run offline on fixtures.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

USER_AGENT = "flyfoundry-research/0.2 (+https://github.com/Alextsvr/FlyFoundry-v0.1; free public APIs, rate-limited)"
Transport = Callable[[str, dict], tuple]   # (url, headers) -> (http_status, body_text)


def urllib_transport(url: str, headers: dict, timeout: float = 30.0):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001 - network failure is data, not a crash
        return 0, f"{type(e).__name__}: {e}"


def load_ideas(path: str | Path = "data/ideas.csv") -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["hn_phrases"] = [p for p in r["hn_phrases"].split("|") if p]
    return rows


class ProbeCache:
    """Append-only JSONL: every fact keeps URL, fetch time, HTTP status and a hash of the raw response."""

    def __init__(self, path: str | Path | None):
        self.path = Path(path) if path else None
        self.facts: dict[str, dict] = {}
        if self.path and self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    d = json.loads(line)
                    self.facts[d["key"]] = d

    def get(self, key: str):
        return self.facts.get(key)

    def put(self, fact: dict) -> None:
        self.facts[fact["key"]] = fact
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(fact, sort_keys=True) + "\n")


def _key(source: str, url: str) -> str:
    return source + ":" + hashlib.sha256(url.encode()).hexdigest()[:16]


def _fetch(source, idea, metric, url, headers, parse, cache, transport, sleep_s, now):
    key = _key(source, url)
    hit = cache.get(key)
    if hit is not None and hit["status"] in ("ok", "blocked"):
        return hit
    time.sleep(sleep_s) if sleep_s else None
    code, body = transport(url, headers)
    fact = {"key": key, "source": source, "idea": idea, "metric": metric, "url": url, "http": code,
            "fetched_utc": now().strftime("%Y-%m-%dT%H:%M:%SZ"), "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
            "value": None, "status": "error"}
    if code in (401, 403, 451):
        fact["status"] = "blocked"          # recorded, never worked around
    elif code == 429:
        fact["status"] = "ratelimited"
    elif code == 200:
        try:
            fact["value"] = parse(json.loads(body))
            fact["status"] = "ok"
        except Exception as e:  # noqa: BLE001
            fact["status"] = "error"
            fact["note"] = f"parse: {type(e).__name__}"
    else:
        fact["note"] = body[:120]
    if fact["status"] != "ratelimited":
        cache.put(fact)
    return fact


def _since(now, months):
    """Start of the window, rounded to the UTC day so that a resumed run produces identical URLs (cache hits)."""
    d = (now() - timedelta(days=30 * months)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(d.timestamp())


def probe_hn(idea, cache, transport, now, months=24, sleep_s=0.2):
    since = _since(now, months)
    out = []
    for ph in idea["hn_phrases"]:
        q = urllib.parse.urlencode({"query": f'"{ph}"', "advancedSyntax": "true", "tags": "(story,comment)",
                                    "numericFilters": f"created_at_i>{since}", "hitsPerPage": 0})
        out.append(_fetch("hn", idea["id"], f"mentions[{ph}]", "https://hn.algolia.com/api/v1/search?" + q,
                          {"User-Agent": USER_AGENT}, lambda j: int(j["nbHits"]), cache, transport, sleep_s, now))
    return out


def probe_github(idea, cache, transport, now, sleep_s=2.2):
    h = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        h["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    q = urllib.parse.urlencode({"q": idea["gh_query"] + " in:name,description,readme", "sort": "stars", "per_page": 5})
    url = "https://api.github.com/search/repositories?" + q

    def parse(j):
        return {"total": int(j["total_count"]), "top5_stars": int(sum(i["stargazers_count"] for i in j["items"]))}
    return [_fetch("github", idea["id"], "free_alternatives", url, h, parse, cache, transport, sleep_s, now)]


def probe_stackexchange(idea, cache, transport, now, months=24, sleep_s=1.0):
    since = _since(now, months)
    q = urllib.parse.urlencode({"q": idea["se_query"], "site": idea["se_site"], "fromdate": since, "filter": "total"})
    url = "https://api.stackexchange.com/2.3/search/advanced?" + q
    return [_fetch("stackexchange", idea["id"], "question_volume", url, {"User-Agent": USER_AGENT},
                   lambda j: int(j["total"]), cache, transport, sleep_s, now)]


def run_probes(ideas, cache, sources=("hn", "github", "stackexchange"), transport: Transport = urllib_transport,
               now=lambda: datetime.now(timezone.utc), sleep_scale=1.0, max_requests=3000):
    """Probe every idea (resumable through the cache). Stops when ``max_requests`` fresh requests were made."""
    fns = {"hn": probe_hn, "github": probe_github, "stackexchange": probe_stackexchange}
    n0, n = len(cache.facts), 0
    facts = []
    for idea in ideas:
        for s in sources:
            kw = {} if sleep_scale == 1.0 else {"sleep_s": {"hn": .2, "github": 2.2, "stackexchange": 1.0}[s] * sleep_scale}
            facts += fns[s](idea, cache, transport, now, **kw)
            n = len(cache.facts) - n0
            if n >= max_requests:
                return facts
    return facts
