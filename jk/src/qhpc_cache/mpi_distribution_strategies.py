"""Workload distribution strategies for MPI ranks.

Pure-Python strategies that partition request lists across ranks. No MPI
dependency -- these operate on plain lists and dicts so they can be tested
and profiled on a single machine.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class DistributionMetrics:
    strategy_name: str
    n_ranks: int
    total_requests: int
    requests_per_rank: List[int] = field(default_factory=list)
    load_imbalance_ratio: float = 1.0
    unique_families_per_rank: List[int] = field(default_factory=list)
    expected_intra_rank_reuse_fraction: float = 0.0


class BaseDistributionStrategy(ABC):

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def assign(
        self, requests: List[Dict], n_ranks: int
    ) -> Dict[int, List[Dict]]:
        ...

    def compute_metrics(
        self, assignments: Dict[int, List[Dict]]
    ) -> DistributionMetrics:
        n_ranks = max(len(assignments), 1)
        requests_per_rank = [len(assignments.get(r, [])) for r in range(n_ranks)]
        total = sum(requests_per_rank)
        mean = total / n_ranks if n_ranks else 1.0
        max_req = max(requests_per_rank) if requests_per_rank else 0
        imbalance = max_req / mean if mean > 0 else 1.0

        unique_families: List[int] = []
        reuse_fractions: List[float] = []

        for r in range(n_ranks):
            rank_reqs = assignments.get(r, [])
            families = {req.get("workload_family", "") for req in rank_reqs}
            unique_families.append(len(families))

            if len(rank_reqs) < 2:
                reuse_fractions.append(0.0)
                continue
            hash_counts: Dict[str, int] = defaultdict(int)
            for req in rank_reqs:
                hash_counts[req.get("parameter_hash", "")] += 1
            reused = sum(c for c in hash_counts.values() if c > 1)
            reuse_fractions.append(reused / len(rank_reqs))

        avg_reuse = (
            sum(reuse_fractions) / len(reuse_fractions) if reuse_fractions else 0.0
        )

        return DistributionMetrics(
            strategy_name=self.name,
            n_ranks=n_ranks,
            total_requests=total,
            requests_per_rank=requests_per_rank,
            load_imbalance_ratio=round(imbalance, 6),
            unique_families_per_rank=unique_families,
            expected_intra_rank_reuse_fraction=round(avg_reuse, 6),
        )


class RoundRobinStrategy(BaseDistributionStrategy):
    """Baseline: cycle requests across ranks in arrival order."""

    @property
    def name(self) -> str:
        return "round_robin"

    def assign(
        self, requests: List[Dict], n_ranks: int
    ) -> Dict[int, List[Dict]]:
        buckets: Dict[int, List[Dict]] = {r: [] for r in range(n_ranks)}
        for idx, req in enumerate(requests):
            buckets[idx % n_ranks].append(req)
        return buckets


class CacheAwareStrategy(BaseDistributionStrategy):
    """Route requests with identical parameter_hash to the same rank."""

    @property
    def name(self) -> str:
        return "cache_aware"

    def assign(
        self, requests: List[Dict], n_ranks: int
    ) -> Dict[int, List[Dict]]:
        buckets: Dict[int, List[Dict]] = {r: [] for r in range(n_ranks)}
        for req in requests:
            ph = req.get("parameter_hash", "")
            rank = hash(ph) % n_ranks
            buckets[rank].append(req)
        return buckets


class LocalityAwareStrategy(BaseDistributionStrategy):
    """Group by workload_family to maximise intra-rank temporal locality.

    When there are more families than ranks, multiple families share a rank.
    Families are assigned to the least-loaded rank to approximate balance.
    """

    @property
    def name(self) -> str:
        return "locality_aware"

    def assign(
        self, requests: List[Dict], n_ranks: int
    ) -> Dict[int, List[Dict]]:
        family_groups: Dict[str, List[Dict]] = defaultdict(list)
        for req in requests:
            family_groups[req.get("workload_family", "unknown")].append(req)

        sorted_families = sorted(
            family_groups.keys(), key=lambda f: -len(family_groups[f])
        )

        buckets: Dict[int, List[Dict]] = {r: [] for r in range(n_ranks)}
        rank_loads = [0] * n_ranks

        for family in sorted_families:
            lightest = min(range(n_ranks), key=lambda r: rank_loads[r])
            buckets[lightest].extend(family_groups[family])
            rank_loads[lightest] += len(family_groups[family])

        return buckets


_STRATEGY_REGISTRY: Dict[str, type] = {
    "round_robin": RoundRobinStrategy,
    "cache_aware": CacheAwareStrategy,
    "locality_aware": LocalityAwareStrategy,
}


def get_strategy(name: str) -> BaseDistributionStrategy:
    """Factory: return a strategy instance by short name."""
    key = str(name).strip().lower()
    cls = _STRATEGY_REGISTRY.get(key)
    if cls is None:
        raise ValueError(
            f"Unknown distribution strategy {name!r}. "
            f"Available: {sorted(_STRATEGY_REGISTRY)}"
        )
    return cls()
