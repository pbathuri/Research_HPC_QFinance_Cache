"""20-minute Quantum Monte Carlo simulation harness.

Runs a time-budgeted simulation across multiple engines, tracking cache access
patterns, feature condensation, and convergence. Outputs comprehensive CSV logs
and drives the live dashboard.

Phases:
  1. GAN data generation (~2 min)
  2. Portfolio sweep across all engines (~8 min)
  3. Convergence study at increasing path counts (~8 min)
  4. Feature condensation analysis (~2 min)
"""

from __future__ import annotations

import csv
import math
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

import numpy as np


@dataclass
class QMCSimulationConfig:
    budget_minutes: float = 20.0
    gan_epochs: int = 30
    gan_num_days: int = 500
    gan_num_assets: int = 100
    portfolio_size: int = 500
    convergence_path_counts: List[int] = field(
        default_factory=lambda: [1_000, 5_000,
                                 10_000, 50_000, 100_000, 500_000]
    )
    convergence_contracts: int = 8
    live_dashboard: bool = True
    output_dir: str = "outputs/qmc_simulation"
    seed: int = 42
    trace_full_mode: bool = False
    enforce_budget: bool = True
    trace_window_size: int = 64
    trace_stride: int = 16
    emit_visuals: bool = True
    max_trace_rows: Optional[int] = None
    max_phase_contracts: Optional[int] = None
    max_phase_convergence_contracts: Optional[int] = None
    max_pricings_total: Optional[int] = None
    engine_allowlist: Optional[List[str]] = None
    trace_output_subdir: str = "trace"
    # similarity
    enable_similarity_matching: bool = True
    similarity_method: str = "hybrid"
    similarity_threshold: float = 0.92
    similarity_max_candidates: int = 32
    similarity_signature_dims: int = 8
    similarity_bucket_bits: int = 12
    # PMU
    enable_pmu: bool = False
    pmu_backend: str = "auto"
    pmu_sample_scope: str = "engine_call"
    pmu_collect_memory: bool = True
    pmu_collect_cycles: bool = True
    pmu_collect_instructions: bool = True
    pmu_collect_cache_refs: bool = True
    pmu_collect_cache_misses: bool = True
    pmu_collect_branches: bool = False
    pmu_collect_page_faults: bool = False
    # backend / HPC intent
    requested_backend: str = "cpu_local"
    execution_mode_intent: str = ""
    execution_deferred_to_hpc: bool = False
    hpc_submission_subdir: str = "hpc_submission"
    hpc_run_command: str = ""
    slurm_job_name: str = "qhpc_qmc"
    slurm_walltime: str = "01:00:00"
    slurm_partition: str = "general"
    slurm_nodes: int = 1
    slurm_ntasks: int = 1
    slurm_cpus_per_task: int = 1
    slurm_mem: str = "16G"
    slurm_output_log: str = "slurm_%j.out"
    slurm_error_log: str = "slurm_%j.err"
    slurm_account: str = ""
    slurm_constraint: str = ""
    slurm_qos: str = ""


_DEFAULT_QMC_OUTPUT_DIR = Path("outputs/qmc_simulation")


def _is_unscoped_default_qmc_output_dir(path_str: str) -> bool:
    """True when *path_str* is the legacy shared default (direct runs get a run folder)."""
    try:
        return Path(path_str).resolve() == (Path.cwd() / _DEFAULT_QMC_OUTPUT_DIR).resolve()
    except (OSError, RuntimeError):
        norm = Path(path_str).as_posix().replace("\\", "/").rstrip("/")
        return norm == _DEFAULT_QMC_OUTPUT_DIR.as_posix()


@dataclass
class SimulationPhaseResult:
    phase: str
    elapsed_seconds: float
    records_produced: int
    summary: Dict[str, Any] = field(default_factory=dict)


class SimulationBudget:
    """Tracks elapsed time and dynamically sizes work to fill the budget."""

    def __init__(self, total_seconds: float):
        self.total = total_seconds
        self._start = time.perf_counter()
        self.phase_budgets = {
            "gan": 0.10,
            "portfolio_sweep": 0.40,
            "convergence": 0.40,
            "analysis": 0.10,
        }

    @property
    def elapsed(self) -> float:
        return time.perf_counter() - self._start

    @property
    def remaining(self) -> float:
        return max(0, self.total - self.elapsed)

    def phase_budget(self, phase: str) -> float:
        frac = self.phase_budgets.get(phase, 0.1)
        return self.total * frac

    def phase_remaining(self, phase: str, phase_start: float) -> float:
        budget = self.phase_budget(phase)
        used = time.perf_counter() - phase_start
        return max(0, budget - used)

    @property
    def exhausted(self) -> bool:
        return self.remaining <= 0


