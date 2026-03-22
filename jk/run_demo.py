"""Canonical demo for the classical finance baseline (package ``qhpc_cache``).

Run from ``jk/`` after ``pip install -e .``. This script is the **source of truth**
walkthrough for this phase: European and exotic-style payoffs via Monte Carlo,
Black–Scholes checks, variance reduction, sample VaR/CVaR, a tiny two-line book,
and a minimal result cache. Sections 8–9 briefly point to semi-analytic,
quantum-shaped, and circuit-level scaffolding (not executed on real hardware).

For automated checks, use ``PYTHONPATH=src python3 -m unittest discover -s tests -v``.
For batch experiments, see ``qhpc_cache.experiment_runner``.
"""

from __future__ import annotations

from qhpc_cache.analytic_pricing import black_scholes_call_price
from qhpc_cache.cache_policy import HeuristicCachePolicy
from qhpc_cache.cache_store import SimpleCacheStore
from qhpc_cache.config import (
    PortfolioDemoDefaults,
    PricingConfig,
    get_default_config,
    get_demo_run_defaults,
)
from qhpc_cache.fourier_placeholder import fourier_price_placeholder
from qhpc_cache.portfolio import (
    OptionPosition,
    PortfolioPricingRequest,
    price_portfolio_positions,
    summarize_portfolio_risk,
)
from qhpc_cache.pricing import MonteCarloPricer
from qhpc_cache.quantum_workflow import run_quantum_mapping_workflow
from qhpc_cache.reporting import (
    format_portfolio_risk_report,
    format_pricing_result_report,
    format_quantum_mapping_report,
)
from qhpc_cache.risk_metrics import compute_conditional_value_at_risk, compute_value_at_risk
from qhpc_cache.variance_reduction import generate_antithetic_standard_normal_pairs


def _section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def _mc_pricer(
    cfg: PricingConfig,
    num_paths: int,
    *,
    random_seed: int | None,
    **kwargs: object,
) -> MonteCarloPricer:
    """Build a ``MonteCarloPricer`` from shared spot/strike/rates (avoids copy-paste)."""
    return MonteCarloPricer(
        cfg.S0,
        cfg.K,
        cfg.r,
        cfg.sigma,
        cfg.T,
        num_paths,
        random_seed=random_seed,
        **kwargs,
    )


