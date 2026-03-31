"""SLM-oriented feature/label export schema.

Produces clean, structured datasets that can feed future SLM/ML pipelines for:
- workload classification
- cacheability prediction
- reuse-policy recommendation
- failure explanation
- regime-conditioned reuse reasoning
- HPC scheduling suggestion

Outputs are standardized CSV/JSONL with provenance fields.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


SLM_FEATURE_SCHEMA = [
    "workload_id",
    "workload_family",
    "workload_regime",
    "lane_id",
    "engine_name",
    "reuse_candidate_type",
    "exact_match_flag",
    "similarity_candidate_available",
    "similarity_score",
    "acceptance_decision",
    "locality_score",
    "reuse_distance",
    "working_set_size",
    "policy_decision",
    "policy_tier",
    "ground_truth_cacheability_label",
    "error_if_reused",
    "latency_saved_ms",
    "utility_score",
    "failure_reason",
    "epistemic_status",
    "data_source_status",
    "regime_tags",
    "portfolio_overlap_score",
    "event_overlap_score",
    "path_ladder_position",
    "feature_vector_summary",
    "validation_required",
    "recomputation_executed",
    "validation_pass",
    "validation_absolute_error",
    "validation_relative_error",
    "tolerance_profile",
    "S0",
    "K",
    "sigma",
    "T",
    "r",
    "num_paths",
    "pricing_compute_time_ms",
    "cache_hit",
    "similarity_hit",
    "parameter_hash",
    "feature_hash",
    "cluster_id",
    "decision_overhead_ms",
    "gross_runtime_saved_ms",
    "net_runtime_saved_ms",
    "net_utility_label",
    "run_label",
    "run_seed",
    "execution_host",
    "backend_name",
    "risk_note",
]


def build_slm_record(
    row: Dict[str, Any],
    *,
    cacheability_label: str = "",
    utility_score: float = 0.0,
    failure_reason: str = "",
    policy_decision: str = "",
    policy_tier: str = "exact_only",
    regime_tag: str = "",
    portfolio_overlap: float = 0.0,
    event_overlap: float = 0.0,
    locality_score: float = 0.0,
    run_label: str = "",
    run_seed: int = 0,
    execution_host: str = "",
    backend_name: str = "",
    validation_info: Optional[Dict[str, Any]] = None,
    overhead_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build one SLM training record from a result row plus enrichment fields."""
    vi = validation_info or {}
    oi = overhead_info or {}
    has_sim_group = bool(row.get("similarity_group_id"))
    is_hit = bool(row.get("cache_hit") or row.get("similarity_hit"))

    return {
        "workload_id": str(row.get("request_id", "")),
        "workload_family": str(row.get("workload_family", "")),
        "workload_regime": regime_tag or str(row.get("workload_regime", "")),
        "lane_id": str(row.get("lane_id", "")),
        "engine_name": str(row.get("engine", "")),
        "reuse_candidate_type": "exact" if row.get("cache_hit") else (
            "similarity" if row.get("similarity_hit") else "none"
        ),
        "exact_match_flag": bool(row.get("cache_hit", False)),
        "similarity_candidate_available": has_sim_group,
        "similarity_score": float(row.get("similarity_score", 0.0)),
        "acceptance_decision": "accepted" if is_hit else ("rejected" if has_sim_group else "no_candidate"),
        "locality_score": locality_score,
        "reuse_distance": float(row.get("reuse_distance_events", float("nan"))),
        "working_set_size": int(row.get("working_set_size", 0)),
        "policy_decision": policy_decision,
        "policy_tier": policy_tier,
        "ground_truth_cacheability_label": cacheability_label,
        "error_if_reused": float(row.get("estimated_price_deviation", 0.0)),
        "latency_saved_ms": float(row.get("time_saved_proxy", 0.0)),
        "utility_score": utility_score,
        "failure_reason": failure_reason,
        "epistemic_status": str(row.get("epistemic_status", "derived")),
        "data_source_status": "synthetic",
        "regime_tags": regime_tag,
        "portfolio_overlap_score": portfolio_overlap,
        "event_overlap_score": event_overlap,
        "path_ladder_position": int(row.get("path_ladder_position", 0)),
        "feature_vector_summary": str(row.get("feature_hash", "")),
        "validation_required": bool(vi.get("validation_required", False)),
        "recomputation_executed": bool(vi.get("recomputation_executed", False)),
        "validation_pass": bool(vi.get("tolerance_pass", False)) if vi else False,
        "validation_absolute_error": float(vi.get("absolute_error", 0.0)),
        "validation_relative_error": float(vi.get("relative_error", 0.0)),
        "tolerance_profile": str(vi.get("tolerance_profile", "default")),
        "S0": float(row.get("S0", 0.0)),
        "K": float(row.get("K", 0.0)),
        "sigma": float(row.get("sigma", 0.0)),
        "T": float(row.get("T", 0.0)),
        "r": float(row.get("r", 0.0)),
        "num_paths": int(row.get("num_paths", 0)),
        "pricing_compute_time_ms": float(row.get("pricing_compute_time_ms", 0.0)),
        "cache_hit": bool(row.get("cache_hit", False)),
        "similarity_hit": bool(row.get("similarity_hit", False)),
        "parameter_hash": str(row.get("parameter_hash", "")),
        "feature_hash": str(row.get("feature_hash", "")),
        "cluster_id": str(row.get("cluster_id", "")),
        "decision_overhead_ms": float(oi.get("decision_overhead_ms", 0.0)),
        "gross_runtime_saved_ms": float(oi.get("gross_runtime_saved_ms", 0.0)),
        "net_runtime_saved_ms": float(oi.get("net_runtime_saved_ms", 0.0)),
        "net_utility_label": str(oi.get("net_utility_label", "")),
        "run_label": run_label,
        "run_seed": run_seed,
        "execution_host": execution_host,
        "backend_name": backend_name,
        "risk_note": "",
    }


