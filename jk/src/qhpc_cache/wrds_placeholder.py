"""WRDS / CRSP — backward-compatible roadmap types.

**Active integration** lives in ``wrds_provider.py``, ``wrds_queries.py``, ``wrds_registry.py``.
Use ``wrds_queries.WRDS_INTEGRATION_ROADMAP`` for the canonical ordered slot list.

This module keeps legacy ``WrdsDatasetPlaceholder`` names for older imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Tuple

from qhpc_cache.wrds_queries import WRDS_INTEGRATION_ROADMAP as _NEW_ROADMAP


WRDS_ACCESS_PENDING = "pending"
WRDS_ACCESS_ACTIVE = "active"
WRDS_ACCESS_UNAVAILABLE = "unavailable"


@dataclass
class WrdsDatasetPlaceholder:
    """Named dataset slot (legacy mirror of ``WrdsDatasetSlot``)."""

    slot_id: str
    description: str
    priority_rank: int
    vendor_tags: Tuple[str, ...] = field(default_factory=tuple)


def _slots_to_placeholders() -> Tuple[WrdsDatasetPlaceholder, ...]:
    return tuple(
        WrdsDatasetPlaceholder(s.slot_id, s.description, s.priority_rank, s.vendor_tags)
        for s in _NEW_ROADMAP
    )


# Priority order from governing spec (1 = highest) — synced with ``wrds_queries``.
WRDS_INTEGRATION_ROADMAP: Tuple[WrdsDatasetPlaceholder, ...] = _slots_to_placeholders()


@dataclass
class WrdsIntegrationState:
    """Serializable status for docs and future auth wiring."""

    access_status: str = WRDS_ACCESS_PENDING
    account_notes: str = "Use wrds_provider.check_wrds_connection() when WRDS_USERNAME is set."
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
