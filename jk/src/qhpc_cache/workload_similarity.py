"""Operational workload similarity signatures and comparisons.

This module defines research-grade similarity artifacts that are suitable for
hypothesis-building. These are not production cache keys or a deployed cache
controller.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


SIM_REL_EXACT_IDENTITY = "exact_identity_similarity"
SIM_REL_NEAR_IDENTITY = "near_identity_structural_similarity"
SIM_REL_SAME_FAMILY = "same_family_similarity"
SIM_REL_PARAMETER_NEIGHBOR = "parameter_neighborhood_similarity"
SIM_REL_WEAK = "weak_similarity"


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


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(float(value))
    except Exception:
        return default


def _bucket_log10(value: float) -> int:
    if value <= 0.0:
        return 0
    return int(max(0, math.floor(math.log10(max(1e-12, value))) + 1))


def _bucket_ratio(value: float, *, step: float = 0.1, max_bucket: int = 20) -> int:
    if value <= 0.0:
        return 0
    return int(min(max_bucket, max(1, math.floor(value / max(1e-12, step)))))


def _norm_abs_diff(a: float, b: float) -> float:
    den = max(1.0, abs(a), abs(b))
    return abs(a - b) / den


def _family_operational_type(workload_family: str) -> str:
    wf = (workload_family or "").strip().lower()
    if wf.startswith("event"):
        return "window_shape_similarity"
    if wf.startswith("feature"):
        return "panel_shape_similarity"
    if wf.startswith("portfolio"):
        return "scenario_family_similarity"
    if wf.startswith("pricing"):
        return "pricing_batch_similarity"
    return "cross_family_shape_similarity"


def build_similarity_signature(row: Mapping[str, Any]) -> Dict[str, Any]:
    """Build candidate similarity keys/signatures from one unified-observation row."""
    family = str(row.get("workload_family", ""))
    variant = str(row.get("workload_variant", ""))
    det = str(row.get("deterministic_label", ""))
    source_labels = str(row.get("source_dataset_labels", ""))
    n_rows = _safe_float(row.get("n_rows", 0.0))
    n_entities = _safe_float(row.get("n_entities", 0.0))
    n_periods = _safe_float(row.get("n_dates_or_periods", 0.0))
    join_width = _safe_float(row.get("join_width", 0.0))
    feat_before = _safe_float(row.get("feature_dim_before", 0.0))
    feat_after = _safe_float(row.get("feature_dim_after", 0.0))
    scenario_count = _safe_float(row.get("scenario_count", 0.0))
    batch_size = _safe_float(row.get("batch_size", 0.0))
    parameter_width = _safe_float(row.get("parameter_grid_width", 0.0))
    timing_p90 = _safe_float(row.get("timing_p90", 0.0))
    reuse_count = _safe_float(row.get("reuse_proxy_count", 0.0))
    recon_count = _safe_float(row.get("reconstruction_proxy_count", 0.0))
    reuse_density = _safe_float(row.get("cache_proxy_reuse_density", 0.0))

    # Exact identity: strongest key candidate.
    exact_payload = f"{family}|{variant}|{det}"
    exact_signature = hashlib.sha256(exact_payload.encode()).hexdigest()[:20]

    # Near-identity structural signature over discretized workload shape.
    shape_bins = {
        "n_rows_b": _bucket_log10(n_rows),
        "n_entities_b": _bucket_log10(n_entities),
        "n_periods_b": _bucket_log10(n_periods),
        "join_b": _bucket_log10(join_width),
        "feat_after_b": _bucket_log10(feat_after),
        "scenario_b": _bucket_log10(scenario_count),
        "batch_b": _bucket_log10(batch_size),
        "param_b": _bucket_log10(parameter_width),
        "timing_p90_b": _bucket_log10(timing_p90),
        "reuse_b": _bucket_log10(reuse_count + recon_count),
        "reuse_density_b": _bucket_ratio(reuse_density, step=0.05, max_bucket=30),
    }
    near_identity_signature = hashlib.sha256(
        json.dumps({"family": family, "shape_bins": shape_bins}, sort_keys=True).encode()
    ).hexdigest()[:20]

    # Same-family signature for grouping.
    family_signature = hashlib.sha256(
        json.dumps(
            {
                "family": family,
                "source_labels": sorted([s for s in source_labels.split(";") if s]),
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()[:18]

    # Parameter neighborhood signature.
    neighborhood_signature = hashlib.sha256(
        json.dumps(
            {
                "family": family,
                "batch_b": shape_bins["batch_b"],
                "param_b": shape_bins["param_b"],
                "scenario_b": shape_bins["scenario_b"],
                "feat_after_b": shape_bins["feat_after_b"],
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()[:18]

    timing_signature = hashlib.sha256(
        json.dumps(
            {
                "family": family,
                "timing_p90_b": shape_bins["timing_p90_b"],
                "n_rows_b": shape_bins["n_rows_b"],
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()[:18]
    reuse_signature = hashlib.sha256(
        json.dumps(
            {
                "family": family,
                "reuse_b": shape_bins["reuse_b"],
                "reuse_density_b": shape_bins["reuse_density_b"],
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()[:18]

    return {
        "workload_family": family,
        "workload_variant": variant,
        "deterministic_label": det,
        "exact_identity_signature": exact_signature,
        "near_identity_signature": near_identity_signature,
        "family_signature": family_signature,
        "neighborhood_signature": neighborhood_signature,
        "timing_signature": timing_signature,
        "reuse_signature": reuse_signature,
        "operational_similarity_type": _family_operational_type(family),
        "n_rows": n_rows,
        "n_entities": n_entities,
        "n_dates_or_periods": n_periods,
        "join_width": join_width,
        "feature_dim_before": feat_before,
        "feature_dim_after": feat_after,
        "scenario_count": scenario_count,
        "batch_size": batch_size,
        "parameter_grid_width": parameter_width,
        "timing_p90": timing_p90,
        "reuse_proxy_count": reuse_count,
        "reconstruction_proxy_count": recon_count,
        "cache_proxy_reuse_density": reuse_density,
        "shape_bin_payload": json.dumps(shape_bins, sort_keys=True),
    }


def build_similarity_signature_table(unified_observations: Any) -> Any:
    """Build per-variant similarity signature table."""
    import pandas as pd

    if unified_observations is None or len(unified_observations) == 0:
        return pd.DataFrame()
    rows = []
    for r in unified_observations.to_dict(orient="records"):
        sig = build_similarity_signature(r)
        sig["workload_spine_id"] = r.get("workload_spine_id", "")
        sig["workload_spine_rank"] = _safe_int(r.get("workload_spine_rank", 0))
        sig["source_dataset_labels"] = r.get("source_dataset_labels", "")
        sig["execution_environment"] = r.get("execution_environment", "")
        sig["mac_executable_now"] = bool(r.get("mac_executable_now", False))
        sig["deferred_to_hpc"] = bool(r.get("deferred_to_hpc", False))
        rows.append(sig)
    return pd.DataFrame(rows)


def build_family_similarity_signature(signature_table: Any) -> Any:
    """Build aggregated family-level similarity signatures."""
    import pandas as pd

    if signature_table is None or len(signature_table) == 0:
        return pd.DataFrame()
    grp = signature_table.groupby("workload_family", dropna=False).agg(
        variant_count=("workload_variant", "nunique"),
        n_rows_mean=("n_rows", "mean"),
        n_entities_mean=("n_entities", "mean"),
        n_periods_mean=("n_dates_or_periods", "mean"),
        feature_dim_after_mean=("feature_dim_after", "mean"),
        timing_p90_mean=("timing_p90", "mean"),
        reuse_proxy_count_mean=("reuse_proxy_count", "mean"),
        reconstruction_proxy_count_mean=("reconstruction_proxy_count", "mean"),
    )
    out = grp.reset_index()
    out["family_similarity_signature"] = out.apply(
        lambda r: hashlib.sha256(
            json.dumps(
                {
                    "family": r["workload_family"],
                    "n_rows_mean": round(float(r["n_rows_mean"]), 4),
                    "n_entities_mean": round(float(r["n_entities_mean"]), 4),
                    "feature_dim_after_mean": round(float(r["feature_dim_after_mean"]), 4),
                    "timing_p90_mean": round(float(r["timing_p90_mean"]), 4),
                    "reuse_proxy_count_mean": round(float(r["reuse_proxy_count_mean"]), 4),
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()[:18],
        axis=1,
    )
    return out


def compare_similarity_signatures(
    signature_a: Mapping[str, Any],
    signature_b: Mapping[str, Any],
) -> Dict[str, Any]:
    """Compare two workload signatures and compute similarity metrics."""
    a = signature_a
    b = signature_b
    exact_identity = str(a.get("exact_identity_signature", "")) == str(
        b.get("exact_identity_signature", "")
    )
    same_family = str(a.get("workload_family", "")) == str(b.get("workload_family", ""))
    same_family_signature = str(a.get("family_signature", "")) == str(
        b.get("family_signature", "")
    )
    neighborhood_match = str(a.get("neighborhood_signature", "")) == str(
        b.get("neighborhood_signature", "")
    )

    structure_distance = (
        _norm_abs_diff(_safe_float(a.get("n_rows")), _safe_float(b.get("n_rows")))
        + _norm_abs_diff(
            _safe_float(a.get("n_entities")), _safe_float(b.get("n_entities"))
        )
        + _norm_abs_diff(
            _safe_float(a.get("n_dates_or_periods")),
            _safe_float(b.get("n_dates_or_periods")),
        )
        + _norm_abs_diff(
            _safe_float(a.get("join_width")), _safe_float(b.get("join_width"))
        )
        + _norm_abs_diff(
            _safe_float(a.get("feature_dim_after")),
            _safe_float(b.get("feature_dim_after")),
        )
    ) / 5.0
    parameter_distance = (
        _norm_abs_diff(
            _safe_float(a.get("scenario_count")), _safe_float(b.get("scenario_count"))
        )
        + _norm_abs_diff(
            _safe_float(a.get("batch_size")), _safe_float(b.get("batch_size"))
        )
        + _norm_abs_diff(
            _safe_float(a.get("parameter_grid_width")),
            _safe_float(b.get("parameter_grid_width")),
        )
    ) / 3.0
    timing_distance = _norm_abs_diff(
        _safe_float(a.get("timing_p90")), _safe_float(b.get("timing_p90"))
    )
    reuse_distance = (
        _norm_abs_diff(
            _safe_float(a.get("reuse_proxy_count")),
            _safe_float(b.get("reuse_proxy_count")),
        )
        + _norm_abs_diff(
            _safe_float(a.get("reconstruction_proxy_count")),
            _safe_float(b.get("reconstruction_proxy_count")),
        )
        + _norm_abs_diff(
            _safe_float(a.get("cache_proxy_reuse_density")),
            _safe_float(b.get("cache_proxy_reuse_density")),
        )
    ) / 3.0

    if exact_identity:
        overall_similarity = 1.0
    else:
        similarity_core = 1.0 - (
            0.40 * structure_distance
            + 0.20 * parameter_distance
            + 0.20 * timing_distance
            + 0.20 * reuse_distance
        )
        bonus = 0.0
        if same_family:
            bonus += 0.05
        if neighborhood_match:
            bonus += 0.05
        overall_similarity = max(0.0, min(0.999, similarity_core + bonus))

    return {
        "exact_identity_match": exact_identity,
        "same_family_match": same_family,
        "same_family_signature_match": same_family_signature,
        "neighborhood_match": neighborhood_match,
        "structure_distance": float(structure_distance),
        "parameter_distance": float(parameter_distance),
        "timing_distance": float(timing_distance),
        "reuse_distance": float(reuse_distance),
        "overall_similarity": float(overall_similarity),
    }


def classify_similarity_relationship(comparison: Mapping[str, Any]) -> str:
    """Classify operational similarity relationship type."""
    if bool(comparison.get("exact_identity_match", False)):
        return SIM_REL_EXACT_IDENTITY
    score = _safe_float(comparison.get("overall_similarity", 0.0))
    sdist = _safe_float(comparison.get("structure_distance", 1.0))
    pdist = _safe_float(comparison.get("parameter_distance", 1.0))
    same_family = bool(comparison.get("same_family_match", False))
    neighborhood = bool(comparison.get("neighborhood_match", False))
    if sdist <= 0.10 and score >= 0.82:
        return SIM_REL_NEAR_IDENTITY
    if same_family and score >= 0.68:
        return SIM_REL_SAME_FAMILY
    if neighborhood and pdist <= 0.25 and score >= 0.55:
        return SIM_REL_PARAMETER_NEIGHBOR
    return SIM_REL_WEAK


def _pairwise_similarity_rows(
    signature_table: Any,
    *,
    within_family_only: Optional[bool],
) -> Any:
    import pandas as pd

    if signature_table is None or len(signature_table) == 0:
        return pd.DataFrame()
    rows = []
    recs = signature_table.to_dict(orient="records")
    for i in range(len(recs)):
        a = recs[i]
        for j in range(i + 1, len(recs)):
            b = recs[j]
            same_family = str(a.get("workload_family", "")) == str(b.get("workload_family", ""))
            if within_family_only is True and not same_family:
                continue
            if within_family_only is False and same_family:
                continue
            cmp = compare_similarity_signatures(a, b)
            rel = classify_similarity_relationship(cmp)
            op_type = (
                _family_operational_type(str(a.get("workload_family", "")))
                if same_family
                else "cross_family_shape_similarity"
            )
            rows.append(
                {
                    "workload_family_a": a.get("workload_family", ""),
                    "workload_family_b": b.get("workload_family", ""),
                    "workload_variant_a": a.get("workload_variant", ""),
                    "workload_variant_b": b.get("workload_variant", ""),
                    "deterministic_label_a": a.get("deterministic_label", ""),
                    "deterministic_label_b": b.get("deterministic_label", ""),
                    "same_family": same_family,
                    "operational_similarity_type": op_type,
                    "similarity_relationship": rel,
                    "overall_similarity": cmp["overall_similarity"],
                    "structure_distance": cmp["structure_distance"],
                    "parameter_distance": cmp["parameter_distance"],
                    "timing_distance": cmp["timing_distance"],
                    "reuse_distance": cmp["reuse_distance"],
                    "exact_identity_match": bool(cmp["exact_identity_match"]),
                    "neighborhood_match": bool(cmp["neighborhood_match"]),
                    "reuse_proxy_count_a": _safe_float(a.get("reuse_proxy_count", 0.0)),
                    "reuse_proxy_count_b": _safe_float(b.get("reuse_proxy_count", 0.0)),
                    "cache_proxy_reuse_density_a": _safe_float(a.get("cache_proxy_reuse_density", 0.0)),
                    "cache_proxy_reuse_density_b": _safe_float(b.get("cache_proxy_reuse_density", 0.0)),
                    "deferred_to_hpc_a": bool(a.get("deferred_to_hpc", False)),
                    "deferred_to_hpc_b": bool(b.get("deferred_to_hpc", False)),
                }
            )
    return pd.DataFrame(rows)


def summarize_similarity_neighbors(
    signature_table: Any,
    *,
    within_family_only: bool = True,
    top_k: int = 5,
    min_similarity: float = 0.45,
) -> Any:
    """Summarize near-neighbor similarity candidates per variant."""
    import pandas as pd

    pairs = _pairwise_similarity_rows(
        signature_table,
        within_family_only=within_family_only,
    )
    if pairs is None or len(pairs) == 0:
        return pd.DataFrame()
    pairs = pairs.loc[pairs["overall_similarity"] >= float(min_similarity)].copy()
    if len(pairs) == 0:
        return pd.DataFrame()

    rows: List[Dict[str, Any]] = []
    # Expand symmetric candidate rows for anchor-based top-k.
    for r in pairs.itertuples(index=False):
        for direction in ("ab", "ba"):
            if direction == "ab":
                fam_anchor, fam_nei = r.workload_family_a, r.workload_family_b
                var_anchor, var_nei = r.workload_variant_a, r.workload_variant_b
                det_anchor, det_nei = r.deterministic_label_a, r.deterministic_label_b
                reuse_anchor, reuse_nei = r.reuse_proxy_count_a, r.reuse_proxy_count_b
                dens_anchor, dens_nei = (
                    r.cache_proxy_reuse_density_a,
                    r.cache_proxy_reuse_density_b,
                )
                deferred_anchor, deferred_nei = r.deferred_to_hpc_a, r.deferred_to_hpc_b
            else:
                fam_anchor, fam_nei = r.workload_family_b, r.workload_family_a
                var_anchor, var_nei = r.workload_variant_b, r.workload_variant_a
                det_anchor, det_nei = r.deterministic_label_b, r.deterministic_label_a
                reuse_anchor, reuse_nei = r.reuse_proxy_count_b, r.reuse_proxy_count_a
                dens_anchor, dens_nei = (
                    r.cache_proxy_reuse_density_b,
                    r.cache_proxy_reuse_density_a,
                )
                deferred_anchor, deferred_nei = r.deferred_to_hpc_b, r.deferred_to_hpc_a
            candidate_id = hashlib.sha256(
                f"{det_anchor}|{det_nei}|{r.similarity_relationship}".encode()
            ).hexdigest()[:18]
            if r.similarity_relationship == SIM_REL_EXACT_IDENTITY:
                evidence_label = "measured"
            elif r.similarity_relationship in (
                SIM_REL_NEAR_IDENTITY,
                SIM_REL_SAME_FAMILY,
            ):
                evidence_label = "derived"
            elif r.similarity_relationship == SIM_REL_PARAMETER_NEIGHBOR:
                evidence_label = "proxy-supported"
            else:
                evidence_label = "hypothesis"
            rows.append(
                {
                    "similarity_candidate_id": candidate_id,
                    "anchor_workload_family": fam_anchor,
                    "anchor_workload_variant": var_anchor,
                    "anchor_deterministic_label": det_anchor,
                    "neighbor_workload_family": fam_nei,
                    "neighbor_workload_variant": var_nei,
                    "neighbor_deterministic_label": det_nei,
                    "analysis_scope": "within_family"
                    if bool(within_family_only)
                    else "cross_family",
                    "operational_similarity_type": r.operational_similarity_type,
                    "similarity_relationship": r.similarity_relationship,
                    "overall_similarity": float(r.overall_similarity),
                    "structure_distance": float(r.structure_distance),
                    "parameter_distance": float(r.parameter_distance),
                    "timing_distance": float(r.timing_distance),
                    "reuse_distance": float(r.reuse_distance),
                    "exact_identity_match": bool(r.exact_identity_match),
                    "neighborhood_match": bool(r.neighborhood_match),
                    "reuse_affinity": float(
                        1.0
                        - (
                            abs(float(reuse_anchor) - float(reuse_nei))
                            / max(1.0, float(reuse_anchor), float(reuse_nei))
                        )
                    ),
                    "reuse_density_affinity": float((float(dens_anchor) + float(dens_nei)) / 2.0),
                    "deferred_to_hpc_pair": bool(deferred_anchor or deferred_nei),
                    "evidence_label": evidence_label,
                }
            )
    cand = pd.DataFrame(rows)
    if len(cand) == 0:
        return cand
    cand = cand.sort_values(
        ["anchor_deterministic_label", "overall_similarity"],
        ascending=[True, False],
    )
    cand = (
        cand.groupby("anchor_deterministic_label", group_keys=False)
        .head(max(1, int(top_k)))
        .reset_index(drop=True)
    )
    return cand


def analyze_similarity_within_family(signature_table: Any) -> Any:
    """Within-family similarity analysis (locked first stage)."""
    import pandas as pd

    pairs = _pairwise_similarity_rows(signature_table, within_family_only=True)
    if pairs is None or len(pairs) == 0:
        return pd.DataFrame(
            columns=[
                "workload_family",
                "pair_count",
                "mean_similarity",
                "exact_identity_count",
                "near_identity_count",
                "same_family_count",
                "parameter_neighborhood_count",
                "weak_similarity_count",
                "evidence_label",
                "notes",
            ]
        )
    out_rows = []
    for family, g in pairs.groupby("workload_family_a", dropna=False):
        rel = g["similarity_relationship"].value_counts()
        out_rows.append(
            {
                "workload_family": family,
                "pair_count": int(len(g)),
                "mean_similarity": _safe_float(g["overall_similarity"].mean()),
                "exact_identity_count": int(rel.get(SIM_REL_EXACT_IDENTITY, 0)),
                "near_identity_count": int(rel.get(SIM_REL_NEAR_IDENTITY, 0)),
                "same_family_count": int(rel.get(SIM_REL_SAME_FAMILY, 0)),
                "parameter_neighborhood_count": int(
                    rel.get(SIM_REL_PARAMETER_NEIGHBOR, 0)
                ),
                "weak_similarity_count": int(rel.get(SIM_REL_WEAK, 0)),
                "evidence_label": "derived",
                "notes": "within-family similarity is strongest defensible first-pass evidence",
            }
        )
    return pd.DataFrame(out_rows).sort_values(
        "mean_similarity", ascending=False
    ).reset_index(drop=True)


def analyze_similarity_across_families(signature_table: Any) -> Any:
    """Cross-family similarity analysis (locked second stage)."""
    import pandas as pd

    pairs = _pairwise_similarity_rows(signature_table, within_family_only=False)
    if pairs is None or len(pairs) == 0:
        return pd.DataFrame(
            columns=[
                "workload_family_a",
                "workload_family_b",
                "pair_count",
                "mean_similarity",
                "top_similarity",
                "near_identity_count",
                "parameter_neighborhood_count",
                "evidence_label",
                "notes",
            ]
        )
    pairs["family_pair"] = pairs.apply(
        lambda r: "||".join(sorted([str(r["workload_family_a"]), str(r["workload_family_b"])])),
        axis=1,
    )
    out_rows = []
    for pair, g in pairs.groupby("family_pair", dropna=False):
        fa, fb = pair.split("||")
        rel = g["similarity_relationship"].value_counts()
        out_rows.append(
            {
                "workload_family_a": fa,
                "workload_family_b": fb,
                "pair_count": int(len(g)),
                "mean_similarity": _safe_float(g["overall_similarity"].mean()),
                "top_similarity": _safe_float(g["overall_similarity"].max()),
                "near_identity_count": int(rel.get(SIM_REL_NEAR_IDENTITY, 0)),
                "parameter_neighborhood_count": int(
                    rel.get(SIM_REL_PARAMETER_NEIGHBOR, 0)
                ),
                "evidence_label": "proxy-supported",
                "notes": "cross-family similarity is approximate and weaker than within-family evidence",
            }
        )
    return pd.DataFrame(out_rows).sort_values(
        "mean_similarity", ascending=False
    ).reset_index(drop=True)


def find_high_value_similarity_clusters(
    signature_table: Any,
    *,
    similarity_threshold: float = 0.72,
    cross_family_threshold: float = 0.80,
) -> Any:
    """Find high-value similarity clusters from pairwise relationships."""
    import pandas as pd

    pairs = _pairwise_similarity_rows(signature_table, within_family_only=None)
    if pairs is None or len(pairs) == 0:
        return pd.DataFrame(
            columns=[
                "cluster_id",
                "cluster_size",
                "family_count",
                "variant_count",
                "mean_similarity",
                "max_similarity",
                "exact_edge_count",
                "near_edge_count",
                "dominant_family",
                "evidence_label",
                "notes",
            ]
        )

    # Union-find over candidate edges.
    labels = sorted(
        set(pairs["deterministic_label_a"].tolist())
        | set(pairs["deterministic_label_b"].tolist())
    )
    parent = {x: x for x in labels}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for r in pairs.itertuples(index=False):
        threshold = similarity_threshold if bool(r.same_family) else cross_family_threshold
        if (
            float(r.overall_similarity) >= float(threshold)
            and str(r.similarity_relationship) != SIM_REL_WEAK
        ):
            union(str(r.deterministic_label_a), str(r.deterministic_label_b))

    cluster_members: Dict[str, List[str]] = {}
    for lbl in labels:
        root = find(lbl)
        cluster_members.setdefault(root, []).append(lbl)

    if signature_table is None or len(signature_table) == 0:
        return pd.DataFrame()
    sig = signature_table.copy()
    map_family = {
        str(r.deterministic_label): str(r.workload_family)
        for r in sig.itertuples(index=False)
    }
    map_variant = {
        str(r.deterministic_label): str(r.workload_variant)
        for r in sig.itertuples(index=False)
    }

    rows = []
    cid = 0
    for _, members in sorted(
        cluster_members.items(), key=lambda kv: (-len(kv[1]), kv[0])
    ):
        cid += 1
        mem_set = set(members)
        edge_sub = pairs.loc[
            pairs["deterministic_label_a"].isin(mem_set)
            & pairs["deterministic_label_b"].isin(mem_set)
        ].copy()
        if len(edge_sub) == 0 and len(members) == 1:
            mean_sim = 1.0
            max_sim = 1.0
            exact_edges = 0
            near_edges = 0
        else:
            mean_sim = _safe_float(edge_sub["overall_similarity"].mean())
            max_sim = _safe_float(edge_sub["overall_similarity"].max())
            exact_edges = int((edge_sub["similarity_relationship"] == SIM_REL_EXACT_IDENTITY).sum())
            near_edges = int((edge_sub["similarity_relationship"] == SIM_REL_NEAR_IDENTITY).sum())
        fams = [map_family.get(m, "") for m in members]
        vars_ = [map_variant.get(m, "") for m in members]
        dominant_family = ""
        if fams:
            counts: Dict[str, int] = {}
            for f in fams:
                counts[f] = counts.get(f, 0) + 1
            dominant_family = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        rows.append(
            {
                "cluster_id": f"sim_cluster_{cid:03d}",
                "cluster_size": int(len(members)),
                "family_count": int(len(set([f for f in fams if f]))),
                "variant_count": int(len(set([v for v in vars_ if v]))),
                "mean_similarity": mean_sim,
                "max_similarity": max_sim,
                "exact_edge_count": exact_edges,
                "near_edge_count": near_edges,
                "dominant_family": dominant_family,
                "evidence_label": "derived",
                "notes": "cluster reflects operational signature proximity only",
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["cluster_size", "mean_similarity"], ascending=[False, False]
    ).reset_index(drop=True)


def rank_similarity_candidates(similarity_candidate_summary: Any) -> Any:
    """Rank similarity candidates for hypothesis follow-up value."""
    if similarity_candidate_summary is None or len(similarity_candidate_summary) == 0:
        return similarity_candidate_summary.head(0) if similarity_candidate_summary is not None else None
    df = similarity_candidate_summary.copy()
    within_bonus = (df["analysis_scope"] == "within_family").astype(int) * 0.08
    exact_bonus = df["exact_identity_match"].astype(int) * 0.10
    hpc_bonus = df["deferred_to_hpc_pair"].astype(int) * 0.04
    df["candidate_value_score"] = (
        0.55 * df["overall_similarity"].astype(float).rank(pct=True)
        + 0.20 * df["reuse_affinity"].astype(float).rank(pct=True)
        + 0.15 * df["reuse_density_affinity"].astype(float).rank(pct=True)
        + within_bonus
        + exact_bonus
        + hpc_bonus
    )
    df["rank"] = df["candidate_value_score"].rank(method="dense", ascending=False).astype(int)
    return df.sort_values("rank").reset_index(drop=True)


def export_similarity_candidate_summary(
    *,
    similarity_candidate_summary: Any,
    output_dir: str | Path,
    filename: str = "similarity_candidate_summary.csv",
) -> Path:
    """Export candidate summary CSV helper."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    p = out / filename
    similarity_candidate_summary.to_csv(p, index=False)
    return p

