"""WRDS SQL templates and **verified canonical** CRSP / TAQ-link tables.

Active integration targets fixed schema.table names confirmed on live WRDS.
**Do not** embed credentials; use ``wrds.Connection`` with environment-based auth
(see ``wrds_provider``).

Legacy candidate tuples (e.g. ``CRSP_TREASURY_TABLE_CANDIDATES``) are kept only
for backward compatibility and point at the same canonical tables.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ── Roadmap (aligned with research priorities; was wrds_placeholder) ─────────

@dataclass(frozen=True)
class WrdsDatasetSlot:
    slot_id: str
    description: str
    priority_rank: int
    vendor_tags: Tuple[str, ...]


# Seven locked tiers (1–7). FRB / file fallbacks for rates live in ``rates_data`` / candidates
# below — not as equal WRDS “dataset categories” on the roadmap.
WRDS_INTEGRATION_ROADMAP: Tuple[WrdsDatasetSlot, ...] = (
    WrdsDatasetSlot(
        "crsp_treasury_inflation",
        "CRSP Treasury / Index Treasury and Inflation",
        1,
        ("CRSP", "Treasury", "Inflation"),
    ),
    WrdsDatasetSlot(
        "crsp_stock_security_events",
        "CRSP Stock / Security Files + Stock / Events",
        2,
        ("CRSP", "Security", "Events"),
    ),
    WrdsDatasetSlot(
        "taq_crsp_link",
        "TAQ CRSP Link / Daily TAQ CRSP Link",
        3,
        ("TAQ", "CRSP"),
    ),
    WrdsDatasetSlot(
        "crsp_compustat_merged",
        "CRSP / Compustat Merged",
        4,
        ("CRSP", "Compustat"),
    ),
    WrdsDatasetSlot(
        "fama_french_liquidity",
        "Fama-French & Liquidity Factors",
        5,
        ("FF", "Liquidity"),
    ),
    WrdsDatasetSlot(
        "wrds_intraday",
        "WRDS Intraday Indicators",
        6,
        ("WRDS", "Intraday"),
    ),
    WrdsDatasetSlot(
        "event_study_eventus",
        "Event Study / Eventus tools",
        7,
        ("Eventus", "EventStudy"),
    ),
)


# ── Verified canonical tables (active WRDS) ─────────────────────────────────

CANONICAL_CRSP_TFZ_DLY: Tuple[str, str] = ("crsp", "tfz_dly")
CANONICAL_CRSP_TFZ_MTH: Tuple[str, str] = ("crsp", "tfz_mth")
CANONICAL_CRSP_STOCKNAMES: Tuple[str, str] = ("crsp", "stocknames")
CANONICAL_CRSP_DSF: Tuple[str, str] = ("crsp", "dsf")
CANONICAL_CRSP_MSF: Tuple[str, str] = ("crsp", "msf")
CANONICAL_CRSP_DSE: Tuple[str, str] = ("crsp", "dse")
CANONICAL_CRSP_MSE: Tuple[str, str] = ("crsp", "mse")
CANONICAL_TAQ_CRSP_TCLINK: Tuple[str, str] = ("wrdsapps_link_crsp_taq", "tclink")
CANONICAL_TAQ_CRSP_TAQMCLINK: Tuple[str, str] = ("wrdsapps_link_crsp_taqm", "taqmclink")
CANONICAL_TAQ_CRSP_CUSIP_2010: Tuple[str, str] = (
    "wrdsapps_link_crsp_taqm",
    "taqmclink_cusip_2010",
)

# Treasury: **only** tfz_dly then tfz_mth. Do **not** use crsp.treasuries or ad-hoc names.
CRSP_TREASURY_TABLE_CANDIDATES: Sequence[Tuple[str, str]] = (
    CANONICAL_CRSP_TFZ_DLY,
    CANONICAL_CRSP_TFZ_MTH,
)

# Fama-French monthly factors — common WRDS layout
FAMA_FRENCH_CANDIDATES: Sequence[Tuple[str, str]] = (
    ("ff", "factors_monthly"),
    ("ff", "five_factors_monthly"),
)

# Liquidity-style factors (subscription-dependent; extend as needed)
LIQUIDITY_STYLE_CANDIDATES: Sequence[Tuple[str, str]] = (
    ("wrdsapps", "liq_ps"),
)

# CRSP–Compustat merged (CCM) — names vary; verify in Schema Finder
CRSP_COMPUSTAT_MERGED_CANDIDATES: Sequence[Tuple[str, str]] = (
    ("crspm", "ccm_link"),
    ("crspm", "ccmxpf_linktable"),
    ("comp", "sec_dprc"),
)

# Eventus / event-study outputs — configure when licensed; tried after explicit setup
EVENT_STUDY_CANDIDATES: Sequence[Tuple[str, str]] = (
    # ("wrdsapps", "evtstudy_results"),
)

# FRB — example schema names (subscription-dependent)
FRB_RATE_CANDIDATES: Sequence[Tuple[str, str]] = (
    ("frb", "wrds_rates"),
)

# Security master — canonical crsp.stocknames only
CRSP_STOCKNAMES_CANDIDATES: Sequence[Tuple[str, str]] = (CANONICAL_CRSP_STOCKNAMES,)

# Daily / monthly stock events (canonical)
CRSP_DSE_CANDIDATES: Sequence[Tuple[str, str]] = (CANONICAL_CRSP_DSE,)
CRSP_MSE_CANDIDATES: Sequence[Tuple[str, str]] = (CANONICAL_CRSP_MSE,)

# TAQ ↔ CRSP identifier bridges (canonical)
TAQ_CRSP_LINK_CANONICAL: Sequence[Tuple[str, str]] = (
    CANONICAL_TAQ_CRSP_TCLINK,
    CANONICAL_TAQ_CRSP_TAQMCLINK,
    CANONICAL_TAQ_CRSP_CUSIP_2010,
)


def sql_treasury_sample(schema: str, table: str, limit: int = 5000) -> str:
    return f'SELECT * FROM "{schema}"."{table}" LIMIT {int(limit)}'


def sql_select_star_limited(schema: str, table: str, limit: int = 5000) -> str:
    """Generic bounded pull (large panels: always use modest limits or date windows)."""
    return f'SELECT * FROM "{schema}"."{table}" LIMIT {int(limit)}'


def sql_treasury_date_bounded(
    schema: str, table: str, date_col: str, start: str, end: str, limit: int = 50_000,
) -> str:
    """Parameterized dates must be validated ISO dates by caller."""
    return (
        f'SELECT * FROM "{schema}"."{table}" '
        f"WHERE \"{date_col}\" >= '{start}' AND \"{date_col}\" <= '{end}' "
        f"LIMIT {int(limit)}"
    )


def sql_fama_french_sample(schema: str, table: str, limit: int = 5000) -> str:
    return f'SELECT * FROM "{schema}"."{table}" LIMIT {int(limit)}'


def sql_list_schema_tables(schema: str) -> str:
    return (
        "SELECT table_schema, table_name FROM information_schema.tables "
        f"WHERE table_schema = '{schema}' ORDER BY table_name"
    )


def describe_slot(slot_id: str) -> Optional[WrdsDatasetSlot]:
    for s in WRDS_INTEGRATION_ROADMAP:
        if s.slot_id == slot_id:
            return s
    return None


def roadmap_dict() -> Dict[str, Any]:
    return {
        "roadmap": [
            {
                "slot_id": s.slot_id,
                "description": s.description,
                "priority_rank": s.priority_rank,
                "vendor_tags": list(s.vendor_tags),
            }
            for s in WRDS_INTEGRATION_ROADMAP
        ]
    }
