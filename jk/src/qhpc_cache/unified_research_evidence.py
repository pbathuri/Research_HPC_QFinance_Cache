"""Unified evidence bundle composing results from all three research paths.

Produces a single research_evidence_bundle.json that links:
- Path A: Pandora circuit cache (circuit-level reuse)
- Path B: SLM-trained policy (AI-assisted cache decisions)
- Path C: MPI scaling (distributed cache-aware execution)

Each path's evidence is loaded from its output directory, validated for
structural completeness, and merged into a claims-aligned summary.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class PathEvidence:
    path_id: str
    path_name: str
    status: str  # "complete", "partial", "missing"
    output_dir: str
    key_metrics: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[str] = field(default_factory=list)
    claims_addressed: List[str] = field(default_factory=list)
    caveats: List[str] = field(default_factory=list)


@dataclass
class UnifiedBundle:
    generated_utc: str
    paths: List[PathEvidence]
    claims_summary: Dict[str, Dict[str, Any]]
    combined_novel_contributions: List[str]
    next_steps: List[str]


def _load_json_safe(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _collect_pandora_evidence(output_dir: Path) -> PathEvidence:
    evidence = PathEvidence(
        path_id="path_a",
        path_name="Pandora Circuit Cache",
        status="missing",
        output_dir=str(output_dir),
        claims_addressed=["C1_exact_reuse_exists", "C2_similarity_reuse_controllable"],
    )
    metrics_file = output_dir / "pandora_cache_metrics.json"
    evidence_file = output_dir / "pandora_cache_evidence.json"
    results_file = output_dir / "pandora_study_results.csv"
    savings_file = output_dir / "pandora_compilation_savings.json"

    for f in [metrics_file, evidence_file, results_file, savings_file]:
        if f.exists():
            evidence.artifacts.append(str(f))

    cache_evidence = _load_json_safe(evidence_file)
    if cache_evidence:
        evidence.status = "complete"
        evidence.key_metrics = {
            "structural_hit_rate": cache_evidence.get("structural_hit_rate", 0),
            "exact_hit_rate": cache_evidence.get("exact_hit_rate", 0),
            "overall_hit_rate": cache_evidence.get("hit_rate", 0),
            "total_compilation_time_saved_ms": cache_evidence.get(
                "total_compilation_time_saved_ms", 0
            ),
            "total_lookups": cache_evidence.get("total_lookups", 0),
            "cache_entries": cache_evidence.get("entries", 0),
            "similarity_threshold": cache_evidence.get("similarity_threshold", 0),
        }
        if evidence.key_metrics["structural_hit_rate"] == 0:
            evidence.caveats.append(
                "No structural hits observed -- threshold may be too high "
                "or problems too dissimilar."
            )
    else:
        evidence.status = "partial" if evidence.artifacts else "missing"
        evidence.caveats.append("Cache evidence file not found or unreadable.")

    return evidence


def _collect_slm_evidence(output_dir: Path) -> PathEvidence:
    evidence = PathEvidence(
        path_id="path_b",
        path_name="SLM-Trained AI Cache Policy",
        status="missing",
        output_dir=str(output_dir),
        claims_addressed=["C7_traces_slm_ready"],
    )
    comparison_file = output_dir / "policy_comparison.csv"
    evaluation_file = output_dir / "policy_evaluation.json"
    model_card_file = output_dir / "slm_model_card.json"
    importance_file = output_dir / "feature_importance.csv"

    for f in [comparison_file, evaluation_file, model_card_file, importance_file]:
        if f.exists():
            evidence.artifacts.append(str(f))

    evaluation = _load_json_safe(evaluation_file)
    model_card = _load_json_safe(model_card_file)

    if evaluation:
        evidence.status = "complete"
        best_f1 = 0.0
        best_policy = ""
        for policy_name, metrics in evaluation.items():
            f1 = metrics.get("f1", 0)
            if f1 > best_f1:
                best_f1 = f1
                best_policy = policy_name

        heuristic_f1 = evaluation.get("heuristic", {}).get("f1", 0)
        slm_f1 = evaluation.get("slm_trained", {}).get("f1", 0)

        evidence.key_metrics = {
            "best_policy": best_policy,
            "best_f1": best_f1,
            "heuristic_f1": heuristic_f1,
            "slm_f1": slm_f1,
            "slm_vs_heuristic_f1_delta": round(slm_f1 - heuristic_f1, 4),
            "policies_compared": list(evaluation.keys()),
        }

        if model_card:
            cv = model_card.get("cross_validation", {})
            evidence.key_metrics["cv_mean_auc_roc"] = cv.get("mean_auc_roc", 0)
            evidence.key_metrics["cv_mean_f1"] = cv.get("mean_f1", 0)

        if slm_f1 <= heuristic_f1:
            evidence.caveats.append(
                "SLM did not outperform heuristic on F1; "
                "may need more training data or feature engineering."
            )
    else:
        evidence.status = "partial" if evidence.artifacts else "missing"
        evidence.caveats.append("Policy evaluation file not found.")

    return evidence


def _collect_mpi_evidence(output_dir: Path) -> PathEvidence:
    evidence = PathEvidence(
        path_id="path_c",
        path_name="MPI Scaling Study",
        status="missing",
        output_dir=str(output_dir),
        claims_addressed=["C5_hpc_evidence"],
    )
    results_file = output_dir / "mpi_scaling_results.csv"
    comm_file = output_dir / "mpi_communication_comparison.json"
    curve_file = output_dir / "mpi_scaling_curve.json"
    rank_file = output_dir / "rank_cache_metrics.csv"
    summary_file = output_dir / "mpi_scaling_summary.json"

    for f in [results_file, comm_file, curve_file, rank_file, summary_file]:
        if f.exists():
            evidence.artifacts.append(str(f))

    summary = _load_json_safe(summary_file)
    comm = _load_json_safe(comm_file)

    if summary:
        evidence.status = "complete"
        strategies = summary.get("strategies", {})
        evidence.key_metrics = {
            "world_size": summary.get("total_requests", 0),
            "strategies_tested": list(strategies.keys()),
        }
        for name, s in strategies.items():
            evidence.key_metrics[f"{name}_cache_hit_rate"] = s.get(
                "aggregate_cache_hit_rate", 0
            )
            evidence.key_metrics[f"{name}_wall_ms"] = s.get("total_wall_ms", 0)
            evidence.key_metrics[f"{name}_speedup"] = s.get("speedup_vs_single", 0)

        rr_wall = strategies.get("round_robin", {}).get("total_wall_ms", 0)
        ca_wall = strategies.get("cache_aware", {}).get("total_wall_ms", 0)
        if rr_wall > 0 and ca_wall > 0:
            evidence.key_metrics["cache_aware_vs_round_robin_speedup"] = round(
                rr_wall / ca_wall, 4
            )

        world = next(
            (s.get("world_size", 1) for s in strategies.values()), 1
        )
        if world <= 1:
            evidence.caveats.append(
                "Single-process execution: MPI scaling and communication "
                "metrics require multi-node cluster run."
            )
    else:
        evidence.status = "partial" if evidence.artifacts else "missing"
        evidence.caveats.append("MPI scaling summary not found.")

    return evidence


def _build_claims_summary(paths: List[PathEvidence]) -> Dict[str, Dict[str, Any]]:
    claim_map: Dict[str, Dict[str, Any]] = {
        "C1_exact_reuse_exists": {
            "status": "not_tested",
            "evidence_paths": [],
            "notes": [],
        },
        "C2_similarity_reuse_controllable": {
            "status": "not_tested",
            "evidence_paths": [],
            "notes": [],
        },
        "C5_hpc_evidence": {
            "status": "not_tested",
            "evidence_paths": [],
            "notes": [],
        },
        "C7_traces_slm_ready": {
            "status": "not_tested",
            "evidence_paths": [],
            "notes": [],
        },
    }

    for p in paths:
        for claim_id in p.claims_addressed:
            if claim_id not in claim_map:
                continue
            claim_map[claim_id]["evidence_paths"].append(p.path_id)

            if p.status == "complete":
                if claim_id == "C1_exact_reuse_exists":
                    hr = p.key_metrics.get("overall_hit_rate", 0)
                    if hr > 0:
                        claim_map[claim_id]["status"] = "supported"
                        claim_map[claim_id]["notes"].append(
                            f"Circuit-level reuse hit rate: {hr:.3f}"
                        )
                elif claim_id == "C2_similarity_reuse_controllable":
                    shr = p.key_metrics.get("structural_hit_rate", 0)
                    if shr > 0:
                        claim_map[claim_id]["status"] = "supported"
                        claim_map[claim_id]["notes"].append(
                            f"Structural similarity hit rate: {shr:.3f}"
                        )
                elif claim_id == "C5_hpc_evidence":
                    strats = p.key_metrics.get("strategies_tested", [])
                    if len(strats) > 1:
                        claim_map[claim_id]["status"] = "partially_supported"
                        claim_map[claim_id]["notes"].append(
                            f"Strategies tested: {strats}"
                        )
                    for c in p.caveats:
                        claim_map[claim_id]["notes"].append(f"Caveat: {c}")
                elif claim_id == "C7_traces_slm_ready":
                    cv_auc = p.key_metrics.get("cv_mean_auc_roc", 0)
                    if cv_auc > 0.5:
                        claim_map[claim_id]["status"] = "supported"
                        claim_map[claim_id]["notes"].append(
                            f"SLM trained with CV AUC-ROC: {cv_auc:.3f}"
                        )
                    else:
                        claim_map[claim_id]["status"] = "partially_supported"
                        claim_map[claim_id]["notes"].append(
                            "Model trained but AUC-ROC below threshold."
                        )

    return claim_map


def compose_unified_bundle(
    pandora_output_dir: Path,
    slm_output_dir: Path,
    mpi_output_dir: Path,
    bundle_output_dir: Path,
) -> Path:
    """Compose all three research paths into a single evidence bundle."""
    bundle_output_dir.mkdir(parents=True, exist_ok=True)

    pandora = _collect_pandora_evidence(pandora_output_dir)
    slm = _collect_slm_evidence(slm_output_dir)
    mpi = _collect_mpi_evidence(mpi_output_dir)

    paths = [pandora, slm, mpi]
    claims = _build_claims_summary(paths)

    contributions: List[str] = []
    if pandora.status == "complete" and pandora.key_metrics.get("structural_hit_rate", 0) > 0:
        contributions.append(
            "Circuit-level structural similarity caching reduces compilation "
            "overhead for repeated quantum finance workloads."
        )
    if slm.status == "complete":
        contributions.append(
            "Supervised ML model (gradient boosted trees) trained on cache "
            "trace data demonstrates feasibility of AI-assisted reuse policy."
        )
    if mpi.status == "complete":
        contributions.append(
            "Cache-aware MPI workload distribution strategy implemented and "
            "validated; ready for multi-node scaling measurement on BigRed200."
        )

    next_steps: List[str] = []
    for p in paths:
        next_steps.extend(p.caveats)
    next_steps.append("Run all three paths at standard/heavy scale on BigRed200.")
    next_steps.append("Compose final paper with unified evidence from cluster runs.")

    bundle = UnifiedBundle(
        generated_utc=datetime.now(timezone.utc).isoformat(),
        paths=[p.__dict__ for p in paths],
        claims_summary=claims,
        combined_novel_contributions=contributions,
        next_steps=next_steps,
    )

    bundle_path = bundle_output_dir / "research_evidence_bundle.json"
    bundle_path.write_text(json.dumps(bundle.__dict__, indent=2, default=str))

    return bundle_path
