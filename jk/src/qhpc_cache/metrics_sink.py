"""Append-only CSV metrics sink for continuous runtime, cache, agent, and experiment tracking.

Each sink writes a header on first open, then appends rows atomically.  Safe for
single-process sequential stages (not concurrent).  Files live under
``QHPC_METRICS_DIR`` (default ``outputs/metrics/``).
"""

from __future__ import annotations

import csv
import os
import time
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


def _metrics_dir() -> Path:
    return Path(os.environ.get("QHPC_METRICS_DIR", "outputs/metrics"))


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ── Row schemas ──────────────────────────────────────────────────────

@dataclass
class RuntimeMetricRow:
    timestamp: str = ""
    run_id: str = ""
    stage: str = ""
    agent: str = ""
    task_id: str = ""
    duration_seconds: float = 0.0
    status: str = "ok"
    records_processed: int = 0
    symbols_processed: int = 0
    experiments_completed: int = 0
    cache_hits: int = 0
    cache_near_hits: int = 0
    cache_misses: int = 0
    estimated_time_saved: float = 0.0
    output_path: str = ""
    backend_name: str = "cpu_local"
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = _utc_now_iso()


@dataclass
class CacheMetricRow:
    timestamp: str = ""
    run_id: str = ""
    policy_name: str = ""
    exact_hits: int = 0
    similarity_hits: int = 0
    misses: int = 0
    evictions: int = 0
    reuse_distance_mean: float = 0.0
    locality_score: float = 0.0
    estimated_compute_avoided_seconds: float = 0.0
    cache_efficiency: float = 0.0
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = _utc_now_iso()


@dataclass
class AgentMetricRow:
    timestamp: str = ""
    run_id: str = ""
    agent_name: str = ""
    task_id: str = ""
    duration_seconds: float = 0.0
    status: str = "ok"
    artifacts_produced: int = 0
    retries: int = 0
    degraded: bool = False
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = _utc_now_iso()


@dataclass
class WorkloadCacheObservationRow:
    """Per–workload-family cache snapshot (finance workload research)."""

    timestamp: str = ""
    run_id: str = ""
    workload_family: str = ""
    workload_spine_id: str = ""
    workload_spine_rank: int = 0  # 1–4 = locked spine; 0 = unknown / custom
    portfolio_family: str = ""
    model_family: str = ""
    pipeline_stage: str = ""
    feature_dim_before: int = 0
    feature_dim_after: int = 0
    exact_hit_rate: float = 0.0
    similarity_hit_rate: float = 0.0
    miss_rate: float = 0.0
    rolling_locality_score: float = 0.0
    reuse_distance_approx: float = -1.0
    working_set_pressure: float = 0.0
    cache_efficiency_workload: float = 0.0
    event_window_stress_flag: bool = False
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = _utc_now_iso()


@dataclass
class SpinePipelineObservationRow:
    """Structured observability for spine phases (event alignment, feature panels, …)."""

    timestamp: str = ""
    run_id: str = ""
    workload_spine_id: str = ""
    workload_spine_rank: int = 0
    pipeline_phase: str = ""  # event_alignment | feature_panel | …
    source_datasets: str = ""
    row_count_primary: int = 0
    row_count_after_join: int = 0
    join_width_estimate: int = 0
    feature_dim_before: int = 0
    feature_dim_after: int = 0
    event_window_seconds: int = 0
    alignment_match_rate: float = -1.0
    reuse_alignment_opportunities: int = 0
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = _utc_now_iso()


@dataclass
class ExperimentMetricRow:
    timestamp: str = ""
    run_id: str = ""
    experiment_id: str = ""
    parameter_hash: str = ""
    simulation_count: int = 0
    seed: int = 0
    wall_clock_seconds: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    output_path: str = ""
    backend_name: str = "cpu_local"
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = _utc_now_iso()


# ── Generic CSV writer ───────────────────────────────────────────────

def _field_names(row_cls: type) -> List[str]:
    return [f.name for f in fields(row_cls)]


def append_metric_row(filename: str, row: Any) -> Path:
    """Append a dataclass row to ``<metrics_dir>/<filename>``.  Creates the file
    with a header if it does not yet exist."""
    directory = _metrics_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    names = _field_names(type(row))
    write_header = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=names)
        if write_header:
            writer.writeheader()
        writer.writerow(asdict(row))
    return path


# ── Convenience sinks ────────────────────────────────────────────────

def log_runtime(row: RuntimeMetricRow) -> Path:
    return append_metric_row("runtime_metrics.csv", row)

def log_cache(row: CacheMetricRow) -> Path:
    return append_metric_row("cache_metrics.csv", row)

def log_agent(row: AgentMetricRow) -> Path:
    return append_metric_row("agent_metrics.csv", row)

def log_experiment(row: ExperimentMetricRow) -> Path:
    return append_metric_row("experiment_metrics.csv", row)


def log_workload_cache(row: WorkloadCacheObservationRow) -> Path:
    return append_metric_row("workload_cache_observations.csv", row)


def log_spine_pipeline(row: SpinePipelineObservationRow) -> Path:
    return append_metric_row("spine_pipeline_observations.csv", row)


# ── Timer context manager ────────────────────────────────────────────

class StageTimer:
    """Measure wall-clock time for a pipeline stage and auto-log a RuntimeMetricRow."""

    def __init__(
        self,
        *,
        run_id: str = "",
        stage: str = "",
        agent: str = "",
        task_id: str = "",
        backend_name: str = "cpu_local",
    ) -> None:
        self.run_id = run_id
        self.stage = stage
        self.agent = agent
        self.task_id = task_id
        self.backend_name = backend_name
        self._start: float = 0.0
        self.elapsed: float = 0.0
        self.row: Optional[RuntimeMetricRow] = None

    def __enter__(self) -> "StageTimer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.elapsed = time.perf_counter() - self._start
        self.row = RuntimeMetricRow(
            run_id=self.run_id,
            stage=self.stage,
            agent=self.agent,
            task_id=self.task_id,
            duration_seconds=round(self.elapsed, 4),
            status="ok" if exc_type is None else "error",
            backend_name=self.backend_name,
            notes=str(exc_val)[:200] if exc_val else "",
        )
        log_runtime(self.row)
