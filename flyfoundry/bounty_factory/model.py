"""Opportunity record. Every field is a Fact that says where its value came from; unknown stays unknown."""
from __future__ import annotations

import hashlib
import re
import urllib.parse
from dataclasses import dataclass, field, asdict
from typing import Any

# source_claim    = the source states it (list API / page text)
# inferred        = computed by this code from source claims (always carries the rule in `evidence`)
# human_confirmed = a person checked it and recorded it in data/bounty_reviews.json
# human_entered   = a person typed it in via the manual intake file
# unknown         = nothing is known; value is None
BASES = ("source_claim", "inferred", "human_confirmed", "human_entered", "unknown")


@dataclass
class Fact:
    value: Any = None
    basis: str = "unknown"
    evidence: str = ""

    def known(self) -> bool:
        return self.value is not None and self.basis != "unknown"

    def to_dict(self) -> dict:
        return {"value": self.value, "basis": self.basis, "evidence": self.evidence}

    @staticmethod
    def from_dict(d: dict) -> "Fact":
        return Fact(d.get("value"), d.get("basis", "unknown"), d.get("evidence", ""))


UNKNOWN = Fact()

# Fact names used across the subsystem (documented in docs/BOUNTY_FACTORY.md)
FACT_NAMES = (
    "prize_amount", "prize_currency", "prize_count", "deadline_date", "deadline_precision", "deadline_tz",
    "location", "geo_restriction_text", "geo_eligible", "invite_only", "fees_required", "fee_text",
    "token_or_wallet_required", "deliverables", "submission_method", "themes", "registrations_count",
    "description_text", "employer_conflict", "paid_tool_required", "hardware_required",
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
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def stable_id(url: str) -> str:
    return "bf-" + hashlib.sha256(canonical_url(url).encode()).hexdigest()[:12]


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
    last_seen: str = ""
    status: str = "listed"                          # listed | unlisted (disappeared from a complete successful listing)
    aliases: list = field(default_factory=list)     # other (source, url) refs merged into this record
    observation_ids: list = field(default_factory=list)
    detail_fetched_at: str = ""

    def fact(self, name: str) -> Fact:
        return self.facts.get(name) or UNKNOWN

    def set(self, name: str, value, basis="source_claim", evidence=""):
        if value is None:
            self.facts[name] = Fact()
        else:
            self.facts[name] = Fact(value, basis, evidence)

    def dedupe_keys(self) -> list:
        keys = ["u:" + canonical_url(self.url)]
        if self.title and self.organizer:
            keys.append("t:" + norm_text(self.title) + "|" + norm_text(self.organizer))
        return keys

    def to_dict(self) -> dict:
        d = asdict(self)
        d["facts"] = {k: v.to_dict() for k, v in self.facts.items()}
        return d

    @staticmethod
    def from_dict(d: dict) -> "Opportunity":
        d = dict(d)
        d["facts"] = {k: Fact.from_dict(v) for k, v in d.get("facts", {}).items()}
        return Opportunity(**d)
