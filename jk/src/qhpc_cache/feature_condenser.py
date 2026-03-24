"""Feature condensation: map high-dimensional portfolio parameters to compact cache keys.

Tracks how full feature vectors (S0, K, r, sigma, T, engine, paths) get reduced
to cache-friendly representations, measuring information loss and collision rates.
"""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class CondensationRecord:
    timestamp: float
    phase: str
    original_dims: int
    reduced_dims: int
    variance_explained: float
    top_features: List[str]
    cache_key_collisions: int
    effective_utilization: float


class FeatureCondenser:
    """PCA-based dimensionality reduction with collision tracking for cache keys."""

    def __init__(self, n_components: int = 3):
        self.n_components = n_components
        self._feature_names: List[str] = []
        self._pca_components: Optional[np.ndarray] = None
        self._pca_mean: Optional[np.ndarray] = None
        self._pca_explained: Optional[np.ndarray] = None
        self._key_map: Dict[str, List[str]] = {}
        self._records: List[CondensationRecord] = []

    def fit(self, feature_matrix: np.ndarray, feature_names: Optional[List[str]] = None) -> None:
        self._feature_names = feature_names or [f"f{i}" for i in range(feature_matrix.shape[1])]
        n = min(self.n_components, feature_matrix.shape[1], feature_matrix.shape[0])

        self._pca_mean = feature_matrix.mean(axis=0)
        centered = feature_matrix - self._pca_mean

        cov = np.cov(centered, rowvar=False)
        if cov.ndim == 0:
            cov = np.array([[cov]])
        eigvals, eigvecs = np.linalg.eigh(cov)

        idx = np.argsort(eigvals)[::-1][:n]
        self._pca_components = eigvecs[:, idx].T
        total_var = eigvals.sum()
        self._pca_explained = eigvals[idx] / total_var if total_var > 0 else np.zeros(n)

    def transform(self, feature_vector: np.ndarray) -> np.ndarray:
        if self._pca_components is None:
            raise RuntimeError("Call fit() first")
        centered = feature_vector - self._pca_mean
        return centered @ self._pca_components.T

    def condensed_cache_key(self, feature_vector: np.ndarray, precision: int = 4) -> str:
        reduced = self.transform(feature_vector)
        rounded = tuple(round(float(x), precision) for x in reduced)
        return hashlib.sha256(str(rounded).encode()).hexdigest()[:16]

    def track_key(self, original_key: str, condensed_key: str) -> None:
        self._key_map.setdefault(condensed_key, []).append(original_key)

    @property
    def collision_count(self) -> int:
        return sum(1 for v in self._key_map.values() if len(v) > 1)

    @property
    def total_keys(self) -> int:
        return sum(len(v) for v in self._key_map.values())

    @property
    def unique_condensed_keys(self) -> int:
        return len(self._key_map)

    def variance_explained_ratio(self) -> float:
        if self._pca_explained is None:
            return 0.0
        return float(self._pca_explained.sum())

    def top_feature_names(self, n: int = 3) -> List[str]:
        if self._pca_components is None or not self._feature_names:
            return []
        importance = np.abs(self._pca_components[0])
        idx = np.argsort(importance)[::-1][:n]
        return [self._feature_names[i] for i in idx if i < len(self._feature_names)]

    def record_snapshot(self, phase: str) -> CondensationRecord:
        rec = CondensationRecord(
            timestamp=time.time(),
            phase=phase,
            original_dims=len(self._feature_names),
            reduced_dims=self.n_components,
            variance_explained=self.variance_explained_ratio(),
            top_features=self.top_feature_names(),
            cache_key_collisions=self.collision_count,
            effective_utilization=self.unique_condensed_keys / max(1, self.total_keys),
        )
        self._records.append(rec)
        return rec

    @property
    def records(self) -> List[CondensationRecord]:
        return list(self._records)

    def reset_keys(self) -> None:
        self._key_map.clear()
