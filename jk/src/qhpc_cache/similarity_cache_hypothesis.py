"""Similarity-caching hypothesis layer on unified workload observability.

This module is explicitly hypothesis-building from workload evidence.
It does not prove low-level hardware cache effects and does not implement a
production cache engine.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from qhpc_cache.workload_similarity import (
    SIM_REL_EXACT_IDENTITY,
    SIM_REL_NEAR_IDENTITY,
    SIM_REL_PARAMETER_NEIGHBOR,
    SIM_REL_SAME_FAMILY,
    analyze_similarity_across_families,
    analyze_similarity_within_family,
    build_family_similarity_signature,
    build_similarity_signature_table,
    export_similarity_candidate_summary,
    find_high_value_similarity_clusters,
    rank_similarity_candidates,
    summarize_similarity_neighbors,
)


EVIDENCE_MEASURED = "measured"
EVIDENCE_DERIVED = "derived"
EVIDENCE_PROXY = "proxy-supported"
EVIDENCE_HYPOTHESIS = "hypothesis"
EVIDENCE_DEFERRED = "deferred"


def _safe_mean(series: Any) -> float:
    if series is None or len(series) == 0:
        return 0.0
    return float(series.mean())


def _safe_nunique(series: Any) -> int:
    if series is None or len(series) == 0:
        return 0
    return int(series.dropna().nunique())


def identify_supported_similarity_claims(
    *,
    signature_table: Any,
    within_family_summary: Any,
    cross_family_summary: Any,
    similarity_candidate_summary: Any,
    similarity_cluster_summary: Any,
) -> Any:
    """Identify supported claims and label each as measured/derived/proxy-supported."""
    import pandas as pd

    rows: List[Dict[str, Any]] = []
    exact_count = int(
        (similarity_candidate_summary["similarity_relationship"] == SIM_REL_EXACT_IDENTITY).sum()
    ) if similarity_candidate_summary is not None and len(similarity_candidate_summary) else 0
    rows.append(
        {
            "claim_id": "supported_exact_identity_neighbors",
            "claim_text": "Some variants have exact identity signatures suitable for exact-match retrieval candidates.",
            "evidence_level": EVIDENCE_MEASURED,
            "support_strength": float(exact_count),
            "support_basis": f"exact_identity_candidate_count={exact_count}",
        }
    )

    within_mean = _safe_mean(within_family_summary.get("mean_similarity", []))
    cross_mean = _safe_mean(cross_family_summary.get("mean_similarity", []))
    margin = within_mean - cross_mean
    rows.append(
        {
            "claim_id": "supported_within_family_stronger_than_cross_family",
            "claim_text": "Within-family similarity tends to be stronger than cross-family similarity.",
            "evidence_level": EVIDENCE_DERIVED,
            "support_strength": float(margin),
            "support_basis": f"within_mean={within_mean:.4f};cross_mean={cross_mean:.4f};margin={margin:.4f}",
        }
    )

    near_count = int(
        (similarity_candidate_summary["similarity_relationship"].isin([SIM_REL_NEAR_IDENTITY, SIM_REL_SAME_FAMILY])).sum()
    ) if similarity_candidate_summary is not None and len(similarity_candidate_summary) else 0
    proxy_strength = _safe_mean(similarity_candidate_summary.get("reuse_density_affinity", []))
    rows.append(
        {
            "claim_id": "supported_near_neighbor_reuse_candidates",
            "claim_text": "Near-neighbor similarity candidates exist with reuse-proxy support for similarity-aware retrieval experiments.",
            "evidence_level": EVIDENCE_PROXY,
            "support_strength": float(near_count * max(0.0, proxy_strength)),
            "support_basis": f"near_neighbor_count={near_count};reuse_density_affinity_mean={proxy_strength:.4f}",
        }
    )

    cluster_count = int(len(similarity_cluster_summary)) if similarity_cluster_summary is not None else 0
    rows.append(
        {
            "claim_id": "supported_similarity_clusters_present",
            "claim_text": "High-value similarity clusters are present in operational signature space.",
            "evidence_level": EVIDENCE_DERIVED,
            "support_strength": float(cluster_count),
            "support_basis": f"cluster_count={cluster_count}",
        }
    )

    return pd.DataFrame(rows)


def identify_unsupported_or_deferred_claims(
    *,
    similarity_candidate_summary: Any,
    unified_observations: Any,
) -> Any:
    """Identify unsupported or deferred claims for explicit no-hallucination reporting."""
    import pandas as pd

    rows: List[Dict[str, Any]] = [
        {
            "claim_id": "unsupported_similarity_cache_perf_gain",
            "claim_text": "Similarity-aware caching has proven runtime speedups in production workloads.",
            "evidence_level": EVIDENCE_HYPOTHESIS,
            "support_strength": 0.0,
            "support_basis": "no direct controlled A/B cache-engine experiment in current repository",
        },
        {
            "claim_id": "deferred_hardware_cache_behavior_proof",
            "claim_text": "Workload similarity implies proven L1/L2/L3 cache improvements.",
            "evidence_level": EVIDENCE_DEFERRED,
            "support_strength": 0.0,
            "support_basis": "requires later HPC/x86 PMU counters; not measured on Mac workload proxies",
        },
    ]

    deferred_pairs = int(
        similarity_candidate_summary.get("deferred_to_hpc_pair", pd.Series(dtype=bool)).sum()
    ) if similarity_candidate_summary is not None and len(similarity_candidate_summary) else 0
    deferred_variants = int(
        unified_observations.get("deferred_to_hpc", pd.Series(dtype=bool)).sum()
    ) if unified_observations is not None and len(unified_observations) else 0
    rows.append(
        {
            "claim_id": "deferred_high_scale_candidate_validation",
            "claim_text": "Top similarity candidates should be validated under larger sweeps and PMU-backed runs.",
            "evidence_level": EVIDENCE_DEFERRED,
            "support_strength": float(deferred_pairs + deferred_variants),
            "support_basis": f"deferred_pair_count={deferred_pairs};deferred_variant_count={deferred_variants}",
        }
    )
    return pd.DataFrame(rows)


def rank_similarity_hypothesis_strength(
    *,
    supported_claims: Any,
    unsupported_or_deferred_claims: Any,
    similarity_candidate_rankings: Any,
) -> Any:
    """Rank hypothesis strengths with explicit evidence labels."""
    import pandas as pd

    rows: List[Dict[str, Any]] = []
    if supported_claims is not None and len(supported_claims):
        for r in supported_claims.itertuples(index=False):
            level = str(r.evidence_level)
            level_weight = {
                EVIDENCE_MEASURED: 1.00,
                EVIDENCE_DERIVED: 0.80,
                EVIDENCE_PROXY: 0.65,
                EVIDENCE_HYPOTHESIS: 0.40,
                EVIDENCE_DEFERRED: 0.20,
            }.get(level, 0.30)
            rows.append(
                {
                    "hypothesis_id": str(r.claim_id),
                    "hypothesis_focus": str(r.claim_text),
                    "evidence_level": level,
                    "strength_score": float(level_weight * float(r.support_strength)),
                    "notes": str(r.support_basis),
                }
            )
    if unsupported_or_deferred_claims is not None and len(unsupported_or_deferred_claims):
        for r in unsupported_or_deferred_claims.itertuples(index=False):
            level = str(r.evidence_level)
            level_weight = 0.15 if level == EVIDENCE_DEFERRED else 0.05
            rows.append(
                {
                    "hypothesis_id": str(r.claim_id),
                    "hypothesis_focus": str(r.claim_text),
                    "evidence_level": level,
                    "strength_score": float(level_weight * float(r.support_strength)),
                    "notes": str(r.support_basis),
                }
            )

    # Add a hypothesis row based on ranked candidate concentration.
    if similarity_candidate_rankings is not None and len(similarity_candidate_rankings):
        top = similarity_candidate_rankings.head(max(1, min(20, len(similarity_candidate_rankings))))
        rows.append(
            {
                "hypothesis_id": "candidate_concentration_signal",
                "hypothesis_focus": "Top similarity candidates are concentrated enough to justify targeted next-step experiments.",
                "evidence_level": EVIDENCE_PROXY,
                "strength_score": float(_safe_mean(top["candidate_value_score"])),
                "notes": f"top_candidate_count={len(top)}",
            }
        )

    out = pd.DataFrame(rows)
    if len(out):
        out["rank"] = out["strength_score"].rank(method="dense", ascending=False).astype(int)
        out = out.sort_values("rank").reset_index(drop=True)
    return out


def summarize_similarity_caching_hypothesis(
    *,
    supported_claims: Any,
    unsupported_or_deferred_claims: Any,
    within_family_summary: Any,
    cross_family_summary: Any,
) -> Dict[str, Any]:
    """Produce structured hypothesis summary with explicit evidence labels."""
    within_mean = _safe_mean(within_family_summary.get("mean_similarity", []))
    cross_mean = _safe_mean(cross_family_summary.get("mean_similarity", []))
    measured = (
        supported_claims.loc[supported_claims["evidence_level"] == EVIDENCE_MEASURED]
        if supported_claims is not None and len(supported_claims)
        else []
    )
    derived = (
        supported_claims.loc[supported_claims["evidence_level"] == EVIDENCE_DERIVED]
        if supported_claims is not None and len(supported_claims)
        else []
    )
    proxy = (
        supported_claims.loc[supported_claims["evidence_level"] == EVIDENCE_PROXY]
        if supported_claims is not None and len(supported_claims)
        else []
    )
    hypo = (
        unsupported_or_deferred_claims.loc[
            unsupported_or_deferred_claims["evidence_level"] == EVIDENCE_HYPOTHESIS
        ]
        if unsupported_or_deferred_claims is not None and len(unsupported_or_deferred_claims)
        else []
    )
    deferred = (
        unsupported_or_deferred_claims.loc[
            unsupported_or_deferred_claims["evidence_level"] == EVIDENCE_DEFERRED
        ]
        if unsupported_or_deferred_claims is not None and len(unsupported_or_deferred_claims)
        else []
    )

    return {
        "headline": "Similarity-caching is hypothesis-supported by workload-structure evidence but not hardware-cache proven.",
        "summary_metrics": {
            "within_family_mean_similarity": within_mean,
            "cross_family_mean_similarity": cross_mean,
            "within_minus_cross_margin": within_mean - cross_mean,
        },
        "measured_claims": (
            measured[["claim_id", "claim_text", "support_basis"]].to_dict(orient="records")
            if hasattr(measured, "to_dict")
            else []
        ),
        "derived_claims": (
            derived[["claim_id", "claim_text", "support_basis"]].to_dict(orient="records")
            if hasattr(derived, "to_dict")
            else []
        ),
        "proxy_supported_claims": (
            proxy[["claim_id", "claim_text", "support_basis"]].to_dict(orient="records")
            if hasattr(proxy, "to_dict")
            else []
        ),
        "hypothesis_only_claims": (
            hypo[["claim_id", "claim_text", "support_basis"]].to_dict(orient="records")
            if hasattr(hypo, "to_dict")
            else []
        ),
        "deferred_claims": (
            deferred[["claim_id", "claim_text", "support_basis"]].to_dict(orient="records")
            if hasattr(deferred, "to_dict")
            else []
        ),
    }


def rank_similarity_candidates(similarity_candidate_summary: Any) -> Any:
    """Compatibility wrapper to canonical candidate ranking helper."""
    from qhpc_cache.workload_similarity import rank_similarity_candidates as _rank

    return _rank(similarity_candidate_summary)


def export_similarity_candidate_summary(
    *,
    similarity_candidate_summary: Any,
    output_dir: str | Path,
) -> Path:
    """Compatibility wrapper to candidate-summary CSV export helper."""
    from qhpc_cache.workload_similarity import (
        export_similarity_candidate_summary as _export,
    )

    return _export(
        similarity_candidate_summary=similarity_candidate_summary,
        output_dir=output_dir,
        filename="similarity_candidate_summary.csv",
    )


def run_similarity_caching_hypothesis_bundle(
    *,
    unified_bundle: Optional[Mapping[str, Any]] = None,
    unified_observations: Optional[Any] = None,
    top_k_neighbors: int = 6,
    min_similarity: float = 0.45,
    run_id: str = "",
) -> Dict[str, Any]:
    """Run full similarity-caching hypothesis workflow.

    Locked order:
    1) within-family similarity analysis
    2) cross-family similarity analysis
    """
    import pandas as pd

    obs = unified_observations
    if obs is None and unified_bundle is not None:
        obs = unified_bundle.get("unified_workload_observations")
    if obs is None:
        raise ValueError("Provide unified_observations or unified_bundle with unified_workload_observations.")
    if obs is None or len(obs) == 0:
        raise ValueError("Unified observations cannot be empty for similarity hypothesis phase.")

    signature_table = build_similarity_signature_table(obs)
    family_signature_table = build_family_similarity_signature(signature_table)

    # Stage 1: within-family first (locked).
    within_family_summary = analyze_similarity_within_family(signature_table)
    within_candidates = summarize_similarity_neighbors(
        signature_table,
        within_family_only=True,
        top_k=top_k_neighbors,
        min_similarity=min_similarity,
    )

    # Stage 2: cross-family second (locked).
    cross_family_summary = analyze_similarity_across_families(signature_table)
    all_candidates = summarize_similarity_neighbors(
        signature_table,
        within_family_only=False,
        top_k=top_k_neighbors,
        min_similarity=min_similarity,
    )
    cross_candidates = (
        all_candidates.loc[
            all_candidates["anchor_workload_family"]
            != all_candidates["neighbor_workload_family"]
        ].copy()
        if all_candidates is not None and len(all_candidates)
        else pd.DataFrame()
    )

    candidate_summary = (
        pd.concat([within_candidates, cross_candidates], ignore_index=True)
        if len(within_candidates) or len(cross_candidates)
        else pd.DataFrame()
    )
    if len(candidate_summary):
        candidate_summary = candidate_summary.drop_duplicates(
            subset=["anchor_deterministic_label", "neighbor_deterministic_label", "similarity_relationship"],
            keep="first",
        ).reset_index(drop=True)

    cluster_summary = find_high_value_similarity_clusters(signature_table)
    candidate_rankings = rank_similarity_candidates(candidate_summary)

    supported_claims = identify_supported_similarity_claims(
        signature_table=signature_table,
        within_family_summary=within_family_summary,
        cross_family_summary=cross_family_summary,
        similarity_candidate_summary=candidate_summary,
        similarity_cluster_summary=cluster_summary,
    )
    unsupported_or_deferred_claims = identify_unsupported_or_deferred_claims(
        similarity_candidate_summary=candidate_summary,
        unified_observations=obs,
    )
    hypothesis_rankings = rank_similarity_hypothesis_strength(
        supported_claims=supported_claims,
        unsupported_or_deferred_claims=unsupported_or_deferred_claims,
        similarity_candidate_rankings=candidate_rankings,
    )
    hypothesis_summary = summarize_similarity_caching_hypothesis(
        supported_claims=supported_claims,
        unsupported_or_deferred_claims=unsupported_or_deferred_claims,
        within_family_summary=within_family_summary,
        cross_family_summary=cross_family_summary,
    )

    rid = run_id or f"similarity_caching_hypothesis::{_safe_nunique(obs['deterministic_label'])}_{_safe_nunique(obs['workload_family'])}"
    signature_manifest = {
        "run_id": rid,
        "schema_version": "1.0",
        "signature_row_count": int(len(signature_table)),
        "family_signature_row_count": int(len(family_signature_table)),
        "signature_fields": [
            "exact_identity_signature",
            "near_identity_signature",
            "family_signature",
            "neighborhood_signature",
            "timing_signature",
            "reuse_signature",
        ],
        "evidence_labels": [
            EVIDENCE_MEASURED,
            EVIDENCE_DERIVED,
            EVIDENCE_PROXY,
            EVIDENCE_HYPOTHESIS,
            EVIDENCE_DEFERRED,
        ],
    }
    candidate_manifest = {
        "run_id": rid,
        "schema_version": "1.0",
        "candidate_count": int(len(candidate_summary)),
        "within_family_candidate_count": int(
            (candidate_summary["analysis_scope"] == "within_family").sum()
        )
        if len(candidate_summary)
        else 0,
        "cross_family_candidate_count": int(
            (candidate_summary["analysis_scope"] == "cross_family").sum()
        )
        if len(candidate_summary)
        else 0,
        "relationship_counts": (
            candidate_summary["similarity_relationship"].value_counts().to_dict()
            if len(candidate_summary)
            else {}
        ),
    }
    hypothesis_manifest = {
        "run_id": rid,
        "schema_version": "1.0",
        "supported_claims": supported_claims.to_dict(orient="records"),
        "unsupported_or_deferred_claims": unsupported_or_deferred_claims.to_dict(
            orient="records"
        ),
        "hypothesis_summary": hypothesis_summary,
        "notes": (
            "similarity-caching conclusions are hypothesis-level unless labeled measured; "
            "hardware cache proof deferred"
        ),
    }

    return {
        "run_id": rid,
        "similarity_signature_table": signature_table,
        "similarity_family_signature_table": family_signature_table,
        "similarity_candidate_summary": candidate_summary,
        "similarity_cluster_summary": cluster_summary,
        "similarity_within_family_summary": within_family_summary,
        "similarity_cross_family_summary": cross_family_summary,
        "similarity_candidate_rankings": candidate_rankings,
        "similarity_hypothesis_rankings": hypothesis_rankings,
        "supported_similarity_claims": supported_claims,
        "unsupported_or_deferred_claims": unsupported_or_deferred_claims,
        "similarity_hypothesis_summary": hypothesis_summary,
        "similarity_signature_manifest": signature_manifest,
        "similarity_candidate_manifest": candidate_manifest,
        "similarity_hypothesis_manifest": hypothesis_manifest,
    }


def _safe_plot_library() -> Tuple[Any, Any]:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return None, None
    try:
        import seaborn as sns

        return plt, sns
    except Exception:
        return plt, None


def _plot_bar(
    frame: Any,
    *,
    x: str,
    y: str,
    title: str,
    output_path: Path,
    hue: str = "",
) -> Optional[Path]:
    if frame is None or len(frame) == 0:
        return None
    if x not in frame.columns or y not in frame.columns:
        return None
    if hue and hue not in frame.columns:
        hue = ""
    plt, sns = _safe_plot_library()
    if plt is None:
        return None
    fig = plt.figure(figsize=(9, 4.5))
    ax = fig.add_subplot(111)
    if sns is not None:
        if hue:
            sns.barplot(data=frame, x=x, y=y, hue=hue, ax=ax)
        else:
            sns.barplot(data=frame, x=x, y=y, ax=ax)
    else:
        if hue:
            frame.pivot_table(index=x, columns=hue, values=y, aggfunc="mean").plot(
                kind="bar", ax=ax
            )
        else:
            frame.groupby(x)[y].mean().plot(kind="bar", ax=ax)
    ax.set_title(title)
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(output_path, dpi=140)
    plt.close(fig)
    return output_path


def _write_md(path: Path, *, title: str, bullets: Sequence[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {title}", ""]
    for b in bullets:
        lines.append(f"- {b}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def export_similarity_caching_hypothesis_bundle(
    *,
    bundle: Mapping[str, Any],
    output_dir: str | Path,
) -> Dict[str, str]:
    """Export primary CSV/JSON artifacts first, then secondary markdown/plots."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    csv_signature = out / "similarity_signature_table.csv"
    csv_candidate = out / "similarity_candidate_summary.csv"
    csv_cluster = out / "similarity_cluster_summary.csv"
    csv_within = out / "similarity_within_family_summary.csv"
    csv_cross = out / "similarity_cross_family_summary.csv"
    csv_hyp_rank = out / "similarity_hypothesis_rankings.csv"

    bundle["similarity_signature_table"].to_csv(csv_signature, index=False)
    bundle["similarity_candidate_summary"].to_csv(csv_candidate, index=False)
    bundle["similarity_cluster_summary"].to_csv(csv_cluster, index=False)
    bundle["similarity_within_family_summary"].to_csv(csv_within, index=False)
    bundle["similarity_cross_family_summary"].to_csv(csv_cross, index=False)
    bundle["similarity_hypothesis_rankings"].to_csv(csv_hyp_rank, index=False)

    json_sig_manifest = out / "similarity_signature_manifest.json"
    json_cand_manifest = out / "similarity_candidate_manifest.json"
    json_hyp_manifest = out / "similarity_hypothesis_manifest.json"
    json_sig_manifest.write_text(
        json.dumps(bundle["similarity_signature_manifest"], indent=2),
        encoding="utf-8",
    )
    json_cand_manifest.write_text(
        json.dumps(bundle["similarity_candidate_manifest"], indent=2),
        encoding="utf-8",
    )
    json_hyp_manifest.write_text(
        json.dumps(bundle["similarity_hypothesis_manifest"], indent=2),
        encoding="utf-8",
    )

    md_hyp = out / "similarity_caching_hypothesis.md"
    md_cand = out / "similarity_candidate_summary.md"
    md_rank = out / "similarity_rankings_summary.md"

    h = bundle["similarity_hypothesis_summary"]
    bullets_h = [
        f"headline: {h.get('headline', '')}",
        (
            "within-family mean similarity="
            f"{float(h.get('summary_metrics', {}).get('within_family_mean_similarity', 0.0)):.4f}; "
            "cross-family mean similarity="
            f"{float(h.get('summary_metrics', {}).get('cross_family_mean_similarity', 0.0)):.4f}"
        ),
        "claim levels are explicitly labeled as measured / derived / proxy-supported / hypothesis / deferred",
    ]
    _write_md(md_hyp, title="Similarity Caching Hypothesis", bullets=bullets_h)

    cand = bundle["similarity_candidate_summary"]
    bullets_c = [
        (
            f"{r.analysis_scope}: {r.anchor_workload_family}/{r.anchor_workload_variant} "
            f"~ {r.neighbor_workload_family}/{r.neighbor_workload_variant} "
            f"rel={r.similarity_relationship} score={float(r.overall_similarity):.4f} "
            f"evidence={r.evidence_label}"
        )
        for r in cand.head(80).itertuples(index=False)
    ]
    _write_md(md_cand, title="Similarity Candidate Summary", bullets=bullets_c)

    rank = bundle["similarity_hypothesis_rankings"]
    bullets_r = [
        (
            f"rank={int(r.rank)} level={r.evidence_level} "
            f"score={float(r.strength_score):.4f} hypothesis={r.hypothesis_id}"
        )
        for r in rank.itertuples(index=False)
    ]
    _write_md(md_rank, title="Similarity Rankings Summary", bullets=bullets_r)

    plot_within = out / "plot_within_family_similarity.png"
    plot_cross = out / "plot_cross_family_similarity.png"
    plot_clusters = out / "plot_similarity_clusters.png"
    plot_candidates = out / "plot_similarity_candidate_rankings.png"
    plot_exact_vs_near = out / "plot_exact_match_vs_near_match_comparison.png"

    _plot_bar(
        bundle["similarity_within_family_summary"],
        x="workload_family",
        y="mean_similarity",
        title="Within-Family Similarity",
        output_path=plot_within,
    )
    _plot_bar(
        bundle["similarity_cross_family_summary"],
        x="workload_family_a",
        y="mean_similarity",
        hue="workload_family_b",
        title="Cross-Family Similarity",
        output_path=plot_cross,
    )
    _plot_bar(
        bundle["similarity_cluster_summary"],
        x="cluster_id",
        y="cluster_size",
        hue="dominant_family",
        title="Similarity Clusters",
        output_path=plot_clusters,
    )
    _plot_bar(
        bundle["similarity_candidate_rankings"].head(30),
        x="anchor_workload_family",
        y="candidate_value_score",
        hue="analysis_scope",
        title="Similarity Candidate Rankings",
        output_path=plot_candidates,
    )
    exact_near = (
        bundle["similarity_candidate_summary"]
        .assign(
            match_class=lambda d: d["similarity_relationship"].map(
                lambda x: "exact_match"
                if x == SIM_REL_EXACT_IDENTITY
                else ("near_match" if x in (SIM_REL_NEAR_IDENTITY, SIM_REL_SAME_FAMILY, SIM_REL_PARAMETER_NEIGHBOR) else "weak")
            )
        )
        .groupby("match_class", dropna=False)["overall_similarity"]
        .mean()
        .reset_index()
    )
    _plot_bar(
        exact_near,
        x="match_class",
        y="overall_similarity",
        title="Exact-match vs Near-match",
        output_path=plot_exact_vs_near,
    )

    return {
        "similarity_signature_table_csv": str(csv_signature),
        "similarity_candidate_summary_csv": str(csv_candidate),
        "similarity_cluster_summary_csv": str(csv_cluster),
        "similarity_within_family_summary_csv": str(csv_within),
        "similarity_cross_family_summary_csv": str(csv_cross),
        "similarity_hypothesis_rankings_csv": str(csv_hyp_rank),
        "similarity_signature_manifest_json": str(json_sig_manifest),
        "similarity_candidate_manifest_json": str(json_cand_manifest),
        "similarity_hypothesis_manifest_json": str(json_hyp_manifest),
        "similarity_caching_hypothesis_md": str(md_hyp),
        "similarity_candidate_summary_md": str(md_cand),
        "similarity_rankings_summary_md": str(md_rank),
        "plot_within_family_similarity": str(plot_within),
        "plot_cross_family_similarity": str(plot_cross),
        "plot_similarity_clusters": str(plot_clusters),
        "plot_similarity_candidate_rankings": str(plot_candidates),
        "plot_exact_match_vs_near_match_comparison": str(plot_exact_vs_near),
    }

