"""Structured types for the Campus Customs vendor desk agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class VendorDecision(BaseModel):
    """The agent's final answer for one vendor document (handbook section 13)."""

    vendor: str = Field(description="Vendor name exactly as the document gives it.")
    sku: str | None = Field(description="Campus Customs SKU, e.g. CC-HD-006. null if the document does not say.")
    unit_price: float | None = Field(description="Quoted unit price in US dollars. null if the document does not say.")
    lead_time_days: int | None = Field(description="Quoted lead time in days. null if the document does not say.")
    min_order: int | None = Field(description="Minimum order in units. null if the document does not say.")
    decision: Literal["recommend", "do_not_recommend"] = Field(
        description="recommend only if all four purchasing checks in handbook section 4 pass."
    )
    reason: str = Field(description="One sentence naming the purchasing check that decided it.")


@dataclass
class DeskDeps:
    """Per-run state handed to every tool."""

    doc_path: Path  # the one document this run is allowed to read
    audit: list[dict[str, Any]] = field(default_factory=list)  # tool calls made during this run
    defenses: frozenset[str] = frozenset()  # active defense layers: any of "code", "design", "prompt"
