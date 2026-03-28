"""Tests for MPI distribution strategies and scaling study.

All tests run WITHOUT mpi4py installed -- they exercise the pure-Python
strategy logic and the single-process fallback path.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from qhpc_cache.mpi_distribution_strategies import (
    BaseDistributionStrategy,
    CacheAwareStrategy,
    DistributionMetrics,
    LocalityAwareStrategy,
    RoundRobinStrategy,
    get_strategy,
)
from qhpc_cache.mpi_workload_runner import (
    CommMetrics,
    MPIStudyResult,
    MPIWorkloadRunner,
    RankResult,
)
from qhpc_cache.mpi_scaling_study import ScalingStudyConfig, run_mpi_scaling_study


def _make_requests(n: int, families: int = 3, hashes: int = 5) -> list:
    reqs = []
    for i in range(n):
        fam = f"family_{i % families}"
        ph = f"hash_{i % hashes}"
        reqs.append({
            "request_id": f"req_{i}",
            "parameter_hash": ph,
            "feature_hash": f"feat_{i % hashes}",
            "workload_family": fam,
            "lane_id": "lane_a",
            "S0": 100.0,
            "K": 105.0,
            "r": 0.05,
            "sigma": 0.2,
            "T": 1.0,
            "num_paths": 1_000,
        })
    return reqs


class TestRoundRobinDistribution:
    def test_all_requests_assigned_and_balanced(self):
        reqs = _make_requests(10)
        strategy = RoundRobinStrategy()
        assignments = strategy.assign(reqs, 3)

        total_assigned = sum(len(v) for v in assignments.values())
        assert total_assigned == 10

        counts = [len(assignments[r]) for r in range(3)]
        assert max(counts) - min(counts) <= 1


class TestCacheAwareDistribution:
    def test_shared_hash_same_rank(self):
        reqs = _make_requests(20, families=4, hashes=4)
        strategy = CacheAwareStrategy()
        assignments = strategy.assign(reqs, 4)

        hash_to_rank = {}
        for rank_id, rank_reqs in assignments.items():
            for req in rank_reqs:
                ph = req["parameter_hash"]
                if ph in hash_to_rank:
                    assert hash_to_rank[ph] == rank_id, (
                        f"parameter_hash {ph} split across ranks "
                        f"{hash_to_rank[ph]} and {rank_id}"
                    )
                else:
                    hash_to_rank[ph] = rank_id


class TestLocalityAwareDistribution:
    def test_same_family_same_rank(self):
        reqs = _make_requests(15, families=3, hashes=10)
        strategy = LocalityAwareStrategy()
        assignments = strategy.assign(reqs, 5)

        family_to_rank = {}
        for rank_id, rank_reqs in assignments.items():
            for req in rank_reqs:
                fam = req["workload_family"]
                if fam in family_to_rank:
                    assert family_to_rank[fam] == rank_id, (
                        f"family {fam} split across ranks "
                        f"{family_to_rank[fam]} and {rank_id}"
                    )
                else:
                    family_to_rank[fam] = rank_id


class TestDistributionMetrics:
    def test_imbalance_and_reuse(self):
        reqs = _make_requests(12, families=2, hashes=3)
        strategy = CacheAwareStrategy()
        assignments = strategy.assign(reqs, 3)
        metrics = strategy.compute_metrics(assignments)

        assert isinstance(metrics, DistributionMetrics)
        assert metrics.n_ranks == 3
        assert metrics.total_requests == 12
        assert len(metrics.requests_per_rank) == 3
        assert metrics.load_imbalance_ratio >= 1.0
        assert 0.0 <= metrics.expected_intra_rank_reuse_fraction <= 1.0
        assert len(metrics.unique_families_per_rank) == 3


class TestGetStrategyFactory:
    def test_returns_correct_types(self):
        assert isinstance(get_strategy("round_robin"), RoundRobinStrategy)
        assert isinstance(get_strategy("cache_aware"), CacheAwareStrategy)
        assert isinstance(get_strategy("locality_aware"), LocalityAwareStrategy)

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown distribution strategy"):
            get_strategy("nonexistent")


class TestSingleProcessFallback:
    def test_runner_produces_valid_result(self):
        reqs = _make_requests(8, families=2, hashes=3)
        runner = MPIWorkloadRunner(strategy_name="round_robin")
        result = runner.run(reqs)

        assert isinstance(result, MPIStudyResult)
        assert result.world_size == 1
        assert result.strategy_name == "round_robin"
        assert len(result.rank_results) == 1
        assert result.rank_results[0].requests_processed == 8
        assert result.total_wall_ms > 0
        assert 0.0 <= result.aggregate_cache_hit_rate <= 1.0


class TestRankResultStructure:
    def test_fields_present(self):
        rr = RankResult(
            rank=0,
            requests_processed=5,
            cache_hits=2,
            cache_misses=3,
            total_compute_ms=10.0,
            total_wall_ms=15.0,
            cache_hit_rate=0.4,
            results=[],
        )
        assert rr.rank == 0
        assert rr.requests_processed == 5
        assert rr.cache_hits == 2
        assert rr.cache_misses == 3
        assert rr.cache_hit_rate == pytest.approx(0.4)


class TestCommMetricsStructure:
    def test_defaults_and_fields(self):
        cm = CommMetrics()
        assert cm.bytes_scattered == 0
        assert cm.bytes_gathered == 0
        assert cm.scatter_time_ms == 0.0
        assert cm.gather_time_ms == 0.0
        assert cm.total_comm_time_ms == 0.0
        assert cm.n_messages == 0

    def test_custom_values(self):
        cm = CommMetrics(
            bytes_scattered=1024,
            bytes_gathered=2048,
            scatter_time_ms=1.5,
            gather_time_ms=2.5,
            total_comm_time_ms=4.0,
            n_messages=8,
        )
        assert cm.bytes_scattered == 1024
        assert cm.n_messages == 8


class TestStudySmoke:
    def test_smoke_run_produces_outputs(self, tmp_path):
        config = ScalingStudyConfig(
            scale_label="smoke",
            strategies=["round_robin", "cache_aware", "locality_aware"],
            output_dir=tmp_path / "mpi_study_out",
            seed=42,
        )
        summary = run_mpi_scaling_study(config)

        assert "strategies" in summary
        assert len(summary["strategies"]) == 3
        assert summary["total_requests"] > 0

        out = config.output_dir
        assert (out / "mpi_scaling_results.csv").exists()
        assert (out / "mpi_communication_comparison.json").exists()
        assert (out / "mpi_scaling_curve.json").exists()
        assert (out / "rank_cache_metrics.csv").exists()
        assert (out / "mpi_scaling_summary.json").exists()
