"""Manual intake: a human types in an opportunity found anywhere (including sources we cannot access compliantly)."""
from __future__ import annotations

import json
from pathlib import Path

from ..model import Opportunity, stable_id

ALLOWED = ("prize_amount", "prize_currency", "prize_count", "deadline_date", "deadline_tz", "geo_restriction_text", "invite_only",
           "fees_required", "fee_text", "token_or_wallet_required", "deliverables", "submission_method", "themes", "location",
           "description_text", "paid_tool_required", "hardware_required")


def load_manual(path) -> list:
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for e in json.loads(p.read_text(encoding="utf-8")).get("entries", []):
        if not e.get("url") or not e.get("title"):
            continue
        o = Opportunity(id=stable_id(e["url"]), source="manual", source_key=e["url"], url=e["url"], title=e["title"],
                        organizer=e.get("organizer", ""), kind=e.get("kind", "hackathon"))
        for k in ALLOWED:
            if k in e:
                o.set(k, e[k], "human_entered", f"typed into manual intake (entered {e.get('entered_at', 'unknown date')})", origin="manual")
        if e.get("deadline_date"):
            o.set("deadline_precision", "date" if len(str(e["deadline_date"])) == 10 else "datetime", "human_entered", "as typed", origin="manual")
        out.append(o)
    return out