def export_slm_dataset(
    result_rows: Sequence[Dict[str, Any]],
    output_dir: Path,
    *,
    cacheability_assignments: Optional[Sequence[Dict[str, Any]]] = None,
    utility_rows: Optional[Sequence[Dict[str, Any]]] = None,
    validation_results: Optional[Sequence[Dict[str, Any]]] = None,
    overhead_rows: Optional[Sequence[Dict[str, Any]]] = None,
    run_label: str = "",
    run_seed: int = 0,
    execution_host: str = "",
    backend_name: str = "",
) -> Dict[str, str]:
    """Export SLM-ready datasets in CSV and JSONL formats."""
    output_dir.mkdir(parents=True, exist_ok=True)

    label_map: Dict[str, str] = {}
    failure_map: Dict[str, str] = {}
    if cacheability_assignments:
        for a in cacheability_assignments:
            rid = str(a.get("request_id", ""))
            label_map[rid] = str(a.get("ground_truth_cacheability_label", ""))
            failure_map[rid] = str(a.get("failure_reason", ""))

    utility_map: Dict[str, Dict[str, Any]] = {}
    if utility_rows:
        for u in utility_rows:
            rid = str(u.get("request_id", ""))
            utility_map[rid] = u

    val_map: Dict[str, Dict[str, Any]] = {}
    if validation_results:
        for v in validation_results:
            rid = str(v.get("request_id", ""))
            val_map[rid] = {
                "validation_required": True,
                "recomputation_executed": True,
                "tolerance_pass": v.get("tolerance_pass", False),
                "absolute_error": v.get("absolute_error", 0.0),
                "relative_error": v.get("relative_error", 0.0),
                "tolerance_profile": "default",
            }

    overhead_map: Dict[str, Dict[str, Any]] = {}
    if overhead_rows:
        for o in overhead_rows:
            rid = str(o.get("request_id", ""))
            overhead_map[rid] = o

    records: List[Dict[str, Any]] = []
    for row in result_rows:
        rid = str(row.get("request_id", ""))
        u_row = utility_map.get(rid, {})

        record = build_slm_record(
            row,
            cacheability_label=label_map.get(rid, "undetermined"),
            utility_score=float(u_row.get("utility_score", 0.0)),
            failure_reason=failure_map.get(rid, ""),
            policy_decision=str(u_row.get("policy_decision", "")),
            policy_tier=str(u_row.get("policy_tier", "exact_only")),
            run_label=run_label,
            run_seed=run_seed,
            execution_host=execution_host,
            backend_name=backend_name,
            validation_info=val_map.get(rid),
            overhead_info=overhead_map.get(rid),
        )
        records.append(record)

    jsonl_path = output_dir / "slm_training_examples.jsonl"
    with open(jsonl_path, "w") as f:
        for rec in records:
            f.write(json.dumps(rec, default=str) + "\n")

    csv_path = output_dir / "reuse_decision_dataset.csv"
    if records:
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=SLM_FEATURE_SCHEMA, extrasaction="ignore")
            writer.writeheader()
            for rec in records:
                writer.writerow(rec)

    family_csv_path = output_dir / "workload_family_dataset.csv"
    _export_family_dataset(records, family_csv_path)

    labels_csv_path = output_dir / "cacheability_labels.csv"
    _export_cacheability_labels(records, labels_csv_path)

    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "record_count": len(records),
        "schema_version": "1.0",
        "feature_count": len(SLM_FEATURE_SCHEMA),
        "files": {
            "training_jsonl": str(jsonl_path),
            "reuse_decision_csv": str(csv_path),
            "family_csv": str(family_csv_path),
            "cacheability_labels_csv": str(labels_csv_path),
        },
    }

    manifest_path = output_dir / "slm_export_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    return {
        "slm_training_jsonl": str(jsonl_path),
        "reuse_decision_csv": str(csv_path),
        "workload_family_csv": str(family_csv_path),
        "cacheability_labels_csv": str(labels_csv_path),
        "manifest": str(manifest_path),
    }