def main() -> None:
    cfg = get_default_config()
    demo = get_demo_run_defaults()
    portfolio_demo = PortfolioDemoDefaults()

    _section(
        "1) European call — risk-neutral Monte Carlo vs Black–Scholes (confidence interval)"
    )
    pricer = _mc_pricer(
        cfg,
        demo.european_call_paths,
        random_seed=demo.european_call_seed,
        payoff_type="european_call",
        compare_analytic_black_scholes=True,
    )
    mc_result = pricer.price_option()
    print(format_pricing_result_report(mc_result))
    print(
        "Note: the interval is Gaussian around the sample mean of discounted payoffs "
        "(see qhpc_cache.variance_reduction.confidence_interval_from_standard_error)."
    )

    _section(
        "2) Variance reduction — antithetic normals + optional control variate (vanilla call)"
    )
    paired_z = generate_antithetic_standard_normal_pairs(
        demo.antithetic_pairs_demo_count,
        random_seed=demo.antithetic_pairs_demo_seed,
    )
    print(
        f"Antithetic Z draws (pairs Z, −Z): length {len(paired_z)}, first values {paired_z[:4]}…"
    )
    anti_only = _mc_pricer(
        cfg,
        demo.antithetic_paths,
        random_seed=demo.antithetic_seed,
        payoff_type="european_call",
        use_antithetic_variates=True,
        compare_analytic_black_scholes=True,
    )
    anti_result = anti_only.price_option()
    print(
        f"Antithetic only — price ≈ {anti_result.estimated_price:.6f}, "
        f"SE ≈ {anti_result.standard_error:.6f}, paths = {anti_result.number_of_paths}"
    )
    anti_cv = _mc_pricer(
        cfg,
        demo.variance_reduction_paths,
        random_seed=demo.variance_reduction_seed,
        payoff_type="european_call",
        use_antithetic_variates=True,
        use_black_scholes_control_variate=True,
        compare_analytic_black_scholes=True,
    )
    cv_result = anti_cv.price_option()
    print("Antithetic + Black–Scholes control variate (terminal spot):")
    print(format_pricing_result_report(cv_result))

    _section("3) Digital call — cash-or-nothing, terminal simulation, discounted PV")
    digital = _mc_pricer(
        cfg,
        demo.digital_call_paths,
        random_seed=demo.digital_call_seed,
        payoff_type="digital_call",
        digital_payout_amount=1.0,
    )
    digital_result = digital.price_option()
    print(
        f"Present value (risk-neutral expectation of discounted payout): "
        f"{digital_result.estimated_price:.6f}"
    )

    _section("4) Asian call — path-dependent payoff (arithmetic average vs strike)")
    asian = _mc_pricer(
        cfg,
        demo.asian_call_paths,
        random_seed=demo.asian_call_seed,
        payoff_type="asian_call",
        simulation_mode="path",
        num_time_steps=demo.asian_time_steps,
    )
    print(format_pricing_result_report(asian.price_option()))

    _section("5) VaR and CVaR — toy P&L sample (historical-simulation style quantiles)")
    pnl_sample = [-4.0, -2.5, -1.0, 0.5, 1.2, 2.0, 3.5]
    confidence = 0.95
    var95 = compute_value_at_risk(pnl_sample, confidence)
    cvar95 = compute_conditional_value_at_risk(pnl_sample, confidence)
    print(f"P&L scenarios: {pnl_sample}")
    print(
        f"VaR ({confidence:.0%}, reported as loss magnitude): {var95:.4f}\n"
        f"CVaR ({confidence:.0%}, expected shortfall in the tail): {cvar95:.4f}"
    )

    _section(
        "6) Portfolio — per-line Monte Carlo PV; scenario VaR/CVaR via analytic repricing"
    )
    positions = [
        OptionPosition(
            position_name="call_leg",
            payoff_name="european_call",
            quantity=1.0,
            initial_asset_price=cfg.S0,
            strike_price=105.0,
            risk_free_rate=cfg.r,
            volatility=0.22,
            time_to_maturity=cfg.T,
        ),
        OptionPosition(
            position_name="put_leg",
            payoff_name="european_put",
            quantity=1.0,
            initial_asset_price=cfg.S0,
            strike_price=95.0,
            risk_free_rate=cfg.r,
            volatility=0.22,
            time_to_maturity=cfg.T,
        ),
    ]
    portfolio_request = PortfolioPricingRequest(
        portfolio_name="demo_book",
        positions=positions,
        number_of_paths=portfolio_demo.number_of_paths_per_line,
        random_seed=demo.portfolio_random_seed,
        scenario_underlying_prices=list(portfolio_demo.scenario_underlying_prices),
        baseline_underlying_price=portfolio_demo.baseline_underlying_price,
        risk_confidence_level=confidence,
    )
    book = price_portfolio_positions(portfolio_request)
    risk_summary = summarize_portfolio_risk(portfolio_request, confidence_level=confidence)
    print(format_portfolio_risk_report(book, risk_summary))

    _section("7) Result cache — heuristic policy reuses stored Monte Carlo output")
    heuristic_store = SimpleCacheStore()
    cached_pricer = _mc_pricer(
        cfg,
        min(cfg.num_paths, demo.cache_demo_max_paths),
        random_seed=demo.cache_demo_seed,
        cache_policy=HeuristicCachePolicy(),
        cache_store=heuristic_store,
    )
    first = cached_pricer.price_option()
    second = cached_pricer.price_option()
    print(f"First estimate:  {first.estimated_price:.6f}")
    print(f"Second estimate: {second.estimated_price:.6f} (same key → cache hit)")
    print(f"Cache stats: {heuristic_store.stats()}")

    _section("8) Semi-analytic check + quantum-shaped mapping (placeholders, no hardware)")
    cos_price, analytic_ref = fourier_price_placeholder(
        cfg.S0, cfg.K, cfg.r, cfg.sigma, cfg.T
    )
    bs_direct = black_scholes_call_price(cfg.S0, cfg.K, cfg.r, cfg.sigma, cfg.T)
    print(
        f"COS-style numerical benchmark: {cos_price:.6f}\n"
        f"Same-module analytic reference: {analytic_ref:.6f}\n"
        f"black_scholes_call_price:       {bs_direct:.6f}"
    )
    bundle = run_quantum_mapping_workflow(pricer, request_identifier="demo-bundle")
    print(format_quantum_mapping_report(bundle))

    _section("9) Where to go next (this repo)")
    print(
        "• Circuit exact-match cache, similarity scores, rich cache features: "
        "``circuit_cache.py``, ``circuit_similarity.py``, ``cache_policy_features.py`` "
        "— see ``tests/test_circuit_*.py`` and ``tests/test_cache_policy_features.py``.\n"
        "• Repeated trials and policy comparisons: ``experiment_runner.py`` "
        "(e.g. ``run_repeated_pricing_experiment``, ``run_payoff_comparison_experiment``).\n"
        "• Legacy standalone script (European-only sketch): ``monte_carlo_cache_baseline.py`` "
        "— prefer ``qhpc_cache`` + this demo for new work.\n"
        "• Architecture: ``docs/finance_baseline_architecture.md`` (classical stack) and "
        "``docs/architecture_overview.md`` (full scaffold)."
    )

    print("\nDone. Educational baseline only; not investment advice.")


if __name__ == "__main__":
    main()
