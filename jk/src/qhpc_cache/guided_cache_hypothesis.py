"""Guided-cache architecture hypothesis and evidence-bounded exports.

This module synthesizes existing workload evidence into architecture hypotheses.
It does not implement a production cache controller and does not claim PMU-level
hardware validation.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from qhpc_cache.evidence_synthesis import (
    EVIDENCE_DEFERRED,
    EVIDENCE_DERIVED,
    EVIDENCE_HYPOTHESIS,
    EVIDENCE_MEASURED,
    EVIDENCE_PROXY,
    build_evidence_matrix,
    classify_supported_vs_deferred_claims,
    collect_family_evidence_summary,
    collect_similarity_hypothesis_summary,
    load_canonical_evidence_tables,
    summarize_guided_cache_evidence,
)


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


def define_guided_cache_components(evidence_matrix: Any) -> Any:
    """Define candidate guided-cache components and their evidence status."""
    import pandas as pd

    if evidence_matrix is None:
        evidence_matrix = pd.DataFrame()
    level_order = {
        EVIDENCE_MEASURED: 5,
        EVIDENCE_DERIVED: 4,
        EVIDENCE_PROXY: 3,
        EVIDENCE_HYPOTHESIS: 2,
        EVIDENCE_DEFERRED: 1,
    }
    component_specs = [
        ("workload_signature_layer", "supported_now", "Canonical workload-signature substrate used for grouping/ranking."),
        ("exact_match_reuse_layer", "supported_now", "Exact deterministic signature match candidates for strict reuse."),
        ("similarity_aware_reuse_layer", "hypothesized_now", "Near-neighbor candidate retrieval for similarity-aware reuse."),
        ("routing_prioritization_layer", "hypothesized_now", "Policy/routing concept layered over signatures and candidates."),
        ("deferred_hardware_aware_layer", "deferred", "Hardware-aware layer requiring PMU-backed evidence."),
        ("deferred_hpc_qhpc_escalation_layer", "deferred", "HPC/QHPC escalation stage for large-scale and hybrid validation."),
    ]
    rows = []
    for comp, policy_state, desc in component_specs:
        sub = (
            evidence_matrix.loc[evidence_matrix["architecture_component"] == comp]
            if len(evidence_matrix)
            else pd.DataFrame()
        )
        if len(sub):
            strongest = sorted(
                sub["evidence_level"].astype(str).tolist(),
                key=lambda x: -level_order.get(x, 0),
            )[0]
            strength = _safe_float(sub["support_strength"].max())
            source = ";".join(sorted(set(";".join(sub["source_artifacts"].astype(str)).split(";"))))
        else:
            strongest = EVIDENCE_HYPOTHESIS
            strength = 0.0
            source = ""
        rows.append(
            {
                "component_id": comp,
                "component_policy_state": policy_state,
                "component_description": desc,
                "strongest_evidence_level": strongest,
                "support_strength": strength,
                "source_artifacts": source,
            }
        )
    return pd.DataFrame(rows)


def define_guided_cache_dataflow(architecture_components: Any) -> Any:
    """Define conceptual dataflow for guided-cache hypothesis layers."""
    import pandas as pd

    rows = [
        {
            "from_component": "workload_signature_layer",
            "to_component": "exact_match_reuse_layer",
            "dataflow_description": "Deterministic signatures route exact-match candidates.",
            "evidence_level": EVIDENCE_MEASURED,
        },
        {
            "from_component": "workload_signature_layer",
            "to_component": "similarity_aware_reuse_layer",
            "dataflow_description": "Operational signatures route near-neighbor candidate retrieval.",
            "evidence_level": EVIDENCE_PROXY,
        },
        {
            "from_component": "exact_match_reuse_layer",
            "to_component": "routing_prioritization_layer",
            "dataflow_description": "Exact-match confidence can feed guided routing decisions.",
            "evidence_level": EVIDENCE_HYPOTHESIS,
        },
        {
            "from_component": "similarity_aware_reuse_layer",
            "to_component": "routing_prioritization_layer",
            "dataflow_description": "Similarity score and candidate quality can feed routing thresholds.",
            "evidence_level": EVIDENCE_HYPOTHESIS,
        },
        {
            "from_component": "routing_prioritization_layer",
            "to_component": "deferred_hardware_aware_layer",
            "dataflow_description": "Routing hypotheses require hardware-aware validation later.",
            "evidence_level": EVIDENCE_DEFERRED,
        },
        {
            "from_component": "deferred_hardware_aware_layer",
            "to_component": "deferred_hpc_qhpc_escalation_layer",
            "dataflow_description": "PMU-backed results motivate HPC/QHPC escalation and larger sweeps.",
            "evidence_level": EVIDENCE_DEFERRED,
        },
    ]
    return pd.DataFrame(rows)


def map_similarity_evidence_to_guided_cache_components(
    *,
    similarity_candidate_summary: Any,
    architecture_components: Any,
) -> Any:
    """Map similarity candidate relationships onto guided-cache components."""
    import pandas as pd

    if similarity_candidate_summary is None or len(similarity_candidate_summary) == 0:
        return pd.DataFrame(
            columns=[
                "component_id",
                "similarity_relationship",
                "candidate_count",
                "mean_similarity",
                "evidence_level",
            ]
        )
    relation_component = {
        "exact_identity_similarity": "exact_match_reuse_layer",
        "near_identity_structural_similarity": "similarity_aware_reuse_layer",
        "same_family_similarity": "similarity_aware_reuse_layer",
        "parameter_neighborhood_similarity": "similarity_aware_reuse_layer",
        "weak_similarity": "routing_prioritization_layer",
    }
    relation_level = {
        "exact_identity_similarity": EVIDENCE_MEASURED,
        "near_identity_structural_similarity": EVIDENCE_DERIVED,
        "same_family_similarity": EVIDENCE_DERIVED,
        "parameter_neighborhood_similarity": EVIDENCE_PROXY,
        "weak_similarity": EVIDENCE_HYPOTHESIS,
    }
    d = similarity_candidate_summary.copy()
    d["component_id"] = d["similarity_relationship"].map(
        lambda x: relation_component.get(str(x), "routing_prioritization_layer")
    )
    d["mapped_evidence_level"] = d["similarity_relationship"].map(
        lambda x: relation_level.get(str(x), EVIDENCE_HYPOTHESIS)
    )
    out = (
        d.groupby(["component_id", "similarity_relationship", "mapped_evidence_level"], dropna=False)
        .agg(
            candidate_count=("similarity_candidate_id", "count"),
            mean_similarity=("overall_similarity", "mean"),
        )
        .reset_index()
        .rename(columns={"mapped_evidence_level": "evidence_level"})
        .sort_values(["candidate_count", "mean_similarity"], ascending=[False, False])
        .reset_index(drop=True)
    )
    return out


def identify_guided_cache_candidate_workloads(
    *,
    unified_workload_observations: Any,
    similarity_candidate_summary: Any,
    unified_workload_rankings: Any,
) -> Any:
    """Identify and rank guided-cache candidate workloads."""
    import pandas as pd

    obs = unified_workload_observations
    if obs is None or len(obs) == 0:
        return pd.DataFrame()
    cands = similarity_candidate_summary if similarity_candidate_summary is not None else pd.DataFrame()
    exact = (
        cands.loc[cands["similarity_relationship"] == "exact_identity_similarity"]
        if len(cands)
        else pd.DataFrame()
    )
    near = (
        cands.loc[
            cands["similarity_relationship"].isin(
                [
                    "near_identity_structural_similarity",
                    "same_family_similarity",
                    "parameter_neighborhood_similarity",
                ]
            )
        ]
        if len(cands)
        else pd.DataFrame()
    )

    exact_ct = (
        exact.groupby("anchor_deterministic_label", dropna=False)
        .size()
        .rename("exact_match_neighbor_count")
        .reset_index()
        if len(exact)
        else pd.DataFrame(columns=["anchor_deterministic_label", "exact_match_neighbor_count"])
    )
    near_stats = (
        near.groupby("anchor_deterministic_label", dropna=False)
        .agg(
            near_match_neighbor_count=("neighbor_deterministic_label", "count"),
            near_match_similarity_mean=("overall_similarity", "mean"),
        )
        .reset_index()
        if len(near)
        else pd.DataFrame(
            columns=[
                "anchor_deterministic_label",
                "near_match_neighbor_count",
                "near_match_similarity_mean",
            ]
        )
    )

    family_score = {}
    if unified_workload_rankings is not None and len(unified_workload_rankings):
        f = unified_workload_rankings.loc[
            unified_workload_rankings["ranking_axis"] == "family_cache_study_value"
        ]
        family_score = {
            str(r.workload_family): _safe_float(r.score)
            for r in f.itertuples(index=False)
        }

    d = obs.copy()
    d = d.merge(
        exact_ct.rename(columns={"anchor_deterministic_label": "deterministic_label"}),
        on="deterministic_label",
        how="left",
    )
    d = d.merge(
        near_stats.rename(columns={"anchor_deterministic_label": "deterministic_label"}),
        on="deterministic_label",
        how="left",
    )
    d["exact_match_neighbor_count"] = (
        pd.to_numeric(d["exact_match_neighbor_count"], errors="coerce").fillna(0).astype(int)
    )
    d["near_match_neighbor_count"] = (
        pd.to_numeric(d["near_match_neighbor_count"], errors="coerce").fillna(0).astype(int)
    )
    d["near_match_similarity_mean"] = (
        pd.to_numeric(d["near_match_similarity_mean"], errors="coerce").fillna(0.0).astype(float)
    )
    d["family_rank_score"] = d["workload_family"].map(lambda x: _safe_float(family_score.get(str(x), 0.0)))

    d["candidate_score"] = (
        0.28 * d["exact_match_neighbor_count"].rank(pct=True)
        + 0.28 * d["near_match_neighbor_count"].rank(pct=True)
        + 0.18 * d["near_match_similarity_mean"].rank(pct=True)
        + 0.14 * d["reuse_proxy_count"].fillna(0.0).rank(pct=True)
        + 0.12 * d["family_rank_score"].rank(pct=True)
    )
    d["candidate_layer"] = d.apply(
        lambda r: "exact_match_reuse_layer"
        if int(r["exact_match_neighbor_count"]) > 0
        else (
            "similarity_aware_reuse_layer"
            if int(r["near_match_neighbor_count"]) > 0
            else "routing_prioritization_layer"
        ),
        axis=1,
    )
    d["candidate_evidence_level"] = d.apply(
        lambda r: EVIDENCE_MEASURED
        if int(r["exact_match_neighbor_count"]) > 0
        else (EVIDENCE_PROXY if int(r["near_match_neighbor_count"]) > 0 else EVIDENCE_HYPOTHESIS),
        axis=1,
    )
    d["escalation_state"] = d.apply(
        lambda r: "hpc_later" if bool(r["deferred_to_hpc"]) else "mac_now",
        axis=1,
    )
    out_cols = [
        "workload_family",
        "workload_variant",
        "deterministic_label",
        "candidate_layer",
        "candidate_evidence_level",
        "exact_match_neighbor_count",
        "near_match_neighbor_count",
        "near_match_similarity_mean",
        "reuse_proxy_count",
        "reconstruction_proxy_count",
        "candidate_score",
        "mac_executable_now",
        "deferred_to_hpc",
        "escalation_state",
    ]
    out = d[out_cols].copy().sort_values("candidate_score", ascending=False).reset_index(drop=True)
    out["rank"] = out["candidate_score"].rank(method="dense", ascending=False).astype(int)
    return out


def identify_architecture_risks_and_limitations(
    *,
    evidence_matrix: Any,
    guided_cache_candidate_workloads: Any,
) -> Any:
    """Identify explicit risks and limitations from evidence status."""
    import pandas as pd

    rows = []
    if evidence_matrix is not None and len(evidence_matrix):
        for r in evidence_matrix.loc[
            evidence_matrix["evidence_level"].isin([EVIDENCE_HYPOTHESIS, EVIDENCE_DEFERRED])
        ].itertuples(index=False):
            rows.append(
                {
                    "risk_id": f"risk_{r.claim_id}",
                    "risk_statement": str(r.claim_text),
                    "evidence_level": str(r.evidence_level),
                    "severity": "high" if str(r.evidence_level) == EVIDENCE_DEFERRED else "medium",
                    "mitigation_requirement": str(r.what_strengthens_later),
                }
            )
    if guided_cache_candidate_workloads is not None and len(guided_cache_candidate_workloads):
        weak = guided_cache_candidate_workloads.loc[
            guided_cache_candidate_workloads["candidate_evidence_level"] == EVIDENCE_HYPOTHESIS
        ]
        rows.append(
            {
                "risk_id": "risk_weak_candidate_coverage",
                "risk_statement": "Some workload variants have no strong exact/near candidate support yet.",
                "evidence_level": EVIDENCE_HYPOTHESIS,
                "severity": "medium",
                "mitigation_requirement": f"add broader workload sweeps and candidate replay validation (weak_variants={len(weak)})",
            }
        )
    return pd.DataFrame(rows)


def define_guided_cache_architecture(
    *,
    architecture_components: Any,
    architecture_dataflow: Any,
    guided_cache_evidence_summary: Mapping[str, Any],
    architecture_risks_and_limitations: Any,
) -> Dict[str, Any]:
    """Define architecture hypothesis bundle object."""
    return {
        "architecture_name": "guided_cache_architecture_hypothesis_v1",
        "architecture_scope": "evidence-bounded hypothesis; no production controller",
        "components": architecture_components.to_dict(orient="records")
        if architecture_components is not None
        else [],
        "dataflow": architecture_dataflow.to_dict(orient="records")
        if architecture_dataflow is not None
        else [],
        "evidence_summary": dict(guided_cache_evidence_summary or {}),
        "risk_register": architecture_risks_and_limitations.to_dict(orient="records")
        if architecture_risks_and_limitations is not None
        else [],
    }


def _rank_guided_cache_hypotheses(
    *,
    guided_cache_evidence_matrix: Any,
    guided_cache_candidate_workloads: Any,
    guided_cache_architecture_components: Any,
) -> Any:
    import pandas as pd

    rows = []
    level_weight = {
        EVIDENCE_MEASURED: 1.0,
        EVIDENCE_DERIVED: 0.8,
        EVIDENCE_PROXY: 0.65,
        EVIDENCE_HYPOTHESIS: 0.35,
        EVIDENCE_DEFERRED: 0.15,
    }
    if guided_cache_evidence_matrix is not None and len(guided_cache_evidence_matrix):
        for r in guided_cache_evidence_matrix.itertuples(index=False):
            w = level_weight.get(str(r.evidence_level), 0.3)
            rows.append(
                {
                    "hypothesis_id": str(r.claim_id),
                    "hypothesis_area": str(r.claim_area),
                    "evidence_level": str(r.evidence_level),
                    "hypothesis_score": float(w * _safe_float(r.support_strength)),
                    "notes": str(r.claim_text),
                }
            )
    if guided_cache_candidate_workloads is not None and len(guided_cache_candidate_workloads):
        top = guided_cache_candidate_workloads.head(max(1, min(20, len(guided_cache_candidate_workloads))))
        rows.append(
            {
                "hypothesis_id": "hypothesis_candidate_workload_concentration",
                "hypothesis_area": "candidate_workload_selection",
                "evidence_level": EVIDENCE_PROXY,
                "hypothesis_score": float(_safe_float(top["candidate_score"].mean())),
                "notes": f"top_candidate_count={len(top)}",
            }
        )
    if guided_cache_architecture_components is not None and len(guided_cache_architecture_components):
        for r in guided_cache_architecture_components.itertuples(index=False):
            w = level_weight.get(str(r.strongest_evidence_level), 0.3)
            rows.append(
                {
                    "hypothesis_id": f"component_{r.component_id}",
                    "hypothesis_area": "architecture_component",
                    "evidence_level": str(r.strongest_evidence_level),
                    "hypothesis_score": float(w * _safe_float(r.support_strength)),
                    "notes": str(r.component_description),
                }
            )
    out = pd.DataFrame(rows)
    if len(out):
        out["rank"] = out["hypothesis_score"].rank(method="dense", ascending=False).astype(int)
        out = out.sort_values("rank").reset_index(drop=True)
    return out


def run_guided_cache_hypothesis_bundle(
    *,
    outputs_root: str | Path = "outputs",
    evidence_tables: Optional[Mapping[str, Any]] = None,
    run_id: str = "",
) -> Dict[str, Any]:
    """Run evidence synthesis + guided-cache architecture hypothesis workflow."""
    tables = dict(evidence_tables or {})
    if not tables:
        tables = load_canonical_evidence_tables(outputs_root=outputs_root)

    family_summary = collect_family_evidence_summary(
        unified_workload_observations=tables.get("unified_workload_observations"),
        unified_workload_rankings=tables.get("unified_workload_rankings"),
        event_library_comparison=tables.get("event_library_comparison"),
        feature_panel_comparison_summary=tables.get("feature_panel_comparison_summary"),
        portfolio_risk_rankings=tables.get("portfolio_risk_rankings"),
        pricing_workload_rankings=tables.get("pricing_workload_rankings"),
    )
    similarity_summary = collect_similarity_hypothesis_summary(
        similarity_candidate_summary=tables.get("similarity_candidate_summary"),
        similarity_hypothesis_rankings=tables.get("similarity_hypothesis_rankings"),
    )
    evidence_matrix = build_evidence_matrix(
        family_evidence_summary=family_summary,
        similarity_hypothesis_summary=similarity_summary,
        similarity_candidate_summary=tables.get("similarity_candidate_summary"),
        unified_workload_observations=tables.get("unified_workload_observations"),
        unified_workload_rankings=tables.get("unified_workload_rankings"),
    )
    classified = classify_supported_vs_deferred_claims(evidence_matrix)
    supported_claims = classified["supported_claims"]
    deferred_claims = classified["deferred_claims"]
    evidence_summary = summarize_guided_cache_evidence(
        family_evidence_summary=family_summary,
        similarity_hypothesis_summary=similarity_summary,
        evidence_matrix=evidence_matrix,
    )

    components = define_guided_cache_components(evidence_matrix)
    dataflow = define_guided_cache_dataflow(components)
    component_similarity_map = map_similarity_evidence_to_guided_cache_components(
        similarity_candidate_summary=tables.get("similarity_candidate_summary"),
        architecture_components=components,
    )
    candidate_workloads = identify_guided_cache_candidate_workloads(
        unified_workload_observations=tables.get("unified_workload_observations"),
        similarity_candidate_summary=tables.get("similarity_candidate_summary"),
        unified_workload_rankings=tables.get("unified_workload_rankings"),
    )
    risks = identify_architecture_risks_and_limitations(
        evidence_matrix=evidence_matrix,
        guided_cache_candidate_workloads=candidate_workloads,
    )
    architecture = define_guided_cache_architecture(
        architecture_components=components,
        architecture_dataflow=dataflow,
        guided_cache_evidence_summary=evidence_summary,
        architecture_risks_and_limitations=risks,
    )
    hypothesis_rankings = _rank_guided_cache_hypotheses(
        guided_cache_evidence_matrix=evidence_matrix,
        guided_cache_candidate_workloads=candidate_workloads,
        guided_cache_architecture_components=components,
    )

    rid = run_id or "guided_cache_architecture_hypothesis::v1"
    hypothesis_manifest = {
        "run_id": rid,
        "claim_typing": [
            EVIDENCE_MEASURED,
            EVIDENCE_DERIVED,
            EVIDENCE_PROXY,
            EVIDENCE_HYPOTHESIS,
            EVIDENCE_DEFERRED,
        ],
        "headline": (
            "guided-cache architecture remains a hypothesis layer; exact-match support is strongest, "
            "similarity-aware reuse is proxy-supported, low-level hardware behavior is deferred"
        ),
        "supported_claim_count": int(len(supported_claims)) if supported_claims is not None else 0,
        "deferred_claim_count": int(len(deferred_claims)) if deferred_claims is not None else 0,
    }
    evidence_manifest = {
        "run_id": rid,
        "source_tables_detected": {k: bool(v is not None and len(v)) if hasattr(v, "__len__") else bool(v) for k, v in tables.items()},
        "family_evidence_rows": int(len(family_summary)),
        "evidence_matrix_rows": int(len(evidence_matrix)),
        "summary": evidence_summary,
    }
    architecture_manifest = {
        "run_id": rid,
        "components": components.to_dict(orient="records"),
        "dataflow": dataflow.to_dict(orient="records"),
        "component_similarity_map_preview": component_similarity_map.head(20).to_dict(orient="records")
        if component_similarity_map is not None
        else [],
        "risks": risks.to_dict(orient="records") if risks is not None else [],
        "notes": "architecture concepts are hypothesis-level and evidence-bounded",
    }

    return {
        "run_id": rid,
        "family_evidence_summary": family_summary,
        "similarity_hypothesis_summary": similarity_summary,
        "guided_cache_evidence_matrix": evidence_matrix,
        "guided_cache_supported_claims": supported_claims,
        "guided_cache_deferred_claims": deferred_claims,
        "guided_cache_candidate_workloads": candidate_workloads,
        "guided_cache_architecture_components": components,
        "guided_cache_architecture_dataflow": dataflow,
        "guided_cache_component_similarity_map": component_similarity_map,
        "guided_cache_architecture_risks": risks,
        "guided_cache_hypothesis_rankings": hypothesis_rankings,
        "guided_cache_evidence_summary": evidence_summary,
        "guided_cache_architecture": architecture,
        "guided_cache_hypothesis_manifest": hypothesis_manifest,
        "guided_cache_evidence_manifest": evidence_manifest,
        "guided_cache_architecture_manifest": architecture_manifest,
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
    lines.extend([f"- {b}" for b in bullets])
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def export_research_direction_bridge(
    *,
    bundle: Mapping[str, Any],
    output_path: str | Path,
) -> Path:
    """Export markdown bridge from current evidence layer to original direction."""
    path = Path(output_path)
    summary = bundle.get("guided_cache_evidence_summary", {})
    strongest = summary.get("strongest_families_by_evidence", [])
    bullets = [
        "constant focus retained: finance workloads, reuse/caching structure, and eventual HPC/QHPC relevance",
        "discipline added: explicit claim typing (measured/derived/proxy-supported/hypothesis/deferred) at each architecture statement",
        "scope refined: production controller work deferred; architecture remains hypothesis-level evidence synthesis",
        (
            "current strongest family evidence: "
            + ", ".join([f"{r.get('workload_family')}={float(r.get('evidence_strength_score', 0.0)):.3f}" for r in strongest])
            if strongest
            else "current strongest family evidence: unavailable"
        ),
        "next bridge stages: HPC PMU validation, scale sweeps, then potential hybrid QHPC mapping studies",
    ]
    return _write_md(path, title="Research Direction Bridge", bullets=bullets)


def export_guided_cache_hypothesis_bundle(
    *,
    bundle: Mapping[str, Any],
    output_dir: str | Path,
) -> Dict[str, str]:
    """Export guided-cache architecture hypothesis artifacts."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    csv_evidence = out / "guided_cache_evidence_matrix.csv"
    csv_supported = out / "guided_cache_supported_claims.csv"
    csv_deferred = out / "guided_cache_deferred_claims.csv"
    csv_candidates = out / "guided_cache_candidate_workloads.csv"
    csv_components = out / "guided_cache_architecture_components.csv"
    csv_rankings = out / "guided_cache_hypothesis_rankings.csv"

    bundle["guided_cache_evidence_matrix"].to_csv(csv_evidence, index=False)
    bundle["guided_cache_supported_claims"].to_csv(csv_supported, index=False)
    bundle["guided_cache_deferred_claims"].to_csv(csv_deferred, index=False)
    bundle["guided_cache_candidate_workloads"].to_csv(csv_candidates, index=False)
    bundle["guided_cache_architecture_components"].to_csv(csv_components, index=False)
    bundle["guided_cache_hypothesis_rankings"].to_csv(csv_rankings, index=False)

    json_hyp = out / "guided_cache_hypothesis_manifest.json"
    json_evidence = out / "guided_cache_evidence_manifest.json"
    json_arch = out / "guided_cache_architecture_manifest.json"
    json_hyp.write_text(
        json.dumps(bundle["guided_cache_hypothesis_manifest"], indent=2),
        encoding="utf-8",
    )
    json_evidence.write_text(
        json.dumps(bundle["guided_cache_evidence_manifest"], indent=2),
        encoding="utf-8",
    )
    json_arch.write_text(
        json.dumps(bundle["guided_cache_architecture_manifest"], indent=2),
        encoding="utf-8",
    )

    md_arch = out / "guided_cache_architecture_hypothesis.md"
    md_evidence = out / "guided_cache_evidence_summary.md"
    md_rank = out / "guided_cache_rankings_summary.md"
    md_limits = out / "guided_cache_limitations_and_future_work.md"

    _write_md(
        md_arch,
        title="Guided Cache Architecture Hypothesis",
        bullets=[
            "architecture is evidence-bounded and not a production controller commitment",
            "layers: workload-signature, exact-match reuse, similarity-aware reuse, routing/prioritization, deferred hardware-aware, deferred HPC/QHPC escalation",
            "claim typing is explicit: measured / derived / proxy-supported / hypothesis / deferred",
        ],
    )
    e = bundle["guided_cache_evidence_summary"]
    _write_md(
        md_evidence,
        title="Guided Cache Evidence Summary",
        bullets=[
            str(e.get("summary_statement", "")),
            f"claim_counts_by_evidence_level={e.get('claim_counts_by_evidence_level', {})}",
            f"exact_identity_candidate_count={e.get('exact_identity_candidate_count', 0.0)}",
            f"near_similarity_candidate_count={e.get('near_similarity_candidate_count', 0.0)}",
        ],
    )
    _write_md(
        md_rank,
        title="Guided Cache Rankings Summary",
        bullets=[
            f"rank={int(r.rank)} level={r.evidence_level} score={float(r.hypothesis_score):.4f} id={r.hypothesis_id}"
            for r in bundle["guided_cache_hypothesis_rankings"].itertuples(index=False)
        ],
    )
    _write_md(
        md_limits,
        title="Guided Cache Limitations and Future Work",
        bullets=[
            f"{r.risk_id}: level={r.evidence_level} severity={r.severity} mitigation={r.mitigation_requirement}"
            for r in bundle["guided_cache_architecture_risks"].itertuples(index=False)
        ],
    )

    plot_supported_deferred = out / "plot_supported_vs_deferred_claims.png"
    plot_candidates = out / "plot_candidate_workload_rankings.png"
    plot_family_strength = out / "plot_cross_family_evidence_strength.png"
    plot_exact_vs_similarity = out / "plot_exact_vs_similarity_candidate_comparison.png"
    plot_mac_hpc = out / "plot_mac_now_vs_hpc_later_escalation.png"

    claims_plot = (
        bundle["guided_cache_evidence_matrix"]
        .groupby("evidence_level", dropna=False)["claim_id"]
        .count()
        .reset_index(name="claim_count")
    )
    _plot_bar(
        claims_plot,
        x="evidence_level",
        y="claim_count",
        title="Supported vs Deferred Claims",
        output_path=plot_supported_deferred,
    )
    _plot_bar(
        bundle["guided_cache_candidate_workloads"].head(25),
        x="workload_variant",
        y="candidate_score",
        hue="candidate_layer",
        title="Candidate Workload Rankings",
        output_path=plot_candidates,
    )
    _plot_bar(
        bundle["family_evidence_summary"],
        x="workload_family",
        y="evidence_strength_score",
        title="Cross-Family Evidence Strength",
        output_path=plot_family_strength,
    )
    exact_sim = (
        bundle["guided_cache_candidate_workloads"]
        .assign(
            candidate_type=lambda d: d["candidate_layer"].map(
                lambda x: "exact_match"
                if x == "exact_match_reuse_layer"
                else ("similarity_aware" if x == "similarity_aware_reuse_layer" else "routing_hypothesis")
            )
        )
        .groupby("candidate_type", dropna=False)["candidate_score"]
        .mean()
        .reset_index()
    )
    _plot_bar(
        exact_sim,
        x="candidate_type",
        y="candidate_score",
        title="Exact-match vs Similarity-aware Candidates",
        output_path=plot_exact_vs_similarity,
    )
    mac_hpc = (
        bundle["guided_cache_candidate_workloads"]
        .groupby("escalation_state", dropna=False)["workload_variant"]
        .count()
        .reset_index(name="variant_count")
    )
    _plot_bar(
        mac_hpc,
        x="escalation_state",
        y="variant_count",
        title="Mac-now vs HPC-later Escalation",
        output_path=plot_mac_hpc,
    )

    bridge_out = out / "research_direction_bridge.md"
    export_research_direction_bridge(bundle=bundle, output_path=bridge_out)

    return {
        "guided_cache_evidence_matrix_csv": str(csv_evidence),
        "guided_cache_supported_claims_csv": str(csv_supported),
        "guided_cache_deferred_claims_csv": str(csv_deferred),
        "guided_cache_candidate_workloads_csv": str(csv_candidates),
        "guided_cache_architecture_components_csv": str(csv_components),
        "guided_cache_hypothesis_rankings_csv": str(csv_rankings),
        "guided_cache_hypothesis_manifest_json": str(json_hyp),
        "guided_cache_evidence_manifest_json": str(json_evidence),
        "guided_cache_architecture_manifest_json": str(json_arch),
        "guided_cache_architecture_hypothesis_md": str(md_arch),
        "guided_cache_evidence_summary_md": str(md_evidence),
        "guided_cache_rankings_summary_md": str(md_rank),
        "guided_cache_limitations_and_future_work_md": str(md_limits),
        "plot_supported_vs_deferred_claims": str(plot_supported_deferred),
        "plot_candidate_workload_rankings": str(plot_candidates),
        "plot_cross_family_evidence_strength": str(plot_family_strength),
        "plot_exact_vs_similarity_candidate_comparison": str(plot_exact_vs_similarity),
        "plot_mac_now_vs_hpc_later_escalation": str(plot_mac_hpc),
        "research_direction_bridge_md": str(bridge_out),
    }

