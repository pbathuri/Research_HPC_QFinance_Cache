"""Real approximate similarity matching for cache-pattern inference.

Supports exact key matching, cosine similarity, lightweight LSH bucketing,
and a hybrid mode that combines deterministic signature buckets with
feature-vector proximity.

Similarity matches are observational/inferential only and do not short-circuit
engine execution or return cached numeric outputs.
"""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

_ENGINE_INDEX: Dict[str, int] = {}
_TINY = 1e-12


def _engine_idx(name: str) -> float:
    if name not in _ENGINE_INDEX:
        _ENGINE_INDEX[name] = len(_ENGINE_INDEX)
    return float(_ENGINE_INDEX[name])


def build_similarity_vector(
    S0: float, K: float, r: float, sigma: float, T: float,
    num_paths: int, engine: str, phase_index: int = 0,
    locality_score: float = 0.0, reuse_distance: float = 0.0,
) -> np.ndarray:
    """Deterministic feature vector for similarity comparison."""
    moneyness = S0 / max(K, _TINY)
    return np.array([
        S0 / 500.0,
        K / 500.0,
        moneyness,
        r,
        sigma,
        T,
        math.log1p(num_paths),
        _engine_idx(engine) / max(len(_ENGINE_INDEX), 1),
        phase_index / 4.0,
        locality_score,
        1.0 / (1.0 + reuse_distance) if reuse_distance > 0 else 0.0,
    ], dtype=np.float64)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    dot = float(np.dot(a, b))
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na < _TINY or nb < _TINY:
        return 0.0
    return dot / (na * nb)


def build_lsh_signature(vec: np.ndarray, bucket_bits: int = 12) -> str:
    """Deterministic locality-sensitive hash via random hyperplane projection."""
    rng = np.random.RandomState(seed=42)
    planes = rng.randn(bucket_bits, len(vec))
    bits = (planes @ vec > 0).astype(int)
    raw = "".join(str(b) for b in bits)
    return hashlib.md5(raw.encode()).hexdigest()[:12]


class SimilarityMatcher:
    """Maintains a pool of observed feature vectors for approximate matching."""

    def __init__(
        self,
        method: str = "hybrid",
        threshold: float = 0.92,
        max_candidates: int = 32,
        signature_dims: int = 8,
        bucket_bits: int = 12,
    ):
        self.method = method
        self.threshold = threshold
        self.max_candidates = max_candidates
        self.signature_dims = signature_dims
        self.bucket_bits = bucket_bits

        self._pool: List[Dict[str, Any]] = []
        self._lsh_buckets: Dict[str, List[int]] = defaultdict(list)

    @property
    def pool_size(self) -> int:
        return len(self._pool)

    def add(self, vec: np.ndarray, cache_key_short: str, signature_id: str,
            engine: str, phase: str, event_id: int) -> None:
        idx = len(self._pool)
        entry = {
            "vec": vec, "key": cache_key_short, "sig": signature_id,
            "engine": engine, "phase": phase, "eid": event_id,
        }
        self._pool.append(entry)
        if self.method in ("lsh", "hybrid"):
            lsh = build_lsh_signature(vec, self.bucket_bits)
            self._lsh_buckets[lsh].append(idx)

    def query(self, vec: np.ndarray) -> Tuple[bool, float, str, str, int]:
        """Find the best similar candidate above threshold.

        Returns (hit, score, matched_sig, matched_key, candidate_count).
        """
        if not self._pool:
            return False, 0.0, "", "", 0

        candidates = self._get_candidates(vec)
        if not candidates:
            return False, 0.0, "", "", 0

        best_score = 0.0
        best_entry: Optional[Dict[str, Any]] = None
        for idx in candidates:
            entry = self._pool[idx]
            score = cosine_similarity(vec, entry["vec"])
            if score > best_score:
                best_score = score
                best_entry = entry

        if best_score >= self.threshold and best_entry is not None:
            return (True, best_score, best_entry["sig"],
                    best_entry["key"], len(candidates))

        return False, best_score, "", "", len(candidates)

    def _get_candidates(self, vec: np.ndarray) -> List[int]:
        if self.method == "exact":
            return []

        if self.method == "cosine":
            n = min(self.max_candidates, len(self._pool))
            return list(range(max(0, len(self._pool) - n), len(self._pool)))

        if self.method == "lsh":
            lsh = build_lsh_signature(vec, self.bucket_bits)
            return self._lsh_buckets.get(lsh, [])[-self.max_candidates:]

        # hybrid: union of LSH bucket and recent pool
        lsh = build_lsh_signature(vec, self.bucket_bits)
        bucket_hits = self._lsh_buckets.get(lsh, [])[-self.max_candidates:]
        recent_n = min(self.max_candidates // 2, len(self._pool))
        recent = list(range(max(0, len(self._pool) - recent_n), len(self._pool)))
        combined = list(set(bucket_hits + recent))
        return combined[-self.max_candidates:]
