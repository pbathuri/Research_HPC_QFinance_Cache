"""LangGraph-style stateful research orchestrator: explicit state, typed transitions, event tracing.

Uses a lightweight internal state machine when LangGraph is not installed.
If ``langgraph`` is available, the graph definition is compatible with LangGraph
StateGraph semantics.

Each agent role is a callable stage that reads shared state, does work, and
writes results back.  The supervisor routes between agents based on status flags.
"""

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Set

from qhpc_cache.metrics_sink import AgentMetricRow, StageTimer, log_agent


# ── State ────────────────────────────────────────────────────────────

class RunMode(str, Enum):
    FULL = "full"
    DATA_REFRESH = "data_refresh"
    EXPERIMENT_BATCH = "experiment_batch"
    RESEARCH_EXPANSION = "research_expansion"
    VISUALIZATION_ONLY = "visualization_only"
    DRY_RUN = "dry_run"


@dataclass
class PipelineState:
    """Shared mutable state passed through the agent graph."""
    run_id: str = ""
    mode: RunMode = RunMode.FULL
    started_at: str = ""
    backend_name: str = "cpu_local"
    config: Dict[str, Any] = field(default_factory=dict)

    completed_stages: Set[str] = field(default_factory=set)
    failed_stages: Dict[str, str] = field(default_factory=dict)
    artifacts: Dict[str, List[str]] = field(default_factory=dict)
    events: List[Any] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

    should_stop: bool = False
    checkpoint_path: str = ""

    def mark_done(self, stage: str, artifact_paths: Optional[List[str]] = None) -> None:
        self.completed_stages.add(stage)
        if artifact_paths:
            self.artifacts.setdefault(stage, []).extend(artifact_paths)

    def mark_failed(self, stage: str, reason: str) -> None:
        self.failed_stages[stage] = reason

    def is_done(self, stage: str) -> bool:
        return stage in self.completed_stages


# ── Agent definitions ────────────────────────────────────────────────

AgentFn = Callable[[PipelineState], PipelineState]


@dataclass
class AgentNode:
    """One node in the research workflow graph."""
    name: str
    role: str
    fn: AgentFn
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    can_skip: bool = True
    retry_limit: int = 1


class ResearchOrchestrator:
    """Lightweight state-machine graph executor.  Nodes run sequentially in
    registration order unless ``should_stop`` is set or a prerequisite failed."""

    def __init__(self, run_id: str = "", mode: RunMode = RunMode.FULL) -> None:
        self.run_id = run_id or datetime.now(timezone.utc).strftime("run_%Y%m%d_%H%M%S")
        self.mode = mode
        self._nodes: List[AgentNode] = []
        self._state = PipelineState(
            run_id=self.run_id,
            mode=mode,
            started_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        )

    @property
    def state(self) -> PipelineState:
        return self._state

    def add_agent(self, node: AgentNode) -> None:
        self._nodes.append(node)

    def run(self, *, selected_stages: Optional[Set[str]] = None) -> PipelineState:
        """Execute the graph.  If ``selected_stages`` is provided, only run those nodes."""
        for node in self._nodes:
            if self._state.should_stop:
                break
            if selected_stages and node.name not in selected_stages:
                continue
            if self._state.is_done(node.name):
                continue

            self._run_node(node)

        return self._state

    def _run_node(self, node: AgentNode) -> None:
        for dep in node.inputs:
            if dep not in self._state.completed_stages and dep in self._state.failed_stages:
                if not node.can_skip:
                    self._state.mark_failed(node.name, f"dependency {dep} failed")
                    return

        attempts = 0
        while attempts <= node.retry_limit:
            attempts += 1
            try:
                with StageTimer(run_id=self.run_id, stage=node.name, agent=node.role) as timer:
                    self._state = node.fn(self._state)

                log_agent(AgentMetricRow(
                    run_id=self.run_id,
                    agent_name=node.role,
                    task_id=node.name,
                    duration_seconds=round(timer.elapsed, 4),
                    status="ok" if node.name not in self._state.failed_stages else "degraded",
                    artifacts_produced=len(self._state.artifacts.get(node.name, [])),
                    retries=attempts - 1,
                ))

                if node.name not in self._state.failed_stages:
                    self._state.mark_done(node.name)
                return

            except Exception as exc:
                if attempts > node.retry_limit:
                    reason = f"{type(exc).__name__}: {exc}"
                    self._state.mark_failed(node.name, reason)
                    log_agent(AgentMetricRow(
                        run_id=self.run_id,
                        agent_name=node.role,
                        task_id=node.name,
                        duration_seconds=0.0,
                        status="error",
                        retries=attempts - 1,
                        notes=reason[:200],
                    ))
                    return


