"""Canonical option-pricing benchmark workload family.

Locked model-family order:
1) Black-Scholes closed-form baseline
2) Monte Carlo European pricing (GBM)
3) Heston Monte Carlo (Euler full-truncation approximation)
4) Cox-Ross-Rubinstein lattice

This module focuses on workload-structure evidence, not production derivatives
infrastructure. Primary artifacts are CSV/JSON outputs.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import platform
import time
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from qhpc_cache.analytic_pricing import (
    black_scholes_call_delta,
    black_scholes_call_price,
    black_scholes_gamma,
    black_scholes_put_delta,
    black_scholes_put_price,
    black_scholes_theta_call,
    black_scholes_theta_put,
    black_scholes_vega,
)
from qhpc_cache.pricing import MonteCarloPricer
from qhpc_cache.workload_signatures import (
    model_family_label,
    portfolio_family_label,
    workload_family_label,
)


MODEL_FAMILY_BLACK_SCHOLES = "black_scholes_closed_form"
MODEL_FAMILY_MONTE_CARLO_EUROPEAN = "monte_carlo_european"
MODEL_FAMILY_HESTON_MONTE_CARLO = "heston_monte_carlo"
MODEL_FAMILY_CRR_LATTICE = "crr_lattice"

LOCKED_MODEL_FAMILY_ORDER: Tuple[str, ...] = (
    MODEL_FAMILY_BLACK_SCHOLES,
    MODEL_FAMILY_MONTE_CARLO_EUROPEAN,
    MODEL_FAMILY_HESTON_MONTE_CARLO,
    MODEL_FAMILY_CRR_LATTICE,
)


def _safe_mean(series: Any) -> float:
    if series is None or len(series) == 0:
        return 0.0
    return float(series.mean())


def _safe_nunique(series: Any) -> int:
    if series is None or len(series) == 0:
        return 0
    return int(series.dropna().nunique())


def _quantile(series: Any, q: float) -> float:
    if series is None or len(series) == 0:
        return 0.0
    return float(series.quantile(q))


def _workload_family_label(*, variant_label: str, model_family: str, batch_size: int) -> str:
    pf = portfolio_family_label(
        universe_name=variant_label, n_symbols=batch_size, book_tag=model_family
    )
    mf = model_family_label(
        engine_or_model=model_family, path_bucket=variant_label, phase="pricing_workload"
    )
    return workload_family_label(
        pipeline_stage="option_pricing",
        portfolio_family=pf,
        model_family=mf,
        event_stress=False,
    )


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalize_contract(contract: Mapping[str, Any]) -> Dict[str, Any]:
    option_type = str(contract.get("option_type", "call")).strip().lower()
    if option_type not in ("call", "put"):
        raise ValueError(f"unsupported option_type={option_type}")
    out = {
        "contract_id": str(contract.get("contract_id", "")),
        "option_type": option_type,
        "S0": float(contract.get("S0", 100.0)),
        "K": float(contract.get("K", 100.0)),
        "r": float(contract.get("r", 0.03)),
        "sigma": float(contract.get("sigma", 0.2)),
        "T": float(contract.get("T", 1.0)),
        "num_paths": int(contract.get("num_paths", 20_000)),
        "heston_kappa": float(contract.get("heston_kappa", 2.0)),
        "heston_theta": float(contract.get("heston_theta", 0.04)),
        "heston_xi": float(contract.get("heston_xi", 0.5)),
        "heston_rho": float(contract.get("heston_rho", -0.7)),
        "heston_v0": float(
            contract.get("heston_v0", float(contract.get("sigma", 0.2)) ** 2)
        ),
        "heston_steps": int(contract.get("heston_steps", 100)),
        "crr_steps": int(contract.get("crr_steps", 200)),
        "valuation_date": str(contract.get("valuation_date", "")),
    }
    if not out["contract_id"]:
        raw = (
            f"{out['option_type']}|{out['S0']}|{out['K']}|{out['r']}|"
            f"{out['sigma']}|{out['T']}"
        )
        out["contract_id"] = hashlib.sha256(raw.encode()).hexdigest()[:14]
    return out


def _result_row(
    *,
    model_family_id: str,
    contract: Mapping[str, Any],
    price: float,
    std_error: float,
    timing_ms: float,
    status: str = "ok",
    skip_reason: str = "",
    assumptions: str = "",
    supported_contract_types: str = "european_call;european_put",
) -> Dict[str, Any]:
    c = _normalize_contract(contract)
    return {
        "model_family_id": model_family_id,
        "contract_id": c["contract_id"],
        "option_type": c["option_type"],
        "S0": c["S0"],
        "K": c["K"],
        "r": c["r"],
        "sigma": c["sigma"],
        "T": c["T"],
        "num_paths": c["num_paths"],
        "price": float(price),
        "std_error": float(std_error),
        "timing_ms": float(timing_ms),
        "status": status,
        "skip_reason": skip_reason,
        "assumptions": assumptions,
        "supported_contract_types": supported_contract_types,
    }


def price_black_scholes_contract(contract: Mapping[str, Any]) -> Dict[str, Any]:
    """Closed-form European pricing baseline.

    Assumptions:
      - GBM under risk-neutral measure
      - constant rate/volatility
      - no dividends
      - European exercise only
    """
    t0 = time.perf_counter()
    c = _normalize_contract(contract)
    try:
        if c["option_type"] == "call":
            price = black_scholes_call_price(c["S0"], c["K"], c["r"], c["sigma"], c["T"])
        else:
            price = black_scholes_put_price(c["S0"], c["K"], c["r"], c["sigma"], c["T"])
        return _result_row(
            model_family_id=MODEL_FAMILY_BLACK_SCHOLES,
            contract=c,
            price=price,
            std_error=0.0,
            timing_ms=(time.perf_counter() - t0) * 1000.0,
            assumptions="closed_form_bsm_no_dividends_constant_params",
        )
    except Exception as exc:
        return _result_row(
            model_family_id=MODEL_FAMILY_BLACK_SCHOLES,
            contract=c,
            price=float("nan"),
            std_error=float("nan"),
            timing_ms=(time.perf_counter() - t0) * 1000.0,
            status="skipped",
            skip_reason=f"pricing_failed:{type(exc).__name__}",
            assumptions="closed_form_bsm_no_dividends_constant_params",
        )


def price_monte_carlo_european_contract(
    contract: Mapping[str, Any],
    *,
    random_seed: int = 42,
) -> Dict[str, Any]:
    """GBM Monte Carlo for European contracts (terminal payoff only)."""
    t0 = time.perf_counter()
    c = _normalize_contract(contract)
    payoff = "european_call" if c["option_type"] == "call" else "european_put"
    try:
        pricer = MonteCarloPricer(
            S0=c["S0"],
            K=c["K"],
            r=c["r"],
            sigma=c["sigma"],
            T=c["T"],
            num_paths=c["num_paths"],
            payoff_type=payoff,
            simulation_mode="terminal",
            compare_analytic_black_scholes=False,
            random_seed=random_seed,
        )
        res = pricer.price_option()
        return _result_row(
            model_family_id=MODEL_FAMILY_MONTE_CARLO_EUROPEAN,
            contract=c,
            price=res.estimated_price,
            std_error=res.standard_error,
            timing_ms=(time.perf_counter() - t0) * 1000.0,
            assumptions="gbm_monte_carlo_terminal_payoff_european",
        )
    except Exception as exc:
        return _result_row(
            model_family_id=MODEL_FAMILY_MONTE_CARLO_EUROPEAN,
            contract=c,
            price=float("nan"),
            std_error=float("nan"),
            timing_ms=(time.perf_counter() - t0) * 1000.0,
            status="skipped",
            skip_reason=f"pricing_failed:{type(exc).__name__}",
            assumptions="gbm_monte_carlo_terminal_payoff_european",
        )


def _heston_mc_price(
    *,
    S0: float,
    K: float,
    r: float,
    T: float,
    option_type: str,
    v0: float,
    kappa: float,
    theta: float,
    xi: float,
    rho: float,
    n_paths: int,
    n_steps: int,
    seed: int,
) -> Tuple[float, float]:
    import numpy as np

    if n_paths < 2 or n_steps < 1:
        return float("nan"), float("nan")
    dt = T / max(1, n_steps)
    sqrt_dt = float(np.sqrt(max(1e-12, dt)))
    rng = np.random.default_rng(seed)
    s = np.full(n_paths, float(S0), dtype=float)
    v = np.full(n_paths, float(max(0.0, v0)), dtype=float)

    for _ in range(n_steps):
        z1 = rng.standard_normal(n_paths)
        z2 = rng.standard_normal(n_paths)
        w1 = z1
        w2 = rho * z1 + float(np.sqrt(max(0.0, 1.0 - rho * rho))) * z2
        v_clip = np.maximum(v, 0.0)
        v = v + kappa * (theta - v_clip) * dt + xi * np.sqrt(v_clip) * sqrt_dt * w2
        v = np.maximum(v, 0.0)
        s = s * np.exp((r - 0.5 * v) * dt + np.sqrt(v) * sqrt_dt * w1)

    if option_type == "call":
        payoff = np.maximum(s - K, 0.0)
    else:
        payoff = np.maximum(K - s, 0.0)
    disc = float(np.exp(-r * T))
    dp = disc * payoff
    price = float(np.mean(dp))
    std_error = float(np.std(dp, ddof=1) / np.sqrt(max(1, len(dp))))
    return price, std_error


def price_heston_monte_carlo_contract(
    contract: Mapping[str, Any],
    *,
    random_seed: int = 42,
) -> Dict[str, Any]:
    """Heston Monte Carlo (Euler full-truncation approximation).

    Assumptions:
      - stochastic variance with mean reversion
      - full-truncation Euler discretization
      - European exercise only
    """
    t0 = time.perf_counter()
    c = _normalize_contract(contract)
    try:
        price, se = _heston_mc_price(
            S0=c["S0"],
            K=c["K"],
            r=c["r"],
            T=c["T"],
            option_type=c["option_type"],
            v0=c["heston_v0"],
            kappa=c["heston_kappa"],
            theta=c["heston_theta"],
            xi=c["heston_xi"],
            rho=c["heston_rho"],
            n_paths=c["num_paths"],
            n_steps=c["heston_steps"],
            seed=random_seed,
        )
        status = "ok" if price == price else "skipped"
        skip_reason = "" if status == "ok" else "invalid_heston_output"
        return _result_row(
            model_family_id=MODEL_FAMILY_HESTON_MONTE_CARLO,
            contract=c,
            price=price,
            std_error=se,
            timing_ms=(time.perf_counter() - t0) * 1000.0,
            status=status,
            skip_reason=skip_reason,
            assumptions="heston_mc_euler_full_truncation_approximation",
        )
    except Exception as exc:
        return _result_row(
            model_family_id=MODEL_FAMILY_HESTON_MONTE_CARLO,
            contract=c,
            price=float("nan"),
            std_error=float("nan"),
            timing_ms=(time.perf_counter() - t0) * 1000.0,
            status="skipped",
            skip_reason=f"heston_failed:{type(exc).__name__}",
            assumptions="heston_mc_euler_full_truncation_approximation",
        )


def _crr_price(
    *,
    S0: float,
    K: float,
    r: float,
    sigma: float,
    T: float,
    steps: int,
    option_type: str,
) -> Optional[float]:
    import math
    import numpy as np

    if steps < 1 or T <= 0.0 or sigma <= 0.0:
        return None
    dt = T / steps
    u = math.exp(sigma * math.sqrt(dt))
    d = 1.0 / u
    disc = math.exp(-r * dt)
    p = (math.exp(r * dt) - d) / (u - d)
    if p < 0.0 or p > 1.0:
        return None
    j = np.arange(steps + 1)
    sT = S0 * (u**j) * (d ** (steps - j))
    if option_type == "call":
        values = np.maximum(sT - K, 0.0)
    else:
        values = np.maximum(K - sT, 0.0)
    for _ in range(steps):
        values = disc * (p * values[1:] + (1.0 - p) * values[:-1])
    return float(values[0])


def price_crr_lattice_contract(contract: Mapping[str, Any]) -> Dict[str, Any]:
    """CRR binomial lattice (European exercise baseline)."""
    t0 = time.perf_counter()
    c = _normalize_contract(contract)
    try:
        price = _crr_price(
            S0=c["S0"],
            K=c["K"],
            r=c["r"],
            sigma=c["sigma"],
            T=c["T"],
            steps=max(1, c["crr_steps"]),
            option_type=c["option_type"],
        )
        if price is None:
            return _result_row(
                model_family_id=MODEL_FAMILY_CRR_LATTICE,
                contract=c,
                price=float("nan"),
                std_error=float("nan"),
                timing_ms=(time.perf_counter() - t0) * 1000.0,
                status="skipped",
                skip_reason="invalid_crr_probability_or_params",
                assumptions="crr_binomial_lattice_european",
            )
        return _result_row(
            model_family_id=MODEL_FAMILY_CRR_LATTICE,
            contract=c,
            price=price,
            std_error=0.0,
            timing_ms=(time.perf_counter() - t0) * 1000.0,
            assumptions="crr_binomial_lattice_european",
        )
    except Exception as exc:
        return _result_row(
            model_family_id=MODEL_FAMILY_CRR_LATTICE,
            contract=c,
            price=float("nan"),
            std_error=float("nan"),
            timing_ms=(time.perf_counter() - t0) * 1000.0,
            status="skipped",
            skip_reason=f"crr_failed:{type(exc).__name__}",
            assumptions="crr_binomial_lattice_european",
        )


def _resolve_default_rate(rates_frame: Optional[Any], *, valuation_date: str) -> float:
    import pandas as pd

    if rates_frame is None or len(rates_frame) == 0:
        return 0.03
    rf = rates_frame.copy()
    dcol = "date" if "date" in rf.columns else rf.columns[0]
    rcol = "risk_free_rate" if "risk_free_rate" in rf.columns else rf.columns[1]
    rf[dcol] = pd.to_datetime(rf[dcol], errors="coerce").dt.normalize()
    target = pd.to_datetime(valuation_date, errors="coerce").normalize()
    row = rf.loc[rf[dcol] == target]
    if len(row):
        val = pd.to_numeric(row[rcol], errors="coerce").dropna()
        if len(val):
            return float(val.iloc[0])
    rr = pd.to_numeric(rf[rcol], errors="coerce").dropna()
    return float(rr.mean()) if len(rr) else 0.03


def build_contract_batch(
    *,
    batch_id: str,
    option_types: Sequence[str] = ("call", "put"),
    spot_grid: Sequence[float] = (80.0, 100.0, 120.0),
    strike_grid: Sequence[float] = (80.0, 100.0, 120.0),
    sigma_grid: Sequence[float] = (0.15, 0.25),
    maturity_grid: Sequence[float] = (0.5, 1.0),
    base_rate: Optional[float] = None,
    rates_frame: Optional[Any] = None,
    num_paths: int = 20_000,
    valuation_date: str = "2020-01-02",
) -> Any:
    """Build deterministic benchmark contract batch from controlled parameter grid."""
    import pandas as pd

    rate = (
        float(base_rate)
        if base_rate is not None
        else _resolve_default_rate(rates_frame, valuation_date=valuation_date)
    )
    out: List[Dict[str, Any]] = []
    idx = 0
    for otype in option_types:
        for s0 in spot_grid:
            for k in strike_grid:
                for sig in sigma_grid:
                    for t in maturity_grid:
                        cid = f"{batch_id}::c{idx:05d}"
                        out.append(
                            {
                                "batch_id": batch_id,
                                "contract_id": cid,
                                "option_type": str(otype).lower(),
                                "S0": float(s0),
                                "K": float(k),
                                "r": rate,
                                "sigma": float(sig),
                                "T": float(t),
                                "num_paths": int(num_paths),
                                "valuation_date": valuation_date,
                            }
                        )
                        idx += 1
    return pd.DataFrame(out)


def build_contract_batch_family(
    *,
    family_id: str = "deterministic_contract_batch_family",
    batch_sizes: Sequence[int] = (16, 32, 64),
    rates_frame: Optional[Any] = None,
) -> Any:
    """Build deterministic repeated contract batch family."""
    import pandas as pd

    base = build_contract_batch(
        batch_id=f"{family_id}::base",
        rates_frame=rates_frame,
        num_paths=10_000,
    )
    frames = []
    for i, n in enumerate(batch_sizes):
        batch = base.head(int(max(1, n))).copy()
        bid = f"{family_id}::batch_{i:02d}_n{int(n)}"
        batch["batch_id"] = bid
        batch["batch_size"] = int(len(batch))
        batch["batch_family_id"] = family_id
        batch["parameter_grid_marker"] = hashlib.sha256(
            json.dumps(
                {
                    "spots": sorted(batch["S0"].unique().tolist()),
                    "strikes": sorted(batch["K"].unique().tolist()),
                    "sigmas": sorted(batch["sigma"].unique().tolist()),
                    "maturities": sorted(batch["T"].unique().tolist()),
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()[:14]
        frames.append(batch)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _mac_degrade_contract_batches(
    batches: Any,
    *,
    max_contracts: int,
    max_paths_per_contract: int,
) -> Tuple[Any, List[str]]:
    if batches is None or len(batches) == 0:
        return batches, []
    if platform.system().lower() != "darwin":
        return batches, []
    notes: List[str] = []
    out = batches.copy()
    if len(out) > max_contracts:
        notes.append(
            f"mac_scope_degraded_pricing_contracts original={len(out)} capped={max_contracts}"
        )
        out = out.head(max_contracts).copy()
    if "num_paths" in out.columns:
        over = out["num_paths"] > max_paths_per_contract
        if over.any():
            n = int(over.sum())
            notes.append(f"hpc_deferred::high_path_contracts={n}")
            out.loc[over, "num_paths"] = int(max_paths_per_contract)
    return out, notes


def _family_pricer(model_family_id: str):
    if model_family_id == MODEL_FAMILY_BLACK_SCHOLES:
        return price_black_scholes_contract
    if model_family_id == MODEL_FAMILY_MONTE_CARLO_EUROPEAN:
        return price_monte_carlo_european_contract
    if model_family_id == MODEL_FAMILY_HESTON_MONTE_CARLO:
        return price_heston_monte_carlo_contract
    if model_family_id == MODEL_FAMILY_CRR_LATTICE:
        return price_crr_lattice_contract
    raise ValueError(f"unknown model_family_id={model_family_id}")


def build_pricing_family_bundle(
    contracts: Any,
    *,
    model_family_order: Sequence[str] = LOCKED_MODEL_FAMILY_ORDER,
    seed: int = 42,
) -> Any:
    """Run locked-order model-family comparison for contract set."""
    import pandas as pd

    if contracts is None or len(contracts) == 0:
        return pd.DataFrame()
    rows: List[Dict[str, Any]] = []
    for family_rank, family in enumerate(model_family_order, start=1):
        pricer = _family_pricer(family)
        for ci, c in enumerate(contracts.to_dict(orient="records")):
            if family in (
                MODEL_FAMILY_MONTE_CARLO_EUROPEAN,
                MODEL_FAMILY_HESTON_MONTE_CARLO,
            ):
                row = pricer(c, random_seed=seed + ci)  # type: ignore[misc]
            else:
                row = pricer(c)
            row["model_family_rank"] = family_rank
            row["workload_family_label"] = _workload_family_label(
                variant_label="model_family_compare_price_only",
                model_family=family,
                batch_size=1,
            )
            rows.append(row)
    return pd.DataFrame(rows)


def compare_pricing_model_families(pricing_results: Any) -> Any:
    """Aggregate model-family comparison summary."""
    if pricing_results is None or len(pricing_results) == 0:
        return pricing_results.head(0) if pricing_results is not None else None
    ok = pricing_results.loc[pricing_results["status"] == "ok"].copy()
    if len(ok) == 0:
        return pricing_results.head(0)
    grp = ok.groupby(["model_family_rank", "model_family_id"], dropna=False).agg(
        contract_count=("contract_id", "nunique"),
        mean_price=("price", "mean"),
        mean_std_error=("std_error", "mean"),
        timing_ms_mean=("timing_ms", "mean"),
        timing_ms_p90=("timing_ms", lambda s: _quantile(s, 0.90)),
        workload_family_label=("workload_family_label", "first"),
    )
    return grp.reset_index().sort_values("model_family_rank").reset_index(drop=True)


def run_batch_pricing(
    contract_batch_family: Any,
    *,
    model_family_order: Sequence[str] = LOCKED_MODEL_FAMILY_ORDER,
    seed: int = 42,
) -> Any:
    """Run repeated pricing across deterministic contract batches."""
    import pandas as pd

    if contract_batch_family is None or len(contract_batch_family) == 0:
        return pd.DataFrame()
    rows: List[Dict[str, Any]] = []
    for family_rank, family in enumerate(model_family_order, start=1):
        pricer = _family_pricer(family)
        for i, c in enumerate(contract_batch_family.to_dict(orient="records")):
            if family in (
                MODEL_FAMILY_MONTE_CARLO_EUROPEAN,
                MODEL_FAMILY_HESTON_MONTE_CARLO,
            ):
                row = pricer(c, random_seed=seed + i)  # type: ignore[misc]
            else:
                row = pricer(c)
            row["batch_id"] = c.get("batch_id", "")
            row["batch_size"] = int(c.get("batch_size", 0) or 0)
            row["batch_family_id"] = c.get("batch_family_id", "")
            row["parameter_grid_marker"] = c.get("parameter_grid_marker", "")
            row["model_family_rank"] = family_rank
            row["workload_variant_label"] = "contract_batch_price_only"
            row["workload_family_label"] = _workload_family_label(
                variant_label="contract_batch_price_only",
                model_family=family,
                batch_size=int(c.get("batch_size", 1) or 1),
            )
            rows.append(row)
    return pd.DataFrame(rows)


def _compute_greeks_for_contract(
    contract: Mapping[str, Any],
    *,
    family_id: str,
    base_price: float,
    seed: int,
) -> Dict[str, Any]:
    c = _normalize_contract(contract)
    greek_calls = 0
    if family_id == MODEL_FAMILY_BLACK_SCHOLES:
        # Exact analytic Greeks under Black-Scholes assumptions.
        if c["option_type"] == "call":
            delta = black_scholes_call_delta(c["S0"], c["K"], c["r"], c["sigma"], c["T"])
            theta = black_scholes_theta_call(c["S0"], c["K"], c["r"], c["sigma"], c["T"])
        else:
            delta = black_scholes_put_delta(c["S0"], c["K"], c["r"], c["sigma"], c["T"])
            theta = black_scholes_theta_put(c["S0"], c["K"], c["r"], c["sigma"], c["T"])
        gamma = black_scholes_gamma(c["S0"], c["K"], c["r"], c["sigma"], c["T"])
        vega = black_scholes_vega(c["S0"], c["K"], c["r"], c["sigma"], c["T"])
        greek_calls = 1
        return {
            "delta": float(delta),
            "gamma": float(gamma),
            "vega": float(vega),
            "theta": float(theta),
            "greek_repricing_calls": greek_calls,
            "greeks_method": "analytic",
            "supported_greeks": "delta;gamma;vega;theta",
        }

    pricer = _family_pricer(family_id)
    hS = max(1e-4, 0.01 * c["S0"])
    hV = max(1e-5, 0.02 * c["sigma"])
    hT = max(1e-4, min(1.0 / 365.0, 0.05 * c["T"] if c["T"] > 0 else 1.0 / 365.0))

    def p(mod: Dict[str, Any], offset: int) -> float:
        nonlocal greek_calls
        greek_calls += 1
        if family_id in (MODEL_FAMILY_MONTE_CARLO_EUROPEAN, MODEL_FAMILY_HESTON_MONTE_CARLO):
            out = pricer(mod, random_seed=seed + offset)  # type: ignore[misc]
        else:
            out = pricer(mod)
        return float(out.get("price", float("nan")))

    c_up = dict(c)
    c_dn = dict(c)
    c_up["S0"] = c["S0"] + hS
    c_dn["S0"] = max(1e-6, c["S0"] - hS)
    p_up = p(c_up, 11)
    p_dn = p(c_dn, 17)
    delta = (p_up - p_dn) / (2.0 * hS)
    gamma = (p_up - 2.0 * base_price + p_dn) / (hS * hS)

    v_up = dict(c)
    v_dn = dict(c)
    v_up["sigma"] = c["sigma"] + hV
    v_dn["sigma"] = max(1e-6, c["sigma"] - hV)
    pv_up = p(v_up, 23)
    pv_dn = p(v_dn, 29)
    vega = (pv_up - pv_dn) / (2.0 * hV)

    t_up = dict(c)
    t_dn = dict(c)
    t_up["T"] = c["T"] + hT
    t_dn["T"] = max(1e-6, c["T"] - hT)
    pt_up = p(t_up, 31)
    pt_dn = p(t_dn, 37)
    theta = -(pt_up - pt_dn) / (2.0 * hT)

    return {
        "delta": float(delta),
        "gamma": float(gamma),
        "vega": float(vega),
        "theta": float(theta),
        "greek_repricing_calls": greek_calls,
        "greeks_method": "finite_difference",
        "supported_greeks": "delta;gamma;vega;theta",
    }


def run_greeks_batch(
    price_batch_results: Any,
    *,
    seed: int = 42,
) -> Any:
    """Run Greeks workload layered on top of price-only batch results."""
    import pandas as pd

    if price_batch_results is None or len(price_batch_results) == 0:
        return pd.DataFrame()
    ok = price_batch_results.loc[price_batch_results["status"] == "ok"].copy()
    if len(ok) == 0:
        return pd.DataFrame()
    rows: List[Dict[str, Any]] = []
    for i, r in ok.iterrows():
        contract = {
            "contract_id": r["contract_id"],
            "option_type": r["option_type"],
            "S0": r["S0"],
            "K": r["K"],
            "r": r["r"],
            "sigma": r["sigma"],
            "T": r["T"],
            "num_paths": r.get("num_paths", 10_000),
            "heston_kappa": r.get("heston_kappa", 2.0),
            "heston_theta": r.get("heston_theta", 0.04),
            "heston_xi": r.get("heston_xi", 0.5),
            "heston_rho": r.get("heston_rho", -0.7),
            "heston_v0": r.get("heston_v0", float(r.get("sigma", 0.2)) ** 2),
            "heston_steps": r.get("heston_steps", 100),
            "crr_steps": r.get("crr_steps", 200),
        }
        t0 = time.perf_counter()
        try:
            g = _compute_greeks_for_contract(
                contract,
                family_id=str(r["model_family_id"]),
                base_price=float(r["price"]),
                seed=seed + int(i),
            )
            row = dict(r.to_dict())
            row.update(g)
            row["greeks_timing_ms"] = (time.perf_counter() - t0) * 1000.0
            row["workload_variant_label"] = "contract_batch_price_plus_greeks"
            row["workload_family_label"] = _workload_family_label(
                variant_label="contract_batch_price_plus_greeks",
                model_family=str(r["model_family_id"]),
                batch_size=int(r.get("batch_size", 1) or 1),
            )
            rows.append(row)
        except Exception as exc:
            row = dict(r.to_dict())
            row.update(
                {
                    "delta": float("nan"),
                    "gamma": float("nan"),
                    "vega": float("nan"),
                    "theta": float("nan"),
                    "greek_repricing_calls": 0,
                    "greeks_method": "unavailable",
                    "supported_greeks": "",
                    "greeks_timing_ms": (time.perf_counter() - t0) * 1000.0,
                    "status": "skipped",
                    "skip_reason": f"greeks_failed:{type(exc).__name__}",
                    "workload_variant_label": "contract_batch_price_plus_greeks",
                    "workload_family_label": _workload_family_label(
                        variant_label="contract_batch_price_plus_greeks",
                        model_family=str(r["model_family_id"]),
                        batch_size=int(r.get("batch_size", 1) or 1),
                    ),
                }
            )
            rows.append(row)
    return pd.DataFrame(rows)


def compare_price_only_vs_price_plus_greeks(
    *,
    price_only_results: Any,
    price_plus_greeks_results: Any,
) -> Any:
    """Compare repeated price-only vs price+Greeks workload structures."""
    import pandas as pd

    rows = []
    for label, frame in (
        ("price_only", price_only_results),
        ("price_plus_greeks", price_plus_greeks_results),
    ):
        if frame is None or len(frame) == 0:
            continue
        rows.append(
            {
                "workload_variant_label": label,
                "row_count": int(len(frame)),
                "contract_count": _safe_nunique(frame["contract_id"]) if "contract_id" in frame.columns else 0,
                "model_family_count": _safe_nunique(frame["model_family_id"]) if "model_family_id" in frame.columns else 0,
                "greeks_count": 4 if label == "price_plus_greeks" else 0,
                "timing_ms_mean": _safe_mean(frame["timing_ms"]) if "timing_ms" in frame.columns else 0.0,
                "greeks_timing_ms_mean": _safe_mean(frame.get("greeks_timing_ms", [])),
                "repeated_pricing_call_count": int(frame.get("greek_repricing_calls", pd.Series(dtype=float)).sum()) if label == "price_plus_greeks" else int(len(frame)),
            }
        )
    return pd.DataFrame(rows)


def summarize_contract_batch_workload(price_batch_results: Any) -> Any:
    """Summarize deterministic contract-batch workload properties."""
    if price_batch_results is None or len(price_batch_results) == 0:
        return price_batch_results.head(0) if price_batch_results is not None else None
    grp = price_batch_results.groupby(["batch_family_id", "batch_id"], dropna=False).agg(
        batch_size=("contract_id", "nunique"),
        model_family_count=("model_family_id", "nunique"),
        row_count=("contract_id", "size"),
        parameter_grid_width=("parameter_grid_marker", "nunique"),
        timing_ms_mean=("timing_ms", "mean"),
        timing_ms_p90=("timing_ms", lambda s: _quantile(s, 0.90)),
    )
    return grp.reset_index().sort_values(["batch_family_id", "batch_id"]).reset_index(drop=True)


def compare_closed_form_vs_simulation(pricing_results: Any) -> Any:
    """Compare Black-Scholes baseline versus simulation families."""
    import pandas as pd

    if pricing_results is None or len(pricing_results) == 0:
        return pd.DataFrame()
    ok = pricing_results.loc[pricing_results["status"] == "ok"].copy()
    if len(ok) == 0:
        return pd.DataFrame()
    base = ok.loc[ok["model_family_id"] == MODEL_FAMILY_BLACK_SCHOLES, ["contract_id", "price"]].rename(
        columns={"price": "price_bs"}
    )
    sim = ok.loc[ok["model_family_id"] != MODEL_FAMILY_BLACK_SCHOLES].copy()
    merged = sim.merge(base, on="contract_id", how="left")
    merged["abs_price_gap_vs_bs"] = (merged["price"] - merged["price_bs"]).abs()
    out = merged.groupby("model_family_id", dropna=False).agg(
        contract_count=("contract_id", "nunique"),
        mean_abs_price_gap_vs_bs=("abs_price_gap_vs_bs", "mean"),
        mean_timing_ms=("timing_ms", "mean"),
    )
    out = out.reset_index()
    out["comparison_id"] = "closed_form_vs_simulation"
    return out


def compare_model_family_timing(pricing_results: Any) -> Any:
    """Timing-focused model family comparison."""
    if pricing_results is None or len(pricing_results) == 0:
        return pricing_results.head(0) if pricing_results is not None else None
    ok = pricing_results.loc[pricing_results["status"] == "ok"].copy()
    grp = ok.groupby("model_family_id", dropna=False).agg(
        timing_ms_mean=("timing_ms", "mean"),
        timing_ms_p50=("timing_ms", lambda s: _quantile(s, 0.50)),
        timing_ms_p90=("timing_ms", lambda s: _quantile(s, 0.90)),
        timing_ms_p99=("timing_ms", lambda s: _quantile(s, 0.99)),
        contract_count=("contract_id", "nunique"),
    )
    return grp.reset_index()


def compare_contract_batch_workloads(price_batch_results: Any) -> Any:
    """Compare repeated deterministic contract batches."""
    if price_batch_results is None or len(price_batch_results) == 0:
        return price_batch_results.head(0) if price_batch_results is not None else None
    grp = price_batch_results.groupby(["batch_family_id", "batch_id"], dropna=False).agg(
        row_count=("contract_id", "size"),
        batch_size=("contract_id", "nunique"),
        model_family_count=("model_family_id", "nunique"),
        timing_ms_mean=("timing_ms", "mean"),
        timing_ms_p90=("timing_ms", lambda s: _quantile(s, 0.90)),
        parameter_grid_width=("parameter_grid_marker", "nunique"),
    )
    return grp.reset_index()


def compare_price_only_vs_greeks_workloads(
    price_batch_results: Any,
    greeks_batch_results: Any,
) -> Any:
    return compare_price_only_vs_price_plus_greeks(
        price_only_results=price_batch_results,
        price_plus_greeks_results=greeks_batch_results,
    )


def summarize_pricing_recomputation_patterns(
    *,
    price_batch_results: Any,
    greeks_batch_results: Any,
) -> Any:
    import pandas as pd

    rows = []
    if price_batch_results is not None and len(price_batch_results):
        rows.append(
            {
                "workload_variant_label": "contract_batch_price_only",
                "repeated_pricing_call_count": int(len(price_batch_results)),
                "repeated_parameter_structure_markers": _safe_nunique(
                    price_batch_results.get("parameter_grid_marker", pd.Series(dtype=str))
                ),
                "repeated_batch_family_markers": _safe_nunique(
                    price_batch_results.get("batch_id", pd.Series(dtype=str))
                ),
            }
        )
    if greeks_batch_results is not None and len(greeks_batch_results):
        rows.append(
            {
                "workload_variant_label": "contract_batch_price_plus_greeks",
                "repeated_pricing_call_count": int(
                    greeks_batch_results.get("greek_repricing_calls", pd.Series(dtype=float)).sum()
                ),
                "repeated_parameter_structure_markers": _safe_nunique(
                    greeks_batch_results.get("parameter_grid_marker", pd.Series(dtype=str))
                ),
                "repeated_batch_family_markers": _safe_nunique(
                    greeks_batch_results.get("batch_id", pd.Series(dtype=str))
                ),
            }
        )
    return pd.DataFrame(rows)


def summarize_pricing_reuse_proxies(
    *,
    model_family_results: Any,
    price_batch_results: Any,
    greeks_batch_results: Any,
) -> Any:
    import pandas as pd

    rows = []
    for frame, variant in (
        (model_family_results, "model_family_compare_price_only"),
        (price_batch_results, "contract_batch_price_only"),
        (greeks_batch_results, "contract_batch_price_plus_greeks"),
    ):
        if frame is None or len(frame) == 0:
            continue
        rows.append(
            {
                "workload_variant_label": variant,
                "row_count": int(len(frame)),
                "contract_count": _safe_nunique(frame.get("contract_id", pd.Series(dtype=str))),
                "model_family_count": _safe_nunique(frame.get("model_family_id", pd.Series(dtype=str))),
                "batch_size_mean": _safe_mean(frame.get("batch_size", pd.Series(dtype=float))),
                "parameter_grid_width": _safe_nunique(frame.get("parameter_grid_marker", pd.Series(dtype=str))),
                "repeated_parameter_structure_markers": _safe_nunique(frame.get("parameter_grid_marker", pd.Series(dtype=str))),
                "repeated_batch_family_markers": _safe_nunique(frame.get("batch_id", pd.Series(dtype=str))),
                "timing_ms_mean": _safe_mean(frame.get("timing_ms", pd.Series(dtype=float))),
                "greeks_count": 4 if "greeks_timing_ms" in frame.columns else 0,
            }
        )
    return pd.DataFrame(rows)


def rank_pricing_workloads_for_cache_study_value(
    reuse_proxy_summary: Any,
    timing_summary: Any,
) -> Any:
    import pandas as pd

    if reuse_proxy_summary is None or len(reuse_proxy_summary) == 0:
        return pd.DataFrame()
    rs = reuse_proxy_summary.copy()
    ts = timing_summary if timing_summary is not None else pd.DataFrame()
    t_map: Dict[str, float] = {}
    if len(ts) and "workload_variant_label" in ts.columns:
        ttmp = ts.groupby("workload_variant_label", dropna=False)["timing_ms_mean"].mean()
        t_map = {str(k): float(v) for k, v in ttmp.to_dict().items()}
    rows = []
    for _, r in rs.iterrows():
        variant = str(r.get("workload_variant_label", ""))
        repeat_score = float(r.get("repeated_parameter_structure_markers", 0)) + float(
            r.get("repeated_batch_family_markers", 0)
        )
        size_score = float(r.get("row_count", 0)) / max(1.0, float(r.get("contract_count", 1)))
        greek_bonus = float(r.get("greeks_count", 0)) * 0.3
        timing_penalty = max(1e-9, t_map.get(variant, float(r.get("timing_ms_mean", 0.0))))
        score = (repeat_score + size_score + greek_bonus) / (1.0 + 0.001 * timing_penalty)
        rows.append(
            {
                "workload_variant_label": variant,
                "cache_study_value_score": score,
                "repeat_score": repeat_score,
                "size_score": size_score,
                "greek_bonus": greek_bonus,
                "timing_penalty_ms": timing_penalty,
                "rank_notes": "higher score favors repeated structure with manageable runtime",
            }
        )
    out = pd.DataFrame(rows)
    if len(out):
        out = out.sort_values("cache_study_value_score", ascending=False).reset_index(drop=True)
        out["rank"] = range(1, len(out) + 1)
    return out


def run_pricing_workload_bundle(
    *,
    rates_frame: Optional[Any] = None,
    batch_sizes: Sequence[int] = (16, 32, 64),
    benchmark_contract_count: int = 24,
    max_contracts_mac: int = 96,
    max_paths_mac: int = 20_000,
    seed: int = 42,
    run_id: Optional[str] = None,
    record_observability: bool = True,
) -> Dict[str, Any]:
    """Canonical end-to-end pricing workload family bundle."""
    import pandas as pd

    rid = run_id or f"pricing_workload_bundle::{_now_iso()}"
    deferred_notes: List[str] = []

    family = build_contract_batch_family(batch_sizes=batch_sizes, rates_frame=rates_frame)
    family, degrade_notes = _mac_degrade_contract_batches(
        family,
        max_contracts=max_contracts_mac,
        max_paths_per_contract=max_paths_mac,
    )
    deferred_notes.extend(degrade_notes)

    benchmark_contracts = family.head(max(1, benchmark_contract_count)).copy()
    model_family_results = build_pricing_family_bundle(benchmark_contracts, seed=seed)
    model_family_summary = compare_pricing_model_families(model_family_results)

    batch_price_results = run_batch_pricing(family, seed=seed + 1000)
    batch_summary = summarize_contract_batch_workload(batch_price_results)
    batch_compare = compare_contract_batch_workloads(batch_price_results)

    greeks_results = run_greeks_batch(batch_price_results, seed=seed + 2000)
    price_vs_greeks = compare_price_only_vs_greeks_workloads(batch_price_results, greeks_results)

    closed_vs_sim = compare_closed_form_vs_simulation(model_family_results)
    family_timing = compare_model_family_timing(model_family_results)

    timing_rows = []
    for label, frame in (
        ("model_family_compare_price_only", model_family_results),
        ("contract_batch_price_only", batch_price_results),
        ("contract_batch_price_plus_greeks", greeks_results),
    ):
        if frame is None or len(frame) == 0:
            continue
        timing_rows.append(
            {
                "workload_variant_label": label,
                "row_count": int(len(frame)),
                "timing_ms_mean": _safe_mean(frame["timing_ms"]) if "timing_ms" in frame.columns else 0.0,
                "timing_ms_p50": _quantile(frame["timing_ms"], 0.50) if "timing_ms" in frame.columns else 0.0,
                "timing_ms_p90": _quantile(frame["timing_ms"], 0.90) if "timing_ms" in frame.columns else 0.0,
                "timing_ms_p99": _quantile(frame["timing_ms"], 0.99) if "timing_ms" in frame.columns else 0.0,
                "greeks_timing_ms_mean": _safe_mean(frame.get("greeks_timing_ms", pd.Series(dtype=float))),
            }
        )
    timing_summary = pd.DataFrame(timing_rows)

    recomputation_summary = summarize_pricing_recomputation_patterns(
        price_batch_results=batch_price_results,
        greeks_batch_results=greeks_results,
    )
    reuse_proxy_summary = summarize_pricing_reuse_proxies(
        model_family_results=model_family_results,
        price_batch_results=batch_price_results,
        greeks_batch_results=greeks_results,
    )
    rankings = rank_pricing_workloads_for_cache_study_value(
        reuse_proxy_summary=reuse_proxy_summary,
        timing_summary=timing_summary,
    )

    workload_manifest = pd.DataFrame(
        [
            {
                "run_id": rid,
                "workload_variant_label": "model_family_compare_price_only",
                "model_family_count": _safe_nunique(model_family_results.get("model_family_id", pd.Series(dtype=str))),
                "contract_count": _safe_nunique(model_family_results.get("contract_id", pd.Series(dtype=str))),
                "batch_size": benchmark_contract_count,
                "parameter_grid_width": _safe_nunique(model_family_results.get("contract_id", pd.Series(dtype=str))),
                "greeks_count": 0,
                "repeated_pricing_call_count": int(len(model_family_results)),
                "workload_family_label": _workload_family_label(
                    variant_label="model_family_compare_price_only",
                    model_family="all_locked_families",
                    batch_size=int(max(1, benchmark_contract_count)),
                ),
                "deferred_hpc_notes": ";".join(deferred_notes),
            },
            {
                "run_id": rid,
                "workload_variant_label": "contract_batch_price_only",
                "model_family_count": _safe_nunique(batch_price_results.get("model_family_id", pd.Series(dtype=str))),
                "contract_count": _safe_nunique(batch_price_results.get("contract_id", pd.Series(dtype=str))),
                "batch_size": int(_safe_mean(batch_price_results.get("batch_size", pd.Series(dtype=float)))),
                "parameter_grid_width": _safe_nunique(batch_price_results.get("parameter_grid_marker", pd.Series(dtype=str))),
                "greeks_count": 0,
                "repeated_pricing_call_count": int(len(batch_price_results)),
                "workload_family_label": _workload_family_label(
                    variant_label="contract_batch_price_only",
                    model_family="all_locked_families",
                    batch_size=int(max(1, _safe_mean(batch_price_results.get("batch_size", pd.Series(dtype=float))))),
                ),
                "deferred_hpc_notes": ";".join(deferred_notes),
            },
            {
                "run_id": rid,
                "workload_variant_label": "contract_batch_price_plus_greeks",
                "model_family_count": _safe_nunique(greeks_results.get("model_family_id", pd.Series(dtype=str))),
                "contract_count": _safe_nunique(greeks_results.get("contract_id", pd.Series(dtype=str))),
                "batch_size": int(_safe_mean(greeks_results.get("batch_size", pd.Series(dtype=float)))),
                "parameter_grid_width": _safe_nunique(greeks_results.get("parameter_grid_marker", pd.Series(dtype=str))),
                "greeks_count": 4,
                "repeated_pricing_call_count": int(greeks_results.get("greek_repricing_calls", pd.Series(dtype=float)).sum()),
                "workload_family_label": _workload_family_label(
                    variant_label="contract_batch_price_plus_greeks",
                    model_family="all_locked_families",
                    batch_size=int(max(1, _safe_mean(greeks_results.get("batch_size", pd.Series(dtype=float))))),
                ),
                "deferred_hpc_notes": ";".join(deferred_notes),
            },
        ]
    )

    if record_observability:
        try:
            from qhpc_cache.cache_workload_mapping import record_spine_pipeline_observation
            from qhpc_cache.workload_signatures import WORKLOAD_SPINE_OPTION_PRICING

            for _, m in workload_manifest.iterrows():
                record_spine_pipeline_observation(
                    run_id=rid,
                    workload_spine_id=WORKLOAD_SPINE_OPTION_PRICING,
                    pipeline_phase=str(m["workload_variant_label"]),
                    source_datasets="pricing.py;analytic_pricing.py;rates_data",
                    row_count_primary=int(m.get("contract_count", 0)),
                    row_count_after_join=int(m.get("repeated_pricing_call_count", 0)),
                    join_width_estimate=int(m.get("batch_size", 0)),
                    feature_dim_before=int(m.get("parameter_grid_width", 0)),
                    feature_dim_after=int(m.get("parameter_grid_width", 0)) + int(
                        m.get("greeks_count", 0)
                    ),
                    reuse_alignment_opportunities=int(m.get("repeated_pricing_call_count", 0)),
                    notes="pricing_workload_bundle",
                )
        except Exception:
            pass

    model_family_manifest = {
        "run_id": rid,
        "locked_model_family_order": list(LOCKED_MODEL_FAMILY_ORDER),
        "assumptions": {
            MODEL_FAMILY_BLACK_SCHOLES: "closed_form_bsm_no_dividends_constant_params",
            MODEL_FAMILY_MONTE_CARLO_EUROPEAN: "gbm_monte_carlo_terminal_payoff_european",
            MODEL_FAMILY_HESTON_MONTE_CARLO: "heston_mc_euler_full_truncation_approximation",
            MODEL_FAMILY_CRR_LATTICE: "crr_binomial_lattice_european",
        },
        "supported_contract_types": {
            k: ["european_call", "european_put"] for k in LOCKED_MODEL_FAMILY_ORDER
        },
        "greeks_policy": {
            "black_scholes_closed_form": "analytic delta/gamma/vega/theta",
            "others": "finite_difference delta/gamma/vega/theta",
        },
        "optional_dependency_notes": "No optional dependency required for this canonical family layer.",
    }
    batch_manifest = {
        "run_id": rid,
        "batch_family_id": str(family["batch_family_id"].iloc[0]) if len(family) and "batch_family_id" in family.columns else "",
        "batch_ids": sorted(family["batch_id"].dropna().unique().tolist()) if len(family) and "batch_id" in family.columns else [],
        "batch_sizes": sorted(family["batch_size"].dropna().unique().tolist()) if len(family) and "batch_size" in family.columns else [],
        "parameter_grid_markers": sorted(family["parameter_grid_marker"].dropna().unique().tolist()) if len(family) and "parameter_grid_marker" in family.columns else [],
        "deferred_hpc_notes": deferred_notes,
    }

    return {
        "run_id": rid,
        "generated_at_utc": _now_iso(),
        "pricing_workload_manifest": workload_manifest,
        "pricing_model_family_summary": model_family_summary,
        "pricing_contract_batch_summary": batch_summary,
        "pricing_greeks_summary": greeks_results,
        "pricing_timing_summary": timing_summary,
        "pricing_reuse_proxy_summary": reuse_proxy_summary,
        "pricing_workload_rankings": rankings,
        "pricing_model_family_results": model_family_results,
        "pricing_batch_price_results": batch_price_results,
        "pricing_batch_vs_greeks_comparison": price_vs_greeks,
        "pricing_closed_form_vs_simulation": closed_vs_sim,
        "pricing_model_family_timing": family_timing,
        "pricing_contract_batch_compare": batch_compare,
        "pricing_recomputation_summary": recomputation_summary,
        "pricing_model_family_manifest": model_family_manifest,
        "pricing_batch_manifest": batch_manifest,
        "hpc_deferred_workloads": deferred_notes,
    }


def _safe_plot_library():
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns

        return plt, sns
    except Exception:
        return None, None


def _plot_bar(df: Any, *, x: str, y: str, title: str, output_path: Path) -> bool:
    if df is None or len(df) == 0:
        return False
    plt, sns = _safe_plot_library()
    if plt is None or sns is None:
        return False
    fig = plt.figure(figsize=(8, 4))
    ax = fig.add_subplot(111)
    sns.barplot(data=df, x=x, y=y, ax=ax)
    ax.set_title(title)
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return True


def _write_markdown_summary(path: Path, *, title: str, frame: Any, notes: Sequence[str]) -> None:
    lines = [f"# {title}", ""]
    for n in notes:
        lines.append(f"- {n}")
    lines.append("")
    if frame is not None and len(frame):
        preview = frame.head(50)
        try:
            lines.append(preview.to_markdown(index=False))
        except Exception:
            lines.append("```text")
            lines.append(preview.to_string(index=False))
            lines.append("```")
    path.write_text("\n".join(lines), encoding="utf-8")


def export_pricing_workload_bundle(
    *,
    bundle: Mapping[str, Any],
    output_dir: str,
) -> Dict[str, str]:
    """Export canonical pricing workload artifacts (CSV/JSON/markdown/plots)."""
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    paths: Dict[str, str] = {}

    csv_map = {
        "pricing_workload_manifest": "pricing_workload_manifest.csv",
        "pricing_model_family_summary": "pricing_model_family_summary.csv",
        "pricing_contract_batch_summary": "pricing_contract_batch_summary.csv",
        "pricing_greeks_summary": "pricing_greeks_summary.csv",
        "pricing_timing_summary": "pricing_timing_summary.csv",
        "pricing_reuse_proxy_summary": "pricing_reuse_proxy_summary.csv",
        "pricing_workload_rankings": "pricing_workload_rankings.csv",
    }
    for key, name in csv_map.items():
        frame = bundle.get(key)
        if frame is None:
            continue
        p = outdir / name
        frame.to_csv(p, index=False)
        paths[key] = str(p)

    json_map = {
        "pricing_workload_manifest_json": ("pricing_workload_manifest.json", bundle.get("pricing_workload_manifest", [])),
        "pricing_model_family_manifest_json": ("pricing_model_family_manifest.json", bundle.get("pricing_model_family_manifest", {})),
        "pricing_batch_manifest_json": ("pricing_batch_manifest.json", bundle.get("pricing_batch_manifest", {})),
    }
    for key, (name, payload) in json_map.items():
        p = outdir / name
        if hasattr(payload, "to_dict"):
            data = payload.to_dict(orient="records")
        else:
            data = payload
        p.write_text(json.dumps(data, indent=2, sort_keys=False), encoding="utf-8")
        paths[key] = str(p)

    md_model = outdir / "pricing_model_family_summary.md"
    _write_markdown_summary(
        md_model,
        title="Pricing Model Family Summary",
        frame=bundle.get("pricing_model_family_summary"),
        notes=[
            "Locked family order: Black-Scholes, MC European, Heston MC, CRR lattice.",
            "Monte Carlo and Heston are simulation approximations; Black-Scholes is closed-form baseline.",
        ],
    )
    paths["pricing_model_family_summary_md"] = str(md_model)

    md_batch = outdir / "pricing_contract_batch_summary.md"
    _write_markdown_summary(
        md_batch,
        title="Pricing Contract Batch Summary",
        frame=bundle.get("pricing_contract_batch_summary"),
        notes=[
            "Deterministic contract grids used for repeated workload structure.",
            "Batch comparison emphasizes repeated pricing and parameter-grid reuse markers.",
        ],
    )
    paths["pricing_contract_batch_summary_md"] = str(md_batch)

    md_rank = outdir / "pricing_workload_rankings_summary.md"
    _write_markdown_summary(
        md_rank,
        title="Pricing Workload Rankings Summary",
        frame=bundle.get("pricing_workload_rankings"),
        notes=[
            "Ranking favors repeated structure and manageable timing.",
            "Scores are workload-structure proxies, not microarchitectural proof.",
        ],
    )
    paths["pricing_workload_rankings_summary_md"] = str(md_rank)

    _plot_bar(
        bundle.get("pricing_model_family_summary"),
        x="model_family_id",
        y="timing_ms_mean",
        title="Model Family Timing Comparison",
        output_path=outdir / "plot_model_family_timing_comparison.png",
    )
    paths["plot_model_family_timing"] = str(outdir / "plot_model_family_timing_comparison.png")

    _plot_bar(
        bundle.get("pricing_contract_batch_summary"),
        x="batch_id",
        y="timing_ms_mean",
        title="Batch Size Timing Comparison",
        output_path=outdir / "plot_batch_size_comparison.png",
    )
    paths["plot_batch_size"] = str(outdir / "plot_batch_size_comparison.png")

    _plot_bar(
        bundle.get("pricing_batch_vs_greeks_comparison"),
        x="workload_variant_label",
        y="timing_ms_mean",
        title="Price-only vs Greeks Timing",
        output_path=outdir / "plot_price_only_vs_greeks_comparison.png",
    )
    paths["plot_price_vs_greeks"] = str(outdir / "plot_price_only_vs_greeks_comparison.png")

    _plot_bar(
        bundle.get("pricing_workload_rankings"),
        x="workload_variant_label",
        y="cache_study_value_score",
        title="Pricing Workload Ranking",
        output_path=outdir / "plot_pricing_workload_ranking.png",
    )
    paths["plot_workload_ranking"] = str(outdir / "plot_pricing_workload_ranking.png")

    _plot_bar(
        bundle.get("pricing_contract_batch_summary"),
        x="batch_id",
        y="parameter_grid_width",
        title="Parameter Grid Width Comparison",
        output_path=outdir / "plot_parameter_grid_comparison.png",
    )
    paths["plot_parameter_grid"] = str(outdir / "plot_parameter_grid_comparison.png")

    return paths

