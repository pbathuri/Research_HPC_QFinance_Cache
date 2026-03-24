"""Optional HPC/QHPC future-extension planning artifacts.

This module is planning-only. It organizes next-step x86/HPC/QHPC validation
paths from current canonical evidence and does not claim those runs are complete.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple


STATUS_IMPLEMENTED = "implemented now"
STATUS_READY_X86 = "ready for x86/HPC validation"
STATUS_READY_BIGRED = "ready for BigRed200 execution planning"
STATUS_QHPC_MAP = "conceptually mappable to QHPC later"
STATUS_DEFERRED = "deferred / speculative"


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


def load_future_extension_sources(outputs_root: str | Path = "outputs") -> Dict[str, Any]:
    """Load canonical outputs used for future-extension planning."""
    root = Path(outputs_root)
    return {
        "unified_workload_observations": _read_csv_if_exists(
            root / "unified_observability_phase" / "unified_workload_observations.csv"
        ),
        "unified_workload_rankings": _read_csv_if_exists(
            root / "unified_observability_phase" / "unified_workload_rankings.csv"
        ),
        "similarity_candidate_summary": _read_csv_if_exists(
            root / "similarity_caching_hypothesis_phase" / "similarity_candidate_summary.csv"
        ),
        "guided_cache_candidate_workloads": _read_csv_if_exists(
            root / "guided_cache_hypothesis_phase" / "guided_cache_candidate_workloads.csv"
        ),
        "paper_claims_matrix": _read_csv_if_exists(
            root / "formal_paper_packaging_phase" / "paper_claims_matrix.csv"
        ),
        "paper_claims_manifest": _read_json_if_exists(
            root / "formal_paper_packaging_phase" / "paper_claims_manifest.json"
        ),
    }


def build_future_extension_workload_priority(
    *,
    unified_workload_observations: Any,
    unified_workload_rankings: Any,
    guided_cache_candidate_workloads: Any,
) -> Any:
    """Build workload-family escalation priority planning table."""
    import pandas as pd

    if unified_workload_observations is None or len(unified_workload_observations) == 0:
        return pd.DataFrame(
            columns=[
                "workload_family",
                "implemented_status",
                "hpc_validation_status",
                "bigred200_planning_status",
                "qhpc_mapping_status",
                "priority_score",
                "priority_rank",
                "rationale",
            ]
        )

    family_rank = {}
    if unified_workload_rankings is not None and len(unified_workload_rankings):
        sub = unified_workload_rankings.loc[
            unified_workload_rankings["ranking_axis"] == "family_cache_study_value",
            ["workload_family", "score"],
        ]
        family_rank = {str(r.workload_family): _safe_float(r.score) for r in sub.itertuples(index=False)}

    candidate_rank = {}
    if guided_cache_candidate_workloads is not None and len(guided_cache_candidate_workloads):
        c = (
            guided_cache_candidate_workloads.groupby("workload_family", dropna=False)["candidate_score"]
            .mean()
            .reset_index()
        )
        candidate_rank = {str(r.workload_family): _safe_float(r.candidate_score) for r in c.itertuples(index=False)}

    rows = []
    for fam, g in unified_workload_observations.groupby("workload_family", dropna=False):
        fam = str(fam)
        implemented = STATUS_IMPLEMENTED
        hpc_status = STATUS_READY_X86
        bigred_status = STATUS_READY_BIGRED
        if fam.startswith("pricing") or fam.startswith("portfolio"):
            qhpc_status = STATUS_QHPC_MAP
        elif fam.startswith("feature") or fam.startswith("event"):
            qhpc_status = STATUS_READY_X86
        else:
            qhpc_status = STATUS_DEFERRED

        hpc_deferred_ratio = _safe_float(g["deferred_to_hpc"].astype(float).mean())
        reuse_mean = _safe_float(g["reuse_proxy_count"].mean())
        timing_p90 = _safe_float(g["timing_p90"].mean())
        fam_score = _safe_float(family_rank.get(fam, 0.0))
        cand_score = _safe_float(candidate_rank.get(fam, 0.0))
        priority_score = (
            0.30 * fam_score
            + 0.25 * cand_score
            + 0.20 * min(1.0, hpc_deferred_ratio + 0.2)
            + 0.15 * min(1.0, reuse_mean / 250.0)
            + 0.10 * min(1.0, timing_p90 / 800.0)
        )
        rows.append(
            {
                "workload_family": fam,
                "implemented_status": implemented,
                "hpc_validation_status": hpc_status,
                "bigred200_planning_status": bigred_status,
                "qhpc_mapping_status": qhpc_status,
                "priority_score": float(priority_score),
                "rationale": (
                    "priority uses unified family ranking, candidate concentration, deferred workload share, "
                    "reuse proxy intensity, and timing pressure"
                ),
            }
        )
    out = pd.DataFrame(rows).sort_values("priority_score", ascending=False).reset_index(drop=True)
    if len(out):
        out["priority_rank"] = out["priority_score"].rank(method="dense", ascending=False).astype(int)
    return out


def build_pmu_validation_priority(
    *,
    future_extension_workload_priority: Any,
) -> Any:
    """Map workload families to PMU metric priorities and research questions."""
    import pandas as pd

    if future_extension_workload_priority is None or len(future_extension_workload_priority) == 0:
        return pd.DataFrame()

    metric_map = {
        "event_workloads": [
            ("L1/L2/L3 miss metrics", "window-join reconstruction locality and miss pressure"),
            ("TLB metrics", "join-path and identifier mapping translation pressure"),
            ("prefetch metrics", "sequential window scan efficiency"),
        ],
        "feature_panel_workloads": [
            ("L1/L2/L3 miss metrics", "feature matrix construction locality and dimensional sweeps"),
            ("prefetch metrics", "columnar/rolling feature traversal behavior"),
            ("TLB metrics", "large panel translation pressure"),
        ],
        "portfolio_risk_workloads": [
            ("L1/L2/L3 miss metrics", "scenario recomputation and covariance-window pressure"),
            ("NUMA / remote-hit metrics", "slice/scenario decomposition placement behavior"),
            ("false-sharing/cache-line-bounce", "parallel aggregation contention risk"),
        ],
        "pricing_workloads": [
            ("L1/L2/L3 miss metrics", "batch and Greeks recomputation locality"),
            ("prefetch metrics", "path/contract traversal and simulation memory access"),
            ("TLB metrics", "large batch parameter-sweep translation pressure"),
        ],
    }
    rows = []
    for r in future_extension_workload_priority.itertuples(index=False):
        fam = str(r.workload_family)
        for metric, question in metric_map.get(fam, []):
            rows.append(
                {
                    "workload_family": fam,
                    "pmu_metric_group": metric,
                    "research_question": question,
                    "status_label": STATUS_READY_X86,
                    "priority_rank": int(r.priority_rank),
                    "dependency_artifacts": "unified_workload_observations.csv;guided_cache_candidate_workloads.csv",
                    "strengthening_target": "convert proxy-supported/hypothesis claims into stronger hardware-grounded evidence",
                }
            )
    return pd.DataFrame(rows).sort_values(["priority_rank", "workload_family"]).reset_index(drop=True)


def build_bigred200_candidate_workloads(
    *,
    guided_cache_candidate_workloads: Any,
    future_extension_workload_priority: Any,
) -> Any:
    """Build planning-level BigRed200 candidate workload table."""
    import pandas as pd

    if guided_cache_candidate_workloads is None or len(guided_cache_candidate_workloads) == 0:
        return pd.DataFrame()

    priority_rank = {
        str(r.workload_family): int(r.priority_rank)
        for r in future_extension_workload_priority.itertuples(index=False)
    } if future_extension_workload_priority is not None and len(future_extension_workload_priority) else {}

    top = guided_cache_candidate_workloads.head(min(40, len(guided_cache_candidate_workloads))).copy()
    top["family_priority_rank"] = top["workload_family"].map(lambda x: priority_rank.get(str(x), 99))
    top["status_label"] = STATUS_READY_BIGRED
    top["partitioning_strategy"] = top["workload_family"].map(
        lambda f: (
            "event-set x window-family partition"
            if str(f).startswith("event")
            else (
                "panel date-chunk x security-slice partition"
                if str(f).startswith("feature")
                else (
                    "scenario-family x slice partition"
                    if str(f).startswith("portfolio")
                    else "model-family x contract-batch partition"
                )
            )
        )
    )
    top["launch_plan_hint"] = "slurm-array-style planning (documentation only; no execution in this phase)"
    out_cols = [
        "workload_family",
        "workload_variant",
        "deterministic_label",
        "candidate_layer",
        "candidate_evidence_level",
        "candidate_score",
        "family_priority_rank",
        "status_label",
        "partitioning_strategy",
        "launch_plan_hint",
    ]
    return top[out_cols].sort_values(
        ["family_priority_rank", "candidate_score"], ascending=[True, False]
    ).reset_index(drop=True)


def build_qhpc_mapping_summary(
    *,
    future_extension_workload_priority: Any,
    pmu_validation_priority: Any,
) -> Any:
    """Build conceptual mapping from current workloads to later QHPC framing."""
    import pandas as pd

    rows = []
    if future_extension_workload_priority is None or len(future_extension_workload_priority) == 0:
        return pd.DataFrame()
    for r in future_extension_workload_priority.itertuples(index=False):
        fam = str(r.workload_family)
        if fam.startswith("pricing"):
            qhpc_theme = "hybrid simulation acceleration and reuse-guided Monte Carlo orchestration"
            readiness = STATUS_QHPC_MAP
        elif fam.startswith("portfolio"):
            qhpc_theme = "scenario decomposition and hybrid risk aggregation mapping"
            readiness = STATUS_QHPC_MAP
        elif fam.startswith("feature"):
            qhpc_theme = "high-dimensional panel transformation and reuse-aware preconditioning"
            readiness = STATUS_READY_X86
        else:
            qhpc_theme = "event-window reconstruction scheduling and similarity-guided retrieval"
            readiness = STATUS_READY_X86
        rows.append(
            {
                "workload_family": fam,
                "qhpc_mapping_theme": qhpc_theme,
                "status_label": readiness,
                "required_preconditions": (
                    "x86 PMU validation + BigRed200 scaling evidence before experimental QHPC claims"
                ),
                "source_dependencies": (
                    "future_extension_workload_priority.csv;pmu_validation_priority.csv;guided_cache_hypothesis outputs"
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("workload_family").reset_index(drop=True)


def build_phase2_research_program_summary(
    *,
    future_extension_workload_priority: Any,
    pmu_validation_priority: Any,
    bigred200_candidate_workloads: Any,
    qhpc_mapping_summary: Any,
) -> Any:
    """Build structured Phase 2 continuation program summary."""
    import pandas as pd

    rows = [
        {
            "track_id": "track_x86_pmu_validation",
            "horizon": "near-term",
            "status_label": STATUS_READY_X86,
            "scope": "PMU-backed validation across prioritized workload families",
            "dependency_artifacts": "pmu_validation_priority.csv",
        },
        {
            "track_id": "track_bigred200_scaling",
            "horizon": "medium-term",
            "status_label": STATUS_READY_BIGRED,
            "scope": "cluster-scale batch/partition planning and replay measurements",
            "dependency_artifacts": "bigred200_candidate_workloads.csv",
        },
        {
            "track_id": "track_similarity_validation",
            "horizon": "near-term",
            "status_label": STATUS_READY_X86,
            "scope": "controlled exact-vs-similarity replay on x86/HPC",
            "dependency_artifacts": "similarity_caching_hypothesis + guided_cache_hypothesis outputs",
        },
        {
            "track_id": "track_guided_cache_systems",
            "horizon": "medium-term",
            "status_label": STATUS_DEFERRED,
            "scope": "routing/admission policy experiments after stronger PMU evidence",
            "dependency_artifacts": "guided_cache_evidence_matrix.csv",
        },
        {
            "track_id": "track_qhpc_mapping",
            "horizon": "long-term",
            "status_label": STATUS_QHPC_MAP,
            "scope": "experimental hybrid QHPC mapping contingent on HPC validation",
            "dependency_artifacts": "qhpc_mapping_summary.csv",
        },
    ]
    out = pd.DataFrame(rows)
    out["program_readiness_score"] = out["status_label"].map(
        {
            STATUS_READY_X86: 0.85,
            STATUS_READY_BIGRED: 0.75,
            STATUS_QHPC_MAP: 0.55,
            STATUS_DEFERRED: 0.35,
            STATUS_IMPLEMENTED: 1.0,
        }
    )
    out["program_rank"] = out["program_readiness_score"].rank(method="dense", ascending=False).astype(int)
    return out.sort_values("program_rank").reset_index(drop=True)


def _safe_plot_library() -> Any:
    try:
        import matplotlib.pyplot as plt

        return plt
    except Exception:
        return None


def _plot_bar(
    *,
    frame: Any,
    x: str,
    y: str,
    title: str,
    output_path: Path,
) -> Optional[Path]:
    plt = _safe_plot_library()
    if plt is None:
        return None
    fig = plt.figure(figsize=(8.8, 4.6))
    ax = fig.add_subplot(111)
    if frame is None or len(frame) == 0 or x not in frame.columns or y not in frame.columns:
        ax.text(0.5, 0.5, "Data unavailable", ha="center", va="center")
        ax.set_axis_off()
        ax.set_title(title)
    else:
        ax.bar(frame[x].astype(str).tolist(), frame[y].astype(float).tolist())
        ax.set_title(title)
        ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)
    return output_path


def run_future_extension_planning_bundle(
    *,
    outputs_root: str | Path = "outputs",
    source_tables: Optional[Mapping[str, Any]] = None,
    run_id: str = "",
) -> Dict[str, Any]:
    """Run planning-only future extension synthesis bundle."""
    tables = dict(source_tables or {})
    if not tables:
        tables = load_future_extension_sources(outputs_root=outputs_root)

    future_priority = build_future_extension_workload_priority(
        unified_workload_observations=tables.get("unified_workload_observations"),
        unified_workload_rankings=tables.get("unified_workload_rankings"),
        guided_cache_candidate_workloads=tables.get("guided_cache_candidate_workloads"),
    )
    pmu_priority = build_pmu_validation_priority(
        future_extension_workload_priority=future_priority
    )
    bigred_candidates = build_bigred200_candidate_workloads(
        guided_cache_candidate_workloads=tables.get("guided_cache_candidate_workloads"),
        future_extension_workload_priority=future_priority,
    )
    qhpc_map = build_qhpc_mapping_summary(
        future_extension_workload_priority=future_priority,
        pmu_validation_priority=pmu_priority,
    )
    phase2 = build_phase2_research_program_summary(
        future_extension_workload_priority=future_priority,
        pmu_validation_priority=pmu_priority,
        bigred200_candidate_workloads=bigred_candidates,
        qhpc_mapping_summary=qhpc_map,
    )
    rid = run_id or "optional_hpc_qhpc_future_extension_planning::v1"

    future_manifest = {
        "run_id": rid,
        "status_labels": [
            STATUS_IMPLEMENTED,
            STATUS_READY_X86,
            STATUS_READY_BIGRED,
            STATUS_QHPC_MAP,
            STATUS_DEFERRED,
        ],
        "dependency_outputs": [
            "unified_workload_observations.csv",
            "unified_workload_rankings.csv",
            "similarity_candidate_summary.csv",
            "guided_cache_candidate_workloads.csv",
            "paper_claims_matrix.csv",
        ],
        "planning_only_note": "No x86/HPC/BigRed200/QHPC runs are executed in this phase.",
    }
    pmu_manifest = {
        "run_id": rid,
        "metric_groups": sorted(set(pmu_priority["pmu_metric_group"].astype(str).tolist()))
        if pmu_priority is not None and len(pmu_priority)
        else [],
        "workload_family_count": int(_safe_float(len(pmu_priority["workload_family"].unique())))
        if pmu_priority is not None and len(pmu_priority)
        else 0,
        "status_label": STATUS_READY_X86,
    }
    bigred_manifest = {
        "run_id": rid,
        "candidate_count": int(len(bigred_candidates)) if bigred_candidates is not None else 0,
        "status_label": STATUS_READY_BIGRED,
        "execution_note": "partitioning and launch strategy are planning hooks only",
    }
    qhpc_manifest = {
        "run_id": rid,
        "mapping_count": int(len(qhpc_map)) if qhpc_map is not None else 0,
        "status_label": STATUS_QHPC_MAP,
        "validation_dependency": "requires PMU-backed x86/HPC and BigRed200 evidence before experimental QHPC claims",
    }
    return {
        "run_id": rid,
        "source_tables": tables,
        "future_extension_workload_priority": future_priority,
        "pmu_validation_priority": pmu_priority,
        "bigred200_candidate_workloads": bigred_candidates,
        "qhpc_mapping_summary": qhpc_map,
        "phase2_research_program_summary": phase2,
        "future_extension_manifest": future_manifest,
        "pmu_validation_manifest": pmu_manifest,
        "bigred200_plan_manifest": bigred_manifest,
        "qhpc_relevance_manifest": qhpc_manifest,
    }


def export_future_extension_planning_bundle(
    *,
    bundle: Mapping[str, Any],
    output_dir: str | Path,
) -> Dict[str, str]:
    """Export planning artifacts (CSV/JSON first, markdown/plots second)."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    csv_future = out / "future_extension_workload_priority.csv"
    csv_pmu = out / "pmu_validation_priority.csv"
    csv_bigred = out / "bigred200_candidate_workloads.csv"
    csv_qhpc = out / "qhpc_mapping_summary.csv"
    csv_phase2 = out / "phase2_research_program_summary.csv"

    bundle["future_extension_workload_priority"].to_csv(csv_future, index=False)
    bundle["pmu_validation_priority"].to_csv(csv_pmu, index=False)
    bundle["bigred200_candidate_workloads"].to_csv(csv_bigred, index=False)
    bundle["qhpc_mapping_summary"].to_csv(csv_qhpc, index=False)
    bundle["phase2_research_program_summary"].to_csv(csv_phase2, index=False)

    json_future = out / "future_extension_manifest.json"
    json_pmu = out / "pmu_validation_manifest.json"
    json_bigred = out / "bigred200_plan_manifest.json"
    json_qhpc = out / "qhpc_relevance_manifest.json"
    json_future.write_text(json.dumps(bundle["future_extension_manifest"], indent=2), encoding="utf-8")
    json_pmu.write_text(json.dumps(bundle["pmu_validation_manifest"], indent=2), encoding="utf-8")
    json_bigred.write_text(json.dumps(bundle["bigred200_plan_manifest"], indent=2), encoding="utf-8")
    json_qhpc.write_text(json.dumps(bundle["qhpc_relevance_manifest"], indent=2), encoding="utf-8")

    # Secondary planning plots
    fig_priority = out / "plot_workload_escalation_priority.png"
    fig_mac_hpc = out / "plot_mac_now_vs_hpc_later_comparison.png"
    fig_hpc_readiness = out / "plot_workload_family_hpc_readiness.png"
    fig_roadmap = out / "plot_future_extension_roadmap.png"

    _plot_bar(
        frame=bundle["future_extension_workload_priority"],
        x="workload_family",
        y="priority_score",
        title="Workload Escalation Priority",
        output_path=fig_priority,
    )
    mac_hpc_frame = (
        bundle["future_extension_workload_priority"]
        .assign(
            implemented_score=lambda d: d["implemented_status"].map(
                lambda x: 1.0 if str(x) == STATUS_IMPLEMENTED else 0.0
            ),
            hpc_ready_score=lambda d: d["hpc_validation_status"].map(
                lambda x: 1.0 if str(x) == STATUS_READY_X86 else 0.0
            ),
        )[["workload_family", "implemented_score", "hpc_ready_score"]]
    )
    # stacked-ish by plotting hpc_ready_score only; data table still captures both.
    _plot_bar(
        frame=mac_hpc_frame,
        x="workload_family",
        y="hpc_ready_score",
        title="Mac-now vs x86/HPC-later Readiness",
        output_path=fig_mac_hpc,
    )
    hpc_ready = (
        bundle["pmu_validation_priority"]
        .groupby("workload_family", dropna=False)["pmu_metric_group"]
        .count()
        .reset_index(name="pmu_metric_groups_planned")
    )
    _plot_bar(
        frame=hpc_ready,
        x="workload_family",
        y="pmu_metric_groups_planned",
        title="Workload-family HPC Readiness Plan",
        output_path=fig_hpc_readiness,
    )
    _plot_bar(
        frame=bundle["phase2_research_program_summary"],
        x="track_id",
        y="program_readiness_score",
        title="Future-extension Roadmap",
        output_path=fig_roadmap,
    )

    return {
        "future_extension_workload_priority_csv": str(csv_future),
        "pmu_validation_priority_csv": str(csv_pmu),
        "bigred200_candidate_workloads_csv": str(csv_bigred),
        "qhpc_mapping_summary_csv": str(csv_qhpc),
        "phase2_research_program_summary_csv": str(csv_phase2),
        "future_extension_manifest_json": str(json_future),
        "pmu_validation_manifest_json": str(json_pmu),
        "bigred200_plan_manifest_json": str(json_bigred),
        "qhpc_relevance_manifest_json": str(json_qhpc),
        "plot_workload_escalation_priority_png": str(fig_priority),
        "plot_mac_now_vs_hpc_later_comparison_png": str(fig_mac_hpc),
        "plot_workload_family_hpc_readiness_png": str(fig_hpc_readiness),
        "plot_future_extension_roadmap_png": str(fig_roadmap),
    }

