"""Plain-text and markdown-friendly reports for experiments."""

from __future__ import annotations

from typing import Any, Dict

from qhpc_cache.portfolio import PortfolioPricingResult, PortfolioRiskSummary
from qhpc_cache.pricing import MonteCarloPricingResult
from qhpc_cache.quantum_workflow import QuantumWorkflowBundle


def format_pricing_result_report(result: MonteCarloPricingResult) -> str:
    lines = [
        "## Monte Carlo pricing result",
        f"- Estimated price: **{result.estimated_price:.6f}**",
        f"- Discounted payoff mean: {result.discounted_payoff_mean:.6f}",
        f"- Payoff variance: {result.payoff_variance:.6f}",
        f"- Standard error: {result.standard_error:.6f}",
        f"- {result.confidence_interval_low:.6f} .. {result.confidence_interval_high:.6f} (interval)",
        f"- Paths: {result.number_of_paths}",
        f"- Payoff: {result.payoff_name}",
        f"- Path simulation: {result.used_path_simulation}",
        f"- Antithetic variates: {result.used_antithetic_variates}",
        f"- Control variate: {result.used_control_variate}",
    ]
    if result.analytic_reference_price is not None:
        lines.append(
            f"- Analytic reference (Black–Scholes): {result.analytic_reference_price:.6f}"
        )
    return "\n".join(lines)


def format_portfolio_risk_report(
    portfolio_result: PortfolioPricingResult,
    risk_summary: PortfolioRiskSummary,
) -> str:
    lines = [
        "## Portfolio pricing",
        f"- Portfolio: **{portfolio_result.portfolio_name}**",
        f"- Total estimated value (MC): **{portfolio_result.total_estimated_value:.6f}**",
    ]
    if portfolio_result.notes:
        lines.append(f"- Notes: {portfolio_result.notes}")
    for index in range(len(portfolio_result.individual_position_results)):
        lines.append(
            f"- Line {index + 1} unit MC price: "
            f"{portfolio_result.individual_position_results[index].estimated_price:.6f}"
        )
    dist = risk_summary.distribution_summary
    lines.extend(
        [
            "## Portfolio scenario P&L (analytic repricing; sample quantiles)",
            f"- VaR (loss magnitude): {risk_summary.value_at_risk:.6f}",
            f"- CVaR (loss magnitude): {risk_summary.conditional_value_at_risk:.6f}",
            f"- P&L sample mean: {dist.sample_mean:.6f}",
            f"- P&L sample std: {dist.sample_std:.6f}",
        ]
    )
    return "\n".join(lines)


def format_cache_experiment_report(metrics: Dict[str, Any]) -> str:
    lines = ["## Cache experiment", f"- Policy label: {metrics.get('policy_label')}"]
    for key, value in metrics.items():
        if key == "policy_label":
            continue
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def format_quantum_mapping_report(bundle: QuantumWorkflowBundle) -> str:
    fp = bundle.finance_problem
    task = bundle.estimation_task
    req = bundle.circuit_request
    res = bundle.resource_estimate
    return "\n".join(
        [
            "## Quantum mapping bundle",
            f"- Instrument: {fp.instrument_name} ({fp.payoff_type})",
            f"- Model: {fp.stochastic_model_name}, path sim: {fp.requires_path_simulation}",
            f"- Target: {task.target_expectation_description}",
            f"- AE target note: {task.amplitude_estimation_target}",
            f"- Circuit family: {req.circuit_family_name}, "
            f"qubits~{req.expected_qubit_count}, depth~{req.expected_depth}",
            f"- Shots (placeholder): {res.estimated_shot_count}",
            f"- Notes: {res.notes}",
        ]
    )
