"""HPC provenance capture and BigRed200 execution context reporting.

Detects execution environment, captures Slurm job metadata, Python/module
state, and emits structured provenance artifacts.
"""

from __future__ import annotations

import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _safe_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def detect_execution_context() -> Dict[str, Any]:
    """Detect whether running on local, login node, Slurm batch, etc."""
    slurm_job_id = _safe_env("SLURM_JOB_ID")
    slurm_array_job_id = _safe_env("SLURM_ARRAY_JOB_ID")
    slurm_array_task_id = _safe_env("SLURM_ARRAY_TASK_ID")
    slurm_partition = _safe_env("SLURM_JOB_PARTITION")
    slurm_cpus = _safe_env("SLURM_CPUS_ON_NODE")
    slurm_nodes = _safe_env("SLURM_JOB_NUM_NODES")
    slurm_nodelist = _safe_env("SLURM_JOB_NODELIST")
    slurm_cluster = _safe_env("SLURM_CLUSTER_NAME")

    hostname = platform.node()
    is_slurm = bool(slurm_job_id)
    is_bigred200 = "bigred200" in hostname.lower() or "bigred" in slurm_cluster.lower()

    if is_slurm and slurm_array_job_id:
        mode = "slurm_array_task"
    elif is_slurm:
        mode = "slurm_batch"
    elif is_bigred200:
        mode = "bigred200_login_node"
    else:
        mode = "local_workstation"

    cluster_name = ""
    if is_bigred200:
        cluster_name = "bigred200"
    elif is_slurm:
        cluster_name = slurm_cluster or "unknown_cluster"

    return {
        "execution_host": hostname,
        "cluster_name": cluster_name,
        "slurm_job_id": slurm_job_id,
        "slurm_array_job_id": slurm_array_job_id,
        "slurm_array_task_id": slurm_array_task_id,
        "slurm_partition": slurm_partition,
        "slurm_cpus_allocated": slurm_cpus,
        "slurm_nodes_allocated": slurm_nodes,
        "slurm_nodelist": slurm_nodelist,
        "physical_execution_context": mode,
        "is_slurm_job": is_slurm,
        "is_bigred200": is_bigred200,
    }


def detect_backend_execution_mode(requested_backend: str = "cpu_local") -> Dict[str, Any]:
    """Classify backend execution intent vs actual capability."""
    ctx = detect_execution_context()
    is_slurm = ctx["is_slurm_job"]

    mode_map = {
        "cpu_local": "cpu_single_node",
        "slurm_bigred200": "slurm_single_node_batch" if is_slurm else "deferred_to_hpc",
        "bigred200_cpu_batch": "slurm_single_node_batch" if is_slurm else "deferred_to_hpc",
        "bigred200_mpi_batch": "future_mpi_distributed",
        "bigred200_gpu_future": "future_gpu_distributed",
        "mpi_placeholder": "future_mpi_distributed",
        "cuda_placeholder": "future_gpu_distributed",
    }

    return {
        "backend_intent": requested_backend,
        "backend_execution_mode": mode_map.get(requested_backend, "unknown"),
        "physical_execution_context": ctx["physical_execution_context"],
        **ctx,
    }


def capture_python_environment() -> Dict[str, Any]:
    """Capture Python version, venv state, and key package availability."""
    venv = _safe_env("VIRTUAL_ENV") or _safe_env("CONDA_DEFAULT_ENV")
    return {
        "python_version": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "venv_active": bool(venv),
        "venv_path": venv,
    }


def detect_available_engines() -> Dict[str, Dict[str, Any]]:
    """Probe engine availability with reason codes."""
    engines: Dict[str, Dict[str, Any]] = {}

    engines["classical_mc"] = {"available": True, "reason": "builtin_always_available"}

    for name, module_path in [
        ("quantlib_mc", "QuantLib"),
        ("cirq_qmci", "cirq"),
        ("monaco_mc", "monaco"),
    ]:
        try:
            __import__(module_path)
            engines[name] = {"available": True, "reason": "import_succeeded"}
        except ImportError:
            engines[name] = {"available": False, "reason": "dependency_missing"}
        except Exception as exc:
            engines[name] = {"available": False, "reason": f"import_failed:{type(exc).__name__}"}

    return engines


def detect_loaded_modules() -> List[str]:
    """Best-effort detection of loaded environment modules (HPC module system)."""
    loaded = _safe_env("LOADEDMODULES")
    if loaded:
        return [m for m in loaded.split(":") if m]

    modulepath = _safe_env("MODULEPATH")
    if modulepath:
        return [f"modulepath_detected:{modulepath[:80]}"]

    return []


