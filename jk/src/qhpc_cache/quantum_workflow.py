"""Map a classical ``MonteCarloPricer``-style object to quantum **planning** artifacts.

Produces descriptors and **placeholder** resource estimates only — no backend
execution. Use ``run_quantum_mapping_workflow`` from demos and experiments.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Tuple

from qhpc_cache.quantum_mapping import (
    FinanceProblemDescriptor,
    QuantumCircuitRequest,
    QuantumEstimationTask,
    QuantumResourceEstimate,
    build_finance_problem_from_monte_carlo_pricer,
    build_quantum_circuit_request,
    build_quantum_estimation_task,
    estimate_quantum_resources_placeholder,
)


@dataclass
class QuantumWorkflowBundle:
    """Finance + estimation + circuit request + **placeholder** resource estimate."""

    finance_problem: FinanceProblemDescriptor
    estimation_task: QuantumEstimationTask
    circuit_request: QuantumCircuitRequest
    resource_estimate: QuantumResourceEstimate


def run_quantum_mapping_workflow(
    pricer_like: Any,
    request_identifier: str = "demo-request",
    acceptable_error_tolerance: float = 0.01,
    confidence_level: float = 0.95,
) -> QuantumWorkflowBundle:
    """Map a classical pricer configuration to quantum planning objects."""
    finance_problem = build_finance_problem_from_monte_carlo_pricer(pricer_like)
    estimation_task = build_quantum_estimation_task(
        finance_problem,
        acceptable_error_tolerance=acceptable_error_tolerance,
        confidence_level=confidence_level,
    )
    circuit_request = build_quantum_circuit_request(
        finance_problem, estimation_task, request_identifier=request_identifier
    )
    resource_estimate = estimate_quantum_resources_placeholder(
        circuit_request, estimation_task
    )
    return QuantumWorkflowBundle(
        finance_problem=finance_problem,
        estimation_task=estimation_task,
        circuit_request=circuit_request,
        resource_estimate=resource_estimate,
    )


def bundle_to_tuple(bundle: QuantumWorkflowBundle) -> Tuple[
    FinanceProblemDescriptor,
    QuantumEstimationTask,
    QuantumCircuitRequest,
    QuantumResourceEstimate,
]:
    """Structured unpacking helper for experiments."""
    return (
        bundle.finance_problem,
        bundle.estimation_task,
        bundle.circuit_request,
        bundle.resource_estimate,
    )
