"""Evidence synthesis primitives for guided-cache architecture hypothesis.

This module builds evidence tables and claim classifications from existing
canonical workload artifacts. It is intentionally evidence-bounded and does not
claim hardware-cache proof.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


EVIDENCE_MEASURED = "measured"
EVIDENCE_DERIVED = "derived"
EVIDENCE_PROXY = "proxy-supported"
EVIDENCE_HYPOTHESIS = "hypothesis"
EVIDENCE_DEFERRED = "deferred"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except Exception:
        return default


def _safe_nunique(series: Any) -> int:
    if series is None or len(series) == 0:
        return 0
    return int(series.dropna().nunique())


def _read_csv_if_exists(path: Path) -> Any:
    import pandas as pd

    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _read_json_if_exists(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_canonical_evidence_tables(outputs_root: str | Path = "outputs") -> Dict[str, Any]:
    """Load canonical prior-phase tables from outputs directory."""
    root = Path(outputs_root)
    return {
        "event_library_comparison": _read_csv_if_exists(
            root / "event_library_comparison_phase" / "event_library_comparison.csv"
        ),
        "event_workload_signature_summary": _read_csv_if_exists(
            root / "event_library_comparison_phase" / "workload_signature_summary.csv"
        ),
        "cache_study_rankings": _read_csv_if_exists(
            root / "cache_study_analysis_phase" / "cache_study_rankings.csv"
        ),
        "feature_panel_comparison_summary": _read_csv_if_exists(
            root / "feature_panel_comparison_phase" / "feature_panel_comparison_summary.csv"
        ),
        "portfolio_risk_rankings": _read_csv_if_exists(
            root / "portfolio_risk_workloads_phase" / "portfolio_risk_rankings.csv"
        ),
        "pricing_workload_rankings": _read_csv_if_exists(
            root / "pricing_workload_family_phase" / "pricing_workload_rankings.csv"
        ),
        "unified_workload_observations": _read_csv_if_exists(
            root / "unified_observability_phase" / "unified_workload_observations.csv"
        ),
        "unified_workload_rankings": _read_csv_if_exists(
            root / "unified_observability_phase" / "unified_workload_rankings.csv"
        ),
        "unified_workload_manifest": _read_json_if_exists(
            root / "unified_observability_phase" / "unified_workload_manifest.json"
        ),
        "similarity_candidate_summary": _read_csv_if_exists(
            root / "similarity_caching_hypothesis_phase" / "similarity_candidate_summary.csv"
        ),
        "similarity_hypothesis_rankings": _read_csv_if_exists(
            root / "similarity_caching_hypothesis_phase" / "similarity_hypothesis_rankings.csv"
        ),
        "similarity_hypothesis_manifest": _read_json_if_exists(
            root / "similarity_caching_hypothesis_phase" / "similarity_hypothesis_manifest.json"
        ),
    }


def collect_family_evidence_summary(
    *,
    unified_workload_observations: Any,
    unified_workload_rankings: Optional[Any] = None,
    event_library_comparison: Optional[Any] = None,
    feature_panel_comparison_summary: Optional[Any] = None,
    portfolio_risk_rankings: Optional[Any] = None,
    pricing_workload_rankings: Optional[Any] = None,
) -> Any:
    """Collect cross-family evidence summary from canonical tables."""
    import pandas as pd

    obs = unified_workload_observations
    if obs is None or len(obs) == 0:
        return pd.DataFrame(
            columns=[
                "workload_family",
                "n_variants",
                "n_rows_mean",
                "timing_p90_mean",
                "reuse_proxy_count_mean",
                "reconstruction_proxy_count_mean",
                "mac_ready_ratio",
                "hpc_deferred_ratio",
                "family_ranking_score",
                "evidence_strength_score",
                "evidence_level",
                "source_artifacts",
            ]
        )

    ranking_map: Dict[str, float] = {}
    if unified_workload_rankings is not None and len(unified_workload_rankings):
        sub = unified_workload_rankings.loc[
            unified_workload_rankings["ranking_axis"] == "family_cache_study_value"
        ].copy()
        if len(sub):
            ranking_map = {
                str(r.workload_family): _safe_float(r.score, 0.0)
                for r in sub.itertuples(index=False)
            }

    rows = []
    for family, g in obs.groupby("workload_family", dropna=False):
        family = str(family)
        source_artifacts = ["unified_workload_observations.csv"]
        if family.startswith("event") and event_library_comparison is not None and len(event_library_comparison):
            source_artifacts.append("event_library_comparison.csv")
        if family.startswith("feature") and feature_panel_comparison_summary is not None and len(feature_panel_comparison_summary):
            source_artifacts.append("feature_panel_comparison_summary.csv")
        if family.startswith("portfolio") and portfolio_risk_rankings is not None and len(portfolio_risk_rankings):
            source_artifacts.append("portfolio_risk_rankings.csv")
        if family.startswith("pricing") and pricing_workload_rankings is not None and len(pricing_workload_rankings):
            source_artifacts.append("pricing_workload_rankings.csv")

        n_variants = int(_safe_nunique(g["workload_variant"]))
        n_rows_mean = _safe_float(g["n_rows"].mean())
        timing_p90_mean = _safe_float(g["timing_p90"].mean())
        reuse_mean = _safe_float(g["reuse_proxy_count"].mean())
        recon_mean = _safe_float(g["reconstruction_proxy_count"].mean())
        mac_ratio = _safe_float(g["mac_executable_now"].astype(float).mean())
        hpc_ratio = _safe_float(g["deferred_to_hpc"].astype(float).mean())
        fam_score = _safe_float(ranking_map.get(family, 0.0))
        # Score is derived from direct and proxy signals; still not hardware proof.
        evidence_strength = (
            0.25 * min(1.0, n_variants / 6.0)
            + 0.20 * min(1.0, math.log10(max(1.0, n_rows_mean)) / 5.0)
            + 0.25 * min(1.0, math.log10(max(1.0, reuse_mean + recon_mean + 1.0)) / 3.0)
            + 0.20 * mac_ratio
            + 0.10 * min(1.0, fam_score)
        )
        rows.append(
            {
                "workload_family": family,
                "n_variants": n_variants,
                "n_rows_mean": n_rows_mean,
                "timing_p90_mean": timing_p90_mean,
                "reuse_proxy_count_mean": reuse_mean,
                "reconstruction_proxy_count_mean": recon_mean,
                "mac_ready_ratio": mac_ratio,
                "hpc_deferred_ratio": hpc_ratio,
                "family_ranking_score": fam_score,
                "evidence_strength_score": float(max(0.0, min(1.0, evidence_strength))),
                "evidence_level": EVIDENCE_DERIVED,
                "source_artifacts": ";".join(source_artifacts),
            }
        )
    return pd.DataFrame(rows).sort_values(
        "evidence_strength_score", ascending=False
    ).reset_index(drop=True)


def collect_similarity_hypothesis_summary(
    *,
    similarity_candidate_summary: Any,
    similarity_hypothesis_rankings: Any,
) -> Any:
    """Collect summary metrics from similarity-hypothesis outputs."""
    import pandas as pd

    rows = []
    c = similarity_candidate_summary
    h = similarity_hypothesis_rankings
    cand_count = int(len(c)) if c is not None else 0
    within_count = int((c["analysis_scope"] == "within_family").sum()) if c is not None and len(c) else 0
    cross_count = int((c["analysis_scope"] == "cross_family").sum()) if c is not None and len(c) else 0
    exact_count = int((c["similarity_relationship"] == "exact_identity_similarity").sum()) if c is not None and len(c) else 0
    near_count = int(
        c["similarity_relationship"].isin(
            [
                "near_identity_structural_similarity",
                "same_family_similarity",
                "parameter_neighborhood_similarity",
            ]
        ).sum()
    ) if c is not None and len(c) else 0
    rows.extend(
        [
            {
                "metric_name": "candidate_count",
                "metric_value": float(cand_count),
                "evidence_level": EVIDENCE_DERIVED,
                "notes": "candidate table built from operational similarity signatures",
            },
            {
                "metric_name": "within_family_candidate_count",
                "metric_value": float(within_count),
                "evidence_level": EVIDENCE_DERIVED,
                "notes": "within-family stage is locked first analysis stage",
            },
            {
                "metric_name": "cross_family_candidate_count",
                "metric_value": float(cross_count),
                "evidence_level": EVIDENCE_PROXY,
                "notes": "cross-family comparisons are approximate",
            },
            {
                "metric_name": "exact_identity_candidate_count",
                "metric_value": float(exact_count),
                "evidence_level": EVIDENCE_MEASURED,
                "notes": "exact identity under deterministic signature match",
            },
            {
                "metric_name": "near_similarity_candidate_count",
                "metric_value": float(near_count),
                "evidence_level": EVIDENCE_PROXY,
                "notes": "near-neighbor relationships use structural and proxy distances",
            },
        ]
    )
    if h is not None and len(h):
        for level in [
            EVIDENCE_MEASURED,
            EVIDENCE_DERIVED,
            EVIDENCE_PROXY,
            EVIDENCE_HYPOTHESIS,
            EVIDENCE_DEFERRED,
        ]:
            ct = int((h["evidence_level"] == level).sum())
            rows.append(
                {
                    "metric_name": f"hypothesis_ranking_count_{level}",
                    "metric_value": float(ct),
                    "evidence_level": EVIDENCE_DERIVED,
                    "notes": "counts from similarity_hypothesis_rankings.csv",
                }
            )
    return pd.DataFrame(rows)


def build_evidence_matrix(
    *,
    family_evidence_summary: Any,
    similarity_hypothesis_summary: Any,
    similarity_candidate_summary: Any,
    unified_workload_observations: Any,
    unified_workload_rankings: Any,
) -> Any:
    """Build guided-cache evidence matrix with explicit claim typing."""
    import pandas as pd

    def _metric(name: str) -> float:
        if similarity_hypothesis_summary is None or len(similarity_hypothesis_summary) == 0:
            return 0.0
        sub = similarity_hypothesis_summary.loc[
            similarity_hypothesis_summary["metric_name"] == name
        ]
        if len(sub) == 0:
            return 0.0
        return _safe_float(sub["metric_value"].iloc[0])

    exact_ct = _metric("exact_identity_candidate_count")
    near_ct = _metric("near_similarity_candidate_count")
    within_ct = _metric("within_family_candidate_count")
    cross_ct = _metric("cross_family_candidate_count")

    deferred_variants = int(
        unified_workload_observations["deferred_to_hpc"].sum()
    ) if unified_workload_observations is not None and len(unified_workload_observations) else 0

    rows = [
        {
            "claim_id": "claim_workload_signature_layer_supported",
            "claim_area": "workload_signature_layer",
            "architecture_component": "workload_signature_layer",
            "source_families": "event;feature_panel;portfolio_risk;pricing",
            "source_artifacts": "unified_workload_observations.csv",
            "evidence_level": EVIDENCE_MEASURED,
            "support_strength": float(1.0 if unified_workload_observations is not None and len(unified_workload_observations) else 0.0),
            "claim_text": "Common workload signatures are available across all four workload families.",
            "what_strengthens_later": "expand variant coverage and rerun unified observation exports",
        },
        {
            "claim_id": "claim_exact_match_reuse_candidates",
            "claim_area": "exact_match_reuse_layer",
            "architecture_component": "exact_match_reuse_layer",
            "source_families": "all",
            "source_artifacts": "similarity_candidate_summary.csv",
            "evidence_level": EVIDENCE_MEASURED if exact_ct > 0 else EVIDENCE_HYPOTHESIS,
            "support_strength": float(exact_ct),
            "claim_text": "Exact-match reuse candidates are present under deterministic identity signatures.",
            "what_strengthens_later": "measure retrieval hit quality under controlled replay tests",
        },
        {
            "claim_id": "claim_similarity_aware_reuse_candidates",
            "claim_area": "similarity_aware_reuse_layer",
            "architecture_component": "similarity_aware_reuse_layer",
            "source_families": "all",
            "source_artifacts": "similarity_candidate_summary.csv;similarity_hypothesis_rankings.csv",
            "evidence_level": EVIDENCE_PROXY,
            "support_strength": float(near_ct),
            "claim_text": "Similarity-aware near-neighbor reuse candidates are present with proxy support.",
            "what_strengthens_later": "controlled ablation to test threshold sensitivity and retrieval quality",
        },
        {
            "claim_id": "claim_guided_routing_layer_hypothesis",
            "claim_area": "routing_prioritization_layer",
            "architecture_component": "routing_prioritization_layer",
            "source_families": "all",
            "source_artifacts": "unified_workload_rankings.csv;similarity_candidate_summary.csv",
            "evidence_level": EVIDENCE_HYPOTHESIS,
            "support_strength": float(max(within_ct, near_ct) / max(1.0, within_ct + cross_ct)),
            "claim_text": "A guided routing/prioritization layer may improve reuse targeting.",
            "what_strengthens_later": "implement controlled replay simulator with exact-vs-similarity routing policy variants",
        },
        {
            "claim_id": "claim_hardware_aware_layer_deferred",
            "claim_area": "deferred_hardware_aware_layer",
            "architecture_component": "deferred_hardware_aware_layer",
            "source_families": "all",
            "source_artifacts": "mac_vs_hpc_observability policy",
            "evidence_level": EVIDENCE_DEFERRED,
            "support_strength": float(deferred_variants),
            "claim_text": "Hardware-aware layer cannot be confirmed from current Mac-side proxies alone.",
            "what_strengthens_later": "PMU-backed HPC runs for L1/L2/L3, TLB, NUMA, and cache-line behavior",
        },
        {
            "claim_id": "claim_hpc_qhpc_escalation_deferred",
            "claim_area": "deferred_hpc_qhpc_escalation_layer",
            "architecture_component": "deferred_hpc_qhpc_escalation_layer",
            "source_families": "all",
            "source_artifacts": "unified_workload_observations.csv;similarity_hypothesis_rankings.csv",
            "evidence_level": EVIDENCE_DEFERRED,
            "support_strength": float(deferred_variants),
            "claim_text": "HPC/QHPC escalation remains a later validation stage, not current proof.",
            "what_strengthens_later": "BigRed200-scale sweeps and eventual hybrid QHPC experiments",
        },
    ]

    # Family-specific synthesis rows.
    if family_evidence_summary is not None and len(family_evidence_summary):
        for r in family_evidence_summary.itertuples(index=False):
            rows.append(
                {
                    "claim_id": f"claim_family_{r.workload_family}_reusable_structures",
                    "claim_area": "family_reuse_structure",
                    "architecture_component": "workload_signature_layer",
                    "source_families": str(r.workload_family),
                    "source_artifacts": str(r.source_artifacts),
                    "evidence_level": EVIDENCE_DERIVED
                    if float(r.evidence_strength_score) >= 0.45
                    else EVIDENCE_PROXY,
                    "support_strength": float(r.evidence_strength_score),
                    "claim_text": f"{r.workload_family} has reusable workload structures relevant to guided-cache study.",
                    "what_strengthens_later": "larger replay sets and controlled policy comparison per family",
                }
            )
    return pd.DataFrame(rows)


def classify_supported_vs_deferred_claims(evidence_matrix: Any) -> Dict[str, Any]:
    """Classify claims into supported vs deferred/hypothesis tables."""
    if evidence_matrix is None or len(evidence_matrix) == 0:
        return {"supported_claims": evidence_matrix, "deferred_claims": evidence_matrix}
    supported = evidence_matrix.loc[
        evidence_matrix["evidence_level"].isin(
            [EVIDENCE_MEASURED, EVIDENCE_DERIVED, EVIDENCE_PROXY]
        )
    ].copy()
    deferred = evidence_matrix.loc[
        evidence_matrix["evidence_level"].isin([EVIDENCE_HYPOTHESIS, EVIDENCE_DEFERRED])
    ].copy()
    if len(supported):
        supported["support_tier"] = supported["support_strength"].apply(
            lambda x: "strong" if _safe_float(x) >= 0.75 else ("moderate" if _safe_float(x) >= 0.35 else "weak")
        )
    if len(deferred):
        deferred["deferred_reason"] = deferred["evidence_level"].apply(
            lambda x: "needs_hardware_or_scale_validation"
            if x == EVIDENCE_DEFERRED
            else "insufficient_direct_evidence"
        )
    return {"supported_claims": supported, "deferred_claims": deferred}


def summarize_guided_cache_evidence(
    *,
    family_evidence_summary: Any,
    similarity_hypothesis_summary: Any,
    evidence_matrix: Any,
) -> Dict[str, Any]:
    """Summarize guided-cache evidence synthesis for manifests/reporting."""
    claim_counts = (
        evidence_matrix["evidence_level"].value_counts().to_dict()
        if evidence_matrix is not None and len(evidence_matrix)
        else {}
    )
    strongest_families = (
        family_evidence_summary.sort_values("evidence_strength_score", ascending=False)
        .head(4)[["workload_family", "evidence_strength_score"]]
        .to_dict(orient="records")
        if family_evidence_summary is not None and len(family_evidence_summary)
        else []
    )
    exact_ct = 0.0
    near_ct = 0.0
    if similarity_hypothesis_summary is not None and len(similarity_hypothesis_summary):
        sub_exact = similarity_hypothesis_summary.loc[
            similarity_hypothesis_summary["metric_name"] == "exact_identity_candidate_count"
        ]
        sub_near = similarity_hypothesis_summary.loc[
            similarity_hypothesis_summary["metric_name"] == "near_similarity_candidate_count"
        ]
        if len(sub_exact):
            exact_ct = _safe_float(sub_exact["metric_value"].iloc[0])
        if len(sub_near):
            near_ct = _safe_float(sub_near["metric_value"].iloc[0])
    return {
        "summary_statement": (
            "guided-cache architecture remains a hypothesis layer: exact-match reuse has direct support, "
            "similarity-aware reuse has proxy support, and hardware-aware behavior is deferred"
        ),
        "claim_counts_by_evidence_level": claim_counts,
        "strongest_families_by_evidence": strongest_families,
        "exact_identity_candidate_count": exact_ct,
        "near_similarity_candidate_count": near_ct,
    }

