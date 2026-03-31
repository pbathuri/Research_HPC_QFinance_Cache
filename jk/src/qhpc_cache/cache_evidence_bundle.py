"""Canonical cache evidence bundle generator.

Produces the full set of evidence artifacts (CSVs, JSONs, Markdown, plots)
from a completed study run. This is the primary research deliverable layer.
"""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from qhpc_cache.reuse_distance_analytics import (
    ReuseDistanceRow,
    LocalityMetrics,
    WorkingSetWindow,
    compute_reuse_distances,
    compute_locality_metrics,
    compute_working_set_timeline,
)
from qhpc_cache.cache_economics import (
    CacheEconomicsSummary,
    compute_economics_from_rows,
    compute_similarity_decomposition,
)
from qhpc_cache.hpc_provenance import build_hpc_provenance_fields
from qhpc_cache.workload_registry import (
    build_workload_regime_summary,
    get_all_family_metadata,
)


def _rows_to_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in fieldnames})


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def generate_evidence_bundle(
    result_rows: List[Dict[str, Any]],
    output_dir: Path,
    *,
    run_label: str = "",
    emit_plots: bool = True,
    requested_backend: str = "cpu_local",
    budget_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """Generate the canonical cache evidence bundle from study result rows.

    Parameters
    ----------
    result_rows : per-access result dicts with standardized fields
    output_dir : directory for evidence artifacts
    run_label : human-readable run label
    emit_plots : whether to generate PNG plots
    requested_backend : backend intent for provenance
    budget_info : optional budget utilization info

    Returns
    -------
    dict mapping artifact names to file paths
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    artifacts: Dict[str, str] = {}

    key_stream = [str(r.get("request_key_hash", r.get("request_key", ""))) for r in result_rows]
    hit_stream = [bool(r.get("cache_hit", False)) for r in result_rows]
    sim_group_stream = [str(r.get("similarity_group_id", "")) for r in result_rows]

    # 1. Reuse-distance analysis
    reuse_rows = compute_reuse_distances(key_stream, similarity_group_stream=sim_group_stream)
    reuse_csv_path = out / "cache_reuse_distance.csv"
    _rows_to_csv(
        reuse_csv_path,
        [r.to_dict() for r in reuse_rows],
        fieldnames=[
            "event_index", "request_key_hash", "exact_reuse_distance",
            "similarity_reuse_distance", "first_seen_flag", "cold_start_flag",
            "hit_after_n_distinct_keys", "reuse_distance_bucket",
        ],
    )
    artifacts["cache_reuse_distance_csv"] = str(reuse_csv_path)

    # 2. Locality metrics (per-family and aggregate)
    locality_all = compute_locality_metrics(key_stream, reuse_rows)
    locality_by_family: Dict[str, LocalityMetrics] = {}
    family_groups: Dict[str, List[int]] = defaultdict(list)
    for idx, r in enumerate(result_rows):
        fam = r.get("workload_family", "")
        if fam:
            family_groups[fam].append(idx)
    for fam, indices in family_groups.items():
        fam_keys = [key_stream[i] for i in indices]
        fam_reuse = compute_reuse_distances(fam_keys)
        locality_by_family[fam] = compute_locality_metrics(fam_keys, fam_reuse)

    locality_rows: List[Dict[str, Any]] = []
    agg = locality_all.to_dict()
    agg["workload_family"] = "_aggregate"
    agg["lane_id"] = ""
    locality_rows.append(agg)
    for fam, lm in locality_by_family.items():
        row = lm.to_dict()
        row["workload_family"] = fam
        row["lane_id"] = ""
        locality_rows.append(row)
    locality_csv_path = out / "cache_locality_summary.csv"
    _rows_to_csv(
        locality_csv_path,
        locality_rows,
        fieldnames=[
            "workload_family", "lane_id", "temporal_locality_score",
            "key_stream_entropy", "hotset_concentration_ratio", "top_k_key_share",
            "burstiness_score", "periodicity_score", "locality_regime",
            "one_hit_wonder_fraction", "stack_distance_p50", "stack_distance_p90",
            "stack_distance_p99", "total_accesses", "unique_keys",
        ],
    )
    artifacts["cache_locality_summary_csv"] = str(locality_csv_path)

    # 3. Working set timeline
    ws_windows = compute_working_set_timeline(key_stream, hit_stream)
    ws_csv_path = out / "working_set_timeline.csv"
    _rows_to_csv(
        ws_csv_path,
        [w.to_dict() for w in ws_windows],
        fieldnames=[
            "window_id", "time_index_start", "time_index_end",
            "working_set_size", "cumulative_unique_keys", "hotset_coverage",
            "reuse_intensity", "miss_pressure",
        ],
    )
    artifacts["working_set_timeline_csv"] = str(ws_csv_path)

    # 4. Cache economics
    econ = compute_economics_from_rows(result_rows, label=run_label)
    econ_by_family: Dict[str, CacheEconomicsSummary] = {}
    for fam, indices in family_groups.items():
        fam_rows = [result_rows[i] for i in indices]
        econ_by_family[fam] = compute_economics_from_rows(fam_rows, label=fam)
    econ_rows = [econ.to_dict()]
    for fam_econ in econ_by_family.values():
        econ_rows.append(fam_econ.to_dict())
    econ_csv_path = out / "cache_policy_value_summary.csv"
    _rows_to_csv(
        econ_csv_path,
        econ_rows,
        fieldnames=[
            "label", "total_accesses", "exact_hits", "similarity_hits", "misses",
            "total_lookup_overhead_ms", "total_saved_compute_ms_exact",
            "total_saved_compute_ms_similarity", "total_compute_ms_on_misses",
            "cache_storage_events", "overwrite_events", "net_cache_value_ms",
            "net_cache_value_ratio", "net_benefit_flag", "benefit_per_hit",
            "miss_penalty_mean_ms", "miss_penalty_p50_ms", "miss_penalty_p90_ms",
            "miss_penalty_p99_ms",
        ],
    )
    artifacts["cache_policy_value_summary_csv"] = str(econ_csv_path)

    # 5. Exact vs similarity decomposition
    sim_decomp = compute_similarity_decomposition(result_rows)
    sim_by_family: Dict[str, Dict[str, Any]] = {}
    for fam, indices in family_groups.items():
        fam_rows = [result_rows[i] for i in indices]
        sim_by_family[fam] = compute_similarity_decomposition(fam_rows)
    sim_rows: List[Dict[str, Any]] = []
    agg_sim = dict(sim_decomp)
    agg_sim["workload_family"] = "_aggregate"
    sim_rows.append(agg_sim)
    for fam, decomp in sim_by_family.items():
        row = dict(decomp)
        row["workload_family"] = fam
        sim_rows.append(row)
    sim_csv_path = out / "similarity_acceptance_summary.csv"
    _rows_to_csv(
        sim_csv_path,
        sim_rows,
        fieldnames=[
            "workload_family", "total_accesses", "exact_hit_count", "exact_hit_rate",
            "similarity_candidate_count", "similarity_accepted_count",
            "similarity_rejected_count", "similarity_hit_rate", "combined_hit_rate",
        ],
    )
    artifacts["similarity_acceptance_summary_csv"] = str(sim_csv_path)

    # 6. Workload regime summary
    regime_rows = build_workload_regime_summary(result_rows)
    regime_csv_path = out / "workload_regime_summary.csv"
    _rows_to_csv(
        regime_csv_path,
        regime_rows,
        fieldnames=[
            "workload_family", "observed_request_count", "observed_exact_hit_rate",
            "observed_similarity_hit_rate", "realism_tier", "finance_context_short",
            "expected_reuse_mode", "expected_locality_mode", "approximation_risk",
            "synthetic_control_flag",
        ],
    )
    artifacts["workload_regime_summary_csv"] = str(regime_csv_path)

    # 7. Evidence summary JSON + MD
    provenance = build_hpc_provenance_fields()
    evidence_summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_label": run_label,
        "hpc_provenance": provenance,
        "aggregate_locality": locality_all.to_dict(),
        "aggregate_economics": econ.to_dict(),
        "aggregate_similarity_decomposition": sim_decomp,
        "per_family_locality": {fam: lm.to_dict() for fam, lm in locality_by_family.items()},
        "per_family_economics": {fam: e.to_dict() for fam, e in econ_by_family.items()},
        "workload_regime_count": len(regime_rows),
        "budget_utilization": budget_info or {},
        "artifacts": artifacts,
    }
    summary_json_path = out / "cache_evidence_summary.json"
    _write_json(summary_json_path, evidence_summary)
    artifacts["cache_evidence_summary_json"] = str(summary_json_path)

    summary_md_path = out / "cache_evidence_summary.md"
    summary_md_path.write_text(_render_evidence_md(evidence_summary), encoding="utf-8")
    artifacts["cache_evidence_summary_md"] = str(summary_md_path)

    # 8. Plots
    if emit_plots:
        plot_artifacts = _generate_evidence_plots(
            reuse_rows=reuse_rows,
            locality_all=locality_all,
            locality_by_family=locality_by_family,
            ws_windows=ws_windows,
            econ=econ,
            econ_by_family=econ_by_family,
            sim_decomp=sim_decomp,
            sim_by_family=sim_by_family,
            output_dir=out,
        )
        artifacts.update(plot_artifacts)

    return artifacts


def _render_evidence_md(summary: Dict[str, Any]) -> str:
    loc = summary.get("aggregate_locality", {})
    econ = summary.get("aggregate_economics", {})
    sim = summary.get("aggregate_similarity_decomposition", {})
    prov = summary.get("hpc_provenance", {})
    budget = summary.get("budget_utilization", {})

    lines = [
        "# Cache Evidence Summary",
        "",
        f"- generated: `{summary.get('generated_at_utc', '')}`",
        f"- run_label: `{summary.get('run_label', '')}`",
        f"- host: `{prov.get('execution_host', '')}`",
        f"- cluster: `{prov.get('cluster_name', 'none')}`",
        f"- context: `{prov.get('physical_execution_context', '')}`",
        "",
        "## Locality Profile",
        "",
        f"- regime: `{loc.get('locality_regime', '')}`",
        f"- temporal_locality_score: `{loc.get('temporal_locality_score', 0):.4f}`",
        f"- key_stream_entropy: `{loc.get('key_stream_entropy', 0):.4f}`",
        f"- hotset_concentration: `{loc.get('hotset_concentration_ratio', 0):.4f}`",
        f"- one_hit_wonder_fraction: `{loc.get('one_hit_wonder_fraction', 0):.4f}`",
        f"- stack_distance p50/p90/p99: `{loc.get('stack_distance_p50', 0):.1f}` / `{loc.get('stack_distance_p90', 0):.1f}` / `{loc.get('stack_distance_p99', 0):.1f}`",
        "",
        "## Cache Economics",
        "",
        f"- total_accesses: `{econ.get('total_accesses', 0)}`",
        f"- exact_hits: `{econ.get('exact_hits', 0)}`",
        f"- similarity_hits: `{econ.get('similarity_hits', 0)}`",
        f"- misses: `{econ.get('misses', 0)}`",
        f"- net_cache_value_ms: `{econ.get('net_cache_value_ms', 0):.2f}`",
        f"- net_benefit_flag: `{econ.get('net_benefit_flag', False)}`",
        f"- net_cache_value_ratio: `{econ.get('net_cache_value_ratio', 0):.4f}`",
        "",
        "## Exact vs Similarity Decomposition",
        "",
        f"- exact_hit_rate: `{sim.get('exact_hit_rate', 0):.4f}`",
        f"- similarity_hit_rate: `{sim.get('similarity_hit_rate', 0):.4f}`",
        f"- combined_hit_rate: `{sim.get('combined_hit_rate', 0):.4f}`",
        f"- similarity_candidates: `{sim.get('similarity_candidate_count', 0)}`",
        f"- similarity_accepted: `{sim.get('similarity_accepted_count', 0)}`",
        f"- similarity_rejected: `{sim.get('similarity_rejected_count', 0)}`",
    ]

    if budget:
        lines.extend([
            "",
            "## Budget Utilization",
            "",
            f"- requested_budget_minutes: `{budget.get('requested_budget_minutes', 'n/a')}`",
            f"- actual_runtime_minutes: `{budget.get('actual_runtime_minutes', 'n/a')}`",
            f"- budget_utilization_fraction: `{budget.get('budget_utilization_fraction', 'n/a')}`",
            f"- termination_reason: `{budget.get('termination_reason', 'n/a')}`",
            f"- workload_limited: `{budget.get('workload_limited_flag', 'n/a')}`",
            f"- budget_limited: `{budget.get('budget_limited_flag', 'n/a')}`",
        ])

    per_fam_econ = summary.get("per_family_economics", {})
    if per_fam_econ:
        lines.extend(["", "## Per-Family Economics", ""])
        lines.append("| family | accesses | exact_hits | sim_hits | misses | net_value_ms | benefit_flag |")
        lines.append("|---|---:|---:|---:|---:|---:|---|")
        for fam, fe in per_fam_econ.items():
            lines.append(
                f"| {fam} | {fe.get('total_accesses', 0)} | "
                f"{fe.get('exact_hits', 0)} | {fe.get('similarity_hits', 0)} | "
                f"{fe.get('misses', 0)} | {fe.get('net_cache_value_ms', 0):.2f} | "
                f"{fe.get('net_benefit_flag', False)} |"
            )

    lines.append("")
    return "\n".join(lines)


def _generate_evidence_plots(
    *,
    reuse_rows: List[ReuseDistanceRow],
    locality_all: LocalityMetrics,
    locality_by_family: Dict[str, LocalityMetrics],
    ws_windows: List[WorkingSetWindow],
    econ: CacheEconomicsSummary,
    econ_by_family: Dict[str, CacheEconomicsSummary],
    sim_decomp: Dict[str, Any],
    sim_by_family: Dict[str, Dict[str, Any]],
    output_dir: Path,
) -> Dict[str, str]:
    artifacts: Dict[str, str] = {}

    finite_rd = [
        r.exact_reuse_distance for r in reuse_rows
        if not math.isnan(r.exact_reuse_distance)
    ]

    # Reuse distance histogram
    if finite_rd:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        ax.hist(finite_rd, bins=min(50, max(10, len(set(int(d) for d in finite_rd)))),
                color="#2E86AB", edgecolor="white", alpha=0.85)
        ax.set_xlabel("Exact Reuse Distance")
        ax.set_ylabel("Frequency")
        ax.set_title("Reuse Distance Distribution")
        path = output_dir / "reuse_distance_histogram.png"
        fig.savefig(path, dpi=140, bbox_inches="tight")
        plt.close(fig)
        artifacts["reuse_distance_histogram_png"] = str(path)

    # Reuse distance CDF
    if finite_rd:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        sorted_rd = sorted(finite_rd)
        cdf_y = np.arange(1, len(sorted_rd) + 1) / len(sorted_rd)
        ax.plot(sorted_rd, cdf_y, color="#A23B72", linewidth=1.5)
        ax.set_xlabel("Exact Reuse Distance")
        ax.set_ylabel("Cumulative Fraction")
        ax.set_title("Reuse Distance CDF")
        ax.axhline(y=0.5, color="gray", linestyle="--", alpha=0.5)
        ax.axhline(y=0.9, color="gray", linestyle="--", alpha=0.5)
        path = output_dir / "reuse_distance_cdf.png"
        fig.savefig(path, dpi=140, bbox_inches="tight")
        plt.close(fig)
        artifacts["reuse_distance_cdf_png"] = str(path)

    # Working set over time
    if ws_windows:
        fig, ax = plt.subplots(figsize=(10, 4.5))
        win_ids = [w.window_id for w in ws_windows]
        wss = [w.working_set_size for w in ws_windows]
        cum = [w.cumulative_unique_keys for w in ws_windows]
        ax.plot(win_ids, wss, label="Window Working Set", color="#2E86AB", linewidth=1.5)
        ax.plot(win_ids, cum, label="Cumulative Unique Keys", color="#F26419",
                linewidth=1.5, linestyle="--")
        ax.set_xlabel("Window Index")
        ax.set_ylabel("Key Count")
        ax.set_title("Working Set Dynamics")
        ax.legend()
        path = output_dir / "working_set_over_time.png"
        fig.savefig(path, dpi=140, bbox_inches="tight")
        plt.close(fig)
        artifacts["working_set_over_time_png"] = str(path)

    # Hotset concentration by family
    if locality_by_family:
        fig, ax = plt.subplots(figsize=(max(8, len(locality_by_family) * 0.8), 4.5))
        families = sorted(locality_by_family.keys())
        concentrations = [locality_by_family[f].hotset_concentration_ratio for f in families]
        ax.bar(range(len(families)), concentrations, color="#00A878")
        ax.set_xticks(range(len(families)))
        ax.set_xticklabels(families, rotation=45, ha="right", fontsize=8)
        ax.set_ylabel("Hotset Concentration Ratio")
        ax.set_title("Hotset Concentration by Family")
        ax.set_ylim(0, 1)
        path = output_dir / "hotset_concentration.png"
        fig.savefig(path, dpi=140, bbox_inches="tight")
        plt.close(fig)
        artifacts["hotset_concentration_png"] = str(path)

    # Exact vs similarity hits
    if sim_by_family:
        fig, ax = plt.subplots(figsize=(max(8, len(sim_by_family) * 0.8), 4.5))
        families = sorted(sim_by_family.keys())
        exact_rates = [sim_by_family[f]["exact_hit_rate"] for f in families]
        sim_rates = [sim_by_family[f]["similarity_hit_rate"] for f in families]
        x = np.arange(len(families))
        ax.bar(x - 0.18, exact_rates, width=0.36, label="Exact Hit Rate", color="#2E86AB")
        ax.bar(x + 0.18, sim_rates, width=0.36, label="Similarity Hit Rate", color="#00A878")
        ax.set_xticks(x)
        ax.set_xticklabels(families, rotation=45, ha="right", fontsize=8)
        ax.set_ylabel("Rate")
        ax.set_ylim(0, 1)
        ax.set_title("Exact vs Similarity Hit Rates")
        ax.legend()
        path = output_dir / "exact_vs_similarity_hits.png"
        fig.savefig(path, dpi=140, bbox_inches="tight")
        plt.close(fig)
        artifacts["exact_vs_similarity_hits_png"] = str(path)

    # Net cache value by family
    if econ_by_family:
        fig, ax = plt.subplots(figsize=(max(8, len(econ_by_family) * 0.8), 4.5))
        families = sorted(econ_by_family.keys())
        values = [econ_by_family[f].net_cache_value_ms for f in families]
        colors = ["#00A878" if v >= 0 else "#E63946" for v in values]
        ax.bar(range(len(families)), values, color=colors)
        ax.set_xticks(range(len(families)))
        ax.set_xticklabels(families, rotation=45, ha="right", fontsize=8)
        ax.set_ylabel("Net Cache Value (ms)")
        ax.set_title("Net Cache Value by Family")
        ax.axhline(y=0, color="gray", linestyle="-", alpha=0.5)
        path = output_dir / "net_cache_value_by_policy.png"
        fig.savefig(path, dpi=140, bbox_inches="tight")
        plt.close(fig)
        artifacts["net_cache_value_by_policy_png"] = str(path)

    # Locality regime comparison
    if locality_by_family:
        fig, ax = plt.subplots(figsize=(max(8, len(locality_by_family) * 0.8), 4.5))
        families = sorted(locality_by_family.keys())
        scores = [locality_by_family[f].temporal_locality_score for f in families]
        ax.bar(range(len(families)), scores, color="#F26419")
        ax.set_xticks(range(len(families)))
        ax.set_xticklabels(families, rotation=45, ha="right", fontsize=8)
        ax.set_ylabel("Temporal Locality Score")
        ax.set_ylim(0, 1)
        ax.set_title("Locality Regime Comparison")
        path = output_dir / "locality_regime_comparison.png"
        fig.savefig(path, dpi=140, bbox_inches="tight")
        plt.close(fig)
        artifacts["locality_regime_comparison_png"] = str(path)

    return artifacts
