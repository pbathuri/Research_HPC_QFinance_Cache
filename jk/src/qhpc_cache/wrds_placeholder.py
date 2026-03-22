"""WRDS / CRSP future layer — placeholders only; pipeline runs without institutional login."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple


WRDS_ACCESS_PENDING = "pending"
WRDS_ACCESS_ACTIVE = "active"
WRDS_ACCESS_UNAVAILABLE = "unavailable"


@dataclass
class WrdsDatasetPlaceholder:
    """Named future dataset slot (no live connection)."""

    slot_id: str
    description: str
    priority_rank: int
    vendor_tags: Tuple[str, ...] = field(default_factory=tuple)


# Priority order from governing spec (1 = highest).
WRDS_INTEGRATION_ROADMAP: Tuple[WrdsDatasetPlaceholder, ...] = (
    WrdsDatasetPlaceholder(
        "crsp_treasury_inflation",
        "CRSP Treasury / Index Treasury and Inflation",
        1,
        ("CRSP", "Treasury"),
    ),
    WrdsDatasetPlaceholder(
        "taq_crsp_link",
        "TAQ CRSP Link / Daily TAQ CRSP Link",
        2,
        ("TAQ", "CRSP", "link"),
    ),
    WrdsDatasetPlaceholder(
        "crsp_stock_security_events",
        "CRSP Stock security files and corporate events",
        3,
        ("CRSP", "Securities", "Events"),
    ),
    WrdsDatasetPlaceholder(
        "crsp_compustat_merged",
        "CRSP / Compustat merged fundamentals",
        4,
        ("Compustat",),
    ),
    WrdsDatasetPlaceholder(
        "fama_french_liquidity",
        "Fama-French and liquidity style factors",
        5,
        ("FF", "Factors"),
    ),
    WrdsDatasetPlaceholder(
        "wrds_intraday_indicators",
        "WRDS intraday indicators",
        6,
        ("WRDS", "Intraday"),
    ),
    WrdsDatasetPlaceholder(
        "event_study_eventus",
        "Event study / Eventus tooling",
        7,
        ("Eventus",),
    ),
)


@dataclass
class WrdsIntegrationState:
    """Serializable status for docs and future auth wiring."""

    access_status: str = WRDS_ACCESS_PENDING
    account_notes: str = "WRDS access expected within days; not required for current pipeline."
    roadmap: Tuple[WrdsDatasetPlaceholder, ...] = WRDS_INTEGRATION_ROADMAP

    def to_dict(self) -> Dict[str, Any]:
        return {
            "access_status": self.access_status,
            "account_notes": self.account_notes,
            "roadmap": [
                {
                    "slot_id": item.slot_id,
                    "description": item.description,
                    "priority_rank": item.priority_rank,
                    "vendor_tags": list(item.vendor_tags),
                }
                for item in self.roadmap
            ],
        }


def default_wrds_state() -> WrdsIntegrationState:
    return WrdsIntegrationState()