# ── Standard agent functions (thin wrappers around existing modules) ─

def agent_environment_check(state: PipelineState) -> PipelineState:
    """Validate local environment and record capabilities."""
    from qhpc_cache.backends import create_backend
    from qhpc_cache.backends.cpu_local import CpuLocalBackend
    from qhpc_cache.backends.cuda_placeholder import CudaPlaceholderBackend
    from qhpc_cache.backends.mpi_placeholder import MpiPlaceholderBackend
    from qhpc_cache.backends.slurm_bigred200 import SlurmBigRed200Backend
    from qhpc_cache.taq_kdb_adapter import kdb_backend_ready, default_kdb_taq_repo
    from qhpc_cache.data_sources import DatabentoProvider

    requested_backend = str(state.config.get("requested_backend", "cpu_local"))
    selected = create_backend(requested_backend)
    selected_cap = selected.capabilities()
    caps = {
        "cpu_local": CpuLocalBackend().capabilities().__dict__,
        "cuda": CudaPlaceholderBackend().capabilities().__dict__,
        "mpi": MpiPlaceholderBackend().capabilities().__dict__,
        "slurm_bigred200": SlurmBigRed200Backend().capabilities().__dict__,
        "requested_backend": requested_backend,
        "selected_backend_capabilities": selected_cap.__dict__,
        "databento_key": DatabentoProvider.api_key_present(),
        "kdb_ready": kdb_backend_ready()[0],
        "kdb_taq_path": str(default_kdb_taq_repo()),
    }
    state.metrics["environment"] = caps
    state.mark_done("environment_check", [])
    return state


def agent_data_ingestion(state: PipelineState) -> PipelineState:
    """Real data ingestion: Databento live pull + local TAQ scan + synthetic fallback."""
    from datetime import date as _date
    from qhpc_cache.data_ingestion import load_or_download_daily_universe
    from qhpc_cache.data_models import DailyUniverseRequest
    from qhpc_cache.data_sources import DatabentoProvider
    from qhpc_cache.data_registry import initialize_dataset_registry
    from qhpc_cache.universe_builder import build_large_us_equity_etf_universe_request
    from qhpc_cache.taq_kdb_adapter import (
        default_kdb_taq_repo, inspect_kdb_taq_repo, discover_local_taq_datasets, kdb_backend_ready,
    )
    from qhpc_cache.event_book import build_default_event_catalog, extract_event_windows_from_taq

    data_root = state.config.get("data_root", "data/qhpc_data")
    initialize_dataset_registry(data_root)

    daily_dir = str(Path(data_root) / "daily_universe")
    daily_request = build_large_us_equity_etf_universe_request(
        start_date=_date(2023, 4, 3),
        end_date=_date(2024, 12, 31),
        local_output_directory=daily_dir,
        include_reference_data=False,
    )

    has_db = DatabentoProvider.api_key_present()

    daily_result = load_or_download_daily_universe(
        daily_request, data_root,
        allow_synthetic_fallback=True,
    )
    source = daily_result.get("status", "unknown")
    state.metrics["daily_source"] = source
    state.metrics["daily_result"] = {k: v for k, v in daily_result.items() if k != "panel"}
    state.metrics["daily_symbols"] = list(daily_request.symbols)
    state.metrics["daily_batches"] = daily_result.get("batches_completed", [])

    kdb_repo = default_kdb_taq_repo()
    kdb_info = inspect_kdb_taq_repo(kdb_repo)
    kdb_ready, kdb_msg = kdb_backend_ready(kdb_repo)
    taq_discover = discover_local_taq_datasets(kdb_repo)
    state.metrics["kdb_ready"] = kdb_ready
    state.metrics["kdb_info"] = {
        "exists": kdb_info.get("exists"),
        "q_files": kdb_info.get("q_file_count", 0),
        "candidates": len(taq_discover.get("candidate_q_scripts", [])),
    }

    taq_root = str(Path(data_root) / "taq_incoming")
    event_out = str(Path(data_root) / "event_book")
    catalog = build_default_event_catalog(taq_root=taq_root, output_root=event_out)
    book = extract_event_windows_from_taq(
        catalog, data_root=data_root,
        time_budget_seconds=300, disk_budget_bytes=5 * 1024**3,
        register=True, prefer_kdb_extraction=True, kdb_repo_root=str(kdb_repo),
    )
    state.metrics["event_book"] = {
        "completed": book.completed_events, "rows": book.total_rows,
        "deferred": book.deferred_identifiers,
    }

    return state


