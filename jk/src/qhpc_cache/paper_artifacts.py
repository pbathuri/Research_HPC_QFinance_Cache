"""Formal research-paper packaging artifacts.

This module packages existing canonical outputs into paper-ready tables, figures,
and manifests. It does not invent evidence and does not claim hardware-level
proof beyond available artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple


EVIDENCE_MEASURED = "measured"
EVIDENCE_DERIVED = "derived"
EVIDENCE_PROXY = "proxy-supported"
EVIDENCE_HYPOTHESIS = "hypothesis"
EVIDENCE_DEFERRED = "deferred"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


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


def load_paper_source_tables(outputs_root: str | Path = "outputs") -> Dict[str, Any]:
    """Load canonical phase outputs used for paper packaging."""
    root = Path(outputs_root)
    return {
        "event_library_comparison": _read_csv_if_exists(
            root / "event_library_comparison_phase" / "event_library_comparison.csv"
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
        "similarity_hypothesis_rankings": _read_csv_if_exists(
            root / "similarity_caching_hypothesis_phase" / "similarity_hypothesis_rankings.csv"
        ),
        "guided_cache_evidence_matrix": _read_csv_if_exists(
            root / "guided_cache_hypothesis_phase" / "guided_cache_evidence_matrix.csv"
        ),
        "guided_cache_supported_claims": _read_csv_if_exists(
            root / "guided_cache_hypothesis_phase" / "guided_cache_supported_claims.csv"
        ),
        "guided_cache_deferred_claims": _read_csv_if_exists(
            root / "guided_cache_hypothesis_phase" / "guided_cache_deferred_claims.csv"
        ),
        "guided_cache_candidate_workloads": _read_csv_if_exists(
            root / "guided_cache_hypothesis_phase" / "guided_cache_candidate_workloads.csv"
        ),
        "guided_cache_hypothesis_manifest": _read_json_if_exists(
            root / "guided_cache_hypothesis_phase" / "guided_cache_hypothesis_manifest.json"
        ),
    }


def build_paper_narrative_outline(source_tables: Mapping[str, Any]) -> Any:
    """Build paper narrative outline from available evidence."""
    import pandas as pd

    sections = [
        (
            "motivation",
            "Quantitative finance workloads exhibit repeated structure suitable for cache/reuse study.",
            EVIDENCE_DERIVED,
            "event, panel, risk, pricing phases",
        ),
        (
            "problem_framing",
            "Evidence-first architecture framing: workload structure before low-level controller claims.",
            EVIDENCE_DERIVED,
            "unified observability + hypothesis phases",
        ),
        (
            "methods_scope",
            "Canonical WRDS/CRSP + TAQ alignment and four workload families support disciplined comparability.",
            EVIDENCE_MEASURED,
            "family outputs + unified tables",
        ),
        (
            "results_scope",
            "Exact-match and similarity-aware reuse candidates exist, with explicit claim typing.",
            EVIDENCE_PROXY,
            "similarity + guided-cache evidence tables",
        ),
        (
            "limitations",
            "Hardware-aware and PMU-backed conclusions are deferred.",
            EVIDENCE_DEFERRED,
            "mac_vs_hpc policy + deferred claims",
        ),
        (
            "future_work",
            "HPC PMU validation, scale replay, and possible QHPC coupling remain later stages.",
            EVIDENCE_DEFERRED,
            "guided-cache deferred layer",
        ),
    ]
    return pd.DataFrame(
        [
            {
                "section_id": sid,
                "section_statement": stmt,
                "evidence_level": level,
                "source_basis": src,
            }
            for sid, stmt, level, src in sections
        ]
    )


def summarize_research_contribution(source_tables: Mapping[str, Any]) -> Dict[str, Any]:
    """Summarize primary research contributions from current evidence."""
    obs = source_tables.get("unified_workload_observations")
    sim = source_tables.get("similarity_hypothesis_rankings")
    guided = source_tables.get("guided_cache_evidence_matrix")
    return {
        "contribution_1": "Canonical multi-family finance workload substrate for cache/reuse evidence.",
        "contribution_2": "Unified observability schema enabling cross-family comparison.",
        "contribution_3": "Similarity-caching hypothesis with explicit evidence labels.",
        "contribution_4": "Guided-cache architecture hypothesis with supported/deferred claim split.",
        "supporting_counts": {
            "unified_observation_rows": int(len(obs)) if obs is not None else 0,
            "similarity_hypothesis_rows": int(len(sim)) if sim is not None else 0,
            "guided_claim_rows": int(len(guided)) if guided is not None else 0,
        },
    }


def summarize_project_evolution(source_tables: Mapping[str, Any]) -> Any:
    """Summarize evolution from proposal-style framing to evidence-bounded packaging."""
    import pandas as pd

    rows = [
        {
            "stage": "initial_proposal_direction",
            "what_changed": "broad architecture ambition",
            "what_stayed_constant": "finance + cache/reuse + HPC/QHPC relevance",
            "evidence_level": EVIDENCE_HYPOTHESIS,
        },
        {
            "stage": "workload_family_buildout",
            "what_changed": "shift to canonical workload-family evidence",
            "what_stayed_constant": "realistic quant workload focus",
            "evidence_level": EVIDENCE_MEASURED,
        },
        {
            "stage": "unified_and_similarity_layers",
            "what_changed": "cross-family schema and similarity candidates",
            "what_stayed_constant": "reuse/caching structural emphasis",
            "evidence_level": EVIDENCE_DERIVED,
        },
        {
            "stage": "guided_cache_hypothesis",
            "what_changed": "architecture hypothesis claim typing",
            "what_stayed_constant": "evidence-first discipline",
            "evidence_level": EVIDENCE_PROXY,
        },
    ]
    return pd.DataFrame(rows)


def build_methods_summary(source_tables: Mapping[str, Any]) -> Any:
    """Build methods summary table for paper methods section."""
    import pandas as pd

    rows = [
        {
            "method_component": "data_sources_and_integration",
            "canonical_assets": "wrds_provider.py;rates_data.py;taq_event_pipeline.py",
            "source_outputs": "event_library_comparison_phase/*;feature/risk/pricing phases",
            "evidence_level": EVIDENCE_MEASURED,
            "notes": "WRDS/CRSP canonical integration with TAQ alignment path",
        },
        {
            "method_component": "event_library_and_cache_study_design",
            "canonical_assets": "event_set_library.py;event_library_compare.py;cache_study_analysis.py",
            "source_outputs": "event_library_comparison.csv;cache_study_rankings.csv",
            "evidence_level": EVIDENCE_MEASURED,
            "notes": "event sets A-E with within-set then cross-set analysis ordering",
        },
        {
            "method_component": "feature_panel_comparison",
            "canonical_assets": "feature_panel.py;feature_panel_compare.py",
            "source_outputs": "feature_panel_comparison_summary.csv",
            "evidence_level": EVIDENCE_MEASURED,
            "notes": "event-aware/non-event-aware and raw/condensed variants",
        },
        {
            "method_component": "portfolio_risk_and_pricing_workloads",
            "canonical_assets": "portfolio_risk_workloads.py;pricing_workloads.py",
            "source_outputs": "portfolio_risk_rankings.csv;pricing_workload_rankings.csv",
            "evidence_level": EVIDENCE_MEASURED,
            "notes": "risk and pricing workload families for repeated-structure analysis",
        },
        {
            "method_component": "unified_similarity_guided_hypothesis",
            "canonical_assets": "unified_observability.py;similarity_cache_hypothesis.py;guided_cache_hypothesis.py",
            "source_outputs": "unified_workload_*.csv;similarity_*.csv;guided_cache_*.csv",
            "evidence_level": EVIDENCE_DERIVED,
            "notes": "evidence synthesis and architecture hypotheses with claim typing",
        },
    ]
    return pd.DataFrame(rows)


def _family_summary_from_unified(unified_observations: Any, unified_rankings: Any) -> Any:
    import pandas as pd

    if unified_observations is None or len(unified_observations) == 0:
        return pd.DataFrame()
    fam = (
        unified_observations.groupby("workload_family", dropna=False)
        .agg(
            n_variants=("workload_variant", "nunique"),
            n_rows_mean=("n_rows", "mean"),
            timing_p90_mean=("timing_p90", "mean"),
            reuse_proxy_mean=("reuse_proxy_count", "mean"),
            deferred_ratio=("deferred_to_hpc", "mean"),
        )
        .reset_index()
    )
    if unified_rankings is not None and len(unified_rankings):
        rf = unified_rankings.loc[
            unified_rankings["ranking_axis"] == "family_cache_study_value",
            ["workload_family", "score", "rank"],
        ].copy()
        rf = rf.rename(columns={"score": "family_cache_study_value_score", "rank": "family_rank"})
        fam = fam.merge(rf, on="workload_family", how="left")
    fam["evidence_level"] = EVIDENCE_DERIVED
    return fam


def _build_paper_tables(source_tables: Mapping[str, Any]) -> Dict[str, Any]:
    import pandas as pd

    event_tbl = source_tables.get("event_library_comparison")
    if event_tbl is None:
        event_tbl = pd.DataFrame()
    event_out = event_tbl.copy()
    if len(event_out):
        rename_map = {
            "event_set_id": "event_set_id",
            "defined_event_count": "defined_event_count",
            "materialized_row_count": "materialized_row_count",
            "aligned_permno_count": "aligned_permno_count",
            "timing_p90_ms": "timing_p90_ms",
            "cache_proxy_reuse_density": "cache_proxy_reuse_density",
        }
        cols = [c for c in rename_map if c in event_out.columns]
        event_out = event_out[cols].copy()
        event_out["evidence_level"] = EVIDENCE_MEASURED

    fp = source_tables.get("feature_panel_comparison_summary")
    fp_out = fp.copy() if fp is not None else pd.DataFrame()
    if len(fp_out):
        cols = [
            c
            for c in [
                "panel_variant_label",
                "event_aware",
                "condensed",
                "n_rows",
                "n_securities",
                "n_dates",
                "feature_count_before_condense",
                "feature_count_after_condense",
                "panel_build_timing_ms",
                "reuse_density",
            ]
            if c in fp_out.columns
        ]
        fp_out = fp_out[cols].copy()
        fp_out["evidence_level"] = EVIDENCE_MEASURED

    pr = source_tables.get("portfolio_risk_rankings")
    pr_out = pr.copy() if pr is not None else pd.DataFrame()
    if len(pr_out):
        cols = [
            c
            for c in [
                "risk_workload_variant_label",
                "n_securities",
                "recomputation_count",
                "reuse_proxy",
                "cache_study_value_score",
                "rank",
            ]
            if c in pr_out.columns
        ]
        pr_out = pr_out[cols].copy()
        pr_out["evidence_level"] = EVIDENCE_DERIVED

    pw = source_tables.get("pricing_workload_rankings")
    pw_out = pw.copy() if pw is not None else pd.DataFrame()
    if len(pw_out):
        cols = [
            c
            for c in [
                "workload_variant_label",
                "cache_study_value_score",
                "repeat_score",
                "size_score",
                "greek_bonus",
                "rank",
            ]
            if c in pw_out.columns
        ]
        pw_out = pw_out[cols].copy()
        pw_out["evidence_level"] = EVIDENCE_DERIVED

    unified_out = _family_summary_from_unified(
        source_tables.get("unified_workload_observations"),
        source_tables.get("unified_workload_rankings"),
    )

    sim = source_tables.get("similarity_hypothesis_rankings")
    sim_out = sim.copy() if sim is not None else pd.DataFrame()
    if len(sim_out):
        cols = [
            c
            for c in [
                "hypothesis_id",
                "evidence_level",
                "strength_score",
                "rank",
            ]
            if c in sim_out.columns
        ]
        sim_out = sim_out[cols].copy()

    guided = source_tables.get("guided_cache_evidence_matrix")
    guided_out = guided.copy() if guided is not None else pd.DataFrame()
    if len(guided_out):
        cols = [
            c
            for c in [
                "claim_id",
                "claim_area",
                "architecture_component",
                "evidence_level",
                "support_strength",
                "claim_text",
            ]
            if c in guided_out.columns
        ]
        guided_out = guided_out[cols].copy()

    scope = pd.DataFrame(
        [
            {
                "scope_area": "event_library",
                "primary_artifact": "event_library_comparison_phase/event_library_comparison.csv",
                "row_count": int(len(event_out)),
                "evidence_level": EVIDENCE_MEASURED,
            },
            {
                "scope_area": "feature_panel",
                "primary_artifact": "feature_panel_comparison_phase/feature_panel_comparison_summary.csv",
                "row_count": int(len(fp_out)),
                "evidence_level": EVIDENCE_MEASURED,
            },
            {
                "scope_area": "portfolio_risk",
                "primary_artifact": "portfolio_risk_workloads_phase/portfolio_risk_rankings.csv",
                "row_count": int(len(pr_out)),
                "evidence_level": EVIDENCE_DERIVED,
            },
            {
                "scope_area": "pricing",
                "primary_artifact": "pricing_workload_family_phase/pricing_workload_rankings.csv",
                "row_count": int(len(pw_out)),
                "evidence_level": EVIDENCE_DERIVED,
            },
            {
                "scope_area": "unified_observability",
                "primary_artifact": "unified_observability_phase/unified_workload_observations.csv",
                "row_count": int(len(source_tables.get("unified_workload_observations", pd.DataFrame()))),
                "evidence_level": EVIDENCE_DERIVED,
            },
            {
                "scope_area": "similarity_and_guided_hypothesis",
                "primary_artifact": "similarity_caching_hypothesis_phase/* + guided_cache_hypothesis_phase/*",
                "row_count": int(len(sim_out) + len(guided_out)),
                "evidence_level": EVIDENCE_PROXY,
            },
        ]
    )

    data_workload = pd.DataFrame(
        [
            {
                "data_workload_component": "WRDS/CRSP canonical integration",
                "workload_family": "event/feature/risk/pricing",
                "artifact_dependency": "wrds_provider.py + rates_data.py + canonical outputs",
                "evidence_level": EVIDENCE_MEASURED,
            },
            {
                "data_workload_component": "TAQ/kdb event alignment",
                "workload_family": "event",
                "artifact_dependency": "taq_event_pipeline.py + event_library_comparison_phase",
                "evidence_level": EVIDENCE_MEASURED,
            },
            {
                "data_workload_component": "Unified observability schema",
                "workload_family": "cross-family",
                "artifact_dependency": "unified_workload_observations.csv",
                "evidence_level": EVIDENCE_DERIVED,
            },
            {
                "data_workload_component": "Similarity + guided-cache hypotheses",
                "workload_family": "cross-family",
                "artifact_dependency": "similarity_*.csv + guided_cache_*.csv",
                "evidence_level": EVIDENCE_PROXY,
            },
        ]
    )

    return {
        "table_research_scope_summary": scope,
        "table_data_and_workload_summary": data_workload,
        "table_event_library_summary": event_out,
        "table_feature_panel_comparison": fp_out,
        "table_portfolio_risk_summary": pr_out,
        "table_pricing_workload_summary": pw_out,
        "table_unified_observability_summary": unified_out,
        "table_similarity_hypothesis_summary": sim_out,
        "table_guided_cache_claims_summary": guided_out,
    }


def _safe_plot_library() -> Any:
    try:
        import matplotlib.pyplot as plt

        return plt
    except Exception:
        return None


def _plot_or_placeholder_bar(
    *,
    frame: Any,
    x: str,
    y: str,
    title: str,
    path: Path,
) -> Optional[Path]:
    plt = _safe_plot_library()
    if plt is None:
        return None
    fig = plt.figure(figsize=(8.5, 4.6))
    ax = fig.add_subplot(111)
    if frame is None or len(frame) == 0 or x not in frame.columns or y not in frame.columns:
        ax.text(0.5, 0.5, "Data unavailable", ha="center", va="center")
        ax.set_title(title)
        ax.set_axis_off()
    else:
        try:
            ax.bar(frame[x].astype(str).tolist(), frame[y].astype(float).tolist())
            ax.set_title(title)
            ax.set_ylabel(y)
            ax.tick_params(axis="x", rotation=25)
        except Exception:
            ax.text(0.5, 0.5, "Plot unavailable", ha="center", va="center")
            ax.set_title(title)
            ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def export_paper_narrative(
    *,
    narrative_outline: Any,
    contribution_summary: Mapping[str, Any],
    evolution_summary: Any,
    output_path: str | Path,
) -> Path:
    """Export paper narrative markdown section."""
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Paper Narrative",
        "",
        "This narrative is evidence-bounded and claim-typed.",
        "",
        "## Outline",
    ]
    if narrative_outline is not None and len(narrative_outline):
        for r in narrative_outline.itertuples(index=False):
            lines.append(
                f"- `{r.section_id}` [{r.evidence_level}]: {r.section_statement} (basis: {r.source_basis})"
            )
    lines.extend(
        [
            "",
            "## Contributions",
            f"- {contribution_summary.get('contribution_1', '')}",
            f"- {contribution_summary.get('contribution_2', '')}",
            f"- {contribution_summary.get('contribution_3', '')}",
            f"- {contribution_summary.get('contribution_4', '')}",
            "",
            "## Project Evolution",
        ]
    )
    if evolution_summary is not None and len(evolution_summary):
        for r in evolution_summary.itertuples(index=False):
            lines.append(
                f"- `{r.stage}` [{r.evidence_level}]: {r.what_changed}; constant: {r.what_stayed_constant}"
            )
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def export_methods_tables(*, methods_summary: Any, output_path: str | Path) -> Path:
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    methods_summary.to_csv(p, index=False)
    return p


def export_methods_narrative(*, methods_summary: Any, output_path: str | Path) -> Path:
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Paper Methods", "", "Methods are aligned to implemented canonical modules.", ""]
    if methods_summary is not None and len(methods_summary):
        for r in methods_summary.itertuples(index=False):
            lines.append(
                f"- `{r.method_component}` [{r.evidence_level}]: {r.notes} (assets: {r.canonical_assets}; outputs: {r.source_outputs})"
            )
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def run_paper_packaging_bundle(
    *,
    outputs_root: str | Path = "outputs",
    source_tables: Optional[Mapping[str, Any]] = None,
    run_id: str = "",
) -> Dict[str, Any]:
    """Build full paper-packaging bundle from canonical outputs."""
    import pandas as pd

    tables = dict(source_tables or {})
    if not tables:
        tables = load_paper_source_tables(outputs_root=outputs_root)

    narrative_outline = build_paper_narrative_outline(tables)
    contribution_summary = summarize_research_contribution(tables)
    evolution_summary = summarize_project_evolution(tables)
    methods_summary = build_methods_summary(tables)
    paper_tables = _build_paper_tables(tables)

    # Core packaging artifacts
    paper_claims_matrix = (
        tables.get("guided_cache_evidence_matrix").copy()
        if tables.get("guided_cache_evidence_matrix") is not None
        else pd.DataFrame()
    )
    if len(paper_claims_matrix):
        claim_cols = [
            c
            for c in [
                "claim_id",
                "claim_area",
                "architecture_component",
                "source_families",
                "source_artifacts",
                "evidence_level",
                "support_strength",
                "claim_text",
                "what_strengthens_later",
            ]
            if c in paper_claims_matrix.columns
        ]
        paper_claims_matrix = paper_claims_matrix[claim_cols].copy()

    section_mapping = pd.DataFrame(
        [
            {
                "paper_section": "Introduction and Motivation",
                "primary_artifacts": "table_research_scope_summary.csv;table_data_and_workload_summary.csv",
                "evidence_level": EVIDENCE_DERIVED,
            },
            {
                "paper_section": "Methods",
                "primary_artifacts": "paper_methods_summary.csv;table_data_and_workload_summary.csv",
                "evidence_level": EVIDENCE_MEASURED,
            },
            {
                "paper_section": "Results: Workload Families",
                "primary_artifacts": "table_event_library_summary.csv;table_feature_panel_comparison.csv;table_portfolio_risk_summary.csv;table_pricing_workload_summary.csv",
                "evidence_level": EVIDENCE_MEASURED,
            },
            {
                "paper_section": "Results: Cross-family and Similarity",
                "primary_artifacts": "table_unified_observability_summary.csv;table_similarity_hypothesis_summary.csv;table_guided_cache_claims_summary.csv",
                "evidence_level": EVIDENCE_DERIVED,
            },
            {
                "paper_section": "Limitations and Future Work",
                "primary_artifacts": "paper_claims_matrix.csv;guided_cache_deferred_claims.csv",
                "evidence_level": EVIDENCE_DEFERRED,
            },
        ]
    )

    results_tables_rows = []
    for tname, df in paper_tables.items():
        results_tables_rows.append(
            {
                "table_id": tname,
                "row_count": int(len(df)) if df is not None else 0,
                "curation_note": "curated for paper narrative, not full artifact dump",
            }
        )
    paper_results_tables = pd.DataFrame(results_tables_rows)

    # Artifact index is finalized during export when concrete paths exist.
    rid = run_id or "formal_research_paper_packaging::v1"
    return {
        "run_id": rid,
        "source_tables": tables,
        "paper_narrative_outline": narrative_outline,
        "paper_contribution_summary": contribution_summary,
        "paper_evolution_summary": evolution_summary,
        "paper_methods_summary": methods_summary,
        "paper_tables": paper_tables,
        "paper_results_tables": paper_results_tables,
        "paper_claims_matrix": paper_claims_matrix,
        "paper_section_mapping": section_mapping,
    }


def export_paper_packaging_bundle(
    *,
    bundle: Mapping[str, Any],
    output_dir: str | Path,
) -> Dict[str, str]:
    """Export paper packaging CSV/JSON/figures plus narrative markdowns."""
    import pandas as pd

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    paper_tables = dict(bundle.get("paper_tables", {}))
    # Required paper-ready tables
    table_paths: Dict[str, Path] = {}
    for name in [
        "table_research_scope_summary",
        "table_data_and_workload_summary",
        "table_event_library_summary",
        "table_feature_panel_comparison",
        "table_portfolio_risk_summary",
        "table_pricing_workload_summary",
        "table_unified_observability_summary",
        "table_similarity_hypothesis_summary",
        "table_guided_cache_claims_summary",
    ]:
        p = out / f"{name}.csv"
        df = paper_tables.get(name)
        if df is None:
            df = pd.DataFrame()
        df.to_csv(p, index=False)
        table_paths[name] = p

    # Primary CSV artifacts
    csv_paper_results_tables = out / "paper_results_tables.csv"
    csv_claims_matrix = out / "paper_claims_matrix.csv"
    csv_section_mapping = out / "paper_section_mapping.csv"
    csv_artifact_index = out / "paper_artifact_index.csv"
    bundle["paper_results_tables"].to_csv(csv_paper_results_tables, index=False)
    bundle["paper_claims_matrix"].to_csv(csv_claims_matrix, index=False)
    bundle["paper_section_mapping"].to_csv(csv_section_mapping, index=False)

    # Methods table CSV helper
    csv_methods = out / "paper_methods_summary.csv"
    export_methods_tables(methods_summary=bundle["paper_methods_summary"], output_path=csv_methods)

    # Narrative / methods markdown
    md_narrative = out / "paper_narrative.md"
    md_methods = out / "paper_methods.md"
    export_paper_narrative(
        narrative_outline=bundle["paper_narrative_outline"],
        contribution_summary=bundle["paper_contribution_summary"],
        evolution_summary=bundle["paper_evolution_summary"],
        output_path=md_narrative,
    )
    export_methods_narrative(
        methods_summary=bundle["paper_methods_summary"],
        output_path=md_methods,
    )

    # Results markdown and tables/figures markdown
    md_results = out / "paper_results.md"
    md_tables_figures = out / "paper_tables_and_figures.md"
    md_claim_discipline = out / "paper_claim_discipline.md"
    md_limitations = out / "paper_limitations.md"
    md_future_work = out / "paper_future_work.md"
    md_submission = out / "paper_submission_readiness.md"

    results_lines = [
        "# Paper Results",
        "",
        "Results are curated from canonical outputs and remain claim-typed.",
        "",
    ]
    for r in bundle["paper_results_tables"].itertuples(index=False):
        results_lines.append(
            f"- `{r.table_id}`: rows={int(r.row_count)}; note={r.curation_note}"
        )
    results_lines.append("")
    md_results.write_text("\n".join(results_lines), encoding="utf-8")

    # Figures (matplotlib only)
    fig_paths: Dict[str, Path] = {}
    fig_paths["figure_event_library_comparison"] = out / "figure_event_library_comparison.png"
    fig_paths["figure_cache_study_rankings"] = out / "figure_cache_study_rankings.png"
    fig_paths["figure_feature_panel_comparison"] = out / "figure_feature_panel_comparison.png"
    fig_paths["figure_portfolio_risk_workloads"] = out / "figure_portfolio_risk_workloads.png"
    fig_paths["figure_pricing_workload_comparison"] = out / "figure_pricing_workload_comparison.png"
    fig_paths["figure_unified_observability"] = out / "figure_unified_observability.png"
    fig_paths["figure_similarity_candidates"] = out / "figure_similarity_candidates.png"
    fig_paths["figure_guided_cache_evidence"] = out / "figure_guided_cache_evidence.png"

    _plot_or_placeholder_bar(
        frame=paper_tables.get("table_event_library_summary"),
        x="event_set_id",
        y="defined_event_count",
        title="Event Library Comparison",
        path=fig_paths["figure_event_library_comparison"],
    )
    _plot_or_placeholder_bar(
        frame=bundle["source_tables"].get("cache_study_rankings"),
        x="event_set_id",
        y="cache_study_value_score",
        title="Cache Study Rankings",
        path=fig_paths["figure_cache_study_rankings"],
    )
    _plot_or_placeholder_bar(
        frame=paper_tables.get("table_feature_panel_comparison"),
        x="panel_variant_label",
        y="feature_count_after_condense",
        title="Feature Panel Comparison",
        path=fig_paths["figure_feature_panel_comparison"],
    )
    _plot_or_placeholder_bar(
        frame=paper_tables.get("table_portfolio_risk_summary"),
        x="risk_workload_variant_label",
        y="cache_study_value_score",
        title="Portfolio Risk Workloads",
        path=fig_paths["figure_portfolio_risk_workloads"],
    )
    _plot_or_placeholder_bar(
        frame=paper_tables.get("table_pricing_workload_summary"),
        x="workload_variant_label",
        y="cache_study_value_score",
        title="Pricing Workload Comparison",
        path=fig_paths["figure_pricing_workload_comparison"],
    )
    _plot_or_placeholder_bar(
        frame=paper_tables.get("table_unified_observability_summary"),
        x="workload_family",
        y="family_cache_study_value_score",
        title="Unified Observability Family Summary",
        path=fig_paths["figure_unified_observability"],
    )
    _plot_or_placeholder_bar(
        frame=paper_tables.get("table_similarity_hypothesis_summary"),
        x="hypothesis_id",
        y="strength_score",
        title="Similarity Hypothesis Rankings",
        path=fig_paths["figure_similarity_candidates"],
    )
    _plot_or_placeholder_bar(
        frame=paper_tables.get("table_guided_cache_claims_summary"),
        x="claim_id",
        y="support_strength",
        title="Guided Cache Evidence Claims",
        path=fig_paths["figure_guided_cache_evidence"],
    )

    tables_fig_lines = [
        "# Paper Tables and Figures",
        "",
        "This index lists curated paper tables/figures and their claim mapping.",
        "",
    ]
    for name, path in table_paths.items():
        tables_fig_lines.append(f"- table `{name}` -> `{path.name}`")
    for name, path in fig_paths.items():
        tables_fig_lines.append(f"- figure `{name}` -> `{path.name}`")
    tables_fig_lines.append("")
    md_tables_figures.write_text("\n".join(tables_fig_lines), encoding="utf-8")

    claim_matrix = bundle["paper_claims_matrix"]
    level_counts = (
        claim_matrix["evidence_level"].value_counts().to_dict()
        if claim_matrix is not None and len(claim_matrix)
        else {}
    )
    claim_lines = [
        "# Paper Claim Discipline",
        "",
        "Every architectural claim remains typed and evidence-bounded.",
        "",
        f"- evidence_level_counts={level_counts}",
        "- no PMU/x86/HPC hardware-cache proof is implied by Mac-side workload proxies",
        "",
    ]
    md_claim_discipline.write_text("\n".join(claim_lines), encoding="utf-8")

    lim_lines = [
        "# Paper Limitations",
        "",
        "- measured: workload and phase outputs captured in canonical CSV/JSON artifacts",
        "- derived: unified/similarity/guided synthesis statistics",
        "- proxy-supported: similarity-aware and guided-cache candidate inferences",
        "- hypothesis: routing/admission behavior hypotheses not yet validated by controlled replay engine",
        "- deferred: PMU-backed hardware validation, BigRed200-scale replay, deep low-level systems coupling",
        "",
    ]
    md_limitations.write_text("\n".join(lim_lines), encoding="utf-8")

    fw_lines = [
        "# Paper Future Work",
        "",
        "- controlled replay experiments for exact-vs-similarity routing policies",
        "- PMU-backed x86/HPC validation for cache-level behavior",
        "- BigRed200-scale workload sweeps for escalation candidates",
        "- explicit bridge from validated guided-cache evidence to future hybrid QHPC studies",
        "",
    ]
    md_future_work.write_text("\n".join(fw_lines), encoding="utf-8")

    readiness_lines = [
        "# Paper Submission Readiness",
        "",
        "- narrative/methods/results/limitations/future-work sections exported",
        "- curated paper-ready tables and figures exported",
        "- explicit claim discipline and deferred claims documented",
        "- proposal-to-paper bridge maintained",
        "- remaining blocker: PMU/HPC validation is deferred and should be framed as future work",
        "",
    ]
    md_submission.write_text("\n".join(readiness_lines), encoding="utf-8")

    # Proposal-to-paper bridge export in packaging directory.
    md_bridge = out / "proposal_to_paper_bridge.md"
    bridge_lines = [
        "# Proposal to Paper Bridge",
        "",
        "The original proposal emphasized finance workloads, cache/reuse, and eventual HPC/QHPC relevance.",
        "",
        "What stayed constant:",
        "- finance workload focus (event, panel, risk, pricing)",
        "- caching/reuse structural emphasis",
        "- HPC/QHPC relevance as a later validation stage",
        "",
        "What evolved:",
        "- shifted to staged empirical evidence before low-level claims",
        "- introduced unified observability and claim-typed hypothesis layers",
        "",
        "What is deferred:",
        "- PMU-backed x86/HPC microarchitectural validation",
        "- BigRed200-scale deployment validation",
        "- deeper quantum/HPC coupling experiments",
        "",
    ]
    md_bridge.write_text("\n".join(bridge_lines), encoding="utf-8")

    # Build artifact index after all paths are known.
    artifact_rows = []
    for name, p in table_paths.items():
        artifact_rows.append(
            {
                "artifact_kind": "table",
                "artifact_id": name,
                "path": str(p),
                "claim_level_default": EVIDENCE_DERIVED,
            }
        )
    for name, p in fig_paths.items():
        artifact_rows.append(
            {
                "artifact_kind": "figure",
                "artifact_id": name,
                "path": str(p),
                "claim_level_default": EVIDENCE_DERIVED,
            }
        )
    for name, p in [
        ("paper_narrative", md_narrative),
        ("paper_methods", md_methods),
        ("paper_results", md_results),
        ("paper_tables_and_figures", md_tables_figures),
        ("paper_claim_discipline", md_claim_discipline),
        ("paper_limitations", md_limitations),
        ("paper_future_work", md_future_work),
        ("proposal_to_paper_bridge", md_bridge),
        ("paper_submission_readiness", md_submission),
    ]:
        artifact_rows.append(
            {
                "artifact_kind": "doc",
                "artifact_id": name,
                "path": str(p),
                "claim_level_default": EVIDENCE_DERIVED,
            }
        )
    paper_artifact_index = pd.DataFrame(artifact_rows)
    paper_artifact_index.to_csv(csv_artifact_index, index=False)

    # Primary JSON manifests
    figure_manifest = {
        "figure_count": len(fig_paths),
        "figures": [
            {
                "figure_id": k,
                "path": str(v),
                "source_dependencies": {
                    "figure_event_library_comparison": ["table_event_library_summary.csv"],
                    "figure_cache_study_rankings": ["cache_study_rankings.csv"],
                    "figure_feature_panel_comparison": ["table_feature_panel_comparison.csv"],
                    "figure_portfolio_risk_workloads": ["table_portfolio_risk_summary.csv"],
                    "figure_pricing_workload_comparison": ["table_pricing_workload_summary.csv"],
                    "figure_unified_observability": ["table_unified_observability_summary.csv"],
                    "figure_similarity_candidates": ["table_similarity_hypothesis_summary.csv"],
                    "figure_guided_cache_evidence": ["table_guided_cache_claims_summary.csv"],
                }.get(k, []),
            }
            for k, v in fig_paths.items()
        ],
    }
    results_manifest = {
        "table_count": len(table_paths),
        "primary_tables": [str(p) for p in table_paths.values()],
        "paper_results_tables": str(csv_paper_results_tables),
        "section_mapping": str(csv_section_mapping),
    }
    claims_manifest = {
        "claims_matrix_path": str(csv_claims_matrix),
        "claim_counts_by_evidence_level": level_counts,
        "claim_levels": [
            EVIDENCE_MEASURED,
            EVIDENCE_DERIVED,
            EVIDENCE_PROXY,
            EVIDENCE_HYPOTHESIS,
            EVIDENCE_DEFERRED,
        ],
    }
    packaging_manifest = {
        "run_id": bundle.get("run_id", ""),
        "primary_csv": [
            str(csv_paper_results_tables),
            str(csv_claims_matrix),
            str(csv_section_mapping),
            str(csv_artifact_index),
        ],
        "primary_json": [
            str(out / "paper_results_manifest.json"),
            str(out / "paper_figure_manifest.json"),
            str(out / "paper_claims_manifest.json"),
            str(out / "paper_packaging_manifest.json"),
        ],
        "primary_methods_table": str(csv_methods),
        "docs_exported": [
            str(md_narrative),
            str(md_methods),
            str(md_results),
            str(md_limitations),
            str(md_future_work),
            str(md_bridge),
            str(md_submission),
        ],
        "no_hallucination_note": "Artifacts are derived from canonical phase outputs only.",
    }
    (out / "paper_results_manifest.json").write_text(
        json.dumps(results_manifest, indent=2), encoding="utf-8"
    )
    (out / "paper_figure_manifest.json").write_text(
        json.dumps(figure_manifest, indent=2), encoding="utf-8"
    )
    (out / "paper_claims_manifest.json").write_text(
        json.dumps(claims_manifest, indent=2), encoding="utf-8"
    )
    (out / "paper_packaging_manifest.json").write_text(
        json.dumps(packaging_manifest, indent=2), encoding="utf-8"
    )

    return {
        "paper_results_tables_csv": str(csv_paper_results_tables),
        "paper_claims_matrix_csv": str(csv_claims_matrix),
        "paper_section_mapping_csv": str(csv_section_mapping),
        "paper_artifact_index_csv": str(csv_artifact_index),
        "paper_results_manifest_json": str(out / "paper_results_manifest.json"),
        "paper_figure_manifest_json": str(out / "paper_figure_manifest.json"),
        "paper_claims_manifest_json": str(out / "paper_claims_manifest.json"),
        "paper_packaging_manifest_json": str(out / "paper_packaging_manifest.json"),
        "paper_narrative_md": str(md_narrative),
        "paper_methods_md": str(md_methods),
        "paper_results_md": str(md_results),
        "paper_tables_and_figures_md": str(md_tables_figures),
        "paper_claim_discipline_md": str(md_claim_discipline),
        "paper_limitations_md": str(md_limitations),
        "paper_future_work_md": str(md_future_work),
        "proposal_to_paper_bridge_md": str(md_bridge),
        "paper_submission_readiness_md": str(md_submission),
        "paper_methods_summary_csv": str(csv_methods),
        **{f"{k}_csv": str(v) for k, v in table_paths.items()},
        **{f"{k}_png": str(v) for k, v in fig_paths.items()},
    }