def _export_family_dataset(records: List[Dict[str, Any]], path: Path) -> None:
    """Per-family aggregate dataset."""
    from collections import defaultdict
    by_family: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in records:
        by_family[r.get("workload_family", "unknown")].append(r)

    family_fields = [
        "workload_family", "count", "exact_hit_rate", "similarity_hit_rate",
        "mean_utility", "mean_latency_saved_ms", "unique_fraction",
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=family_fields)
        writer.writeheader()
        for fam, rows in sorted(by_family.items()):
            n = len(rows)
            exact_hits = sum(1 for r in rows if r.get("exact_match_flag"))
            sim_hits = sum(1 for r in rows if r.get("similarity_hit"))
            mean_util = sum(float(r.get("utility_score", 0)) for r in rows) / n if n > 0 else 0.0
            mean_lat = sum(float(r.get("latency_saved_ms", 0)) for r in rows) / n if n > 0 else 0.0
            unique = sum(1 for r in rows if r.get("ground_truth_cacheability_label") == "unique_first_access")

            writer.writerow({
                "workload_family": fam,
                "count": n,
                "exact_hit_rate": round(exact_hits / n, 6) if n > 0 else 0.0,
                "similarity_hit_rate": round(sim_hits / n, 6) if n > 0 else 0.0,
                "mean_utility": round(mean_util, 4),
                "mean_latency_saved_ms": round(mean_lat, 4),
                "unique_fraction": round(unique / n, 6) if n > 0 else 0.0,
            })


def _export_cacheability_labels(records: List[Dict[str, Any]], path: Path) -> None:
    """Cacheability labels dataset."""
    label_fields = [
        "workload_id", "workload_family", "ground_truth_cacheability_label",
        "failure_reason", "cache_hit", "similarity_hit", "epistemic_status",
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=label_fields, extrasaction="ignore")
        writer.writeheader()
        for r in records:
            writer.writerow(r)