def agent_cache_experiment(state: PipelineState) -> PipelineState:
    """Run QMC simulation with cache research tracking."""
    from qhpc_cache.qmc_simulation import run_qmc_simulation, QMCSimulationConfig

    budget = float(state.config.get("qmc_budget_minutes", 20.0))
    cfg = QMCSimulationConfig(
        budget_minutes=budget,
        output_dir=str(Path(state.config.get("output_root", "outputs")) / "qmc_simulation"),
        live_dashboard=state.config.get("qmc_live_dashboard", False),
        trace_full_mode=state.config.get("qmc_trace_full", False),
        enforce_budget=state.config.get("qmc_enforce_budget", True),
        requested_backend=str(state.config.get("requested_backend", "cpu_local")),
        execution_deferred_to_hpc=bool(state.config.get("execution_deferred_to_hpc", False)),
        slurm_job_name=str(state.config.get("slurm_job_name", "qhpc_qmc")),
        slurm_walltime=str(state.config.get("slurm_walltime", "01:00:00")),
        slurm_partition=str(state.config.get("slurm_partition", "general")),
        slurm_nodes=int(state.config.get("slurm_nodes", 1)),
        slurm_ntasks=int(state.config.get("slurm_ntasks", 1)),
        slurm_cpus_per_task=int(state.config.get("slurm_cpus_per_task", 1)),
        slurm_mem=str(state.config.get("slurm_mem", "16G")),
        slurm_output_log=str(state.config.get("slurm_output_log", "slurm_%j.out")),
        slurm_error_log=str(state.config.get("slurm_error_log", "slurm_%j.err")),
        slurm_account=str(state.config.get("slurm_account", "")),
        slurm_constraint=str(state.config.get("slurm_constraint", "")),
        slurm_qos=str(state.config.get("slurm_qos", "")),
    )

    summary = run_qmc_simulation(cfg)
    state.metrics["qmc_summary"] = summary
    state.metrics["cache_summary"] = summary.get("cache_final", {})
    all_csvs = list(summary.get("csv_files", {}).values())
    all_csvs.extend(summary.get("trace_files", {}).values())
    state.mark_done("cache_experiment", all_csvs)
    return state


def agent_literature_review(state: PipelineState) -> PipelineState:
    """Run literature expansion and export structured outputs."""
    from qhpc_cache.literature_agent import run_literature_expansion
    output_dir = Path(state.config.get("output_root", "outputs")) / "research"
    paths = run_literature_expansion(output_dir)
    state.mark_done("literature_review", list(paths.values()))
    state.metrics["literature_outputs"] = paths
    return state


