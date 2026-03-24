"""Application-layer cache trace feature computation.

Implements reuse-distance, working-set, burst/periodicity, and signature
features motivated by stack-distance (IBM), SHiP signature correlation,
Mockingjay reuse-distance prediction, and Telescope scalable telemetry.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from typing import List, Optional, Sequence

import numpy as np


# ── Buckets (deterministic, documented) ──────────────────────────────

def bucket_moneyness(S0: float, K: float) -> str:
    if K <= 0:
        return "deep_itm"
    m = S0 / K
    if m < 0.80:
        return "deep_otm"
    if m < 0.95:
        return "otm"
    if m < 1.05:
        return "near_atm"
    if m < 1.20:
        return "itm"
    return "deep_itm"


def bucket_sigma(sigma: float) -> str:
    if sigma < 0.10:
        return "very_low"
    if sigma < 0.20:
        return "low"
    if sigma < 0.40:
        return "medium"
    if sigma < 0.60:
        return "high"
    return "extreme"


def bucket_maturity(T: float) -> str:
    if T < 0.25:
        return "ultra_short"
    if T < 0.75:
        return "short"
    if T < 1.5:
        return "medium"
    if T < 2.5:
        return "long"
    return "ultra_long"


def bucket_paths(num_paths: int) -> str:
    if num_paths <= 1_000:
        return "1e3"
    if num_paths <= 5_000:
        return "5e3"
    if num_paths <= 10_000:
        return "1e4"
    if num_paths <= 50_000:
        return "5e4"
    if num_paths <= 100_000:
        return "1e5"
    if num_paths <= 500_000:
        return "5e5"
    return "other"


# ── Pattern signature ────────────────────────────────────────────────

def build_pattern_signature(
    engine: str,
    S0: float,
    K: float,
    sigma: float,
    T: float,
    num_paths: int,
    cache_hit: bool,
) -> str:
    parts = [
        engine,
        bucket_moneyness(S0, K),
        bucket_sigma(sigma),
        bucket_maturity(T),
        bucket_paths(num_paths),
        "hit" if cache_hit else "miss",
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


# ── Entropy ──────────────────────────────────────────────────────────

def safe_entropy(values: Sequence[str]) -> float:
    if not values:
        return 0.0
    counts = Counter(values)
    total = len(values)
    ent = 0.0
    for c in counts.values():
        p = c / total
        if p > 0:
            ent -= p * math.log2(p)
    return ent


# ── Reuse distance ───────────────────────────────────────────────────

def compute_reuse_distance(
    event_idx: int,
    last_seen_idx: Optional[int],
) -> Optional[int]:
    if last_seen_idx is None:
        return None
    return event_idx - last_seen_idx


# ── Rolling statistics ───────────────────────────────────────────────

def rolling_unique_count(seq: Sequence[str]) -> int:
    return len(set(seq))


def rolling_working_set(keys: Sequence[str]) -> int:
    return len(set(keys))


def compute_burst_score(flags: Sequence[int]) -> float:
    """Run-length ratio of longest same-value run to window size."""
    if len(flags) < 2:
        return 0.0
    max_run = 1
    current = 1
    for i in range(1, len(flags)):
        if flags[i] == flags[i - 1]:
            current += 1
            max_run = max(max_run, current)
        else:
            current = 1
    return max_run / len(flags)


def compute_periodic_score(flags: Sequence[int]) -> float:
    """Centered FFT magnitude ratio — peak-to-mean of non-DC components."""
    if len(flags) < 8:
        return 0.0
    arr = np.array(flags, dtype=float)
    arr = arr - arr.mean()
    fft = np.abs(np.fft.rfft(arr))
    if len(fft) < 2:
        return 0.0
    non_dc = fft[1:]
    mean_val = non_dc.mean()
    if mean_val < 1e-12:
        return 0.0
    return float(non_dc.max() / mean_val) / 10.0


def compute_locality_score(reuse_distances: Sequence[int]) -> float:
    if not reuse_distances:
        return 0.0
    return 1.0 / (1.0 + float(np.mean(reuse_distances)))


# ── Feature-vector helpers ───────────────────────────────────────────

def feature_l2_norm(S0: float, K: float, r: float, sigma: float, T: float) -> float:
    return math.sqrt(S0**2 + K**2 + r**2 + sigma**2 + T**2)


