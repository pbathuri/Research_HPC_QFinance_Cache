"""Quantum finance **abstractions** — classical tasks described for future QMCI work.

Nothing in this module executes on a quantum device. Text fields describe the
estimation problem; **numeric fields on** ``QuantumResourceEstimate`` **and rough
qubit/depth counts on** ``QuantumCircuitRequest`` **are illustrative placeholders**
unless you replace them with backend-derived numbers.

The goal is to mirror how finance problems decompose into **expectation
estimation**, **state preparation**, and **amplitude estimation** framing so a
later Qiskit/Cirq layer can attach without rewriting pricing mathematics here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class FinanceProblemDescriptor:
    """What classical problem we are solving, in language both finance and quantum teams share."""

    instrument_name: str
    payoff_type: str
    stochastic_model_name: str
    maturity_in_years: float
    strike_price: float
    volatility: float
    risk_free_rate: float
    number_of_samples: int
    requires_path_simulation: bool
    portfolio_context_label: str = "single_name"


@dataclass
class QuantumEstimationTask:
    """How a quantum estimator would frame the same expectation problem."""

    target_expectation_description: str
    state_preparation_notes: str
    payoff_encoding_notes: str
    amplitude_estimation_target: str
    acceptable_error_tolerance: float
    confidence_level: float


@dataclass
class QuantumCircuitRequest:
    """Portable description of a circuit family to compile later.

    ``circuit_family_name`` is a label; ``expected_qubit_count`` and
    ``expected_depth`` are **illustrative** unless supplied from real sizing.
    """

    request_identifier: str
    finance_problem_key: str
    circuit_family_name: str
    expected_qubit_count: int
    expected_depth: int
    requires_amplitude_estimation: bool
    requires_state_preparation: bool
    reuse_candidate_label: str


@dataclass
class QuantumResourceEstimate:
    """**PLACEHOLDER** resource budget — not measured on any real device.

    Use for proposals and order-of-magnitude discussion only; replace with
    transpilation and error-model data when moving beyond this baseline.
    """

    estimated_qubit_count: int
    estimated_depth: int
    estimated_shot_count: int
    state_preparation_cost_estimate: str
    arithmetic_oracle_cost_estimate: str
    notes: str


def build_finance_problem_descriptor_from_pricing_request(
    instrument_name: str,
    payoff_type: str,
    stochastic_model_name: str,
    maturity_in_years: float,
    strike_price: float,
    volatility: float,
    risk_free_rate: float,
    number_of_samples: int,
    requires_path_simulation: bool,
    portfolio_context_label: str = "single_name",
) -> FinanceProblemDescriptor:
    """Factory used by classical Monte Carlo and future hybrid runners."""
    return FinanceProblemDescriptor(
        instrument_name=instrument_name,
        payoff_type=payoff_type,
        stochastic_model_name=stochastic_model_name,
        maturity_in_years=maturity_in_years,
        strike_price=strike_price,
        volatility=volatility,
        risk_free_rate=risk_free_rate,
        number_of_samples=number_of_samples,
        requires_path_simulation=requires_path_simulation,
        portfolio_context_label=portfolio_context_label,
    )


def build_quantum_estimation_task(
    finance_problem: FinanceProblemDescriptor,
    acceptable_error_tolerance: float = 0.01,
    confidence_level: float = 0.95,
) -> QuantumEstimationTask:
    """Translate a finance descriptor into estimation language (no execution)."""
    path_note = (
        "Path-dependent payoff requires multi-step state preparation or "
        "auxiliary registers to represent path statistics."
        if finance_problem.requires_path_simulation
        else "Terminal payoff: amplitude encoding can target discounted payoff directly."
    )
    return QuantumEstimationTask(
        target_expectation_description=(
            f"Estimate Q-expectation of discounted payoff for "
            f"{finance_problem.instrument_name} ({finance_problem.payoff_type})."
        ),
        state_preparation_notes=(
            f"Prepare distribution for {finance_problem.stochastic_model_name} "
            f"with horizon T={finance_problem.maturity_in_years}. " + path_note
        ),
        payoff_encoding_notes=(
            "Encode payoff as amplitude or expectation of a Pauli observable "
            "after payoff circuit; details depend on chosen encoding."
        ),
        amplitude_estimation_target=(
            "Canonical amplitude estimation would target success probability "
            "proportional to normalized payoff; classical MC here estimates "
            "the same mean with sampling error."
        ),
        acceptable_error_tolerance=acceptable_error_tolerance,
        confidence_level=confidence_level,
    )


def build_quantum_circuit_request(
    finance_problem: FinanceProblemDescriptor,
    estimation_task: QuantumEstimationTask,
    request_identifier: str,
) -> QuantumCircuitRequest:
    """Draft a circuit request for a future compiler queue.

    ``expected_depth`` and ``expected_qubit_count`` use **placeholder** scaling
    from ``number_of_samples`` — not device benchmarks.
    """
    finance_problem_key = (
        f"{finance_problem.instrument_name}|{finance_problem.payoff_type}|"
        f"{finance_problem.maturity_in_years}|{finance_problem.strike_price}|"
        f"{finance_problem.volatility}|{finance_problem.portfolio_context_label}"
    )
    depth_guess = 50 + int(finance_problem.number_of_samples**0.5)
    qubit_guess = 12 + (
        4 if finance_problem.requires_path_simulation else 0
    )
    return QuantumCircuitRequest(
        request_identifier=request_identifier,
        finance_problem_key=finance_problem_key,
        circuit_family_name="qmci_placeholder",
        expected_qubit_count=qubit_guess,
        expected_depth=depth_guess,
        requires_amplitude_estimation=True,
        requires_state_preparation=True,
        reuse_candidate_label=finance_problem.portfolio_context_label,
    )


def estimate_quantum_resources_placeholder(
    circuit_request: QuantumCircuitRequest,
    estimation_task: QuantumEstimationTask,
) -> QuantumResourceEstimate:
    """Return qualitative resource guesses — **not** calibrated to hardware."""
    shots = max(
        1000,
        int(
            1.0
            / max(estimation_task.acceptable_error_tolerance, 1e-6) ** 2
        ),
    )
    return QuantumResourceEstimate(
        estimated_qubit_count=circuit_request.expected_qubit_count,
        estimated_depth=circuit_request.expected_depth,
        estimated_shot_count=shots,
        state_preparation_cost_estimate=(
            "High if path-dependent; moderate for terminal GBM with fixed steps."
        ),
        arithmetic_oracle_cost_estimate=(
            "Payoff comparator depth grows with precision of fixed-point encoding."
        ),
        notes=(
            "Numbers are placeholders for research planning only. "
            "Real budgets need transpilation targets and error models."
        ),
    )


def build_finance_problem_from_monte_carlo_pricer(pricer: Any) -> FinanceProblemDescriptor:
    """Convenience adapter for MonteCarloPricer-like objects (duck typing)."""
    requires_path = getattr(pricer, "simulation_mode", "terminal") == "path"
    return build_finance_problem_descriptor_from_pricing_request(
        instrument_name="monte_carlo_option",
        payoff_type=getattr(pricer, "payoff_type", "european_call"),
        stochastic_model_name="gbm",
        maturity_in_years=float(getattr(pricer, "T")),
        strike_price=float(getattr(pricer, "K")),
        volatility=float(getattr(pricer, "sigma")),
        risk_free_rate=float(getattr(pricer, "r")),
        number_of_samples=int(getattr(pricer, "num_paths")),
        requires_path_simulation=requires_path,
        portfolio_context_label="single_name",
    )
