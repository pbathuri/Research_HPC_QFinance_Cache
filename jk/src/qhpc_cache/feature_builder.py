"""Feature helpers for cache policy decisions and exact-match cache keys."""

from __future__ import annotations

from typing import Optional


def build_cache_features(
    *,
    instrument_type: str,
    S0: float,
    K: float,
    r: float,
    sigma: float,
    T: float,
    num_paths: int,
    simulation_mode: str = "terminal",
    num_time_steps: int = 12,
    use_antithetic_variates: bool = False,
    use_black_scholes_control_variate: bool = False,
    compare_analytic_black_scholes: bool = False,
    confidence_level: float = 0.95,
    digital_payout_amount: float = 1.0,
    random_seed: Optional[int] = None,
) -> dict:
    """Build cache features used for policy decisions and exact-match reuse.

    The active exact-match key includes all pricing inputs that can affect result
    values or result metadata. This prevents accidental reuse across different
    contracts/parameters.
    """
    return {
        "instrument_type": instrument_type,
        "S0": S0,
        "K": K,
        "r": r,
        "sigma": sigma,
        "T": T,
        "num_paths": num_paths,
        "simulation_mode": simulation_mode,
        "num_time_steps": num_time_steps,
        "use_antithetic_variates": use_antithetic_variates,
        "use_black_scholes_control_variate": use_black_scholes_control_variate,
        "compare_analytic_black_scholes": compare_analytic_black_scholes,
        "confidence_level": confidence_level,
        "digital_payout_amount": digital_payout_amount,
        "random_seed": random_seed,
        # Backward-compatible aliases used by existing policy stubs.
        "volatility": sigma,
        "maturity": T,
        "maturity_in_years": T,
    }


def build_future_circuit_features(
    fragment_depth: int,
    qubit_count: int,
    reuse_count: int,
    similarity_score: float,
) -> dict:
    """Build a feature dict for future circuit-level cache policy input.

    Not connected to active pricing logic yet. Returns a dict with
    fragment_depth, qubit_count, reuse_count, similarity_score.
    """
    return {
        "fragment_depth": fragment_depth,
        "qubit_count": qubit_count,
        "reuse_count": reuse_count,
        "similarity_score": similarity_score,
    }
