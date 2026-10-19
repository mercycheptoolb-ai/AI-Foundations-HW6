"""Design-layer defense: the handbook's purchasing decision, made by code instead of the model.

The model only extracts facts. This module applies handbook section 4 to those facts, reading the
approved list (section 5), the removed/pending list (section 6), and the catalogue (section 9) straight
from data/shop_handbook.md, and writes the reason from a fixed template. Nothing in a vendor document can
change the rules or put its own words into the reason.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from models import VendorDecision

HANDBOOK = Path(__file__).resolve().parent / "data" / "shop_handbook.md"
MAX_LEAD_DAYS = 21
MAX_MIN_ORDER = 600
SKU_PATTERN = re.compile(r"^CC-[A-Z]{2}-\d{3}$")


@dataclass(frozen=True)
class Handbook:
    approved: frozenset[str]
    blocked: frozenset[str]  # removed or pending
    max_cost: dict[str, float]


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def _section(text: str, number: int) -> str:
    match = re.search(rf"^## {number}\..*?(?=^## \d+\.|\Z)", text, re.M | re.S)
    return match.group(0) if match else ""


def _rows(section: str) -> list[list[str]]:
    rows = []
    for line in section.splitlines():
        if line.startswith("|") and not re.match(r"^\|[\s\-|]+\|$", line):
            rows.append([c.strip() for c in line.strip("|").split("|")])
    return rows[1:]  # drop the header row


@lru_cache(maxsize=1)
def handbook() -> Handbook:
    text = HANDBOOK.read_text()
    approved = frozenset(_norm(r[1]) for r in _rows(_section(text, 5)))
    blocked = frozenset(_norm(r[0]) for r in _rows(_section(text, 6)))
    max_cost = {r[0]: float(r[4].lstrip("$")) for r in _rows(_section(text, 9))}
    return Handbook(approved, blocked, max_cost)


def decide(answer: VendorDecision) -> VendorDecision:
    """Return the answer with decision and reason recomputed from the handbook rules."""
    hb = handbook()
    vendor = _norm(answer.vendor)
    sku = answer.sku if answer.sku and SKU_PATTERN.match(answer.sku) else None

    def fail(reason: str) -> VendorDecision:
        return answer.model_copy(update={"sku": sku, "decision": "do_not_recommend", "reason": reason})

    # 1. Approved vendor
    if vendor in hb.blocked:
        return fail(f"{answer.vendor} is on the handbook's removed or pending vendor list, so it fails the approved-vendor check.")
    if vendor not in hb.approved:
        return fail(f"{answer.vendor} is not on the handbook's approved vendor list, so it fails the approved-vendor check.")
    # 2. Price
    if sku is None or sku not in hb.max_cost:
        return fail("The document does not give a Campus Customs SKU from our catalogue, so the price check cannot pass.")
    if answer.unit_price is None:
        return fail(f"The document does not state a unit price for {sku}, so the price check cannot pass.")
    if answer.unit_price > hb.max_cost[sku]:
        return fail(f"The quoted unit price of ${answer.unit_price:.2f} is above our max unit cost for {sku}, so it fails the price check.")
    # 3. Lead time
    if answer.lead_time_days is None:
        return fail("The document does not state a lead time, so the lead-time check cannot pass.")
    if answer.lead_time_days > MAX_LEAD_DAYS:
        return fail(f"The lead time of {answer.lead_time_days} days is over the {MAX_LEAD_DAYS}-day limit, so it fails the lead-time check.")
    # 4. Minimum order
    if answer.min_order is None:
        return fail("The document does not state a minimum order, so the minimum-order check cannot pass.")
    if answer.min_order > MAX_MIN_ORDER:
        return fail(f"The minimum order of {answer.min_order} units is over the {MAX_MIN_ORDER}-unit limit, so it fails the minimum-order check.")

    return answer.model_copy(update={
        "sku": sku,
        "decision": "recommend",
        "reason": (f"All four checks pass: {answer.vendor} is approved, ${answer.unit_price:.2f} is within our max unit cost "
                   f"for {sku}, the {answer.lead_time_days}-day lead time is within {MAX_LEAD_DAYS} days, and the "
                   f"{answer.min_order}-unit minimum is within {MAX_MIN_ORDER} units."),
    })
