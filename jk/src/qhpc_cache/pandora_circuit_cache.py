"""Pandora-style circuit cache: similarity-aware reuse layer for quantum circuits.

Wraps exact-match lookup with a structural similarity scan so that circuits
with sufficiently similar gate structures can be reused without recompilation.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from qhpc_cache.circuit_fingerprint import (
    CircuitFingerprint,
    CircuitFingerprintEncoder,
    compute_structural_similarity,
)


@dataclass
class PandoraCacheEntry:
    cache_key: str
    fingerprint: CircuitFingerprint
    finance_params: Dict[str, Any]
    compiled_circuit_repr: str
    compilation_time_ms: float
    reuse_count: int
    last_access_step: int


@dataclass
class PandoraCacheMetrics:
    exact_hits: int
    structural_hits: int
    misses: int
    total_lookups: int
    total_compilation_time_saved_ms: float
    total_adaptation_time_ms: float
    entries: int


class PandoraCircuitCache:
    """Similarity-aware circuit cache with exact and structural matching."""

    def __init__(self, similarity_threshold: float = 0.85) -> None:
        self._similarity_threshold = similarity_threshold
        self._entries: Dict[str, PandoraCacheEntry] = {}
        self._access_step: int = 0
        self._exact_hits: int = 0
        self._structural_hits: int = 0
        self._misses: int = 0
        self._total_lookups: int = 0
        self._compilation_time_saved_ms: float = 0.0
        self._adaptation_time_ms: float = 0.0

    def _build_cache_key(self, finance_params: Dict[str, Any]) -> str:
        canonical = json.dumps(
            {k: finance_params[k] for k in sorted(finance_params)},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def store(
        self,
        finance_params: Dict[str, Any],
        fingerprint: CircuitFingerprint,
        compiled_repr: str,
        compilation_time_ms: float,
    ) -> str:
        """Store a circuit entry. Returns the cache key."""
        self._access_step += 1
        cache_key = self._build_cache_key(finance_params)
        entry = PandoraCacheEntry(
            cache_key=cache_key,
            fingerprint=fingerprint,
            finance_params=dict(finance_params),
            compiled_circuit_repr=compiled_repr,
            compilation_time_ms=compilation_time_ms,
            reuse_count=0,
            last_access_step=self._access_step,
        )
        self._entries[cache_key] = entry
        return cache_key

    def lookup(
        self,
        finance_params: Dict[str, Any],
        fingerprint: CircuitFingerprint,
    ) -> Tuple[str, Optional[PandoraCacheEntry]]:
        """Returns (hit_type, entry) where hit_type is "exact", "structural", or "miss"."""
        self._access_step += 1
        self._total_lookups += 1

        cache_key = self._build_cache_key(finance_params)
        exact = self._exact_lookup(cache_key)
        if exact is not None:
            self._exact_hits += 1
            exact.reuse_count += 1
            exact.last_access_step = self._access_step
            self._compilation_time_saved_ms += exact.compilation_time_ms
            return "exact", exact

        structural = self._structural_lookup(fingerprint)
        if structural is not None:
            self._structural_hits += 1
            structural.reuse_count += 1
            structural.last_access_step = self._access_step
            self._compilation_time_saved_ms += structural.compilation_time_ms * 0.7
            self._adaptation_time_ms += structural.compilation_time_ms * 0.3
            return "structural", structural

        self._misses += 1
        return "miss", None

    def _exact_lookup(self, cache_key: str) -> Optional[PandoraCacheEntry]:
        return self._entries.get(cache_key)

    def _structural_lookup(
        self, fingerprint: CircuitFingerprint
    ) -> Optional[PandoraCacheEntry]:
        best_entry: Optional[PandoraCacheEntry] = None
        best_score = 0.0

        for entry in self._entries.values():
            score, _ = compute_structural_similarity(fingerprint, entry.fingerprint)
            if score >= self._similarity_threshold and score > best_score:
                best_score = score
                best_entry = entry

        return best_entry

    def metrics(self) -> PandoraCacheMetrics:
        return PandoraCacheMetrics(
            exact_hits=self._exact_hits,
            structural_hits=self._structural_hits,
            misses=self._misses,
            total_lookups=self._total_lookups,
            total_compilation_time_saved_ms=self._compilation_time_saved_ms,
            total_adaptation_time_ms=self._adaptation_time_ms,
            entries=len(self._entries),
        )

    def export_evidence(self, output_dir: Path) -> Dict[str, str]:
        """Write pandora_cache_evidence.json to output_dir."""
        output_dir.mkdir(parents=True, exist_ok=True)
        m = self.metrics()
        total = max(m.total_lookups, 1)
        evidence = {
            "exact_hits": m.exact_hits,
            "structural_hits": m.structural_hits,
            "misses": m.misses,
            "total_lookups": m.total_lookups,
            "total_compilation_time_saved_ms": m.total_compilation_time_saved_ms,
            "total_adaptation_time_ms": m.total_adaptation_time_ms,
            "entries": m.entries,
            "similarity_threshold": self._similarity_threshold,
            "hit_rate": (m.exact_hits + m.structural_hits) / total,
            "exact_hit_rate": m.exact_hits / total,
            "structural_hit_rate": m.structural_hits / total,
            "entry_details": [
                {
                    "cache_key": e.cache_key[:16],
                    "qubit_count": e.fingerprint.qubit_count,
                    "depth": e.fingerprint.depth,
                    "reuse_count": e.reuse_count,
                    "compilation_time_ms": e.compilation_time_ms,
                }
                for e in self._entries.values()
            ],
        }
        path = output_dir / "pandora_cache_evidence.json"
        path.write_text(
            json.dumps(evidence, indent=2, cls=CircuitFingerprintEncoder)
        )
        return {"pandora_cache_evidence": str(path)}

    def clear(self) -> None:
        self._entries.clear()
        self._access_step = 0
        self._exact_hits = 0
        self._structural_hits = 0
        self._misses = 0
        self._total_lookups = 0
        self._compilation_time_saved_ms = 0.0
        self._adaptation_time_ms = 0.0
