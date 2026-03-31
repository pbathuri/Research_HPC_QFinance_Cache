"""Finance-inspired workload family registry with realism metadata.

Each workload family has explicit metadata describing its analogy to real
quantitative-finance compute patterns, expected reuse/locality behavior,
and whether it is a synthetic control or finance-representative workload.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class WorkloadFamilyMeta:
    """Metadata for one workload family."""

    workload_family: str
    realism_tier: str  # "finance_inspired", "finance_analogous", "synthetic_control", "stress_control"
    finance_context: str
    expected_reuse_mode: str  # "exact", "similarity", "mixed", "none"
    expected_locality_mode: str  # "strong_temporal", "moderate", "weak", "streaming"
    approximation_risk: str  # "none", "low", "moderate", "high"
    synthetic_control_flag: bool
    comments: str
    finance_analogies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workload_family": self.workload_family,
            "realism_tier": self.realism_tier,
            "finance_context": self.finance_context,
            "expected_reuse_mode": self.expected_reuse_mode,
            "expected_locality_mode": self.expected_locality_mode,
            "approximation_risk": self.approximation_risk,
            "synthetic_control_flag": self.synthetic_control_flag,
            "comments": self.comments,
            "finance_analogies": list(self.finance_analogies),
        }


WORKLOAD_FAMILY_REGISTRY: Dict[str, WorkloadFamilyMeta] = {
    "exact_repeat_pricing": WorkloadFamilyMeta(
        workload_family="exact_repeat_pricing",
        realism_tier="finance_inspired",
        finance_context=(
            "Repeated valuation of the same instrument under identical market state. "
            "Occurs in intraday re-checks, audit replay, regulatory scenario re-run, "
            "and cache-warm restart after process failure."
        ),
        expected_reuse_mode="exact",
        expected_locality_mode="strong_temporal",
        approximation_risk="none",
        synthetic_control_flag=False,
        comments="Baseline for exact-match cache validation. High expected hit rate in lane_a.",
        finance_analogies=[
            "Intraday re-valuation with unchanged market snapshot",
            "Regulatory scenario re-run for audit trail",
            "Cache-warm restart after process failure",
            "Identical Greeks computation across risk aggregation trees",
        ],
    ),
    "near_repeat_pricing": WorkloadFamilyMeta(
        workload_family="near_repeat_pricing",
        realism_tier="finance_inspired",
        finance_context=(
            "Valuation of similar instruments under small market perturbations. "
            "Core pattern in intraday scenario ladders, bump-and-revalue Greeks, "
            "and sensitivity analysis where parameters shift by small deltas."
        ),
        expected_reuse_mode="similarity",
        expected_locality_mode="moderate",
        approximation_risk="moderate",
        synthetic_control_flag=False,
        comments=(
            "Primary similarity-cache test family. Clustered parameter neighborhoods "
            "create natural similarity groups suitable for approximate reuse."
        ),
        finance_analogies=[
            "Bump-and-revalue Greeks computation",
            "Intraday scenario ladders with small market shifts",
            "Sensitivity analysis under delta/gamma/vega bumps",
            "Cross-sectional basket repricing with correlated parameter neighborhoods",
        ],
    ),
    "path_ladder_pricing": WorkloadFamilyMeta(
        workload_family="path_ladder_pricing",
        realism_tier="finance_inspired",
        finance_context=(
            "Convergence study: same instrument priced with increasing path counts. "
            "Standard practice in Monte Carlo convergence assessment, production "
            "quality checks, and adaptive-precision pricing workflows."
        ),
        expected_reuse_mode="mixed",
        expected_locality_mode="moderate",
        approximation_risk="low",
        synthetic_control_flag=False,
        comments=(
            "Tests whether cache recognizes structural similarity across path counts. "
            "In lane_a, some seeds are reused across ladder steps."
        ),
        finance_analogies=[
            "Monte Carlo convergence analysis (increasing path count)",
            "Adaptive-precision pricing with quality thresholds",
            "Production vs quick-check pricing path count tiers",
            "Path-count sensitivity for variance-reduction validation",
        ],
    ),
    "portfolio_cluster_condensation": WorkloadFamilyMeta(
        workload_family="portfolio_cluster_condensation",
        realism_tier="finance_analogous",
        finance_context=(
            "Portfolio revaluation where instruments cluster by underlying/sector. "
            "Mirrors portfolio risk aggregation, cluster-based representative "
            "pricing, and feature-condensation workflows."
        ),
        expected_reuse_mode="similarity",
        expected_locality_mode="moderate",
        approximation_risk="moderate",
        synthetic_control_flag=False,
        comments=(
            "Tests portfolio-level similarity reuse. Each cluster has slightly "
            "perturbed members that share a representative instrument."
        ),
        finance_analogies=[
            "Portfolio cluster revaluation (sector/underlying groups)",
            "Feature-condensation for dimensionality reduction in risk",
            "Representative-instrument approximation in large books",
            "Rolling horizon refreshes with overlapping positions",
        ],
    ),
    "overlapping_event_window_rebuild": WorkloadFamilyMeta(
        workload_family="overlapping_event_window_rebuild",
        realism_tier="finance_analogous",
        finance_context=(
            "Overlapping event-window analysis where successive windows share "
            "temporal and parameter overlap. Models event-study workflows, "
            "rolling VaR windows, and intraday signal rebuilds."
        ),
        expected_reuse_mode="mixed",
        expected_locality_mode="strong_temporal",
        approximation_risk="low",
        synthetic_control_flag=False,
        comments=(
            "Tests temporal overlap reuse. In lane_a, overlapping windows "
            "with identical parameters produce exact hits."
        ),
        finance_analogies=[
            "Rolling VaR/CVaR window computation",
            "Overlapping event-study windows for abnormal return estimation",
            "Intraday signal rebuilds with sliding observation windows",
            "Time-series cross-validation with overlapping folds",
        ],
    ),
    "stress_churn_pricing": WorkloadFamilyMeta(
        workload_family="stress_churn_pricing",
        realism_tier="synthetic_control",
        finance_context=(
            "High-churn, low-reuse stress workload with randomized parameters. "
            "Does not represent a typical finance workflow but serves as a control "
            "for measuring cache overhead under adversarial conditions."
        ),
        expected_reuse_mode="none",
        expected_locality_mode="streaming",
        approximation_risk="none",
        synthetic_control_flag=True,
        comments=(
            "Synthetic stress control. Expected near-zero hit rate in lane_b. "
            "Measures cache overhead without reuse benefit. Essential baseline "
            "for validating that cache does not claim benefit where none exists."
        ),
        finance_analogies=[
            "Stress scenario: fully randomized instrument universe (adversarial)",
            "Cache overhead measurement under worst-case conditions",
        ],
    ),
    "intraday_scenario_ladder": WorkloadFamilyMeta(
        workload_family="intraday_scenario_ladder",
        realism_tier="finance_inspired",
        finance_context=(
            "Systematic scenario ladder: base instrument repriced under ordered "
            "spot/vol/rate shocks. Core pattern in front-office risk systems "
            "where PnL attribution requires ordered sensitivity sweeps."
        ),
        expected_reuse_mode="similarity",
        expected_locality_mode="strong_temporal",
        approximation_risk="low",
        synthetic_control_flag=False,
        comments=(
            "New family modeling ordered scenario grids. Adjacent scenarios "
            "have high parameter similarity, creating natural similarity reuse."
        ),
        finance_analogies=[
            "Front-office PnL attribution scenario ladder",
            "Ordered spot/vol/rate shock grids for desk-level risk",
            "Regulatory stress test scenario sequences",
        ],
    ),
    "cross_sectional_basket_repricing": WorkloadFamilyMeta(
        workload_family="cross_sectional_basket_repricing",
        realism_tier="finance_inspired",
        finance_context=(
            "Large basket of correlated underlyings repriced simultaneously. "
            "Parameter neighborhoods arise from sector correlation, shared "
            "vol surface, and common rate curves."
        ),
        expected_reuse_mode="similarity",
        expected_locality_mode="moderate",
        approximation_risk="moderate",
        synthetic_control_flag=False,
        comments=(
            "Tests cross-sectional similarity. Instruments sharing sector/vol "
            "characteristics create natural similarity groups."
        ),
        finance_analogies=[
            "Index constituent repricing with correlated underlyings",
            "Basket option component valuation",
            "Cross-sectional risk factor decomposition",
        ],
    ),
    "rolling_horizon_refresh": WorkloadFamilyMeta(
        workload_family="rolling_horizon_refresh",
        realism_tier="finance_inspired",
        finance_context=(
            "End-of-day to next-day roll: same book, shifted horizon, "
            "slightly updated market data. High overlap with previous day."
        ),
        expected_reuse_mode="mixed",
        expected_locality_mode="strong_temporal",
        approximation_risk="low",
        synthetic_control_flag=False,
        comments=(
            "Models the daily roll pattern. Most instruments are re-priced "
            "with small maturity/rate shifts, creating both exact and "
            "similarity reuse opportunities."
        ),
        finance_analogies=[
            "End-of-day/start-of-day portfolio roll",
            "T+1 settlement revaluation",
            "Daily mark-to-market with overnight parameter drift",
        ],
    ),
    "hotset_coldset_mixed": WorkloadFamilyMeta(
        workload_family="hotset_coldset_mixed",
        realism_tier="finance_analogous",
        finance_context=(
            "Mixed workload with a hot set of frequently accessed instruments "
            "and a cold tail of rarely accessed ones. Models real trading "
            "book access patterns where a few instruments dominate volume."
        ),
        expected_reuse_mode="exact",
        expected_locality_mode="strong_temporal",
        approximation_risk="none",
        synthetic_control_flag=False,
        comments=(
            "Tests Zipfian-like access distribution. Hot instruments should "
            "achieve high hit rates; cold tail measures miss overhead."
        ),
        finance_analogies=[
            "Active trading book with hot/cold instrument tiers",
            "Market-making inventory with concentrated flow",
            "Pareto-distributed trade volume across instrument universe",
        ],
    ),
    "parameter_shock_grid": WorkloadFamilyMeta(
        workload_family="parameter_shock_grid",
        realism_tier="finance_inspired",
        finance_context=(
            "Factorial grid of parameter shocks for stress testing. "
            "Models regulatory CCAR/DFAST-style grid computation."
        ),
        expected_reuse_mode="none",
        expected_locality_mode="weak",
        approximation_risk="none",
        synthetic_control_flag=False,
        comments=(
            "Limited reuse expected since each grid point is unique. "
            "Tests cache overhead under systematic but non-repeating workload."
        ),
        finance_analogies=[
            "CCAR/DFAST regulatory stress test grids",
            "Full factorial sensitivity analysis",
            "Exhaustive parameter sweep for model validation",
        ],
    ),
}


def get_family_meta(family_id: str) -> WorkloadFamilyMeta:
    """Look up metadata for a workload family, raising if unknown."""
    if family_id not in WORKLOAD_FAMILY_REGISTRY:
        raise KeyError(f"Unknown workload family: {family_id!r}")
    return WORKLOAD_FAMILY_REGISTRY[family_id]


def get_all_family_metadata() -> List[Dict[str, Any]]:
    """Return metadata for all registered families."""
    return [meta.to_dict() for meta in WORKLOAD_FAMILY_REGISTRY.values()]


def get_finance_representative_families() -> List[str]:
    """Return family IDs that are finance-representative (not synthetic controls)."""
    return [
        fid
        for fid, meta in WORKLOAD_FAMILY_REGISTRY.items()
        if not meta.synthetic_control_flag
    ]


def get_synthetic_control_families() -> List[str]:
    """Return family IDs that are synthetic controls."""
    return [
        fid
        for fid, meta in WORKLOAD_FAMILY_REGISTRY.items()
        if meta.synthetic_control_flag
    ]


def build_workload_regime_summary(
    result_rows: list,
    *,
    family_key: str = "workload_family",
) -> List[Dict[str, Any]]:
    """Build per-family regime summary combining registry metadata with observed results."""
    from collections import defaultdict

    by_family: Dict[str, list] = defaultdict(list)
    for row in result_rows:
        fam = row.get(family_key, "")
        if fam:
            by_family[fam].append(row)

    summaries: List[Dict[str, Any]] = []
    for fam_id, rows in by_family.items():
        meta = WORKLOAD_FAMILY_REGISTRY.get(fam_id)
        total = len(rows)
        hits = sum(1 for r in rows if r.get("cache_hit"))
        sim_hits = sum(1 for r in rows if r.get("similarity_hit"))

        entry: Dict[str, Any] = {
            "workload_family": fam_id,
            "observed_request_count": total,
            "observed_exact_hit_rate": float(hits) / total if total > 0 else 0.0,
            "observed_similarity_hit_rate": float(sim_hits) / total if total > 0 else 0.0,
        }
        if meta:
            entry.update({
                "realism_tier": meta.realism_tier,
                "finance_context_short": meta.finance_context[:120],
                "expected_reuse_mode": meta.expected_reuse_mode,
                "expected_locality_mode": meta.expected_locality_mode,
                "approximation_risk": meta.approximation_risk,
                "synthetic_control_flag": meta.synthetic_control_flag,
            })
        else:
            entry.update({
                "realism_tier": "unregistered",
                "finance_context_short": "",
                "expected_reuse_mode": "unknown",
                "expected_locality_mode": "unknown",
                "approximation_risk": "unknown",
                "synthetic_control_flag": False,
            })
        summaries.append(entry)

    return summaries
