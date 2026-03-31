"""Decision overhead and net-utility accounting.

Measures the cost of cache-guided decisions so we can determine
whether reuse actually helps or hurts on a given workload.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class OverheadRow:
    request_id: str
    workload_family: str
    engine: str
    lookup_overhead_ms: float
    similarity_search_overhead_ms: float
    decision_overhead_ms: float
    validation_overhead_ms: float
    total_overhead_ms: float
    gross_runtime_saved_ms: float
    net_runtime_saved_ms: float
    reuse_harm_penalty_ms: float
    net_utility_ms: float
    net_utility_label: str  # "beneficial" | "neutral" | "harmful"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "workload_family": self.workload_family,
            "engine": self.engine,
            "lookup_overhead_ms": round(self.lookup_overhead_ms, 4),
            "similarity_search_overhead_ms": round(self.similarity_search_overhead_ms, 4),
            "decision_overhead_ms": round(self.decision_overhead_ms, 4),
            "validation_overhead_ms": round(self.validation_overhead_ms, 4),
            "total_overhead_ms": round(self.total_overhead_ms, 4),
            "gross_runtime_saved_ms": round(self.gross_runtime_saved_ms, 4),
            "net_runtime_saved_ms": round(self.net_runtime_saved_ms, 4),
            "reuse_harm_penalty_ms": round(self.reuse_harm_penalty_ms, 4),
            "net_utility_ms": round(self.net_utility_ms, 4),
            "net_utility_label": self.net_utility_label,
        }


def compute_overhead_accounting(
    result_rows: Sequence[Dict[str, Any]],
    *,
    validation_results: Optional[Sequence[Dict[str, Any]]] = None,
) -> List[OverheadRow]:
    """Compute per-request overhead and net utility."""
    val_cost_map: Dict[str, float] = {}
    if validation_results:
        for v in validation_results:
            val_cost_map[str(v.get("request_id", ""))] = float(v.get("recompute_time_ms", 0.0))

    rows: List[OverheadRow] = []
    for r in result_rows:
        rid = str(r.get("request_id", ""))
        total_rt = float(r.get("total_runtime_ms", 0.0))
        compute_ms = float(r.get("pricing_compute_time_ms", 0.0))
        saved_proxy = float(r.get("compute_avoided_proxy", 0.0))
        time_saved = float(r.get("time_saved_proxy", 0.0))

        lookup_ms = total_rt if r.get("cache_hit") else min(total_rt * 0.05, 0.5)
        sim_search_ms = 0.0
        if r.get("similarity_group_id"):
            sim_search_ms = min(total_rt * 0.02, 0.2)

        decision_ms = lookup_ms + sim_search_ms
        validation_ms = val_cost_map.get(rid, 0.0)
        total_overhead = decision_ms + validation_ms

        gross_saved = time_saved
        harm_penalty = 0.0
        gt_label = str(r.get("ground_truth_cacheability_label", ""))
        if gt_label in ("similarity_reusable_unsafe",) and (r.get("cache_hit") or r.get("similarity_hit")):
            harm_penalty = compute_ms * 0.5

        net_saved = gross_saved - total_overhead - harm_penalty
        net_utility = net_saved

        if net_utility > 0.5:
            label = "beneficial"
        elif net_utility < -0.5:
            label = "harmful"
        else:
            label = "neutral"

        rows.append(OverheadRow(
            request_id=rid,
            workload_family=str(r.get("workload_family", "")),
            engine=str(r.get("engine", "")),
            lookup_overhead_ms=lookup_ms,
            similarity_search_overhead_ms=sim_search_ms,
            decision_overhead_ms=decision_ms,
            validation_overhead_ms=validation_ms,
            total_overhead_ms=total_overhead,
            gross_runtime_saved_ms=gross_saved,
            net_runtime_saved_ms=net_saved,
            reuse_harm_penalty_ms=harm_penalty,
            net_utility_ms=net_utility,
            net_utility_label=label,
        ))
    return rows


def summarize_overhead(
    rows: Sequence[OverheadRow],
) -> Dict[str, Any]:
    """Aggregate overhead accounting."""
    n = len(rows)
    if n == 0:
        return {"total_requests": 0, "status": "no_data"}

    total_overhead = sum(r.total_overhead_ms for r in rows)
    total_gross = sum(r.gross_runtime_saved_ms for r in rows)
    total_net = sum(r.net_runtime_saved_ms for r in rows)
    total_harm = sum(r.reuse_harm_penalty_ms for r in rows)
    total_val = sum(r.validation_overhead_ms for r in rows)

    beneficial = sum(1 for r in rows if r.net_utility_label == "beneficial")
    harmful = sum(1 for r in rows if r.net_utility_label == "harmful")
    neutral = sum(1 for r in rows if r.net_utility_label == "neutral")

    by_family: Dict[str, List[OverheadRow]] = defaultdict(list)
    for r in rows:
        by_family[r.workload_family].append(r)

    family_summaries = {}
    for fam, frows in by_family.items():
        fn = len(frows)
        family_summaries[fam] = {
            "count": fn,
            "total_overhead_ms": round(sum(r.total_overhead_ms for r in frows), 4),
            "total_gross_saved_ms": round(sum(r.gross_runtime_saved_ms for r in frows), 4),
            "total_net_saved_ms": round(sum(r.net_runtime_saved_ms for r in frows), 4),
            "mean_net_utility_ms": round(sum(r.net_utility_ms for r in frows) / fn, 4),
            "beneficial_count": sum(1 for r in frows if r.net_utility_label == "beneficial"),
            "harmful_count": sum(1 for r in frows if r.net_utility_label == "harmful"),
        }

    return {
        "total_requests": n,
        "total_overhead_ms": round(total_overhead, 4),
        "total_gross_saved_ms": round(total_gross, 4),
        "total_net_saved_ms": round(total_net, 4),
        "total_harm_penalty_ms": round(total_harm, 4),
        "total_validation_cost_ms": round(total_val, 4),
        "mean_overhead_per_request_ms": round(total_overhead / n, 4),
        "mean_net_utility_ms": round(total_net / n, 4),
        "beneficial_count": beneficial,
        "harmful_count": harmful,
        "neutral_count": neutral,
        "beneficial_rate": round(beneficial / n, 6),
        "harmful_rate": round(harmful / n, 6),
        "net_utility_positive": total_net > 0,
        "by_family": family_summaries,
    }


def write_net_utility_summary(
    overhead_summary: Dict[str, Any],
    output_dir: Path,
) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "net_utility_summary.json"
    path.write_text(json.dumps(overhead_summary, indent=2))
    return str(path)
