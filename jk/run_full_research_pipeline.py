#!/usr/bin/env python3
"""Full research pipeline: agentic orchestration of data, cache, literature, visualization, and reporting.

Run from ``jk/``::

    PYTHONPATH=src python3 run_full_research_pipeline.py
    PYTHONPATH=src python3 run_full_research_pipeline.py --mode experiment_batch
    PYTHONPATH=src python3 run_full_research_pipeline.py --mode research_expansion
    PYTHONPATH=src python3 run_full_research_pipeline.py --mode dry_run

Modes:
  full                Run all stages end-to-end
  data_refresh        Only data ingestion and validation
  experiment_batch    Only cache and simulation experiments
  research_expansion  Only literature review and hypothesis generation
  visualization_only  Only visualization from existing data
  dry_run             Print execution plan without running
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))


def _load_dotenv(env_path: Path = ROOT / ".env") -> None:
    """Load key=value pairs from .env without requiring python-dotenv."""
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if " #" in value:
            value = value[:value.index(" #")].strip()
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()

from qhpc_cache.orchestrator import (
    AgentNode,
    LANGGRAPH_AVAILABLE,
    PipelineState,
    ResearchOrchestrator,
    RunMode,
    agent_cache_experiment,
    agent_data_ingestion,
    agent_environment_check,
    agent_literature_review,
    agent_reporting,
    agent_visualization,
    build_default_pipeline,
    build_langgraph_pipeline,
)
from qhpc_cache.metrics_sink import StageTimer, log_runtime, RuntimeMetricRow
from qhpc_cache.visualization.plot_utils import apply_research_style, ensure_output_dirs
from qhpc_cache.visualization.workflow_timeline import plot_agent_timeline, plot_backend_readiness_matrix
from qhpc_cache.visualization.cache_dashboard import plot_hit_miss_breakdown, plot_cache_efficiency_comparison
from qhpc_cache.visualization.throughput_plots import plot_stage_durations


def _section(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run qhpc_cache full research pipeline.",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=[m.value for m in RunMode],
        default=RunMode.FULL.value,
        help="Pipeline mode to execute.",
    )
    parser.add_argument(
        "--budget",
        type=float,
        default=20.0,
        help="QMC budget in minutes.",
    )
    parser.add_argument(
        "--live-dashboard",
        action="store_true",
        help="Enable live dashboard during QMC stage.",
    )
    parser.add_argument(
        "--trace-full",
        action="store_true",
        help="Enable full trace mode for QMC stage.",
    )
    parser.add_argument(
        "--no-enforce-budget",
        action="store_true",
        help="Disable QMC budget enforcement.",
    )
    parser.add_argument(
        "--output-root",
        type=str,
        default=os.environ.get("QHPC_OUTPUT_ROOT", "outputs"),
        help="Root directory for pipeline output runs.",
    )
    parser.add_argument(
        "--latest-only-summary",
        action="store_true",
        help="Do not run pipeline; resolve latest run and emit forensic summary only.",
    )
    parser.add_argument(
        "--outlier-threshold-ms",
        type=float,
        default=60_000.0,
        help="Threshold for suspicious cache compute-time outliers in forensic summary.",
    )
    parser.add_argument(
        "--requested-backend",
        type=str,
        default="cpu_local",
        choices=[
            "cpu_local",
            "slurm_bigred200",
            "bigred200_cpu_batch",
            "bigred200_mpi_batch",
            "bigred200_gpu_future",
            "mpi_placeholder",
            "cuda_placeholder",
        ],
        help="Requested execution backend intent (local default; BigRed200 modes generate submission artifacts).",
    )
    parser.add_argument(
        "--defer-execution-to-hpc",
        action="store_true",
        help="Do not execute local QMC compute; generate BigRed200 Slurm artifacts only.",
    )
    parser.add_argument("--slurm-job-name", type=str, default="qhpc_qmc", help="Slurm job-name for HPC artifacts.")
    parser.add_argument("--slurm-walltime", type=str, default="01:00:00", help="Slurm walltime (HH:MM:SS).")
    parser.add_argument("--slurm-partition", type=str, default="general", help="Slurm partition/queue.")
    parser.add_argument("--slurm-nodes", type=int, default=1, help="Slurm node count.")
    parser.add_argument("--slurm-ntasks", type=int, default=1, help="Slurm total task count.")
    parser.add_argument("--slurm-cpus-per-task", type=int, default=1, help="Slurm CPUs per task.")
    parser.add_argument("--slurm-mem", type=str, default="16G", help="Slurm memory request (e.g. 128G).")
    parser.add_argument("--slurm-output-log", type=str, default="slurm_%j.out", help="Slurm stdout path pattern.")
    parser.add_argument("--slurm-error-log", type=str, default="slurm_%j.err", help="Slurm stderr path pattern.")
    parser.add_argument("--slurm-account", type=str, default="", help="Optional Slurm account.")
    parser.add_argument("--slurm-constraint", type=str, default="", help="Optional Slurm node constraint.")
    parser.add_argument("--slurm-qos", type=str, default="", help="Optional Slurm QoS.")
    return parser


def main(argv: list[str] | None = None) -> int:
    import json as _json

    args = _build_parser().parse_args(argv)
    mode = RunMode(args.mode)

    from qhpc_cache.run_artifacts import (
        resolve_latest_output_run,
        write_latest_run_forensics_summary,
        write_run_forensics_summary,
    )

    from qhpc_cache.output_paths import create_run_output_root
    output_base = Path(args.output_root)

    if args.latest_only_summary:
        latest = resolve_latest_output_run(output_base)
        if latest is None:
            _section("Latest Run Summary")
            print(f"  [warn] no run found under: {output_base.resolve()}")
            return 0
        summary_paths = write_latest_run_forensics_summary(
            output_root=output_base,
            outlier_threshold_ms=args.outlier_threshold_ms,
        )
        _section("Latest Run Summary")
        print(f"  latest_run: {latest}")
        print(f"  forensic_json: {summary_paths['json']}")
        print(f"  forensic_md:   {summary_paths['markdown']}")
        return 0

    os.environ["QHPC_OUTPUT_ROOT"] = str(output_base)
    run_root = create_run_output_root(output_base)

    metrics_dir = run_root / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    os.environ["QHPC_METRICS_DIR"] = str(metrics_dir)

    engine = "LangGraph" if LANGGRAPH_AVAILABLE else "internal"
    _section(f"qhpc_cache Research Pipeline ({mode.value}) [{engine} engine]")
    print(f"  [output] run root: {run_root}")
    apply_research_style()

    if LANGGRAPH_AVAILABLE and mode != RunMode.DRY_RUN:
        print(f"  Using LangGraph {engine} (langgraph installed)")
        orch = build_langgraph_pipeline(mode=mode)
    else:
        orch = build_default_pipeline(mode=mode)
    orch.state.config["output_root"] = str(run_root)
    orch.state.config["data_root"] = os.environ.get("QHPC_DATA_ROOT", "data/qhpc_data")

    qmc_budget = float(args.budget)
    orch.state.config["qmc_budget_minutes"] = qmc_budget
    orch.state.config["qmc_live_dashboard"] = bool(args.live_dashboard)
    orch.state.config["qmc_trace_full"] = bool(args.trace_full)
    orch.state.config["qmc_enforce_budget"] = not bool(args.no_enforce_budget)
    orch.state.config["requested_backend"] = str(args.requested_backend)
    orch.state.config["execution_deferred_to_hpc"] = bool(args.defer_execution_to_hpc)
    orch.state.config["slurm_job_name"] = str(args.slurm_job_name)
    orch.state.config["slurm_walltime"] = str(args.slurm_walltime)
    orch.state.config["slurm_partition"] = str(args.slurm_partition)
    orch.state.config["slurm_nodes"] = int(args.slurm_nodes)
    orch.state.config["slurm_ntasks"] = int(args.slurm_ntasks)
    orch.state.config["slurm_cpus_per_task"] = int(args.slurm_cpus_per_task)
    orch.state.config["slurm_mem"] = str(args.slurm_mem)
    orch.state.config["slurm_output_log"] = str(args.slurm_output_log)
    orch.state.config["slurm_error_log"] = str(args.slurm_error_log)
    orch.state.config["slurm_account"] = str(args.slurm_account)
    orch.state.config["slurm_constraint"] = str(args.slurm_constraint)
    orch.state.config["slurm_qos"] = str(args.slurm_qos)

    run_started_at = datetime.now(timezone.utc).isoformat()

    if mode == RunMode.DRY_RUN:
        print("\n  [dry_run] Would execute these stages:")
        for node in orch._nodes:
            print(f"    - {node.name} ({node.role})")
        print(f"\n  Run root would be: {run_root}")
        print("  No work performed.")
        return 0

    stage_map = {
        RunMode.DATA_REFRESH: {"environment_check", "data_ingestion", "reporting"},
        RunMode.EXPERIMENT_BATCH: {"environment_check", "cache_experiment", "reporting"},
        RunMode.RESEARCH_EXPANSION: {"literature_review", "reporting"},
        RunMode.VISUALIZATION_ONLY: {"visualization", "reporting"},
    }
    selected = stage_map.get(mode)

    t0 = time.perf_counter()
    state = orch.run(selected_stages=selected)
    total_time = time.perf_counter() - t0

    _section("Post-Pipeline Visualization")
    figures_dir = run_root / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    agent_csv = metrics_dir / "agent_metrics.csv"
    if agent_csv.exists():
        import csv
        with agent_csv.open("r") as f:
            agent_rows = list(csv.DictReader(f))
        recent = [r for r in agent_rows if r.get("run_id", "") == state.run_id]
        if recent:
            try:
                plot_agent_timeline(recent, output_path=figures_dir / "agent_timeline.png")
                print("  [ok] agent_timeline.png")
            except Exception as exc:
                print(f"  [warn] agent timeline: {exc}")

    runtime_csv = metrics_dir / "runtime_metrics.csv"
    if runtime_csv.exists():
        try:
            plot_stage_durations(runtime_csv, output_path=figures_dir / "stage_durations.png")
            print("  [ok] stage_durations.png")
        except Exception as exc:
            print(f"  [warn] stage durations: {exc}")

    cache_summary = state.metrics.get("cache_summary", {})
    if cache_summary:
        adapted = {
            "policy_name": "qmc_combined",
            "exact_hits": cache_summary.get("hits", 0),
            "similarity_hits": 0,
            "misses": cache_summary.get("misses", 0),
            "cache_efficiency": cache_summary.get("hits", 0) / max(1, cache_summary.get("hits", 0) + cache_summary.get("misses", 0)),
            "locality_score": 0.0,
        }
        try:
            plot_hit_miss_breakdown([adapted], output_path=figures_dir / "cache_breakdown.png")
            print("  [ok] cache_breakdown.png")
            plot_cache_efficiency_comparison([adapted], output_path=figures_dir / "cache_efficiency.png")
            print("  [ok] cache_efficiency.png")
        except Exception as exc:
            print(f"  [warn] cache dashboard: {exc}")

    env_caps = state.metrics.get("environment", {})
    if env_caps:
        from qhpc_cache.backends.cpu_local import CpuLocalBackend
        from qhpc_cache.backends.cuda_placeholder import CudaPlaceholderBackend
        from qhpc_cache.backends.mpi_placeholder import MpiPlaceholderBackend
        from qhpc_cache.backends.slurm_bigred200 import SlurmBigRed200Backend
        backend_info = [b().capabilities().__dict__ for b in [CpuLocalBackend, CudaPlaceholderBackend, MpiPlaceholderBackend, SlurmBigRed200Backend]]
        try:
            plot_backend_readiness_matrix(backend_info, output_path=figures_dir / "backend_readiness.png")
            print("  [ok] backend_readiness.png")
        except Exception as exc:
            print(f"  [warn] backend readiness: {exc}")

    qmc_dir = run_root / "qmc_simulation"
    if qmc_dir.exists():
        try:
            from qhpc_cache.visualization.live_dashboard import generate_post_simulation_plots
            plots = generate_post_simulation_plots(str(qmc_dir))
            for p in plots:
                print(f"  [ok] QMC plot: {p.name}")
        except Exception as exc:
            print(f"  [warn] QMC plots: {exc}")

    # ── Manifest ──────────────────────────────────────────────────────
    run_finished_at = datetime.now(timezone.utc).isoformat()
    qmc_summary = state.metrics.get("qmc_summary", {})
    backend_exec = qmc_summary.get("backend_execution", {})
    manifest = {
        "run_id": state.run_id,
        "started_at": run_started_at,
        "finished_at": run_finished_at,
        "command_line": " ".join(sys.argv if argv is None else [sys.argv[0], *argv]),
        "output_root": str(run_root),
        "mode": mode.value,
        "trace_full_mode": orch.state.config.get("qmc_trace_full", False),
        "enforce_budget": orch.state.config.get("qmc_enforce_budget", True),
        "budget_minutes": qmc_budget,
        "latest_only_summary": False,
        "outlier_threshold_ms": float(args.outlier_threshold_ms),
        "completed_stages": sorted(state.completed_stages),
        "failed_stages": state.failed_stages if state.failed_stages else {},
        "runtime_seconds": round(total_time, 2),
        "requested_backend": backend_exec.get("requested_backend", orch.state.config.get("requested_backend", "cpu_local")),
        "executed_backend": backend_exec.get("executed_backend", "cpu_local"),
        "execution_environment": backend_exec.get("execution_environment", "local"),
        "execution_mode_intent": backend_exec.get("execution_mode_intent", "cpu_single_node"),
        "execution_mode_actual": backend_exec.get("execution_mode_actual", "cpu_single_node"),
        "slurm_job_manifest_path": backend_exec.get("slurm_job_manifest_path", ""),
        "hpc_ready": bool(backend_exec.get("hpc_ready", False)),
        "mpi_ready": bool(backend_exec.get("mpi_ready", False)),
        "gpu_ready": bool(backend_exec.get("gpu_ready", False)),
        "execution_deferred_to_hpc": bool(backend_exec.get("execution_deferred_to_hpc", False)),
    }
    artifacts_list = []
    for paths_list in state.artifacts.values():
        artifacts_list.extend(paths_list)
    manifest["artifacts_generated"] = len(artifacts_list)
    manifest_path = run_root / "run_manifest.json"
    manifest_path.write_text(_json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    forensic_paths = write_run_forensics_summary(
        run_root=run_root,
        outlier_threshold_ms=args.outlier_threshold_ms,
    )

    # ── Full-pipeline research bundle (parity with repeated-workload) ────
    try:
        from qhpc_cache.artifact_contract import ArtifactContract
        from qhpc_cache.research_honesty import build_honesty_manifest, write_honesty_manifest
        from qhpc_cache.research_claims import evaluate_claims, write_claims_manifest, ClaimStatus
        from qhpc_cache.overhead_accounting import (
            compute_overhead_accounting,
            summarize_overhead,
            write_net_utility_summary,
        )
        from qhpc_cache.speedup_bounds import compute_speedup_bounds, write_speedup_bounds
        from qhpc_cache.slm_exports import export_slm_dataset

        research_dir = run_root / "research"
        research_dir.mkdir(parents=True, exist_ok=True)
        slm_dir = run_root / "slm_datasets"
        slm_dir.mkdir(parents=True, exist_ok=True)

        contract = ArtifactContract(run_path="full_pipeline")
        env_info = state.metrics.get("environment", {})
        engines_avail = [e for e, v in env_info.get("engines", {}).items() if v.get("available")]
        engines_skip = {e: v.get("reason", "unavailable") for e, v in env_info.get("engines", {}).items() if not v.get("available")}

        total_pricings = cache_summary.get("hits", 0) + cache_summary.get("misses", 0)
        exact_hits = cache_summary.get("hits", 0)
        exact_hit_rate = exact_hits / max(1, total_pricings)

        # -- Cacheability summary (placeholder for full pipeline) --
        fp_cacheability = {
            "status": "full_pipeline_aggregate",
            "total_pricings": total_pricings,
            "cache_recall_on_reusable": exact_hit_rate,
            "note": "Full pipeline does not use workload families directly; aggregate metrics only.",
        }
        (research_dir / "cacheability_summary.json").write_text(_json.dumps(fp_cacheability, indent=2))
        contract.mark_generated("cacheability_summary")

        # -- Utility summary --
        fp_utility = {
            "status": "full_pipeline_aggregate",
            "total_pricings": total_pricings,
            "exact_hits": exact_hits,
            "misses": cache_summary.get("misses", 0),
            "total_utility": 0.0,
            "mean_utility": 0.0,
            "note": "Full pipeline utility is aggregate; per-family detail requires repeated-workload path.",
        }
        (research_dir / "utility_summary.json").write_text(_json.dumps(fp_utility, indent=2))
        contract.mark_generated("utility_summary")

        # -- Portfolio overlap --
        contract.write_skipped_placeholder(run_root, "portfolio_overlap",
            "Full pipeline does not generate portfolio-level overlap metrics")

        # -- HPC utilization --
        fp_hpc_util = {
            "total_wall_clock_ms": round(total_time * 1000, 4),
            "total_pricing_compute_ms": 0.0,
            "compute_fraction": 0.0,
            "orchestration_fraction": 1.0,
            "requested_backend": str(args.requested_backend),
            "note": "Per-request timing unavailable in full pipeline; see repeated-workload for detailed decomposition.",
        }
        (research_dir / "hpc_utilization.json").write_text(_json.dumps(fp_hpc_util, indent=2))
        contract.mark_generated("hpc_utilization")

        # -- Similarity validation --
        fp_sim_val = {
            "validation_count": 0,
            "status": "not_applicable_in_full_pipeline",
            "note": "Similarity validation requires repeated-workload path with explicit request tracking.",
        }
        (research_dir / "similarity_validation_summary.json").write_text(_json.dumps(fp_sim_val, indent=2))
        contract.mark_generated("similarity_validation_summary")
        contract.write_skipped_placeholder(run_root, "similarity_validation_examples",
            "No per-request similarity validation in full pipeline mode")

        # -- Expanded metrics --
        fp_expanded = {
            "total_pricings": total_pricings,
            "exact_hit_rate": round(exact_hit_rate, 6),
            "similarity_hit_rate": 0.0,
            "useful_hit_rate": round(exact_hit_rate, 6),
            "harmful_hit_rate": 0.0,
            "by_family": {},
            "note": "Per-family metrics unavailable in full pipeline; use repeated-workload for family-level evidence.",
        }
        (research_dir / "expanded_metrics.json").write_text(_json.dumps(fp_expanded, indent=2))
        contract.mark_generated("expanded_metrics")

        # -- Net utility summary --
        fp_overhead = {
            "total_requests": total_pricings,
            "total_overhead_ms": 0.0,
            "total_gross_saved_ms": 0.0,
            "total_net_saved_ms": 0.0,
            "net_utility_positive": False,
            "note": "Per-request overhead unavailable in full pipeline; aggregate only.",
        }
        write_net_utility_summary(fp_overhead, research_dir)
        contract.mark_generated("net_utility_summary")

        # -- Speedup bounds --
        fp_speedup = compute_speedup_bounds(
            total_wall_ms=total_time * 1000.0,
            pricing_compute_ms=0.0,
            orchestration_ms=total_time * 1000.0,
            total_pricings=total_pricings,
            exact_hit_rate=exact_hit_rate,
        )
        write_speedup_bounds(fp_speedup, research_dir)
        contract.mark_generated("speedup_bounds")

        # -- Research claims --
        fp_evidence = {
            "total_pricings": total_pricings,
            "exact_hit_rate": exact_hit_rate,
            "families_tested": [],
        }
        fp_claims = evaluate_claims(fp_evidence)
        write_claims_manifest(fp_claims, research_dir)
        contract.mark_generated("research_claims_json")
        contract.mark_generated("research_claims_md")

        # -- Research honesty --
        honesty_data = build_honesty_manifest(
            engines_available=engines_avail if engines_avail else ["classical_mc"],
            engines_skipped=engines_skip if engines_skip else {},
            requested_backend=str(args.requested_backend),
            run_label=f"full_pipeline_{mode.value}_{state.run_id[:8]}",
        )
        write_honesty_manifest(honesty_data, research_dir)
        contract.mark_generated("research_honesty_json")
        contract.mark_generated("research_honesty_md")

        # -- SLM exports (minimal for full pipeline) --
        fp_result_rows = [{
            "request_id": f"fp_{i}",
            "workload_family": "full_pipeline",
            "engine": engines_avail[0] if engines_avail else "classical_mc",
            "cache_hit": i < exact_hits,
            "similarity_hit": False,
            "pricing_compute_time_ms": 0.0,
        } for i in range(total_pricings)]

        if fp_result_rows:
            slm_paths = export_slm_dataset(
                fp_result_rows,
                slm_dir,
                run_label=f"full_pipeline_{mode.value}_{state.run_id[:8]}",
                run_seed=0,
            )
            contract.mark_generated("slm_training_jsonl")
            contract.mark_generated("reuse_decision_csv")
            contract.mark_generated("workload_family_csv")
            contract.mark_generated("cacheability_labels_csv")
            contract.mark_generated("slm_manifest")
        else:
            for aid in ("slm_training_jsonl", "reuse_decision_csv", "workload_family_csv",
                        "cacheability_labels_csv", "slm_manifest"):
                contract.write_skipped_placeholder(run_root, aid, "No pricings in this run")

        contract.write(run_root)
        manifest["artifact_contract"] = contract.summary()
        print(f"  [ok] research bundle emitted ({contract.summary()['generated']} artifacts, "
              f"{contract.summary()['skipped']} skipped)")
    except Exception as exc:
        print(f"  [warn] research bundle: {exc}")

    _section("Pipeline Summary")
    print(f"  Run ID:    {state.run_id}")
    print(f"  Mode:      {state.mode.value}")
    print(f"  Runtime:   {total_time:.2f}s")
    print(f"  Completed: {sorted(state.completed_stages)}")
    print(f"  Failed:    {state.failed_stages if state.failed_stages else '(none)'}")
    print(f"  Outputs:   {run_root}")
    print(f"  Forensics: {forensic_paths['json']}")

    all_artifacts = []
    for paths in state.artifacts.values():
        all_artifacts.extend(paths)
    if all_artifacts:
        print(f"  Artifacts: {len(all_artifacts)} files")

    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
