"""Regime-aware workload generation for cache research.

Generates workload parameters conditioned on market regime, producing
realistic parameter distributions for each regime type. Regime tags
become categorical features for analysis and SLM training.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from random import Random
from typing import Any, Dict, List, Optional


class MarketRegime(str, Enum):
    CALM_LOW_VOL = "calm_low_vol"
    HIGH_VOL = "high_vol"
    JUMP = "jump"
    CORRELATION_CLUSTER = "correlation_cluster"
    REBALANCE_BURST = "rebalance_burst"
    EVENT_DRIVEN_SHOCK = "event_driven_shock"
    LIQUIDITY_STRESS = "liquidity_stress"


@dataclass
class RegimeConfig:
    """Parameters that define a market regime's workload characteristics."""

    regime: MarketRegime
    vol_range: tuple  # (low, high) for sigma
    spot_drift_scale: float  # how much spot moves between requests
    correlation_strength: float  # 0-1, how correlated successive requests are
    burst_probability: float  # probability of clustered repeat requests
    unique_fraction: float  # fraction of truly unique (non-repeatable) requests
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "regime": self.regime.value,
            "vol_range_low": self.vol_range[0],
            "vol_range_high": self.vol_range[1],
            "spot_drift_scale": self.spot_drift_scale,
            "correlation_strength": self.correlation_strength,
            "burst_probability": self.burst_probability,
            "unique_fraction": self.unique_fraction,
            "description": self.description,
        }


REGIME_CONFIGS: Dict[MarketRegime, RegimeConfig] = {
    MarketRegime.CALM_LOW_VOL: RegimeConfig(
        regime=MarketRegime.CALM_LOW_VOL,
        vol_range=(0.08, 0.18),
        spot_drift_scale=0.003,
        correlation_strength=0.9,
        burst_probability=0.4,
        unique_fraction=0.15,
        description="Low volatility, stable markets. High parameter similarity between requests.",
    ),
    MarketRegime.HIGH_VOL: RegimeConfig(
        regime=MarketRegime.HIGH_VOL,
        vol_range=(0.30, 0.65),
        spot_drift_scale=0.02,
        correlation_strength=0.5,
        burst_probability=0.2,
        unique_fraction=0.35,
        description="Elevated volatility. Wider parameter spread, moderate reuse opportunity.",
    ),
    MarketRegime.JUMP: RegimeConfig(
        regime=MarketRegime.JUMP,
        vol_range=(0.20, 0.80),
        spot_drift_scale=0.06,
        correlation_strength=0.2,
        burst_probability=0.05,
        unique_fraction=0.60,
        description="Jump regime with discontinuous parameter shifts. Low reuse expected.",
    ),
    MarketRegime.CORRELATION_CLUSTER: RegimeConfig(
        regime=MarketRegime.CORRELATION_CLUSTER,
        vol_range=(0.15, 0.30),
        spot_drift_scale=0.008,
        correlation_strength=0.85,
        burst_probability=0.5,
        unique_fraction=0.10,
        description="Cross-sectional clustering with high correlation. Strong similarity reuse.",
    ),
    MarketRegime.REBALANCE_BURST: RegimeConfig(
        regime=MarketRegime.REBALANCE_BURST,
        vol_range=(0.12, 0.28),
        spot_drift_scale=0.005,
        correlation_strength=0.7,
        burst_probability=0.7,
        unique_fraction=0.05,
        description="Rebalance-day burst: many near-identical repricing requests.",
    ),
    MarketRegime.EVENT_DRIVEN_SHOCK: RegimeConfig(
        regime=MarketRegime.EVENT_DRIVEN_SHOCK,
        vol_range=(0.25, 0.55),
        spot_drift_scale=0.04,
        correlation_strength=0.3,
        burst_probability=0.1,
        unique_fraction=0.50,
        description="Event-driven shock: sudden parameter shifts, limited reuse.",
    ),
    MarketRegime.LIQUIDITY_STRESS: RegimeConfig(
        regime=MarketRegime.LIQUIDITY_STRESS,
        vol_range=(0.35, 0.70),
        spot_drift_scale=0.05,
        correlation_strength=0.15,
        burst_probability=0.02,
        unique_fraction=0.75,
        description="Liquidity stress: high churn, near-zero reuse. Stress control.",
    ),
}


def apply_regime_to_request(
    base_request: Dict[str, Any],
    regime: MarketRegime,
    *,
    rng: Optional[Random] = None,
    request_index: int = 0,
) -> Dict[str, Any]:
    """Apply regime-conditioned parameter perturbations to a base request."""
    if rng is None:
        rng = Random(42 + request_index)

    config = REGIME_CONFIGS[regime]
    req = dict(base_request)

    sigma_low, sigma_high = config.vol_range
    req["sigma"] = round(sigma_low + rng.random() * (sigma_high - sigma_low), 6)

    drift = (rng.random() - 0.5) * 2.0 * config.spot_drift_scale
    req["S0"] = round(float(req.get("S0", 100.0)) * (1.0 + drift), 6)
    req["K"] = round(float(req.get("K", 100.0)) * (1.0 + drift * 0.9), 6)

    if rng.random() < config.burst_probability:
        req["random_seed"] = int(req.get("random_seed", 42))
    else:
        req["random_seed"] = int(req.get("random_seed", 42)) + request_index

    req["regime_tag"] = regime.value
    req["regime_vol_range"] = f"{sigma_low}-{sigma_high}"
    req["regime_drift_scale"] = config.spot_drift_scale
    req["regime_unique_fraction"] = config.unique_fraction

    return req


def generate_regime_tagged_workload(
    base_requests: List[Dict[str, Any]],
    regime: MarketRegime,
    *,
    count: int = 100,
    seed: int = 42,
) -> List[Dict[str, Any]]:
    """Generate a regime-tagged workload from base templates."""
    rng = Random(seed)
    config = REGIME_CONFIGS[regime]
    output: List[Dict[str, Any]] = []

    for i in range(count):
        base = base_requests[i % len(base_requests)]
        req = apply_regime_to_request(base, regime, rng=rng, request_index=i)
        req["workload_regime"] = regime.value
        output.append(req)

    return output


def get_regime_metadata() -> List[Dict[str, Any]]:
    """Return metadata for all registered regimes."""
    return [config.to_dict() for config in REGIME_CONFIGS.values()]
