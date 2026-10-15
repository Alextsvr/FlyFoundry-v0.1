"""Opportunity record. Every field is a Fact that says where its value came from; unknown stays unknown.

Per-fact freshness: `observed_at` is the last time a source asserted THIS value, `changed_at` when the value last changed,
`history` keeps earlier values (never destroyed), `status` is current|withdrawn (a source stopped providing the value)."""
from __future__ import annotations

import hashlib
import re
import unicodedata
import urllib.parse
from dataclasses import dataclass, field, asdict
from typing import Any

# source_claim    = the source states it (list API / page text)
# inferred        = computed by this code from source claims (the rule is in `evidence`)
# human_confirmed = a person checked it and recorded it in data/bounty_reviews.json
# human_entered   = a person typed it in via the manual intake file
# unknown         = nothing is known; value is None
BASES = ("source_claim", "inferred", "human_confirmed", "human_entered", "unknown")
HUMAN = ("human_confirmed", "human_entered")
MAX_HISTORY = 20


@dataclass
class Fact:
    value: Any = None
    basis: str = "unknown"
    evidence: str = ""
    strength: str = ""            # "" (structured/explicit) | "firm" | "weak" (heuristic text signal: never a hard reject)
    origin: str = ""              # list | overview | rules | manual | human | derived
    observed_at: str = ""         # last time a source asserted this value
    changed_at: str = ""          # when the value last changed
    observation_id: Any = None    # raw observation the value was extracted from
    parser_version: str = ""
    status: str = "current"       # current | withdrawn
    last_value: Any = None        # value before withdrawal
    history: list = field(default_factory=list)     # [{value, basis, evidence, from, to, end}]
    conflicts: list = field(default_factory=list)   # competing source claims against a human fact

    def known(self) -> bool:
        return self.value is not None and self.basis != "unknown" and self.status == "current"

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Fact":
        allowed = Fact.__dataclass_fields__
        return Fact(**{k: v for k, v in d.items() if k in allowed})


UNKNOWN = Fact()

FACT_NAMES = (
    "prize_amount", "prize_currency", "prize_count", "deadline_date", "deadline_precision", "deadline_tz",
    "location", "geo_restriction_text", "geo_eligible", "geo_excludes_participant", "geo_includes_participant", "invite_only",
    "fees_required", "fee_text", "token_or_wallet_required", "deliverables", "submission_method", "themes", "registrations_count",
    "description_text", "employer_conflict", "paid_tool_required", "hardware_required", "rules_hash",
)


def canonical_url(url: str) -> str:
    """host (no www) + path without trailing slash; query/fragment dropped. Stable across utm/trailing-slash variants."""
    p = urllib.parse.urlsplit((url or "").strip())
    host = (p.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = re.sub(r"/+$", "", p.path or "")
    return f"{host}{path}".lower()


def norm_text(s: str) -> str:
    """Unicode-aware: NFKC + casefold, tokens are runs of letters/digits in ANY script (Cyrillic, accents, CJK survive)."""
    s = unicodedata.normalize("NFKC", s or "").casefold()
    return " ".join(re.findall(r"[^\W_]+", s))


def stable_id(url: str) -> str:
    return "bf-" + hashlib.sha256(canonical_url(url).encode()).hexdigest()[:12]


def sha256_text(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()


@dataclass
class Opportunity:
    id: str
    source: str
    source_key: str
    url: str
    title: str
    organizer: str = ""
    kind: str = "hackathon"
    facts: dict = field(default_factory=dict)       # name -> Fact
    first_seen: str = ""
    last_seen: str = ""                             # last time the RECORD was observed in a source listing
    status: str = "listed"                          # listed | unlisted (absent from a complete, validated listing)
    aliases: list = field(default_factory=list)     # merged records: {source, source_key, url, matched_by, merged_at}
    observation_ids: list = field(default_factory=list)
    detail_fetched_at: str = ""                     # last time ANY detail page was read (legacy; see `detail`)
    possible_duplicates: list = field(default_factory=list)   # ids that may be the same event (not merged)
    detail: dict = field(default_factory=dict)      # page -> {fetched_at, http_status, ok, observation_id, next_due}

    def fact(self, name: str) -> Fact:
        return self.facts.get(name) or UNKNOWN

    def set(self, name: str, value, basis="source_claim", evidence="", strength="", origin="", observation_id=None, parser_version=""):
        if value is None:
            self.facts[name] = Fact(origin=origin)
        else:
            self.facts[name] = Fact(value, basis, evidence, strength, origin, "", "", observation_id, parser_version)

    def dedupe_keys(self) -> list:
        """'u:' keys are certain identity (same page). 't:' (title|organizer) is only a CANDIDATE key: it needs corroboration.
        Empty normalized parts never produce a key."""
        keys = ["u:" + canonical_url(self.url)]
        t, o = norm_text(self.title), norm_text(self.organizer)
        if t and o:
            keys.append("t:" + t + "|" + o)
        return keys

    def to_dict(self) -> dict:
        d = asdict(self)
        d["facts"] = {k: v.to_dict() for k, v in self.facts.items()}
        return d

    @staticmethod
    def from_dict(d: dict) -> "Opportunity":
        d = dict(d)
        d["facts"] = {k: Fact.from_dict(v) for k, v in d.get("facts", {}).items()}
        allowed = Opportunity.__dataclass_fields__
        return Opportunity(**{k: v for k, v in d.items() if k in allowed})