class QMCSimulationCSVWriter:
    """Manages the three CSV output files."""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.sim_log_path = self.output_dir / "qmc_simulation_log.csv"
        self.cache_pattern_path = self.output_dir / "qmc_cache_patterns.csv"
        self.feature_path = self.output_dir / "qmc_feature_condensation.csv"

        self._headers: Dict[Path, List[str]] = {
            self.sim_log_path: [
                "timestamp", "run_id", "engine", "contract_id", "S0", "K", "r", "sigma", "T",
                "num_paths", "price", "std_error", "wall_clock_ms", "cache_hit",
                "cache_key", "similarity_score", "feature_hash",
            ],
            self.cache_pattern_path: [
                "timestamp", "window_id", "engine", "exact_hit_rate", "similarity_hit_rate",
                "miss_rate", "mean_reuse_distance", "locality_score", "working_set_size",
                "unique_keys_seen", "pattern_type", "burst_score", "periodic_score",
            ],
            self.feature_path: [
                "timestamp", "phase", "original_dims", "reduced_dims",
                "pca_variance_explained", "top_features", "cache_key_collisions",
                "effective_cache_utilization",
                "condensation_status", "condensation_reason",
                "input_row_count", "input_feature_dim",
                "output_row_count", "output_feature_dim",
            ],
        }

        for path, headers in self._headers.items():
            self._init_csv(path, headers)

    def _init_csv(self, path: Path, headers: List[str]) -> None:
        if not path.exists():
            with path.open("w", newline="") as f:
                csv.writer(f).writerow(headers)

    def log_simulation(self, row: Dict[str, Any]) -> None:
        self._append(self.sim_log_path, row)

    def log_cache_pattern(self, row: Dict[str, Any]) -> None:
        self._append(self.cache_pattern_path, row)

    def log_feature_condensation(self, row: Dict[str, Any]) -> None:
        self._append(self.feature_path, row)

    def _append(self, path: Path, row: Dict[str, Any]) -> None:
        headers = self._headers[path]
        with path.open("a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
            w.writerow(row)


def _generate_contracts(rng: np.random.Generator, n: int) -> List[Dict[str, float]]:
    contracts = []
    for i in range(n):
        S0 = rng.uniform(20, 500)
        moneyness = rng.uniform(0.7, 1.3)
        contracts.append({
            "contract_id": f"C{i:05d}",
            "S0": round(S0, 2),
            "K": round(S0 * moneyness, 2),
            "r": round(rng.uniform(0.01, 0.08), 4),
            "sigma": round(rng.uniform(0.05, 0.80), 4),
            "T": round(rng.uniform(0.1, 3.0), 2),
        })
    return contracts


def _budget_active(cfg: QMCSimulationConfig) -> bool:
    return cfg.enforce_budget


def _detect_pattern(hits: List[bool], window: int = 50) -> Dict[str, float]:
    if len(hits) < window:
        return {"pattern_type": "insufficient", "burst_score": 0.0, "periodic_score": 0.0}

    recent = hits[-window:]
    hit_rate = sum(recent) / len(recent)

    run_lengths = []
    current = 1
    for i in range(1, len(recent)):
        if recent[i] == recent[i - 1]:
            current += 1
        else:
            run_lengths.append(current)
            current = 1
    run_lengths.append(current)

    burst_score = max(run_lengths) / window if run_lengths else 0.0

    if len(recent) > 10:
        arr = np.array([1.0 if h else 0.0 for h in recent])
        fft = np.abs(np.fft.rfft(arr - arr.mean()))
        periodic_score = float(fft[1:].max() / (fft[1:].mean() + 1e-8)) / 10.0
    else:
        periodic_score = 0.0

    if burst_score > 0.4:
        ptype = "burst"
    elif periodic_score > 0.5:
        ptype = "periodic"
    elif hit_rate > 0.5:
        ptype = "high_reuse"
    else:
        ptype = "random"

    return {
        "pattern_type": ptype,
        "burst_score": round(burst_score, 4),
        "periodic_score": round(periodic_score, 4),
    }


# ── Trace Collector ──────────────────────────────────────────────────

_TRACE_EVENT_COLS = [
    "event_id", "timestamp", "run_id", "phase", "phase_index", "contract_index",
    "engine_order_index", "event_order_index", "engine", "contract_id",
    "S0", "K", "r", "sigma", "T", "num_paths", "seed", "event_type",
    "cache_key", "cache_key_short", "cache_hit", "similarity_hit",
    "similarity_score", "similarity_method", "similarity_candidate_count",
    "matched_signature_id", "matched_cache_key_short", "similarity_distance",
    "similarity_vector_norm",
    "price", "std_error", "wall_clock_ms",
    "cumulative_elapsed_s", "inter_event_gap_ms",
    "previous_same_key_gap_events", "previous_same_engine_gap_events",
    "reuse_distance_events", "rolling_hit_rate_16", "rolling_hit_rate_64",
    "rolling_miss_rate_16", "rolling_miss_rate_64",
    "rolling_working_set_16", "rolling_working_set_64",
    "rolling_unique_keys_16", "rolling_unique_keys_64",
    "rolling_engine_entropy_16", "rolling_engine_entropy_64",
    "burst_score_16", "burst_score_64", "periodic_score_16", "periodic_score_64",
    "locality_score_16", "locality_score_64",
    "rolling_similarity_rate_16", "rolling_similarity_rate_64",
    "rolling_exact_hit_rate_16", "rolling_exact_hit_rate_64",
    "rolling_total_reuse_signal_16", "rolling_total_reuse_signal_64",
    "feature_hash", "feature_l2_norm", "moneyness", "log_moneyness_abs",
    "normalized_sigma", "normalized_T", "engine_index", "phase_transition_flag",
    "event_runtime_rank",
    "maturity_bucket", "volatility_bucket", "path_bucket", "pattern_signature",
    "phase_progress_ratio",
    "pmu_available", "pmu_backend", "pmu_cycles", "pmu_instructions",
    "pmu_cache_references", "pmu_cache_misses", "pmu_task_clock_ms",
    "pmu_page_faults", "pmu_context_switches", "pmu_error",
    "pmu_measurement_kind",
    "notes",
]

_TRACE_WINDOW_COLS = [
    "window_id", "run_id", "phase", "engine_mix", "start_event_id",
    "end_event_id", "window_size", "exact_hit_rate", "miss_rate",
    "similarity_hit_rate", "similarity_event_rate", "similarity_score_mean",
    "signature_diversity", "dominant_signature_family",
    "mean_reuse_distance", "median_reuse_distance",
    "p90_reuse_distance", "working_set_size", "unique_keys_seen",
    "engine_entropy", "contract_entropy", "burst_score", "periodic_score",
    "locality_score", "mean_inter_event_gap_ms", "mean_wall_clock_ms",
    "cumulative_runtime_s", "price_variation_cv", "std_error_mean",
    "moneyness_mean", "sigma_mean", "T_mean", "num_paths_mean",
    "reuse_signal_mean", "total_reuse_signal",
    "pmu_miss_ratio_mean", "pmu_ipc_mean",
    "polar_r", "polar_theta", "polar_z", "cluster_seed_key",
    "dominant_engine", "dominant_phase", "notes",
]

_TRACE_POLAR_COLS = [
    "window_id", "run_id", "phase", "dominant_engine",
    "polar_r", "polar_theta", "polar_z", "x", "y",
    "locality_score", "miss_rate", "mean_reuse_distance",
    "working_set_size", "cluster_seed_key",
]

_TRACE_SIM_REF_COLS = [
    "signature_id", "representative_key", "representative_engine",
    "representative_phase", "representative_vector_norm",
    "first_seen_event", "last_seen_event",
    "occurrences", "exact_hits", "similarity_hits", "mean_similarity_score",
    "mean_reuse_distance", "mean_locality_score",
    "mean_burst_score", "mean_periodic_score", "mean_wall_clock_ms",
    "dominant_engine", "dominant_phase", "notes",
]

_TRACE_PHASE_SUMMARY_COLS = [
    "phase", "events", "windows", "exact_hit_rate", "similarity_hit_rate",
    "miss_rate", "mean_reuse_distance", "working_set_size_max",
    "locality_score_mean", "runtime_s", "notes",
]

_TRACE_ENGINE_SUMMARY_COLS = [
    "engine", "events", "windows", "exact_hit_rate", "miss_rate",
    "mean_reuse_distance", "working_set_size_max", "locality_score_mean",
    "wall_clock_ms_total", "wall_clock_ms_mean", "price_nan_count",
    "pmu_supported", "pmu_cycles_total", "pmu_instructions_total",
    "pmu_cache_refs_total", "pmu_cache_misses_total",
    "pmu_miss_ratio", "pmu_ipc", "pmu_measurement_kind", "notes",
]


class TraceCollector:
    """Accumulates dense trace events and emits CSVs for cache-pattern research."""

    def __init__(self, trace_dir: Path, run_id: str, cfg: QMCSimulationConfig):
        self.trace_dir = Path(trace_dir)
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        (self.trace_dir / "figures").mkdir(exist_ok=True)
        self.run_id = run_id
        self.cfg = cfg

        self._events: List[Dict[str, Any]] = []
        self._event_counter = 0
        self._window_seq = 0
        self._emitted_windows: List[Dict[str, Any]] = []
        self._run_start = time.perf_counter()
        self._last_event_time: Optional[float] = None
        self._saturated = False
        self._last_phase: str = ""

        self._key_last_seen: Dict[str, int] = {}
        self._engine_last_seen: Dict[str, int] = {}
        self._recent_keys: List[str] = []
        self._recent_engines: List[str] = []
        self._recent_hits: List[int] = []
        self._recent_sim_hits: List[int] = []
        self._recent_reuse_distances: List[float] = []
        self._wall_clocks: List[float] = []

        self._sig_tracker: Dict[str, Dict[str, Any]] = {}

        from qhpc_cache.trace_similarity import SimilarityMatcher
        self.sim_matcher: Optional[SimilarityMatcher] = None
        if cfg.enable_similarity_matching:
            self.sim_matcher = SimilarityMatcher(
                method=cfg.similarity_method,
                threshold=cfg.similarity_threshold,
                max_candidates=cfg.similarity_max_candidates,
                signature_dims=cfg.similarity_signature_dims,
                bucket_bits=cfg.similarity_bucket_bits,
            )

        from qhpc_cache.pmu_trace import create_pmu_collector, PMUCollector
        self.pmu: Optional[Any] = None
        if cfg.enable_pmu:
            self.pmu = create_pmu_collector(
                backend=cfg.pmu_backend,
                collect_cycles=cfg.pmu_collect_cycles,
                collect_instructions=cfg.pmu_collect_instructions,
                collect_cache_refs=cfg.pmu_collect_cache_refs,
                collect_cache_misses=cfg.pmu_collect_cache_misses,
                collect_page_faults=cfg.pmu_collect_page_faults,
            )

        self._files = {
            "events": self.trace_dir / "trace_events.csv",
            "windows": self.trace_dir / "trace_windows.csv",
            "polar": self.trace_dir / "trace_polar_embeddings.csv",
            "sim_ref": self.trace_dir / "trace_similarity_reference.csv",
            "phase_sum": self.trace_dir / "trace_phase_summary.csv",
            "engine_sum": self.trace_dir / "trace_engine_summary.csv",
        }
        self._init_csv("events", _TRACE_EVENT_COLS)
        self._init_csv("windows", _TRACE_WINDOW_COLS)
        self._init_csv("polar", _TRACE_POLAR_COLS)
        self._init_csv("sim_ref", _TRACE_SIM_REF_COLS)
        self._init_csv("phase_sum", _TRACE_PHASE_SUMMARY_COLS)
        self._init_csv("engine_sum", _TRACE_ENGINE_SUMMARY_COLS)

    def _init_csv(self, key: str, cols: List[str]):
        path = self._files[key]
        with path.open("w", newline="") as f:
            csv.writer(f).writerow(cols)

    def _append_csv(self, key: str, row: Dict[str, Any], cols: List[str]):
        path = self._files[key]
        with path.open("a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writerow(row)

    @property
    def accepting(self) -> bool:
        return not self._saturated

    def emit_event(
        self,
        phase: str,
        phase_index: int,
        contract_index: int,
        engine_order_index: int,
        engine: str,
        contract: Dict[str, Any],
        num_paths: int,
        seed_val: int,
        event_type: str,
        cache_key: str,
        cache_hit: bool,
        similarity_hit: bool,
        similarity_score: float,
        price: float,
        std_error: float,
        wall_clock_ms: float,
        phase_progress: float,
        notes: str = "",
        pmu_override: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Emit one trace event row. Returns False when trace is saturated."""
        from qhpc_cache.trace_features import (
            bucket_maturity, bucket_moneyness, bucket_paths, bucket_sigma,
            build_pattern_signature, compute_burst_score, compute_locality_score,
            compute_periodic_score, compute_reuse_distance, feature_l2_norm,
            rolling_working_set, safe_entropy,
        )

        if self._saturated:
            return False

        now = time.perf_counter()
        elapsed_s = now - self._run_start
        gap_ms = (now - self._last_event_time) * 1000 if self._last_event_time else 0.0
        self._last_event_time = now

        eid = self._event_counter
        self._event_counter += 1

        key_short = cache_key[:24] if cache_key else ""
        S0 = contract.get("S0", 0)
        K = contract.get("K", 0)
        r_ = contract.get("r", 0)
        sigma = contract.get("sigma", 0)
        T = contract.get("T", 0)

        same_key_gap = compute_reuse_distance(eid, self._key_last_seen.get(key_short))
        same_engine_gap = compute_reuse_distance(eid, self._engine_last_seen.get(engine))
        reuse_dist = same_key_gap

        self._key_last_seen[key_short] = eid
        self._engine_last_seen[engine] = eid

        self._recent_keys.append(key_short)
        self._recent_engines.append(engine)
        self._recent_hits.append(1 if cache_hit else 0)
        if reuse_dist is not None:
            self._recent_reuse_distances.append(float(reuse_dist))

        def _rolling(seq, w):
            return seq[-w:] if len(seq) >= w else seq

        h16 = _rolling(self._recent_hits, 16)
        h64 = _rolling(self._recent_hits, 64)
        k16 = _rolling(self._recent_keys, 16)
        k64 = _rolling(self._recent_keys, 64)
        e16 = _rolling(self._recent_engines, 16)
        e64 = _rolling(self._recent_engines, 64)
        rd16 = _rolling(self._recent_reuse_distances, 16)
        rd64 = _rolling(self._recent_reuse_distances, 64)

        moneyness = S0 / K if K > 0 else 0
        sig = build_pattern_signature(engine, S0, K, sigma, T, num_paths, cache_hit)

        if sig not in self._sig_tracker:
            self._sig_tracker[sig] = {
                "representative_key": key_short, "first_seen": eid, "last_seen": eid,
                "count": 0, "exact_hits": 0, "sim_hits": 0, "sim_scores": [],
                "rd": [], "burst": [], "periodic": [],
                "wc": [], "engines": [], "phases": [], "vec_norms": [],
            }
        st = self._sig_tracker[sig]
        st["last_seen"] = eid
        st["count"] += 1
        if cache_hit:
            st["exact_hits"] += 1
        if reuse_dist is not None:
            st["rd"].append(reuse_dist)
        st["wc"].append(wall_clock_ms)
        st["engines"].append(engine)
        st["phases"].append(phase)
        st["burst"].append(compute_burst_score(h16))
        st["periodic"].append(compute_periodic_score(h16))

        # similarity
        from qhpc_cache.trace_similarity import build_similarity_vector
        loc_16 = compute_locality_score(rd16)
        sim_vec = build_similarity_vector(
            S0, K, r_, sigma, T, num_paths, engine, phase_index,
            loc_16, float(reuse_dist) if reuse_dist is not None else 0.0,
        )
        sim_vec_norm = float(np.linalg.norm(sim_vec))
        st["vec_norms"].append(sim_vec_norm)

        real_sim_hit = False
        real_sim_score = 0.0
        sim_method = self.cfg.similarity_method if self.cfg.enable_similarity_matching else "disabled"
        sim_cand_count = 0
        matched_sig_id = ""
        matched_key_short = ""

        if (self.sim_matcher is not None
                and not cache_hit
                and event_type in ("cache_miss", "engine_end", "engine_error")):
            real_sim_hit, real_sim_score, matched_sig_id, matched_key_short, sim_cand_count = (
                self.sim_matcher.query(sim_vec)
            )
            if real_sim_hit:
                st["sim_hits"] += 1
                st["sim_scores"].append(real_sim_score)

        if self.sim_matcher is not None:
            self.sim_matcher.add(sim_vec, key_short, sig, engine, phase, eid)

        self._recent_sim_hits.append(1 if real_sim_hit else 0)
        self._wall_clocks.append(wall_clock_ms)

        sim16 = _rolling(self._recent_sim_hits, 16)
        sim64 = _rolling(self._recent_sim_hits, 64)

        def _reuse_signal(hits, sim_h, rd_slice):
            hr = sum(hits) / max(1, len(hits))
            sr = sum(sim_h) / max(1, len(sim_h))
            inv_rd = compute_locality_score(rd_slice) if rd_slice else 0.0
            return round(0.5 * hr + 0.3 * sr + 0.2 * inv_rd, 6)

        phase_transition = 1 if (self._last_phase and self._last_phase != phase) else 0
        self._last_phase = phase

        p_nan = math.isnan(price) if isinstance(price, float) else False
        se_nan = math.isnan(std_error) if isinstance(std_error, float) else False

        from qhpc_cache.trace_similarity import _engine_idx as _eidx
        eng_idx = int(_eidx(engine))
        runtime_rank = sorted(range(len(self._wall_clocks)), key=lambda i: self._wall_clocks[i], reverse=True).index(len(self._wall_clocks) - 1) if self._wall_clocks else 0

        pmu_d: Dict[str, Any] = {
            "pmu_available": False, "pmu_backend": "none",
            "pmu_cycles": 0, "pmu_instructions": 0,
            "pmu_cache_references": 0, "pmu_cache_misses": 0,
            "pmu_task_clock_ms": 0, "pmu_page_faults": 0,
            "pmu_context_switches": 0, "pmu_error": "",
        }
        if self.pmu is not None:
            pmu_d["pmu_available"] = self.pmu.available
            pmu_d["pmu_backend"] = self.pmu.backend_name
        if pmu_override:
            pmu_d.update(pmu_override)
        pmu_measurement_kind = (
            "hardware_counter_measured"
            if bool(pmu_d.get("pmu_available"))
            else "proxy_or_unavailable"
        )

        row = {
            "event_id": eid,
            "timestamp": time.time(),
            "run_id": self.run_id,
            "phase": phase,
            "phase_index": phase_index,
            "contract_index": contract_index,
            "engine_order_index": engine_order_index,
            "event_order_index": eid,
            "engine": engine,
            "contract_id": contract.get("contract_id", ""),
            "S0": S0, "K": K, "r": r_, "sigma": sigma, "T": T,
            "num_paths": num_paths,
            "seed": seed_val,
            "event_type": event_type,
            "cache_key": cache_key[:64] if cache_key else "",
            "cache_key_short": key_short,
            "cache_hit": cache_hit,
            "similarity_hit": real_sim_hit,
            "similarity_score": round(real_sim_score, 6),
            "similarity_method": sim_method,
            "similarity_candidate_count": sim_cand_count,
            "matched_signature_id": matched_sig_id,
            "matched_cache_key_short": matched_key_short,
            "similarity_distance": round(1.0 - real_sim_score, 6) if real_sim_score > 0 else "",
            "similarity_vector_norm": round(sim_vec_norm, 6),
            "price": float("nan") if p_nan else price,
            "std_error": float("nan") if se_nan else std_error,
            "wall_clock_ms": round(wall_clock_ms, 4),
            "cumulative_elapsed_s": round(elapsed_s, 4),
            "inter_event_gap_ms": round(gap_ms, 4),
            "previous_same_key_gap_events": same_key_gap if same_key_gap is not None else float("nan"),
            "previous_same_engine_gap_events": same_engine_gap if same_engine_gap is not None else float("nan"),
            "reuse_distance_events": float(reuse_dist) if reuse_dist is not None else float("nan"),
            "rolling_hit_rate_16": round(sum(h16) / max(1, len(h16)), 6),
            "rolling_hit_rate_64": round(sum(h64) / max(1, len(h64)), 6),
            "rolling_miss_rate_16": round(1 - sum(h16) / max(1, len(h16)), 6),
            "rolling_miss_rate_64": round(1 - sum(h64) / max(1, len(h64)), 6),
            "rolling_working_set_16": rolling_working_set(k16),
            "rolling_working_set_64": rolling_working_set(k64),
            "rolling_unique_keys_16": len(set(k16)),
            "rolling_unique_keys_64": len(set(k64)),
            "rolling_engine_entropy_16": round(safe_entropy(e16), 6),
            "rolling_engine_entropy_64": round(safe_entropy(e64), 6),
            "burst_score_16": round(compute_burst_score(h16), 6),
            "burst_score_64": round(compute_burst_score(h64), 6),
            "periodic_score_16": round(compute_periodic_score(h16), 6),
            "periodic_score_64": round(compute_periodic_score(h64), 6),
            "locality_score_16": round(loc_16, 6),
            "locality_score_64": round(compute_locality_score(rd64), 6),
            "rolling_similarity_rate_16": round(sum(sim16) / max(1, len(sim16)), 6),
            "rolling_similarity_rate_64": round(sum(sim64) / max(1, len(sim64)), 6),
            "rolling_exact_hit_rate_16": round(sum(h16) / max(1, len(h16)), 6),
            "rolling_exact_hit_rate_64": round(sum(h64) / max(1, len(h64)), 6),
            "rolling_total_reuse_signal_16": _reuse_signal(h16, sim16, rd16),
            "rolling_total_reuse_signal_64": _reuse_signal(h64, sim64, rd64),
            "feature_hash": hash((S0, K, r_, sigma, T, engine)) % (10**10),
            "feature_l2_norm": round(feature_l2_norm(S0, K, r_, sigma, T), 6),
            "moneyness": round(moneyness, 6),
            "log_moneyness_abs": round(abs(math.log(moneyness)) if moneyness > 0 else 0, 6),
            "normalized_sigma": round(sigma / 0.4, 6),
            "normalized_T": round(T / 3.0, 6),
            "engine_index": eng_idx,
            "phase_transition_flag": phase_transition,
            "event_runtime_rank": runtime_rank,
            "maturity_bucket": bucket_maturity(T),
            "volatility_bucket": bucket_sigma(sigma),
            "path_bucket": bucket_paths(num_paths),
            "pattern_signature": sig,
            "phase_progress_ratio": round(phase_progress, 6),
            **pmu_d,
            "pmu_measurement_kind": pmu_measurement_kind,
            "notes": notes,
        }

        self._events.append(row)
        self._append_csv("events", row, _TRACE_EVENT_COLS)

        if eid > 0 and eid % self.cfg.trace_stride == 0 and len(self._events) >= self.cfg.trace_window_size:
            self._emit_window()

        if self.cfg.max_trace_rows and self._event_counter >= self.cfg.max_trace_rows:
            self._saturated = True
            return False

        return True

    def _emit_window(self):
        from qhpc_cache.trace_windows import compute_window_summary, window_id as make_wid
        from qhpc_cache.trace_polar import build_polar_row

        self._window_seq += 1
        wid = make_wid(self.run_id, self._window_seq)
        window_events = self._events[-self.cfg.trace_window_size:]

        summary = compute_window_summary(window_events, wid, self.run_id)
        self._emitted_windows.append(summary)
        self._append_csv("windows", summary, _TRACE_WINDOW_COLS)

        polar = build_polar_row(summary, self.run_id)
        self._append_csv("polar", polar, _TRACE_POLAR_COLS)

    def emit_phase_summary(self, phase: str, runtime_s: float):
        phase_events = [e for e in self._events if e.get("phase") == phase]
        n = len(phase_events)
        if n == 0:
            return
        hits = sum(1 for e in phase_events if e.get("cache_hit"))
        rds_f = [float(e["reuse_distance_events"]) for e in phase_events
                 if not math.isnan(float(e.get("reuse_distance_events", float("nan"))))]
        keys = set(e.get("cache_key_short", "") for e in phase_events)
        loc_scores = [float(e.get("locality_score_64", 0)) for e in phase_events]

        actual_windows = [w for w in self._emitted_windows if w.get("dominant_phase") == phase]

        sim_hits = sum(1 for e in phase_events if e.get("similarity_hit"))

        row = {
            "phase": phase,
            "events": n,
            "windows": len(actual_windows),
            "exact_hit_rate": round(hits / n, 6) if n else 0,
            "similarity_hit_rate": round(sim_hits / n, 6) if n else 0,
            "miss_rate": round(1 - hits / n, 6) if n else 0,
            "mean_reuse_distance": round(np.mean(rds_f), 4) if rds_f else 0,
            "working_set_size_max": len(keys),
            "locality_score_mean": round(np.mean(loc_scores), 6) if loc_scores else 0,
            "runtime_s": round(runtime_s, 4),
            "notes": "truncated_by_max_trace_rows" if self._saturated else "",
        }
        self._append_csv("phase_sum", row, _TRACE_PHASE_SUMMARY_COLS)

    def emit_engine_summaries(self):
        from collections import Counter
        engine_events: Dict[str, List[Dict]] = {}
        for e in self._events:
            engine_events.setdefault(e.get("engine", "?"), []).append(e)

        engine_window_counts: Dict[str, int] = Counter()
        for w in self._emitted_windows:
            de = w.get("dominant_engine", "")
            if de:
                engine_window_counts[de] += 1

        for eng, evts in engine_events.items():
            n = len(evts)
            hits = sum(1 for e in evts if e.get("cache_hit"))
            rds = [float(e["reuse_distance_events"]) for e in evts
                   if not math.isnan(float(e.get("reuse_distance_events", float("nan"))))]
            keys = set(e.get("cache_key_short", "") for e in evts)
            loc = [float(e.get("locality_score_64", 0)) for e in evts]
            wc = [float(e.get("wall_clock_ms", 0)) for e in evts]
            nan_count = sum(1 for e in evts if math.isnan(float(e.get("price", float("nan")))))

            pmu_cyc = sum(float(e.get("pmu_cycles", 0)) for e in evts)
            pmu_ins = sum(float(e.get("pmu_instructions", 0)) for e in evts)
            pmu_cref = sum(float(e.get("pmu_cache_references", 0)) for e in evts)
            pmu_cmis = sum(float(e.get("pmu_cache_misses", 0)) for e in evts)
            pmu_ok = any(e.get("pmu_available") for e in evts)
            pmu_measurement_kind = (
                "hardware_counter_measured" if pmu_ok else "proxy_or_unavailable"
            )
            pmu_note = (
                ""
                if pmu_ok
                else "pmu-like fields are proxy/unavailable on this run"
            )

            row = {
                "engine": eng,
                "events": n,
                "windows": engine_window_counts.get(eng, 0),
                "exact_hit_rate": round(hits / n, 6) if n else 0,
                "miss_rate": round(1 - hits / n, 6) if n else 0,
                "mean_reuse_distance": round(np.mean(rds), 4) if rds else 0,
                "working_set_size_max": len(keys),
                "locality_score_mean": round(np.mean(loc), 6) if loc else 0,
                "wall_clock_ms_total": round(sum(wc), 4),
                "wall_clock_ms_mean": round(np.mean(wc), 4) if wc else 0,
                "price_nan_count": nan_count,
                "pmu_supported": pmu_ok,
                "pmu_cycles_total": round(pmu_cyc, 0),
                "pmu_instructions_total": round(pmu_ins, 0),
                "pmu_cache_refs_total": round(pmu_cref, 0),
                "pmu_cache_misses_total": round(pmu_cmis, 0),
                "pmu_miss_ratio": round(pmu_cmis / pmu_cref, 6) if pmu_cref > 0 else 0,
                "pmu_ipc": round(pmu_ins / pmu_cyc, 6) if pmu_cyc > 0 else 0,
                "pmu_measurement_kind": pmu_measurement_kind,
                "notes": pmu_note,
            }
            self._append_csv("engine_sum", row, _TRACE_ENGINE_SUMMARY_COLS)

    def emit_similarity_reference(self):
        from collections import Counter
        for sig, info in self._sig_tracker.items():
            eng_counts = Counter(info["engines"])
            phase_counts = Counter(info["phases"])
            dom_eng = eng_counts.most_common(1)[0][0] if eng_counts else ""
            dom_phase = phase_counts.most_common(1)[0][0] if phase_counts else ""
            row = {
                "signature_id": sig,
                "representative_key": info["representative_key"],
                "representative_engine": dom_eng,
                "representative_phase": dom_phase,
                "representative_vector_norm": round(np.mean(info["vec_norms"]), 6) if info["vec_norms"] else 0,
                "first_seen_event": info["first_seen"],
                "last_seen_event": info["last_seen"],
                "occurrences": info["count"],
                "exact_hits": info["exact_hits"],
                "similarity_hits": info["sim_hits"],
                "mean_similarity_score": round(np.mean(info["sim_scores"]), 6) if info["sim_scores"] else 0,
                "mean_reuse_distance": round(np.mean(info["rd"]), 4) if info["rd"] else 0,
                "mean_locality_score": round(np.mean([1.0 / (1 + d) for d in info["rd"]]), 6) if info["rd"] else 0,
                "mean_burst_score": round(np.mean(info["burst"]), 6) if info["burst"] else 0,
                "mean_periodic_score": round(np.mean(info["periodic"]), 6) if info["periodic"] else 0,
                "mean_wall_clock_ms": round(np.mean(info["wc"]), 4) if info["wc"] else 0,
                "dominant_engine": dom_eng,
                "dominant_phase": dom_phase,
                "notes": "",
            }
            self._append_csv("sim_ref", row, _TRACE_SIM_REF_COLS)

    def flush_and_plot(self):
        self.emit_similarity_reference()
        self.emit_engine_summaries()
        if self.cfg.emit_visuals:
            from qhpc_cache.visualization.cache_trace_plots import generate_all_trace_plots
            plots = generate_all_trace_plots(self.trace_dir)
            for p in plots:
                print(f"  [trace] {p.name}")

    @property
    def event_count(self) -> int:
        return self._event_counter


def run_qmc_simulation(
    config: Optional[QMCSimulationConfig] = None,
    progress_callback: Optional[Callable[[str, float], None]] = None,
) -> Dict[str, Any]:
    """Execute the QMC simulation with optional full-trace observability.

    Returns a summary dict with phase results and output paths.
    """
    from qhpc_cache.cache_store import SimpleCacheStore
    from qhpc_cache.data_models import BackendExecutionProvenance
    from qhpc_cache.feature_condenser import FeatureCondenser
    from qhpc_cache.backends import (
        create_backend,
        default_mode_intent_for_backend,
        normalize_backend_name,
    )
    from qhpc_cache.output_paths import ensure_hpc_submission_dir

    cfg = config or QMCSimulationConfig()

    output_auto_isolated = False
    if _is_unscoped_default_qmc_output_dir(cfg.output_dir):
        from qhpc_cache.output_paths import create_run_output_root

        base = Path(os.environ.get("QHPC_OUTPUT_ROOT", "outputs"))
        run_root = create_run_output_root(base)
        cfg.output_dir = str((run_root / "qmc_simulation").resolve())
        output_auto_isolated = True

    out_dir = Path(cfg.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_writer = QMCSimulationCSVWriter(out_dir)
    run_root = out_dir.parent
    run_id = f"qmc_{int(time.time())}"

    requested_backend_raw = str(cfg.requested_backend or "cpu_local")
    requested_backend_resolved = normalize_backend_name(requested_backend_raw)
    requested_mode_intent = (
        str(cfg.execution_mode_intent).strip()
        if str(cfg.execution_mode_intent).strip()
        else default_mode_intent_for_backend(requested_backend_raw)
    )
    selected_backend = create_backend(requested_backend_raw)
    selected_cap = selected_backend.capabilities()
    execution_deferred_to_hpc = bool(cfg.execution_deferred_to_hpc) or (requested_backend_resolved != "cpu_local")
    slurm_job_manifest_path = ""

    # Slurm-first integration readiness path: generate submission artifacts and exit honestly.
    if execution_deferred_to_hpc:
        cache = SimpleCacheStore(enable_logging=True)
        cache.flush_access_log_csv(out_dir / "cache_access_log.csv")
        submission_dir = ensure_hpc_submission_dir(run_root, cfg.hpc_submission_subdir)
        slurm_backend = create_backend("slurm_bigred200")
        run_command = (
            str(cfg.hpc_run_command).strip()
            if str(cfg.hpc_run_command).strip()
            else (
                "python3 run_full_research_pipeline.py "
                f"--mode experiment_batch --budget {float(cfg.budget_minutes):g} "
                f"--requested-backend {requested_backend_raw} --defer-execution-to-hpc"
            )
        )
        slurm_plan = slurm_backend.build_plan(
            "qmc_simulation",
            {
                "requested_backend": requested_backend_raw,
                "execution_mode_intent": requested_mode_intent,
                "num_paths": int(max(cfg.convergence_path_counts) if cfg.convergence_path_counts else 10000),
                "slurm_job_name": cfg.slurm_job_name or "qhpc_qmc",
                "slurm_walltime": cfg.slurm_walltime,
                "slurm_partition": cfg.slurm_partition,
                "slurm_nodes": int(cfg.slurm_nodes),
                "slurm_ntasks": int(cfg.slurm_ntasks),
                "slurm_cpus_per_task": int(cfg.slurm_cpus_per_task),
                "slurm_mem": cfg.slurm_mem,
                "slurm_output_log": cfg.slurm_output_log,
                "slurm_error_log": cfg.slurm_error_log,
                "slurm_account": cfg.slurm_account,
                "slurm_constraint": cfg.slurm_constraint,
                "slurm_qos": cfg.slurm_qos,
                "artifact_dir": str(submission_dir),
                "run_command": run_command,
                "plan_id": f"qmc_{requested_mode_intent}_{int(time.time())}",
            },
            dry_run=True,
        )
        slurm_result = slurm_backend.execute(slurm_plan)
        slurm_job_manifest_path = str(slurm_result.get("slurm_job_manifest_path", ""))

        provenance = BackendExecutionProvenance(
            requested_backend=requested_backend_raw,
            executed_backend="none_deferred_to_hpc",
            execution_environment="hpc",
            execution_mode_intent=requested_mode_intent,
            execution_mode_actual="deferred_to_hpc",
            slurm_job_manifest_path=slurm_job_manifest_path,
            hpc_ready=bool(selected_cap.hpc_ready),
            mpi_ready=bool(selected_cap.mpi_ready),
            gpu_ready=bool(selected_cap.gpu_ready),
            execution_deferred_to_hpc=True,
            notes="No pricing executed locally; Slurm submission artifacts generated for BigRed200.",
        )
        summary = {
            "run_id": run_id,
            "total_elapsed_seconds": 0.0,
            "budget_seconds": float(cfg.budget_minutes * 60.0),
            "trace_full_mode": cfg.trace_full_mode,
            "output_dir": str(out_dir.resolve()),
            "output_auto_isolated_from_default": output_auto_isolated,
            "max_pricings_total": cfg.max_pricings_total,
            "total_pricings_phases_2_3": 0,
            "pricing_cap_reached": False,
            "engine_allowlist": list(cfg.engine_allowlist) if cfg.engine_allowlist else None,
            "phases": [
                {
                    "phase": "hpc_deferred_planning",
                    "elapsed": 0.0,
                    "records": 0,
                    "slurm_job_manifest_path": slurm_job_manifest_path,
                    "sbatch_script_path": slurm_result.get("sbatch_script_path", ""),
                    "workload_to_slurm_mapping_csv": slurm_result.get("workload_to_slurm_mapping_csv", ""),
                    "backend_readiness_md": slurm_result.get("backend_readiness_md", ""),
                }
            ],
            "cache_final": cache.stats(),
            "feature_condensation": {
                "condensation_status": "skipped",
                "condensation_reason": "execution_deferred_to_hpc",
                "input_row_count": 0,
                "input_feature_dim": 0,
                "output_row_count": 0,
                "output_feature_dim": 0,
            },
            "engines_used": [],
            "optional_capabilities": {"engine_pool": []},
            "pmu_observability": {
                "measurement_status": "deferred_to_hpc",
                "pmu_enabled_in_config": bool(cfg.enable_pmu),
                "pmu_supported_any_engine": False,
                "note": "PMU collection deferred to BigRed200/x86 execution.",
            },
            "backend_execution": provenance.to_dict(),
            "requested_backend": provenance.requested_backend,
            "executed_backend": provenance.executed_backend,
            "execution_environment": provenance.execution_environment,
            "execution_mode_intent": provenance.execution_mode_intent,
            "execution_mode_actual": provenance.execution_mode_actual,
            "slurm_job_manifest_path": provenance.slurm_job_manifest_path,
            "hpc_ready": provenance.hpc_ready,
            "mpi_ready": provenance.mpi_ready,
            "gpu_ready": provenance.gpu_ready,
            "execution_deferred_to_hpc": provenance.execution_deferred_to_hpc,
            "csv_files": {
                "simulation_log": str(csv_writer.sim_log_path.resolve()),
                "cache_patterns": str(csv_writer.cache_pattern_path.resolve()),
                "feature_condensation": str(csv_writer.feature_path.resolve()),
                "cache_access_log": str((out_dir / "cache_access_log.csv").resolve()),
                "run_summary_json": str((out_dir / "qmc_run_summary.json").resolve()),
                "gan_synthetic_data": str((out_dir / "gan_synthetic_data.parquet").resolve()),
            },
        }
        summary_path = out_dir / "qmc_run_summary.json"
        import json

        summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        return summary

    budget = SimulationBudget(cfg.budget_minutes * 60)
    rng = np.random.default_rng(cfg.seed)

    cache = SimpleCacheStore(enable_logging=True)
    condenser = FeatureCondenser(n_components=3)
    hit_history: List[bool] = []
    all_features: List[np.ndarray] = []
    phase_results: List[SimulationPhaseResult] = []

    engines = _load_engines()
    if cfg.engine_allowlist:
        allow = {str(x) for x in cfg.engine_allowlist}
        engines = {k: v for k, v in engines.items() if k in allow}
        missing = sorted(allow - set(engines.keys()))
        if missing:
            print(f"[engine] allowlist: not loaded / unavailable: {missing}")

    total_pricings_done = 0
    pricing_cap_hit = False

    trace: Optional[TraceCollector] = None
    if cfg.trace_full_mode:
        trace_dir = out_dir / cfg.trace_output_subdir
        trace = TraceCollector(trace_dir, run_id, cfg)

    def _report(msg: str) -> None:
        if cfg.enforce_budget:
            pct = min(100, budget.elapsed / budget.total * 100)
            print(f"  [{pct:5.1f}%] {msg}")
        else:
            elapsed = budget.elapsed
            print(f"  [trace {elapsed:7.1f}s] {msg}")
        if progress_callback:
            pct = min(100, budget.elapsed / budget.total * 100) if cfg.enforce_budget else -1.0
            progress_callback(msg, pct)

    # ── Phase 1: GAN Data Generation ─────────────────────────────────
    _report("Phase 1: GAN data generation")
    p1_start = time.perf_counter()
    gan_df = _run_gan_phase(cfg, budget, rng, _report)
    phase_results.append(SimulationPhaseResult(
        "gan",
        time.perf_counter() - p1_start,
        len(gan_df) if gan_df is not None else 0,
        {"rows": len(gan_df) if gan_df is not None else 0},
    ))

    # ── Phase 2: Portfolio Sweep ─────────────────────────────────────
    _report("Phase 2: Portfolio sweep across engines")
    p2_start = time.perf_counter()
    p2_n_contracts = cfg.max_phase_contracts if cfg.max_phase_contracts else cfg.portfolio_size
    contracts = _generate_contracts(rng, p2_n_contracts)
    sweep_count = 0
    window_id = 0
    ci = -1
    ba = _budget_active(cfg)
    trace_stopped = False

    for ci, contract in enumerate(contracts):
        if ba and (budget.phase_remaining("portfolio_sweep", p2_start) <= 0 or budget.exhausted):
            break
        if trace and not trace.accepting:
            trace_stopped = True

        fvec = np.array([contract["S0"], contract["K"],
                        contract["r"], contract["sigma"], contract["T"]])
        all_features.append(fvec)

        for engine_idx, (engine_name, engine) in enumerate(engines.items()):
            if ba and (budget.phase_remaining("portfolio_sweep", p2_start) <= 0 or budget.exhausted):
                break
            if cfg.max_pricings_total is not None and total_pricings_done >= cfg.max_pricings_total:
                pricing_cap_hit = True
                break

            if engine_name == "monaco_mc" and not cfg.trace_full_mode:
                continue

            features = {
                "engine": engine_name,
                "S0": contract["S0"],
                "K": contract["K"],
                "r": contract["r"],
                "sigma": contract["sigma"],
                "T": contract["T"],
                "num_paths": 10_000,
            }

            seed_val = cfg.seed + ci
            cache_key = cache.make_key(features)
            event_notes = ""
            cache_hit = False
            price = float("nan")
            std_err = float("nan")
            wall_ms = 0.0
            engine_failed = False
            phase_prog = ci / max(1, len(contracts))

            if trace and trace.accepting:
                trace.emit_event(
                    phase="portfolio_sweep", phase_index=2,
                    contract_index=ci, engine_order_index=engine_idx,
                    engine=engine_name, contract=contract,
                    num_paths=10_000, seed_val=seed_val,
                    event_type="engine_start", cache_key=cache_key,
                    cache_hit=False, similarity_hit=False,
                    similarity_score=0.0,
                    price=float("nan"), std_error=float("nan"),
                    wall_clock_ms=0.0,
                    phase_progress=phase_prog,
                    notes="",
                )

            pmu_data: Dict[str, Any] = {}
            try:
                result_cached = cache.get(features, engine_name=engine_name)
                cache_hit = True
                price = result_cached["price"]
                std_err = result_cached["std_error"]
            except KeyError:
                if trace and trace.pmu is not None and cfg.enable_pmu:
                    trace.pmu.begin_scope(f"p2_{engine_name}_{ci}")
                t0 = time.perf_counter()
                try:
                    result = engine.price(
                        S0=contract["S0"], K=contract["K"], r=contract["r"],
                        sigma=contract["sigma"], T=contract["T"],
                        num_paths=10_000, seed=seed_val,
                    )
                    price = result.price
                    std_err = result.std_error
                except Exception as exc:
                    event_notes = f"{type(exc).__name__}: {exc}"
                    engine_failed = True
                wall_ms = (time.perf_counter() - t0) * 1000
                if trace and trace.pmu is not None and cfg.enable_pmu:
                    pmu_metrics = trace.pmu.end_scope()
                    pmu_data = pmu_metrics.to_dict()

                if not engine_failed and math.isfinite(price) and math.isfinite(std_err):
                    cache.put(features, {"price": price, "std_error": std_err},
                              engine_name=engine_name, compute_time_ms=wall_ms,
                              stage_elapsed_ms=(time.perf_counter() - p2_start) * 1000.0,
                              row_semantics="put_single_compute_result")

            hit_history.append(cache_hit)
            sweep_count += 1
            total_pricings_done += 1
            if cfg.max_pricings_total is not None and total_pricings_done >= cfg.max_pricings_total:
                pricing_cap_hit = True

            if trace and trace.accepting:
                if cache_hit:
                    trace.emit_event(
                        phase="portfolio_sweep", phase_index=2,
                        contract_index=ci, engine_order_index=engine_idx,
                        engine=engine_name, contract=contract,
                        num_paths=10_000, seed_val=seed_val,
                        event_type="cache_hit", cache_key=cache_key,
                        cache_hit=True, similarity_hit=False,
                        similarity_score=1.0,
                        price=price, std_error=std_err,
                        wall_clock_ms=0.0,
                        phase_progress=phase_prog,
                        notes="",
                    )
                else:
                    trace.emit_event(
                        phase="portfolio_sweep", phase_index=2,
                        contract_index=ci, engine_order_index=engine_idx,
                        engine=engine_name, contract=contract,
                        num_paths=10_000, seed_val=seed_val,
                        event_type="cache_miss", cache_key=cache_key,
                        cache_hit=False, similarity_hit=False,
                        similarity_score=0.0,
                        price=float("nan"), std_error=float("nan"),
                        wall_clock_ms=0.0,
                        phase_progress=phase_prog,
                        notes="",
                    )

            if trace and trace.accepting:
                if engine_failed:
                    trace.emit_event(
                        phase="portfolio_sweep", phase_index=2,
                        contract_index=ci, engine_order_index=engine_idx,
                        engine=engine_name, contract=contract,
                        num_paths=10_000, seed_val=seed_val,
                        event_type="engine_error", cache_key=cache_key,
                        cache_hit=False, similarity_hit=False,
                        similarity_score=0.0,
                        price=float("nan"), std_error=float("nan"),
                        wall_clock_ms=wall_ms,
                        phase_progress=phase_prog,
                        notes=event_notes,
                    )
                elif not cache_hit:
                    trace.emit_event(
                        phase="portfolio_sweep", phase_index=2,
                        contract_index=ci, engine_order_index=engine_idx,
                        engine=engine_name, contract=contract,
                        num_paths=10_000, seed_val=seed_val,
                        event_type="engine_end", cache_key=cache_key,
                        cache_hit=False, similarity_hit=False,
                        similarity_score=0.0,
                        price=price, std_error=std_err,
                        wall_clock_ms=wall_ms,
                        phase_progress=phase_prog,
                        notes="",
                        pmu_override=pmu_data if pmu_data else None,
                    )

            csv_writer.log_simulation({
                "timestamp": time.time(), "run_id": run_id, "engine": engine_name,
                "contract_id": contract["contract_id"],
                "S0": contract["S0"], "K": contract["K"], "r": contract["r"],
                "sigma": contract["sigma"], "T": contract["T"],
                "num_paths": 10_000, "price": price, "std_error": std_err,
                "wall_clock_ms": round(wall_ms, 2), "cache_hit": cache_hit,
                "cache_key": cache_key[:24],
                "similarity_score": 1.0 if cache_hit else 0.0,
                "feature_hash": hash(tuple(fvec)) % (10**8),
            })

            if sweep_count % 100 == 0:
                window_id += 1
                n_recent = hit_history[-100:]
                exact_hr = sum(n_recent) / len(n_recent)
                pattern = _detect_pattern(hit_history)
                keys_seen: Set[str] = set()
                reuse_dists: List[int] = []
                last_seen: Dict[str, int] = {}
                for idx, log in enumerate(cache.access_log[-200:]):
                    keys_seen.add(log.key[:32])
                    k = log.key[:32]
                    if k in last_seen:
                        reuse_dists.append(idx - last_seen[k])
                    last_seen[k] = idx
                csv_writer.log_cache_pattern({
                    "timestamp": time.time(), "window_id": window_id, "engine": "all",
                    "exact_hit_rate": round(exact_hr, 4), "similarity_hit_rate": 0.0,
                    "miss_rate": round(1 - exact_hr, 4),
                    "mean_reuse_distance": round(np.mean(reuse_dists), 2) if reuse_dists else 0,
                    "locality_score": round(1.0 / (1 + np.mean(reuse_dists)), 4) if reuse_dists else 0,
                    "working_set_size": len(keys_seen), "unique_keys_seen": len(keys_seen),
                    **pattern,
                })

            if pricing_cap_hit:
                break

        if pricing_cap_hit:
            break

        if ci % 50 == 0 and ci > 0:
            _report(f"  Sweep: {ci}/{len(contracts)} contracts, {sweep_count} pricings")

    p2_elapsed = time.perf_counter() - p2_start
    phase_results.append(SimulationPhaseResult(
        "portfolio_sweep", p2_elapsed, sweep_count,
        {"contracts_priced": ci + 1, "total_pricings": sweep_count, "cache_stats": cache.stats()},
    ))
    if trace:
        trace.emit_phase_summary("portfolio_sweep", p2_elapsed)

    # ── Phase 3: Convergence Study ───────────────────────────────────
    _report("Phase 3: Convergence study")
    p3_start = time.perf_counter()
    p3_n = cfg.max_phase_convergence_contracts if cfg.max_phase_convergence_contracts else cfg.convergence_contracts
    convergence_contracts = _generate_contracts(rng, p3_n)
    convergence_count = 0

    for contract_idx, contract in enumerate(convergence_contracts):
        if ba and (budget.phase_remaining("convergence", p3_start) <= 0 or budget.exhausted):
            break

        for path_idx, paths in enumerate(cfg.convergence_path_counts):
            if ba and (budget.phase_remaining("convergence", p3_start) <= 0 or budget.exhausted):
                break

            for engine_idx, (engine_name, engine) in enumerate(engines.items()):
                if ba and (budget.phase_remaining("convergence", p3_start) <= 0 or budget.exhausted):
                    break
                if cfg.max_pricings_total is not None and total_pricings_done >= cfg.max_pricings_total:
                    pricing_cap_hit = True
                    break

                if engine_name == "cirq_qmci" and paths > 4_096:
                    continue
                if engine_name == "monaco_mc" and paths > 25_000 and not cfg.trace_full_mode:
                    continue

                features = {
                    "engine": engine_name,
                    "S0": contract["S0"], "K": contract["K"],
                    "r": contract["r"], "sigma": contract["sigma"],
                    "T": contract["T"], "num_paths": paths,
                }

                seed_val = cfg.seed + contract_idx * 10_000 + path_idx * 100 + engine_idx
                cache_key = cache.make_key(features)
                event_notes = ""
                cache_hit = False
                price = float("nan")
                std_err = float("nan")
                wall_ms = 0.0
                engine_failed = False
                total_conv = len(convergence_contracts) * len(cfg.convergence_path_counts) * len(engines)
                prog = (contract_idx * len(cfg.convergence_path_counts) * len(engines) + path_idx * len(engines) + engine_idx) / max(1, total_conv)

                if trace and trace.accepting:
                    trace.emit_event(
                        phase="convergence", phase_index=3,
                        contract_index=contract_idx, engine_order_index=engine_idx,
                        engine=engine_name, contract=contract,
                        num_paths=paths, seed_val=seed_val,
                        event_type="engine_start", cache_key=cache_key,
                        cache_hit=False, similarity_hit=False,
                        similarity_score=0.0,
                        price=float("nan"), std_error=float("nan"),
                        wall_clock_ms=0.0,
                        phase_progress=prog,
                        notes="",
                    )

                pmu_data_p3: Dict[str, Any] = {}
                try:
                    result_cached = cache.get(features, engine_name=engine_name)
                    cache_hit = True
                    price = result_cached["price"]
                    std_err = result_cached["std_error"]
                except KeyError:
                    if trace and trace.pmu is not None and cfg.enable_pmu:
                        trace.pmu.begin_scope(f"p3_{engine_name}_{contract_idx}_{path_idx}")
                    t0 = time.perf_counter()
                    try:
                        result = engine.price(
                            S0=contract["S0"], K=contract["K"], r=contract["r"],
                            sigma=contract["sigma"], T=contract["T"],
                            num_paths=paths, seed=seed_val,
                        )
                        price = result.price
                        std_err = result.std_error
                    except Exception as exc:
                        event_notes = f"{type(exc).__name__}: {exc}"
                        engine_failed = True
                    wall_ms = (time.perf_counter() - t0) * 1000
                    if trace and trace.pmu is not None and cfg.enable_pmu:
                        pmu_metrics_p3 = trace.pmu.end_scope()
                        pmu_data_p3 = pmu_metrics_p3.to_dict()

                    if not engine_failed and math.isfinite(price) and math.isfinite(std_err):
                        cache.put(features, {"price": price, "std_error": std_err},
                                  engine_name=engine_name, compute_time_ms=wall_ms,
                                  stage_elapsed_ms=(time.perf_counter() - p3_start) * 1000.0,
                                  row_semantics="put_single_compute_result")

                hit_history.append(cache_hit)
                convergence_count += 1
                total_pricings_done += 1
                if cfg.max_pricings_total is not None and total_pricings_done >= cfg.max_pricings_total:
                    pricing_cap_hit = True

                if trace and trace.accepting:
                    if cache_hit:
                        trace.emit_event(
                            phase="convergence", phase_index=3,
                            contract_index=contract_idx, engine_order_index=engine_idx,
                            engine=engine_name, contract=contract,
                            num_paths=paths, seed_val=seed_val,
                            event_type="cache_hit", cache_key=cache_key,
                            cache_hit=True, similarity_hit=False,
                            similarity_score=1.0,
                            price=price, std_error=std_err,
                            wall_clock_ms=0.0,
                            phase_progress=prog,
                            notes="",
                        )
                    else:
                        trace.emit_event(
                            phase="convergence", phase_index=3,
                            contract_index=contract_idx, engine_order_index=engine_idx,
                            engine=engine_name, contract=contract,
                            num_paths=paths, seed_val=seed_val,
                            event_type="cache_miss", cache_key=cache_key,
                            cache_hit=False, similarity_hit=False,
                            similarity_score=0.0,
                            price=float("nan"), std_error=float("nan"),
                            wall_clock_ms=0.0,
                            phase_progress=prog,
                            notes="",
                        )

                if trace and trace.accepting:
                    if engine_failed:
                        trace.emit_event(
                            phase="convergence", phase_index=3,
                            contract_index=contract_idx, engine_order_index=engine_idx,
                            engine=engine_name, contract=contract,
                            num_paths=paths, seed_val=seed_val,
                            event_type="engine_error", cache_key=cache_key,
                            cache_hit=False, similarity_hit=False,
                            similarity_score=0.0,
                            price=float("nan"), std_error=float("nan"),
                            wall_clock_ms=wall_ms,
                            phase_progress=prog,
                            notes=event_notes,
                        )
                    elif not cache_hit:
                        trace.emit_event(
                            phase="convergence", phase_index=3,
                            contract_index=contract_idx, engine_order_index=engine_idx,
                            engine=engine_name, contract=contract,
                            num_paths=paths, seed_val=seed_val,
                            event_type="engine_end", cache_key=cache_key,
                            cache_hit=False, similarity_hit=False,
                            similarity_score=0.0,
                            price=price, std_error=std_err,
                            wall_clock_ms=wall_ms,
                            phase_progress=prog,
                            notes="",
                            pmu_override=pmu_data_p3 if pmu_data_p3 else None,
                        )

                csv_writer.log_simulation({
                    "timestamp": time.time(), "run_id": run_id, "engine": engine_name,
                    "contract_id": contract["contract_id"],
                    "S0": contract["S0"], "K": contract["K"], "r": contract["r"],
                    "sigma": contract["sigma"], "T": contract["T"],
                    "num_paths": paths, "price": price, "std_error": std_err,
                    "wall_clock_ms": round(wall_ms, 2), "cache_hit": cache_hit,
                    "cache_key": cache_key[:24],
                    "similarity_score": 1.0 if cache_hit else 0.0,
                    "feature_hash": hash((contract["S0"], contract["K"])) % (10**8),
                })

                if pricing_cap_hit:
                    break
            if pricing_cap_hit:
                break
        if pricing_cap_hit:
            break

    p3_elapsed = time.perf_counter() - p3_start
    phase_results.append(SimulationPhaseResult(
        "convergence", p3_elapsed, convergence_count,
        {"contracts": len(convergence_contracts), "path_counts": cfg.convergence_path_counts},
    ))
    if trace:
        trace.emit_phase_summary("convergence", p3_elapsed)

    # ── Phase 4: Feature Condensation Analysis ───────────────────────
    _report("Phase 4: Feature condensation analysis")
    p4_start = time.perf_counter()

    input_row_count = len(all_features)
    input_feature_dim = int(len(all_features[0])) if all_features else 0
    feature_condensation_summary: Dict[str, Any] = {
        "condensation_status": "skipped",
        "condensation_reason": "insufficient_input_rows",
        "input_row_count": int(input_row_count),
        "input_feature_dim": int(input_feature_dim),
        "output_row_count": 0,
        "output_feature_dim": 0,
    }

    if len(all_features) > 5:
        try:
            feature_matrix = np.array(all_features)
            condenser.fit(feature_matrix, feature_names=[
                          "S0", "K", "r", "sigma", "T"])

            for i, fvec in enumerate(all_features):
                orig_key = f"orig_{i}"
                cond_key = condenser.condensed_cache_key(fvec)
                condenser.track_key(orig_key, cond_key)

            snap = condenser.record_snapshot("final")
            feature_condensation_summary = {
                "condensation_status": "executed",
                "condensation_reason": "",
                "input_row_count": int(feature_matrix.shape[0]),
                "input_feature_dim": int(feature_matrix.shape[1]),
                "output_row_count": int(feature_matrix.shape[0]),
                "output_feature_dim": int(snap.reduced_dims),
            }
            csv_writer.log_feature_condensation({
                "timestamp": time.time(),
                "phase": "final",
                "original_dims": snap.original_dims,
                "reduced_dims": snap.reduced_dims,
                "pca_variance_explained": round(snap.variance_explained, 4),
                "top_features": ",".join(snap.top_features),
                "cache_key_collisions": snap.cache_key_collisions,
                "effective_cache_utilization": round(snap.effective_utilization, 4),
                **feature_condensation_summary,
            })
        except Exception as exc:
            feature_condensation_summary = {
                "condensation_status": "failed",
                "condensation_reason": f"{type(exc).__name__}: {exc}",
                "input_row_count": int(input_row_count),
                "input_feature_dim": int(input_feature_dim),
                "output_row_count": 0,
                "output_feature_dim": 0,
            }
            csv_writer.log_feature_condensation({
                "timestamp": time.time(),
                "phase": "final",
                "original_dims": input_feature_dim,
                "reduced_dims": 0,
                "pca_variance_explained": 0.0,
                "top_features": "",
                "cache_key_collisions": 0,
                "effective_cache_utilization": 0.0,
                **feature_condensation_summary,
            })
    else:
        csv_writer.log_feature_condensation({
            "timestamp": time.time(),
            "phase": "final",
            "original_dims": input_feature_dim,
            "reduced_dims": 0,
            "pca_variance_explained": 0.0,
            "top_features": "",
            "cache_key_collisions": 0,
            "effective_cache_utilization": 0.0,
            **feature_condensation_summary,
        })

    cache.flush_access_log_csv(out_dir / "cache_access_log.csv")

    phase_results.append(SimulationPhaseResult(
        "analysis",
        time.perf_counter() - p4_start,
        len(all_features),
        {"feature_condensation": feature_condensation_summary},
    ))

    total_elapsed = budget.elapsed
    _report(
        f"DONE: {total_elapsed:.1f}s total, {sweep_count + convergence_count} pricings")

    if trace:
        _report("Generating trace outputs and plots...")
        trace.flush_and_plot()
        _report(f"Trace: {trace.event_count} events emitted")

    pmu_supported_any_engine = bool(
        trace and any(bool(evt.get("pmu_available")) for evt in trace._events)
    )
    pmu_measurement_status = (
        "hardware_counter_measured"
        if pmu_supported_any_engine
        else "proxy_or_unavailable"
    )
    optional_capabilities = _runtime_capability_snapshot(engines)

    provenance = BackendExecutionProvenance(
        requested_backend=requested_backend_raw,
        executed_backend="cpu_local",
        execution_environment="local",
        execution_mode_intent=requested_mode_intent,
        execution_mode_actual="cpu_single_node",
        slurm_job_manifest_path=slurm_job_manifest_path,
        hpc_ready=bool(selected_cap.hpc_ready),
        mpi_ready=bool(selected_cap.mpi_ready),
        gpu_ready=bool(selected_cap.gpu_ready),
        execution_deferred_to_hpc=False,
        notes="Executed locally on CPU.",
    )

    summary = {
        "run_id": run_id,
        "total_elapsed_seconds": round(total_elapsed, 2),
        "budget_seconds": budget.total,
        "trace_full_mode": cfg.trace_full_mode,
        "output_dir": str(out_dir.resolve()),
        "output_auto_isolated_from_default": output_auto_isolated,
        "max_pricings_total": cfg.max_pricings_total,
        "total_pricings_phases_2_3": total_pricings_done,
        "pricing_cap_reached": pricing_cap_hit,
        "engine_allowlist": list(cfg.engine_allowlist) if cfg.engine_allowlist else None,
        "phases": [
            {
                "phase": p.phase,
                "elapsed": round(p.elapsed_seconds, 2),
                "records": p.records_produced,
                **p.summary,
            }
            for p in phase_results
        ],
        "cache_final": cache.stats(),
        "feature_condensation": feature_condensation_summary,
        "engines_used": list(engines.keys()),
        "optional_capabilities": optional_capabilities,
        "backend_execution": provenance.to_dict(),
        "requested_backend": provenance.requested_backend,
        "executed_backend": provenance.executed_backend,
        "execution_environment": provenance.execution_environment,
        "execution_mode_intent": provenance.execution_mode_intent,
        "execution_mode_actual": provenance.execution_mode_actual,
        "slurm_job_manifest_path": provenance.slurm_job_manifest_path,
        "hpc_ready": provenance.hpc_ready,
        "mpi_ready": provenance.mpi_ready,
        "gpu_ready": provenance.gpu_ready,
        "execution_deferred_to_hpc": provenance.execution_deferred_to_hpc,
        "pmu_observability": {
            "measurement_status": pmu_measurement_status,
            "pmu_enabled_in_config": bool(cfg.enable_pmu),
            "pmu_supported_any_engine": pmu_supported_any_engine,
            "note": (
                "PMU-like outputs are proxy/derived unless hardware counter support is reported."
                if not pmu_supported_any_engine
                else "At least one engine reported hardware-counter PMU support."
            ),
        },
        "csv_files": {
            "simulation_log": str(csv_writer.sim_log_path.resolve()),
            "cache_patterns": str(csv_writer.cache_pattern_path.resolve()),
            "feature_condensation": str(csv_writer.feature_path.resolve()),
            "cache_access_log": str((out_dir / "cache_access_log.csv").resolve()),
            "run_summary_json": str((out_dir / "qmc_run_summary.json").resolve()),
            "gan_synthetic_data": str((out_dir / "gan_synthetic_data.parquet").resolve()),
        },
    }

    if trace:
        trace_dir = out_dir / cfg.trace_output_subdir
        summary["trace_files"] = {
            "trace_events": str((trace_dir / "trace_events.csv").resolve()),
            "trace_windows": str((trace_dir / "trace_windows.csv").resolve()),
            "trace_polar_embeddings": str((trace_dir / "trace_polar_embeddings.csv").resolve()),
            "trace_similarity_reference": str((trace_dir / "trace_similarity_reference.csv").resolve()),
            "trace_phase_summary": str((trace_dir / "trace_phase_summary.csv").resolve()),
            "trace_engine_summary": str((trace_dir / "trace_engine_summary.csv").resolve()),
        }
        summary["trace_event_count"] = trace.event_count

    summary_path = out_dir / "qmc_run_summary.json"
    import json
    summary_path.write_text(json.dumps(
        summary, indent=2, default=str), encoding="utf-8")

    return summary


def _runtime_capability_snapshot(engines: Dict[str, Any]) -> Dict[str, Any]:
    """Capture optional dependency/runtime capability labels for summaries."""
    caps: Dict[str, Any] = {
        "engine_pool": sorted(list(engines.keys())),
    }

    try:
        from qhpc_cache.gan_data_generator import FinancialGAN

        gan = FinancialGAN()
        caps["financial_gan"] = {
            "available": bool(gan.available()),
            "backend": gan.backend_name,
        }
    except Exception as exc:
        caps["financial_gan"] = {
            "available": False,
            "backend": "error",
            "reason": str(exc),
        }

    try:
        from qhpc_cache.quantum_engines.pyqmc_engine import PyQMCEngine

        pyqmc_available = bool(PyQMCEngine.available())
        caps["pyqmc_engine"] = {
            "available": pyqmc_available,
            "included_in_engine_pool": "pyqmc_vmc" in engines,
            "status_label": (
                "optional_available" if pyqmc_available else "optional_unavailable"
            ),
        }
    except Exception as exc:
        caps["pyqmc_engine"] = {
            "available": False,
            "included_in_engine_pool": False,
            "status_label": "optional_unavailable",
            "reason": str(exc),
        }

    return caps


def _load_engines() -> Dict[str, Any]:
    engines: Dict[str, Any] = {}

    try:
        from qhpc_cache.quantum_engines.quantlib_engine import QuantLibEngine
        eng = QuantLibEngine()
        if eng.available():
            engines["quantlib_mc"] = eng
            print("[engine] loaded quantlib_mc")
        else:
            print("[engine] skipped quantlib_mc: available() returned False")
    except Exception as exc:
        print(f"[engine] skipped quantlib_mc: {exc}")

    try:
        from qhpc_cache.quantum_engines.cirq_engine import CirqEngine
        eng = CirqEngine()
        if eng.available():
            engines["cirq_qmci"] = eng
            print("[engine] loaded cirq_qmci")
        else:
            print("[engine] skipped cirq_qmci: available() returned False")
    except Exception as exc:
        print(f"[engine] skipped cirq_qmci: {exc}")

    try:
        from qhpc_cache.quantum_engines.monaco_engine import MonacoEngine
        eng = MonacoEngine()
        if eng.available():
            engines["monaco_mc"] = eng
            print("[engine] loaded monaco_mc")
        else:
            print("[engine] skipped monaco_mc: available() returned False")
    except Exception as exc:
        print(f"[engine] skipped monaco_mc: {exc}")

    from qhpc_cache.pricing import MonteCarloPricer
    from qhpc_cache.quantum_engines.base_engine import SimulationEngine, SimulationResult

    class _ClassicalWrapper(SimulationEngine):
        @property
        def name(self) -> str:
            return "classical_mc"

        @property
        def engine_type(self) -> str:
            return "classical_mc"

        @classmethod
        def available(cls) -> bool:
            return True

        def price(self, S0, K, r, sigma, T, num_paths=10_000, seed=None) -> SimulationResult:
            t0 = self._start_timer()
            pricer = MonteCarloPricer(
                S0=S0,
                K=K,
                r=r,
                sigma=sigma,
                T=T,
                num_paths=num_paths,
                random_seed=seed,
            )
            result = pricer.price_option()
            return self._make_result(
                price=result.estimated_price,
                std_error=result.standard_error,
                paths_used=num_paths,
                wall_clock_ms=self._elapsed_ms(t0),
                S0=S0,
                K=K,
                r=r,
                sigma=sigma,
                T=T,
                num_paths=num_paths,
            )

    engines["classical_mc"] = _ClassicalWrapper()
    print("[engine] loaded classical_mc")
    return engines


def _run_gan_phase(cfg: QMCSimulationConfig, budget: SimulationBudget, rng, report) -> Any:
    try:
        import pandas as pd
        from qhpc_cache.gan_data_generator import FinancialGAN, GANConfig

        gan = FinancialGAN(GANConfig(epochs=cfg.gan_epochs, seq_len=20))

        real_data_path = Path("data/qhpc_data/daily_universe")
        real_df = None
        if real_data_path.exists():
            for f in real_data_path.iterdir():
                if f.suffix == ".parquet":
                    real_df = pd.read_parquet(f)
                    break
                elif f.suffix == ".csv":
                    real_df = pd.read_csv(f)
                    break

        if real_df is not None and len(real_df) > 100:
            cols = [c for c in ["open", "high", "low",
                                "close", "volume"] if c in real_df.columns]
            if cols:
                train_data = real_df[cols].dropna(
                ).values[:5000].astype(np.float32)
                report(f"  Training GAN on {len(train_data)} real rows...")
                gan.train(train_data, verbose=True)

        report(
            f"  Generating {cfg.gan_num_days}d x {cfg.gan_num_assets} assets...")
        syn_df = gan.generate_dataframe(
            num_days=cfg.gan_num_days, num_assets=cfg.gan_num_assets)
        out = Path(cfg.output_dir) / "gan_synthetic_data.parquet"
        gan.save_generated_dataset(syn_df, out)
        report(f"  GAN: {len(syn_df)} synthetic rows saved")
        return syn_df
    except Exception as exc:
        report(f"  GAN phase failed: {exc}, using parametric fallback")
        return None
