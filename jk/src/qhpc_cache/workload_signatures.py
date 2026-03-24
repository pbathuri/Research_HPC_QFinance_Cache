"""Deterministic labels for finance workloads (portfolio / model / feature space).

Used with cache observability to group metrics by research-relevant families.

**Research spine (cache-observability priority, locked):**

1. ``feature_panel`` — large-universe feature panels
2. ``portfolio_risk`` — VaR / CVaR / scenario risk
3. ``option_pricing`` — many-contract pricing families
4. ``event_window`` — crisis / TAQ-linked windows
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Sequence, Tuple

# Canonical spine IDs in priority order (1 = first for observability studies).
WORKLOAD_SPINE_FEATURE_PANEL = "feature_panel"
WORKLOAD_SPINE_PORTFOLIO_RISK = "portfolio_risk"
WORKLOAD_SPINE_OPTION_PRICING = "option_pricing"
WORKLOAD_SPINE_EVENT_WINDOW = "event_window"

CORE_WORKLOAD_SPINE: Tuple[Tuple[str, int, str], ...] = (
    (WORKLOAD_SPINE_FEATURE_PANEL, 1, "Feature panels across large universes"),
    (WORKLOAD_SPINE_PORTFOLIO_RISK, 2, "Portfolio risk, VaR / CVaR workflows"),
    (WORKLOAD_SPINE_OPTION_PRICING, 3, "Option pricing across many contracts"),
    (WORKLOAD_SPINE_EVENT_WINDOW, 4, "Event-window analytics around crises"),
)

_SPINE_RANK_BY_ID = {sid: rank for sid, rank, _ in CORE_WORKLOAD_SPINE}


def infer_workload_spine(pipeline_stage: str) -> Tuple[str, int]:
    """Map a free-text pipeline stage to ``(workload_spine_id, workload_spine_rank)``.

    Unknown stages return ``(\"\", 0)`` (caller may override explicitly).
    """
    s = (pipeline_stage or "").strip().lower()
    if not s:
        return "", 0
    if re.search(r"feature|panel|alpha|universe|factor", s):
        return WORKLOAD_SPINE_FEATURE_PANEL, _SPINE_RANK_BY_ID[WORKLOAD_SPINE_FEATURE_PANEL]
    if re.search(r"risk|var|cvar|portfolio|scenario|drawdown", s):
        return WORKLOAD_SPINE_PORTFOLIO_RISK, _SPINE_RANK_BY_ID[WORKLOAD_SPINE_PORTFOLIO_RISK]
    if re.search(r"pric|option|mc|qmc|gbm|payoff|engine", s):
        return WORKLOAD_SPINE_OPTION_PRICING, _SPINE_RANK_BY_ID[WORKLOAD_SPINE_OPTION_PRICING]
    if re.search(r"event|taq|window|crisis|stress", s):
        return WORKLOAD_SPINE_EVENT_WINDOW, _SPINE_RANK_BY_ID[WORKLOAD_SPINE_EVENT_WINDOW]
    return "", 0


def workload_spine_rank_for_id(workload_spine_id: str) -> int:
    return _SPINE_RANK_BY_ID.get(workload_spine_id, 0)


def portfolio_family_label(
    *,
    universe_name: str = "",
    n_symbols: int = 0,
    book_tag: str = "",
) -> str:
    parts = [universe_name or "default", str(n_symbols), book_tag or "none"]
    raw = "|".join(parts)
    return f"pf_{hashlib.sha256(raw.encode()).hexdigest()[:10]}"


def model_family_label(
    *,
    engine_or_model: str,
    path_bucket: str = "",
    phase: str = "",
) -> str:
    raw = f"{engine_or_model}|{path_bucket}|{phase}"
    return f"mdl_{hashlib.sha256(raw.encode()).hexdigest()[:10]}"


def feature_space_signature(
    n_before: int,
    n_after: int,
    condenser_name: str = "pca",
) -> str:
    raw = f"{condenser_name}:{n_before}->{n_after}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def workload_family_label(
    *,
    pipeline_stage: str,
    portfolio_family: str,
    model_family: str,
    event_stress: bool = False,
) -> str:
    payload = {
        "stage": pipeline_stage,
        "portfolio": portfolio_family,
        "model": model_family,
        "event_stress": event_stress,
    }
    h = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:14]
    return f"wl_{h}"


def event_window_stress_tag(symbols: Sequence[str], window_id: str) -> str:
    raw = f"{window_id}:{','.join(sorted(symbols))}"
    return f"evt_{hashlib.sha256(raw.encode()).hexdigest()[:10]}"