def build_hpc_execution_summary(
    *,
    requested_backend: str = "cpu_local",
    run_start_utc: Optional[str] = None,
    run_end_utc: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build comprehensive HPC execution summary for a run."""
    ctx = detect_execution_context()
    mode = detect_backend_execution_mode(requested_backend)
    env = capture_python_environment()
    engine_info = detect_available_engines()
    modules = detect_loaded_modules()

    available_engines = [k for k, v in engine_info.items() if v["available"]]
    unavailable_engines = {
        k: v["reason"] for k, v in engine_info.items() if not v["available"]
    }

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_start_utc": run_start_utc or "",
        "run_end_utc": run_end_utc or "",
        "execution_context": ctx,
        "backend_execution": mode,
        "python_environment": env,
        "available_engines": available_engines,
        "unavailable_engines": unavailable_engines,
        "engine_details": engine_info,
        "loaded_modules": modules,
        "cluster_specific_notes": _cluster_notes(ctx),
    }
    if extra:
        summary["extra"] = extra
    return summary


def _cluster_notes(ctx: Dict[str, Any]) -> List[str]:
    notes: List[str] = []
    if ctx.get("is_bigred200"):
        notes.append("BigRed200: IU research computing cluster, AMD EPYC nodes")
        if ctx.get("physical_execution_context") == "bigred200_login_node":
            notes.append("WARNING: Running on login node, not a compute allocation")
        if not ctx.get("slurm_job_id"):
            notes.append("No SLURM_JOB_ID detected; this may be a login-node dry run")
    if ctx.get("physical_execution_context") == "local_workstation":
        notes.append("Local execution: results are not HPC-representative for scaling claims")
    return notes


def build_hpc_provenance_fields() -> Dict[str, Any]:
    """Return flat provenance dict suitable for embedding in any output JSON."""
    ctx = detect_execution_context()
    mode = detect_backend_execution_mode()
    return {
        "execution_host": ctx["execution_host"],
        "cluster_name": ctx["cluster_name"],
        "slurm_job_id": ctx["slurm_job_id"],
        "slurm_array_job_id": ctx["slurm_array_job_id"],
        "slurm_array_task_id": ctx["slurm_array_task_id"],
        "slurm_partition": ctx["slurm_partition"],
        "slurm_cpus_allocated": ctx["slurm_cpus_allocated"],
        "slurm_nodes_allocated": ctx["slurm_nodes_allocated"],
        "backend_intent": mode["backend_intent"],
        "backend_execution_mode": mode["backend_execution_mode"],
        "physical_execution_context": ctx["physical_execution_context"],
    }


def write_hpc_execution_summary(
    output_dir: Path,
    *,
    requested_backend: str = "cpu_local",
    run_start_utc: Optional[str] = None,
    run_end_utc: Optional[str] = None,
) -> Dict[str, str]:
    """Write hpc_execution_summary.json and .md to output_dir."""
    import json

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = build_hpc_execution_summary(
        requested_backend=requested_backend,
        run_start_utc=run_start_utc,
        run_end_utc=run_end_utc,
    )

    json_path = output_dir / "hpc_execution_summary.json"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    md_path = output_dir / "hpc_execution_summary.md"
    md_path.write_text(_render_hpc_md(summary), encoding="utf-8")

    return {"json": str(json_path), "markdown": str(md_path)}


def _render_hpc_md(summary: Dict[str, Any]) -> str:
    ctx = summary.get("execution_context", {})
    be = summary.get("backend_execution", {})
    env = summary.get("python_environment", {})
    avail = summary.get("available_engines", [])
    unavail = summary.get("unavailable_engines", {})
    notes = summary.get("cluster_specific_notes", [])
    modules = summary.get("loaded_modules", [])

    lines = [
        "# HPC Execution Summary",
        "",
        f"- generated: `{summary.get('generated_at_utc', '')}`",
        f"- host: `{ctx.get('execution_host', '')}`",
        f"- cluster: `{ctx.get('cluster_name', 'none')}`",
        f"- context: `{ctx.get('physical_execution_context', '')}`",
        f"- slurm_job_id: `{ctx.get('slurm_job_id', 'n/a')}`",
        f"- partition: `{ctx.get('slurm_partition', 'n/a')}`",
        f"- cpus: `{ctx.get('slurm_cpus_allocated', 'n/a')}`",
        f"- nodes: `{ctx.get('slurm_nodes_allocated', 'n/a')}`",
        "",
        "## Backend Execution",
        "",
        f"- intent: `{be.get('backend_intent', '')}`",
        f"- mode: `{be.get('backend_execution_mode', '')}`",
        "",
        "## Python Environment",
        "",
        f"- version: `{env.get('python_version', '').split()[0] if env.get('python_version') else ''}`",
        f"- venv: `{env.get('venv_active', False)}`",
        "",
        "## Engine Availability",
        "",
        f"- available: `{', '.join(avail) if avail else 'none'}`",
    ]
    for name, reason in unavail.items():
        lines.append(f"- unavailable: `{name}` reason=`{reason}`")

    if modules:
        lines.extend(["", "## Loaded Modules", ""])
        for m in modules:
            lines.append(f"- `{m}`")

    if notes:
        lines.extend(["", "## Notes", ""])
        for n in notes:
            lines.append(f"- {n}")

    lines.append("")
    return "\n".join(lines)