def agent_visualization(state: PipelineState) -> PipelineState:
    """Generate all research visualization figures from available data."""
    import numpy as np
    from qhpc_cache.visualization.plot_utils import apply_research_style, ensure_output_dirs
    apply_research_style()
    output_root = Path(state.config.get("output_root", "outputs")) / "research_visualization"
    dirs = ensure_output_dirs(output_root)
    figures_generated: list = []

    try:
        import pandas as pd
        from qhpc_cache.config import VisualizationConfig
        cfg = VisualizationConfig()
        data_root = state.config.get("data_root", "data/qhpc_data")

        panel = None
        try:
            from qhpc_cache.data_registry import load_dataset_registry
            for entry in load_dataset_registry(data_root):
                if entry.dataset_kind == "daily_ohlcv" and entry.local_paths:
                    for p in entry.local_paths:
                        fp = Path(p)
                        if fp.exists():
                            if fp.suffix == ".parquet":
                                panel = pd.read_parquet(fp)
                            else:
                                panel = pd.read_csv(fp)
                            break
                    if panel is not None:
                        break
        except Exception:
            pass

        if panel is None:
            rng = np.random.default_rng(42)
            dates = pd.bdate_range(cfg.start_date, cfg.end_date)
            rows = []
            for sym in cfg.symbols:
                px = 100.0
                for d in dates:
                    ret = rng.normal(0.0003, 0.015)
                    px *= np.exp(ret)
                    rows.append({"date": d, "symbol": sym, "close": px,
                                 "open": px * (1 + rng.normal(0, 0.003)),
                                 "high": px * (1 + abs(rng.normal(0, 0.008))),
                                 "low": px * (1 - abs(rng.normal(0, 0.008))),
                                 "volume": int(rng.integers(500_000, 50_000_000))})
            panel = pd.DataFrame(rows)

        from qhpc_cache.historical_returns import compute_log_returns, compute_rolling_volatility
        from qhpc_cache.visualization.market_overview import (
            plot_cumulative_returns, plot_rolling_volatility, plot_correlation_heatmap,
        )
        from qhpc_cache.visualization.simulation_comparison import (
            plot_distribution_comparison, plot_qq_comparison,
        )

        pivot = panel.pivot_table(index="date", columns="symbol", values="close")
        log_ret = compute_log_returns(pivot)
        roll_vol = compute_rolling_volatility(log_ret, window=cfg.rolling_vol_window)

        cum_path = dirs["figures"] / "cumulative_returns.png"
        plot_cumulative_returns(log_ret, output_path=cum_path)
        figures_generated.append("cumulative_returns.png")

        vol_path = dirs["figures"] / "rolling_volatility.png"
        plot_rolling_volatility(roll_vol, output_path=vol_path)
        figures_generated.append("rolling_volatility.png")

        corr_path = dirs["figures"] / "correlation_heatmap.png"
        plot_correlation_heatmap(log_ret, output_path=corr_path)
        figures_generated.append("correlation_heatmap.png")

        from qhpc_cache.pricing import MonteCarloPricer
        from qhpc_cache.config import PricingConfig
        pricer = MonteCarloPricer()
        mc_cfg = PricingConfig(num_paths=cfg.mc_paths_for_sim_comparison)
        mc_prices = pricer.price_option(
            S0=mc_cfg.S0, K=mc_cfg.K, r=mc_cfg.r, sigma=mc_cfg.sigma,
            T=mc_cfg.T, num_paths=mc_cfg.num_paths, seed=cfg.mc_seed,
        )
        mc_returns = np.diff(np.log(np.maximum(mc_prices["terminal_prices"], 1e-8)))
        spy_ret = log_ret["SPY"].dropna().values if "SPY" in log_ret.columns else log_ret.iloc[:, 0].dropna().values

        dist_path = dirs["figures"] / "distribution_comparison.png"
        plot_distribution_comparison(spy_ret, mc_returns, output_path=dist_path)
        figures_generated.append("distribution_comparison.png")

        qq_path = dirs["figures"] / "qq_comparison.png"
        plot_qq_comparison(spy_ret, mc_returns, output_path=qq_path)
        figures_generated.append("qq_comparison.png")

        state.metrics["viz_data_source"] = "registry" if len(panel) > 1000 else "synthetic"

    except Exception as exc:
        state.metrics["viz_error"] = str(exc)

    state.metrics["figures_generated"] = figures_generated

    state.mark_done("visualization", [str(output_root)] + figures_generated)
    return state


def agent_reporting(state: PipelineState) -> PipelineState:
    """Generate final run report."""
    import json
    output_root = Path(state.config.get("output_root", "outputs")) / "reports"
    output_root.mkdir(parents=True, exist_ok=True)

    report = {
        "run_id": state.run_id,
        "mode": state.mode.value,
        "started_at": state.started_at,
        "completed_stages": sorted(state.completed_stages),
        "failed_stages": state.failed_stages,
        "metrics": {k: v for k, v in state.metrics.items() if not isinstance(v, (set,))},
        "artifacts": {k: v for k, v in state.artifacts.items()},
    }
    json_path = output_root / f"{state.run_id}_summary.json"
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    md_lines = [
        f"# Research Pipeline Report: {state.run_id}",
        f"\n- Mode: {state.mode.value}",
        f"- Started: {state.started_at}",
        f"- Completed: {len(state.completed_stages)} stages",
        f"- Failed: {len(state.failed_stages)} stages",
        "\n## Completed Stages",
    ]
    for s in sorted(state.completed_stages):
        md_lines.append(f"- {s}")
    if state.failed_stages:
        md_lines.append("\n## Failed Stages")
        for s, r in state.failed_stages.items():
            md_lines.append(f"- **{s}**: {r}")
    md_lines.append("\n## Next Steps")
    md_lines.append("- Slurm-first BigRed200 submission artifact path is available; MPI/CUDA runtime remains future work")
    md_lines.append("- WRDS/CRSP institutional data access pending credentials")
    md_lines.append("- Full quantum circuit execution requires hardware backend")
    md_path = output_root / f"{state.run_id}_report.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    state.mark_done("reporting", [str(json_path), str(md_path)])
    return state


