"""Helpers for deterministic output-run resolution and latest-run forensics."""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _sorted_by_mtime(paths: Iterable[Path]) -> List[Path]:
    return sorted(
        list(paths),
        key=lambda p: (p.stat().st_mtime_ns, p.name),
        reverse=True,
    )


def list_output_runs(output_root: str | Path = "outputs") -> List[Path]:
    """Return run directories sorted by mtime (newest first)."""
    root = Path(output_root)
    if not root.exists() or not root.is_dir():
        return []
    candidates = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        if child.name.startswith("Output_") or (child / "run_manifest.json").exists():
            candidates.append(child)
    return _sorted_by_mtime(candidates)


def resolve_latest_output_run(output_root: str | Path = "outputs") -> Optional[Path]:
    """Resolve latest run directory by filesystem mtime, not lexical order."""
    runs = list_output_runs(output_root)
    if not runs:
        return None
    return runs[0]


def load_latest_run_manifest(output_root: str | Path = "outputs") -> Dict[str, Any]:
    """Load ``run_manifest.json`` for the latest run (empty dict if missing)."""
    run_root = resolve_latest_output_run(output_root)
    if run_root is None:
        return {}
    manifest_path = run_root / "run_manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def find_latest_qmc_artifacts(output_root: str | Path = "outputs") -> Dict[str, Any]:
    """Return canonical QMC artifact paths for the latest run."""
    run_root = resolve_latest_output_run(output_root)
    if run_root is None:
        return {"run_root": None, "exists": False}
    qmc_dir = run_root / "qmc_simulation"
    paths = {
        "run_root": str(run_root.resolve()),
        "qmc_dir": str(qmc_dir.resolve()),
        "run_manifest": str((run_root / "run_manifest.json").resolve()),
        "qmc_run_summary": str((qmc_dir / "qmc_run_summary.json").resolve()),
        "cache_access_log": str((qmc_dir / "cache_access_log.csv").resolve()),
        "feature_condensation_csv": str((qmc_dir / "qmc_feature_condensation.csv").resolve()),
        "trace_engine_summary": str((qmc_dir / "trace" / "trace_engine_summary.csv").resolve()),
        "exists": True,
    }
    paths["exists_map"] = {
        key: Path(value).exists()
        for key, value in paths.items()
        if key not in {"run_root", "qmc_dir", "exists", "exists_map"}
    }
    return paths


def _read_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="") as handle:
        return list(csv.DictReader(handle))


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _collect_evidence_nodes(node: Any, path: str, out: List[Dict[str, Any]]) -> None:
    if isinstance(node, dict):
        if (
            "execution_status" in node
            or "evidence_valid" in node
            or "excluded_from_summary" in node
            or "exclusion_reason" in node
        ):
            out.append(
                {
                    "path": path,
                    "execution_status": node.get("execution_status"),
                    "evidence_valid": node.get("evidence_valid"),
                    "excluded_from_summary": node.get("excluded_from_summary"),
                    "exclusion_reason": node.get("exclusion_reason"),
                }
            )
        for key, value in node.items():
            child_path = f"{path}.{key}" if path else str(key)
            _collect_evidence_nodes(value, child_path, out)
    elif isinstance(node, list):
        for idx, item in enumerate(node):
            child_path = f"{path}[{idx}]"
            _collect_evidence_nodes(item, child_path, out)


def _build_evidence_summary(run_root: Path) -> Dict[str, Any]:
    evidence_nodes: List[Dict[str, Any]] = []
    for json_path in run_root.rglob("*.json"):
        payload = _load_json(json_path)
        if payload:
            _collect_evidence_nodes(payload, json_path.relative_to(run_root).as_posix(), evidence_nodes)

    excluded = [n for n in evidence_nodes if n.get("excluded_from_summary") is True]
    exclusion_counts = Counter(str(n.get("exclusion_reason") or "unspecified") for n in excluded)

    return {
        "evidence_nodes_count": len(evidence_nodes),
        "valid_nodes_count": sum(1 for n in evidence_nodes if n.get("evidence_valid") is True),
        "excluded_nodes_count": len(excluded),
        "excluded_reason_counts": dict(sorted(exclusion_counts.items())),
        "excluded_nodes": excluded[:25],
    }


