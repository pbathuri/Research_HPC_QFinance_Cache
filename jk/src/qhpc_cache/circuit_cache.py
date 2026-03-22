"""Exact-match circuit cache abstractions (in-memory, research scaffold).

This parallels ``SimpleCacheStore`` but speaks the language of **circuit requests**
and **resource estimates** so similarity- and policy-based reuse can evolve
without rewriting the Monte Carlo cache.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Dict

from qhpc_cache.quantum_mapping import (
    FinanceProblemDescriptor,
    QuantumCircuitRequest,
    QuantumResourceEstimate,
)


@dataclass
class CircuitCacheEntry:
    """Single cache line for a logical circuit description (in-memory research store)."""

    cache_key: str
    circuit_request: QuantumCircuitRequest
    compiled_representation_placeholder: str  # **PLACEHOLDER** string (e.g. QASM stub)
    resource_estimate: QuantumResourceEstimate
    reuse_count: int
    last_access_step: int
    source_label: str


@dataclass
class CircuitCacheDecisionContext:
    """Everything a policy might inspect before deciding reuse vs recompile."""

    finance_problem_descriptor: FinanceProblemDescriptor
    quantum_circuit_request: QuantumCircuitRequest
    cache_features: Dict[str, Any]
    expected_reuse_value: float
    expected_compile_cost: float
    expected_accuracy_risk: float


class CircuitCacheStore:
    """In-memory exact key store with simple access statistics."""

    def __init__(self) -> None:
        self._entries: Dict[str, CircuitCacheEntry] = {}
        self._access_step: int = 0
        self._hits: int = 0
        self._misses: int = 0

    @staticmethod
    def build_exact_cache_key(
        circuit_request: QuantumCircuitRequest,
        finance_problem: FinanceProblemDescriptor,
    ) -> str:
        """Stable hash key from structured fields (sorted JSON + SHA256)."""
        payload = {
            "request": asdict(circuit_request),
            "finance": asdict(finance_problem),
        }
        canonical = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def has_exact_match(self, cache_key: str) -> bool:
        return cache_key in self._entries

    def get_exact_match(self, cache_key: str) -> CircuitCacheEntry:
        if cache_key not in self._entries:
            self._misses += 1
            raise KeyError(cache_key)
        self._hits += 1
        entry = self._entries[cache_key]
        return entry

    def put_exact_match(self, entry: CircuitCacheEntry) -> None:
        self._entries[entry.cache_key] = entry

    def record_access(self, cache_key: str) -> None:
        """Bump reuse metadata for an entry if present."""
        self._access_step += 1
        if cache_key not in self._entries:
            return
        entry = self._entries[cache_key]
        updated = CircuitCacheEntry(
            cache_key=entry.cache_key,
            circuit_request=entry.circuit_request,
            compiled_representation_placeholder=entry.compiled_representation_placeholder,
            resource_estimate=entry.resource_estimate,
            reuse_count=entry.reuse_count + 1,
            last_access_step=self._access_step,
            source_label=entry.source_label,
        )
        self._entries[cache_key] = updated

    def stats(self) -> Dict[str, Any]:
        return {
            "hits": self._hits,
            "misses": self._misses,
            "entries": len(self._entries),
            "last_access_step": self._access_step,
        }
