"""Map pipeline stages and workload families to cache observability rows.

Writes via ``metrics_sink.log_workload_cache`` — does not replace ``log_cache``.
"""

from __future__ import annotations

from qhpc_cache.cache_metrics import CacheResearchTracker
from qhpc_cache.metrics_sink import (
    SpinePipelineObservationRow,
    WorkloadCacheObservationRow,
    log_spine_pipeline,
    log_workload_cache,
)
from qhpc_cache.workload_signatures import (
    infer_workload_spine,
    workload_family_label,
    workload_spine_rank_for_id,
)


def record_workload_cache_snapshot(
    *,
    run_id: str,
    tracker: CacheResearchTracker,
    pipeline_stage: str,
    portfolio_family: str,
    model_family: str,
    feature_dim_before: int = 0,
    feature_dim_after: int = 0,
    event_window_stress: bool = False,
    working_set_pressure: float = 0.0,
    workload_spine_id: str = "",
    workload_spine_rank: int = 0,
    notes: str = "",
) -> None:
    """Flush a single workload-scoped observation row (CSV)."""
    s = tracker.summary()
    mrd = s.get("mean_reuse_distance")
    reuse_approx = float(mrd) if mrd is not None else -1.0
    wfl = workload_family_label(
        pipeline_stage=pipeline_stage,
        portfolio_family=portfolio_family,
        model_family=model_family,
        event_stress=event_window_stress,
    )
    spine_id, spine_rank = infer_workload_spine(pipeline_stage)
    if workload_spine_id:
        spine_id = workload_spine_id
    if workload_spine_rank:
        spine_rank = workload_spine_rank
    elif workload_spine_id:
        spine_rank = workload_spine_rank_for_id(workload_spine_id)
    row = WorkloadCacheObservationRow(
        run_id=run_id,
        workload_family=wfl,
        workload_spine_id=spine_id,
        workload_spine_rank=spine_rank,
        portfolio_family=portfolio_family,
        model_family=model_family,
        pipeline_stage=pipeline_stage,
        feature_dim_before=feature_dim_before,
        feature_dim_after=feature_dim_after,
        exact_hit_rate=s.get("exact_hit_rate", 0.0),
        similarity_hit_rate=s.get("similarity_hit_rate", 0.0),
        miss_rate=s.get("miss_rate", 0.0),
        rolling_locality_score=s.get("locality_score", 0.0),
        reuse_distance_approx=reuse_approx,
        working_set_pressure=working_set_pressure,
        cache_efficiency_workload=s.get("cache_efficiency", 0.0),
        event_window_stress_flag=event_window_stress,
        notes=notes,
    )
    log_workload_cache(row)


def record_spine_pipeline_observation(
    *,
    run_id: str,
    workload_spine_id: str,
    pipeline_phase: str,
    source_datasets: str = "",
    row_count_primary: int = 0,
    row_count_after_join: int = 0,
    join_width_estimate: int = 0,
    feature_dim_before: int = 0,
    feature_dim_after: int = 0,
    event_window_seconds: int = 0,
    alignment_match_rate: float = -1.0,
    reuse_alignment_opportunities: int = 0,
    notes: str = "",
) -> None:
    """Append a ``SpinePipelineObservationRow`` (``spine_pipeline_observations.csv``)."""
    rank = workload_spine_rank_for_id(workload_spine_id)
    row = SpinePipelineObservationRow(
        run_id=run_id,
        workload_spine_id=workload_spine_id,
        workload_spine_rank=rank,
        pipeline_phase=pipeline_phase,
        source_datasets=source_datasets,
        row_count_primary=row_count_primary,
        row_count_after_join=row_count_after_join,
        join_width_estimate=join_width_estimate,
        feature_dim_before=feature_dim_before,
        feature_dim_after=feature_dim_after,
        event_window_seconds=event_window_seconds,
        alignment_match_rate=alignment_match_rate,
        reuse_alignment_opportunities=reuse_alignment_opportunities,
        notes=notes,
    )
    log_spine_pipeline(row)


def qmc_trace_derived_pressure(trace_event_count: int, rolling_ws_64: float) -> float:
    """Heuristic pressure proxy from trace scale (0..1 scale, not physical)."""
    if trace_event_count <= 0:
        return 0.0
    return min(1.0, (rolling_ws_64 or 0) / max(1.0, trace_event_count / 10.0))