def build_run_forensics_summary(
    run_root: str | Path,
    *,
    outlier_threshold_ms: float = 60_000.0,
) -> Dict[str, Any]:
    """Build forensic summary for one run directory."""
    root = Path(run_root)
    run_manifest = _load_json(root / "run_manifest.json")
    qmc_summary_path = root / "qmc_simulation" / "qmc_run_summary.json"
    qmc_summary = _load_json(qmc_summary_path)

    qmc_dir = root / "qmc_simulation"
    cache_log_path = qmc_dir / "cache_access_log.csv"
    feature_csv_path = qmc_dir / "qmc_feature_condensation.csv"
    trace_engine_summary_path = qmc_dir / "trace" / "trace_engine_summary.csv"

    cache_rows = _read_csv_rows(cache_log_path)
    feature_rows = _read_csv_rows(feature_csv_path)
    trace_engine_rows = _read_csv_rows(trace_engine_summary_path)

    outlier_rows = []
    semantics_missing = 0
    for row in cache_rows:
        semantics = str(row.get("row_semantics", "")).strip()
        if not semantics:
            semantics_missing += 1
        # Per-call compute outliers should only be evaluated on explicit put rows.
        if semantics and semantics != "put_single_compute_result":
            continue
        compute_ms = _safe_float(
            row.get("pricing_compute_time_ms", row.get("compute_time_ms")),
            default=0.0,
        )
        if compute_ms >= outlier_threshold_ms:
            outlier_rows.append(
                {
                    "timestamp": row.get("timestamp"),
                    "key_hash": row.get("key_hash"),
                    "engine_name": row.get("engine_name"),
                    "pricing_compute_time_ms": compute_ms,
                    "row_semantics": semantics or "missing",
                }
            )

    condensation = qmc_summary.get("feature_condensation")
    if not condensation:
        if feature_rows:
            last = feature_rows[-1]
            condensation = {
                "condensation_status": last.get("condensation_status", "unknown"),
                "condensation_reason": last.get("condensation_reason", ""),
                "input_row_count": int(_safe_float(last.get("input_row_count"), 0)),
                "input_feature_dim": int(_safe_float(last.get("input_feature_dim"), 0)),
                "output_row_count": int(_safe_float(last.get("output_row_count"), 0)),
                "output_feature_dim": int(_safe_float(last.get("output_feature_dim"), 0)),
            }
        else:
            condensation = {
                "condensation_status": "missing",
                "condensation_reason": "qmc_feature_condensation.csv not found",
                "input_row_count": 0,
                "input_feature_dim": 0,
                "output_row_count": 0,
                "output_feature_dim": 0,
            }

    pmu_real = any(str(r.get("pmu_supported", "")).lower() == "true" for r in trace_engine_rows)
    pmu_status = qmc_summary.get("pmu_observability", {})
    if not pmu_status:
        pmu_status = {
            "measurement_status": "hardware_counter_measured" if pmu_real else "proxy_or_unavailable",
            "pmu_supported_any_engine": pmu_real,
            "note": (
                "PMU-like fields are proxy/derived unless backend reports hardware counter support."
                if not pmu_real
                else "At least one engine reported PMU hardware support."
            ),
        }

    backend_execution = qmc_summary.get("backend_execution", {})
    if not backend_execution:
        backend_execution = {
            "requested_backend": run_manifest.get("requested_backend", "cpu_local"),
            "executed_backend": run_manifest.get("executed_backend", "cpu_local"),
            "execution_environment": run_manifest.get("execution_environment", "local"),
            "execution_mode_intent": run_manifest.get("execution_mode_intent", "cpu_single_node"),
            "execution_mode_actual": run_manifest.get("execution_mode_actual", "cpu_single_node"),
            "slurm_job_manifest_path": run_manifest.get("slurm_job_manifest_path", ""),
            "hpc_ready": bool(run_manifest.get("hpc_ready", False)),
            "mpi_ready": bool(run_manifest.get("mpi_ready", False)),
            "gpu_ready": bool(run_manifest.get("gpu_ready", False)),
            "execution_deferred_to_hpc": bool(run_manifest.get("execution_deferred_to_hpc", False)),
        }

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "resolved_latest_run": {
            "run_id": run_manifest.get("run_id", ""),
            "run_root": str(root.resolve()),
            "mtime_epoch_seconds": root.stat().st_mtime,
        },
        "qmc_artifacts": {
            "qmc_run_summary_exists": qmc_summary_path.exists(),
            "cache_access_log_exists": cache_log_path.exists(),
            "feature_condensation_csv_exists": feature_csv_path.exists(),
            "trace_engine_summary_exists": trace_engine_summary_path.exists(),
        },
        "feature_condensation": condensation,
        "cache_log_forensics": {
            "row_count": len(cache_rows),
            "row_semantics_missing_count": semantics_missing,
            "outlier_threshold_ms": float(outlier_threshold_ms),
            "suspicious_outlier_count": len(outlier_rows),
            "suspicious_outliers": outlier_rows[:50],
        },
        "pmu_observability": pmu_status,
        "backend_execution": backend_execution,
        "cache_experiment_evidence": _build_evidence_summary(root),
    }


