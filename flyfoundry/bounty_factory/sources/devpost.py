"""Devpost adapter: public list endpoint /api/hackathons (open hackathons). Only list-level claims are recorded here;
eligibility, fees and deliverables remain unknown until the detail pass or a human review."""
from __future__ import annotations

import html
import json
import re
from datetime import date

from ..http import Fetcher, RobotsDenied, BudgetExceeded
from ..model import Opportunity, stable_id

BASE = "https://devpost.com/api/hackathons"
SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR", "¥": "JPY"}
MONTHS = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def parse_prize(s):
    """'$<span data-currency-value>275</span>' -> (275.0, 'USD', raw). Currency symbol '$' is ambiguous; recorded as USD *claim*."""
    if s is None:
        return None, None, None
    text = html.unescape(re.sub(r"<[^>]+>", "", str(s))).strip()
    m = re.search(r"([^\d\s,.\-]{1,3})?\s*([\d][\d,\.]*)", text)
    if not m:
        return None, None, text
    num = m.group(2).replace(",", "")
    try:
        amount = float(num)
    except ValueError:
        return None, None, text
    sym = (m.group(1) or "").strip()
    return amount, SYMBOLS.get(sym), text


def parse_deadline(s):
    """'Aug 16 - Oct 15, 2026' | 'Oct 12 - 15, 2026' | 'Dec 30, 2026 - Jan 15, 2027' -> end date (ISO) or None."""
    if not s:
        return None
    t = str(s).replace("–", "-").replace("—", "-")
    parts = [p.strip() for p in t.split(" - ")]
    end = parts[-1]
    m = re.match(r"^(?:([A-Za-z]{3})[a-z]*\.?\s+)?(\d{1,2}),?\s+(\d{4})$", end)
    if not m:
        return None
    mon, day, year = m.group(1), int(m.group(2)), int(m.group(3))
    if mon is None:
        sm = re.match(r"^([A-Za-z]{3})", parts[0]) if len(parts) > 1 else None
        if not sm:
            return None
        mon = sm.group(1)
    mnum = MONTHS.get(mon.lower())
    if not mnum:
        return None
    try:
        return date(year, mnum, day).isoformat()
    except ValueError:
        return None


def to_opportunity(item: dict, list_url: str) -> Opportunity | None:
    url = item.get("url")
    if not url or not item.get("title"):
        return None
    o = Opportunity(id=stable_id(url), source="devpost", source_key=str(item.get("id", url)), url=url,
                    title=str(item["title"]).strip(), organizer=str(item.get("organization_name") or "").strip(), kind="hackathon")
    ev = f"Devpost list API {list_url}"
    amount, cur, raw = parse_prize(item.get("prize_amount"))
    o.set("prize_amount", amount, "source_claim", f"{ev}: prize_amount={raw!r}")
    o.set("prize_currency", cur, "source_claim", f"{ev}: symbol of prize_amount={raw!r} (symbol may be ambiguous)")
    pc = item.get("prizes_counts")
    cash = pc.get("cash") if isinstance(pc, dict) else (pc if isinstance(pc, int) else None)
    o.set("prize_count", cash, "source_claim", f"{ev}: prizes_counts={pc!r} (cash prizes)")
    dl = parse_deadline(item.get("submission_period_dates"))
    o.set("deadline_date", dl, "source_claim", f"{ev}: submission_period_dates={item.get('submission_period_dates')!r}")
    if dl:
        o.set("deadline_precision", "date", "inferred", "list gives a calendar date only; no time of day")
        o.set("deadline_tz", None)
    o.set("location", item.get("displayed_location"), "source_claim", f"{ev}: displayed_location (format of participation, NOT an eligibility statement)")
    o.set("invite_only", item.get("invite_only"), "source_claim", f"{ev}: invite_only")
    o.set("themes", [t.get("name") if isinstance(t, dict) else str(t) for t in (item.get("themes") or [])], "source_claim", f"{ev}: themes")
    o.set("registrations_count", item.get("registrations_count"), "source_claim", f"{ev}: registrations_count at fetch time")
    if item.get("start_a_submission_url"):
        o.set("submission_method", "devpost_submission_form", "source_claim", f"{ev}: start_a_submission_url present")
    return o


def fetch_all(fetcher: Fetcher, max_pages: int = 5, per_page: int = 24):
    """Yields (page_url, status, raw_body, parsed_json_or_None, is_last_complete). is_last_complete is True only when the
    final page was reached (empty page or total_count covered); hitting max_pages yields False (listing incomplete)."""
    for page in range(1, max_pages + 1):
        url = f"{BASE}?status[]=open&order_by=deadline&page={page}&per_page={per_page}"
        status, body = fetcher.get_checked(url, "application/json")
        data = None
        if status == 200:
            try:
                data = json.loads(body)
            except ValueError:
                data = None
        items = (data or {}).get("hackathons") or []
        meta = (data or {}).get("meta") or {}
        size = int(meta.get("per_page") or per_page)
        total = meta.get("total_count")
        done = data is not None and (not items or (total is not None and page * size >= int(total)))
        yield url, status, body, data, done
        if status != 200 or data is None or done:
            return
