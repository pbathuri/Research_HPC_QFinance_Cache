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


def _parse_mode() -> RunMode:
    for arg in sys.argv[1:]:
        if arg.startswith("--mode="):
            return RunMode(arg.split("=", 1)[1])
        if arg == "--mode" and sys.argv.index(arg) + 1 < len(sys.argv):
            return RunMode(sys.argv[sys.argv.index(arg) + 1])
    return RunMode.FULL


def main() -> None:
    import json as _json

    mode = _parse_mode()

    from qhpc_cache.output_paths import create_run_output_root
    output_base = Path(os.environ.get("QHPC_OUTPUT_ROOT", "outputs"))
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

    qmc_budget = 20.0
    for arg in sys.argv[1:]:
        if arg.startswith("--budget="):
            qmc_budget = float(arg.split("=", 1)[1])
    orch.state.config["qmc_budget_minutes"] = qmc_budget
    orch.state.config["qmc_live_dashboard"] = "--live-dashboard" in sys.argv
    orch.state.config["qmc_trace_full"] = "--trace-full" in sys.argv
    orch.state.config["qmc_enforce_budget"] = "--no-enforce-budget" not in sys.argv

    run_started_at = datetime.now(timezone.utc).isoformat()

    if mode == RunMode.DRY_RUN:
        print("\n  [dry_run] Would execute these stages:")
        for node in orch._nodes:
            print(f"    - {node.name} ({node.role})")
        print(f"\n  Run root would be: {run_root}")
        print("  No work performed.")
        return

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
    manifest = {
        "run_id": state.run_id,
        "started_at": run_started_at,
        "finished_at": run_finished_at,
        "command_line": " ".join(sys.argv),
        "output_root": str(run_root),
        "mode": mode.value,
        "trace_full_mode": orch.state.config.get("qmc_trace_full", False),
        "enforce_budget": orch.state.config.get("qmc_enforce_budget", True),
        "budget_minutes": qmc_budget,
        "completed_stages": sorted(state.completed_stages),
        "failed_stages": state.failed_stages if state.failed_stages else {},
        "runtime_seconds": round(total_time, 2),
    }
    artifacts_list = []
    for paths_list in state.artifacts.values():
        artifacts_list.extend(paths_list)
    manifest["artifacts_generated"] = len(artifacts_list)
    manifest_path = run_root / "run_manifest.json"
    manifest_path.write_text(_json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    _section("Pipeline Summary")
    print(f"  Run ID:    {state.run_id}")
    print(f"  Mode:      {state.mode.value}")
    print(f"  Runtime:   {total_time:.2f}s")
    print(f"  Completed: {sorted(state.completed_stages)}")
    print(f"  Failed:    {state.failed_stages if state.failed_stages else '(none)'}")
    print(f"  Outputs:   {run_root}")

    all_artifacts = []
    for paths in state.artifacts.values():
        all_artifacts.extend(paths)
    if all_artifacts:
        print(f"  Artifacts: {len(all_artifacts)} files")

    print()


if __name__ == "__main__":
    main()
