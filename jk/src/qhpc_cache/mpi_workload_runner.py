"""Execute distributed workloads across MPI ranks with per-rank caches.

Works in two modes:
  1. MPI mode  -- mpi4py available and world_size > 1
  2. Single-process fallback -- always available, identical result structure
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from qhpc_cache.cache_store import SimpleCacheStore
from qhpc_cache.mpi_distribution_strategies import get_strategy

try:
    from mpi4py import MPI  # type: ignore

    MPI4PY_AVAILABLE = True
except ImportError:
    MPI4PY_AVAILABLE = False


@dataclass
class RankResult:
    rank: int
    requests_processed: int
    cache_hits: int
    cache_misses: int
    total_compute_ms: float
    total_wall_ms: float
    cache_hit_rate: float
    results: List[Dict] = field(default_factory=list)


@dataclass
class CommMetrics:
    bytes_scattered: int = 0
    bytes_gathered: int = 0
    scatter_time_ms: float = 0.0
    gather_time_ms: float = 0.0
    total_comm_time_ms: float = 0.0
    n_messages: int = 0


@dataclass
class MPIStudyResult:
    strategy_name: str
    world_size: int
    rank_results: List[RankResult] = field(default_factory=list)
    comm_metrics: CommMetrics = field(default_factory=CommMetrics)
    total_wall_ms: float = 0.0
    speedup_vs_single: float = 1.0
    aggregate_cache_hit_rate: float = 0.0


class MPIWorkloadRunner:

    def __init__(self, strategy_name: str = "round_robin") -> None:
        self._strategy_name = strategy_name

    def run(
        self,
        requests: List[Dict],
        engine_loader: Optional[Any] = None,
    ) -> MPIStudyResult:
        if MPI4PY_AVAILABLE:
            comm = MPI.COMM_WORLD
            if comm.Get_size() > 1:
                return self._run_mpi(requests)
        return self._run_single_process(requests)

    # ------------------------------------------------------------------
    # MPI path
    # ------------------------------------------------------------------

    def _run_mpi(self, requests: List[Dict]) -> MPIStudyResult:
        comm = MPI.COMM_WORLD
        rank = comm.Get_rank()
        size = comm.Get_size()

        wall_start = time.perf_counter()
        comm_metrics = CommMetrics()

        if rank == 0:
            strategy = get_strategy(self._strategy_name)
            assignments = strategy.assign(requests, size)
            scatter_data = [assignments.get(r, []) for r in range(size)]
            payload_bytes = len(json.dumps(scatter_data).encode())
            comm_metrics.bytes_scattered = payload_bytes
        else:
            scatter_data = None

        scatter_start = time.perf_counter()
        local_requests = comm.scatter(scatter_data, root=0)
        comm_metrics.scatter_time_ms = (time.perf_counter() - scatter_start) * 1000.0

        local_result = self._execute_rank_workload(local_requests, rank)

        result_payload = {
            "rank": local_result.rank,
            "requests_processed": local_result.requests_processed,
            "cache_hits": local_result.cache_hits,
            "cache_misses": local_result.cache_misses,
            "total_compute_ms": local_result.total_compute_ms,
            "total_wall_ms": local_result.total_wall_ms,
            "cache_hit_rate": local_result.cache_hit_rate,
            "results": local_result.results,
        }

        gather_start = time.perf_counter()
        all_results = comm.gather(result_payload, root=0)
        comm_metrics.gather_time_ms = (time.perf_counter() - gather_start) * 1000.0

        if rank == 0:
            comm_metrics.bytes_gathered = len(json.dumps(all_results).encode())
            comm_metrics.n_messages = size * 2
            comm_metrics.total_comm_time_ms = (
                comm_metrics.scatter_time_ms + comm_metrics.gather_time_ms
            )
            return self._assemble_result(all_results, size, wall_start, comm_metrics)

        return MPIStudyResult(
            strategy_name=self._strategy_name,
            world_size=size,
        )

    # ------------------------------------------------------------------
    # single-process fallback
    # ------------------------------------------------------------------

    def _run_single_process(self, requests: List[Dict]) -> MPIStudyResult:
        wall_start = time.perf_counter()

        strategy = get_strategy(self._strategy_name)
        assignments = strategy.assign(requests, 1)
        rank_requests = assignments.get(0, requests)

        rank_result = self._execute_rank_workload(rank_requests, 0)

        total_wall = (time.perf_counter() - wall_start) * 1000.0

        return MPIStudyResult(
            strategy_name=self._strategy_name,
            world_size=1,
            rank_results=[rank_result],
            comm_metrics=CommMetrics(),
            total_wall_ms=total_wall,
            speedup_vs_single=1.0,
            aggregate_cache_hit_rate=rank_result.cache_hit_rate,
        )

    # ------------------------------------------------------------------
    # per-rank execution
    # ------------------------------------------------------------------

    def _execute_rank_workload(
        self, rank_requests: List[Dict], rank_id: int
    ) -> RankResult:
        cache = SimpleCacheStore(enable_logging=False)
        results: List[Dict] = []
        total_compute_ms = 0.0
        wall_start = time.perf_counter()

        for req in rank_requests:
            features = {
                "S0": req.get("S0", 100.0),
                "K": req.get("K", 105.0),
                "r": req.get("r", 0.05),
                "sigma": req.get("sigma", 0.2),
                "T": req.get("T", 1.0),
                "num_paths": req.get("num_paths", 10_000),
            }

            hit, cached_val = cache.try_get(features, engine_name="mpi_mc")
            if hit:
                results.append(
                    {
                        "request_id": req.get("request_id", ""),
                        "price": cached_val["price"],
                        "std_error": cached_val["std_error"],
                        "cache_hit": True,
                        "compute_ms": 0.0,
                    }
                )
                continue

            price, std_err, comp_ms = self._simple_mc_price(features)
            total_compute_ms += comp_ms

            cache.put(
                features,
                {"price": price, "std_error": std_err},
                engine_name="mpi_mc",
                compute_time_ms=comp_ms,
            )
            results.append(
                {
                    "request_id": req.get("request_id", ""),
                    "price": price,
                    "std_error": std_err,
                    "cache_hit": False,
                    "compute_ms": comp_ms,
                }
            )

        stats = cache.stats()
        wall_ms = (time.perf_counter() - wall_start) * 1000.0
        n = len(rank_requests)

        return RankResult(
            rank=rank_id,
            requests_processed=n,
            cache_hits=stats["hits"],
            cache_misses=stats["misses"],
            total_compute_ms=total_compute_ms,
            total_wall_ms=wall_ms,
            cache_hit_rate=stats["hit_rate"],
            results=results,
        )

    @staticmethod
    def _simple_mc_price(params: Dict) -> Tuple[float, float, float]:
        """European call via classical Monte-Carlo (numpy only)."""
        t0 = time.perf_counter()
        S0 = float(params.get("S0", 100.0))
        K = float(params.get("K", 105.0))
        r = float(params.get("r", 0.05))
        sigma = float(params.get("sigma", 0.2))
        T = float(params.get("T", 1.0))
        num_paths = int(params.get("num_paths", 10_000))

        rng = np.random.default_rng()
        z = rng.standard_normal(num_paths)
        ST = S0 * np.exp((r - 0.5 * sigma**2) * T + sigma * np.sqrt(T) * z)
        payoffs = np.maximum(ST - K, 0.0)
        discounted = np.exp(-r * T) * payoffs
        price = float(np.mean(discounted))
        std_err = float(np.std(discounted, ddof=1) / np.sqrt(num_paths))
        wall_ms = (time.perf_counter() - t0) * 1000.0
        return price, std_err, wall_ms

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _assemble_result(
        self,
        all_results: List[Dict],
        world_size: int,
        wall_start: float,
        comm_metrics: CommMetrics,
    ) -> MPIStudyResult:
        rank_results: List[RankResult] = []
        total_hits = 0
        total_processed = 0

        for rd in all_results:
            rr = RankResult(
                rank=rd["rank"],
                requests_processed=rd["requests_processed"],
                cache_hits=rd["cache_hits"],
                cache_misses=rd["cache_misses"],
                total_compute_ms=rd["total_compute_ms"],
                total_wall_ms=rd["total_wall_ms"],
                cache_hit_rate=rd["cache_hit_rate"],
                results=rd["results"],
            )
            rank_results.append(rr)
            total_hits += rr.cache_hits
            total_processed += rr.requests_processed

        total_wall = (time.perf_counter() - wall_start) * 1000.0
        agg_hit_rate = total_hits / total_processed if total_processed else 0.0

        single_compute = sum(rr.total_compute_ms for rr in rank_results)
        speedup = single_compute / total_wall if total_wall > 0 else 1.0

        return MPIStudyResult(
            strategy_name=self._strategy_name,
            world_size=world_size,
            rank_results=rank_results,
            comm_metrics=comm_metrics,
            total_wall_ms=total_wall,
            speedup_vs_single=round(speedup, 4),
            aggregate_cache_hit_rate=round(agg_hit_rate, 6),
        )