def build_default_pipeline(run_id: str = "", mode: RunMode = RunMode.FULL) -> ResearchOrchestrator:
    """Wire the standard research pipeline graph."""
    orch = ResearchOrchestrator(run_id=run_id, mode=mode)

    orch.add_agent(AgentNode("environment_check", "EnvironmentAgent", agent_environment_check))
    orch.add_agent(AgentNode("data_ingestion", "DataIngestionAgent", agent_data_ingestion,
                             inputs=["environment_check"]))
    orch.add_agent(AgentNode("cache_experiment", "CacheResearchAgent", agent_cache_experiment,
                             inputs=["environment_check"]))
    orch.add_agent(AgentNode("literature_review", "LiteratureReviewAgent", agent_literature_review))
    orch.add_agent(AgentNode("visualization", "VisualizationAgent", agent_visualization,
                             inputs=["data_ingestion"]))
    orch.add_agent(AgentNode("reporting", "ReportAgent", agent_reporting,
                             inputs=["data_ingestion", "cache_experiment"]))

    return orch


# ── LangGraph native integration ────────────────────────────────────

def _langgraph_available() -> bool:
    try:
        from langgraph.graph import StateGraph  # type: ignore
        return True
    except (ImportError, AttributeError):
        return False


LANGGRAPH_AVAILABLE = _langgraph_available()


def build_langgraph_pipeline(
    run_id: str = "",
    mode: RunMode = RunMode.FULL,
) -> Any:
    """Build the research pipeline as a real LangGraph StateGraph.

    Requires ``langgraph >= 0.2``.  Each node wraps an agent function and
    mutates a shared ``PipelineState`` carried in graph state.
    Falls back to ``build_default_pipeline`` if LangGraph is not installed.
    """
    if not LANGGRAPH_AVAILABLE:
        return build_default_pipeline(run_id=run_id, mode=mode)

    from langgraph.graph import StateGraph, END  # type: ignore
    from typing import TypedDict

    class GraphState(TypedDict, total=False):
        pipeline: PipelineState

    _selected: Optional[Set[str]] = None

    def _wrap(agent_fn: AgentFn, stage_name: str, role: str) -> Callable:
        def _node(state: GraphState) -> GraphState:
            ps = state["pipeline"]
            if _selected is not None and stage_name not in _selected:
                return {"pipeline": ps}
            with StageTimer(run_id=ps.run_id, stage=stage_name, agent=role):
                try:
                    ps = agent_fn(ps)
                    ps.mark_done(stage_name)
                except Exception as exc:
                    ps.mark_failed(stage_name, f"{type(exc).__name__}: {exc}")
            log_agent(AgentMetricRow(
                run_id=ps.run_id, agent_name=role, task_id=stage_name, status="ok" if stage_name in ps.completed_stages else "error",
            ))
            return {"pipeline": ps}
        return _node

    graph = StateGraph(GraphState)

    graph.add_node("environment_check", _wrap(agent_environment_check, "environment_check", "EnvironmentAgent"))
    graph.add_node("data_ingestion", _wrap(agent_data_ingestion, "data_ingestion", "DataIngestionAgent"))
    graph.add_node("cache_experiment", _wrap(agent_cache_experiment, "cache_experiment", "CacheResearchAgent"))
    graph.add_node("literature_review", _wrap(agent_literature_review, "literature_review", "LiteratureReviewAgent"))
    graph.add_node("visualization", _wrap(agent_visualization, "visualization", "VisualizationAgent"))
    graph.add_node("reporting", _wrap(agent_reporting, "reporting", "ReportAgent"))

    graph.set_entry_point("environment_check")
    graph.add_edge("environment_check", "data_ingestion")
    graph.add_edge("data_ingestion", "cache_experiment")
    graph.add_edge("cache_experiment", "literature_review")
    graph.add_edge("literature_review", "visualization")
    graph.add_edge("visualization", "reporting")
    graph.add_edge("reporting", END)

    compiled = graph.compile()

    initial_state = PipelineState(
        run_id=run_id or datetime.now(timezone.utc).strftime("run_%Y%m%d_%H%M%S"),
        mode=mode,
        started_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )

    class LangGraphOrchestrator:
        """Wraps a compiled LangGraph for the same API as ResearchOrchestrator."""

        def __init__(self) -> None:
            self._state = initial_state
            self._compiled = compiled
            self.run_id = initial_state.run_id
            self._nodes: list = []

        @property
        def state(self) -> PipelineState:
            return self._state

        def run(self, *, selected_stages: Optional[Set[str]] = None) -> PipelineState:
            nonlocal _selected
            _selected = selected_stages
            result = self._compiled.invoke({"pipeline": self._state})
            self._state = result["pipeline"]
            _selected = None
            return self._state

    return LangGraphOrchestrator()