def _render_summary_markdown(summary: Dict[str, Any]) -> str:
    run_info = summary.get("resolved_latest_run", {})
    cond = summary.get("feature_condensation", {})
    cache_fx = summary.get("cache_log_forensics", {})
    pmu = summary.get("pmu_observability", {})
    backend = summary.get("backend_execution", {})
    evidence = summary.get("cache_experiment_evidence", {})
    excluded_reasons = evidence.get("excluded_reason_counts", {})

    lines = [
        "# Latest run forensics summary",
        "",
        f"- run_root: `{run_info.get('run_root', '')}`",
        f"- run_id: `{run_info.get('run_id', '')}`",
        f"- generated_at_utc: `{summary.get('generated_at_utc', '')}`",
        "",
        "## Feature condensation",
        "",
        f"- status: `{cond.get('condensation_status', 'unknown')}`",
        f"- reason: `{cond.get('condensation_reason', '')}`",
        f"- input rows/dim: `{cond.get('input_row_count', 0)}` / `{cond.get('input_feature_dim', 0)}`",
        f"- output rows/dim: `{cond.get('output_row_count', 0)}` / `{cond.get('output_feature_dim', 0)}`",
        "",
        "## Cache log quality",
        "",
        f"- row_count: `{cache_fx.get('row_count', 0)}`",
        f"- row_semantics_missing_count: `{cache_fx.get('row_semantics_missing_count', 0)}`",
        f"- suspicious_outlier_count(>= {cache_fx.get('outlier_threshold_ms', 0)} ms): `{cache_fx.get('suspicious_outlier_count', 0)}`",
        "",
        "## Backend execution provenance",
        "",
        f"- requested_backend: `{backend.get('requested_backend', '')}`",
        f"- executed_backend: `{backend.get('executed_backend', '')}`",
        f"- execution_environment: `{backend.get('execution_environment', '')}`",
        f"- execution_mode_intent: `{backend.get('execution_mode_intent', '')}`",
        f"- execution_mode_actual: `{backend.get('execution_mode_actual', '')}`",
        f"- slurm_job_manifest_path: `{backend.get('slurm_job_manifest_path', '')}`",
        f"- hpc_ready / mpi_ready / gpu_ready: `{backend.get('hpc_ready', False)}` / `{backend.get('mpi_ready', False)}` / `{backend.get('gpu_ready', False)}`",
        f"- execution_deferred_to_hpc: `{backend.get('execution_deferred_to_hpc', False)}`",
        "",
        "## PMU observability label",
        "",
        f"- measurement_status: `{pmu.get('measurement_status', 'unknown')}`",
        f"- note: {pmu.get('note', '')}",
        "",
        "## Evidence validity",
        "",
        f"- evidence_nodes_count: `{evidence.get('evidence_nodes_count', 0)}`",
        f"- valid_nodes_count: `{evidence.get('valid_nodes_count', 0)}`",
        f"- excluded_nodes_count: `{evidence.get('excluded_nodes_count', 0)}`",
        f"- excluded_reason_counts: `{excluded_reasons}`",
        "",
    ]
    return "\n".join(lines)


def write_run_forensics_summary(
    run_root: str | Path,
    *,
    outlier_threshold_ms: float = 60_000.0,
) -> Dict[str, str]:
    """Write JSON+Markdown forensic summary for one run."""
    root = Path(run_root)
    summary = build_run_forensics_summary(root, outlier_threshold_ms=outlier_threshold_ms)
    json_path = root / "latest_run_forensics_summary.json"
    md_path = root / "latest_run_forensics_summary.md"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    md_path.write_text(_render_summary_markdown(summary) + "\n", encoding="utf-8")
    return {
        "json": str(json_path.resolve()),
        "markdown": str(md_path.resolve()),
    }


def write_latest_run_forensics_summary(
    output_root: str | Path = "outputs",
    *,
    outlier_threshold_ms: float = 60_000.0,
) -> Dict[str, str]:
    """Resolve latest run by mtime and write forensic summary there."""
    latest = resolve_latest_output_run(output_root)
    if latest is None:
        raise FileNotFoundError(f"No output runs found in: {Path(output_root).resolve()}")
    return write_run_forensics_summary(
        latest,
        outlier_threshold_ms=outlier_threshold_ms,
    )

