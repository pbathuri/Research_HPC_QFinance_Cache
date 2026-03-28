"""Structural fingerprinting for quantum circuits.

Extracts gate-level features from Cirq circuits or synthesises fingerprints
from metadata dicts when Cirq is not available.  Supports structural
similarity computation independent of exact parameter values.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Dict, Tuple

try:
    import cirq

    _CIRQ_AVAILABLE = True
except ImportError:
    _CIRQ_AVAILABLE = False


@dataclass
class CircuitFingerprint:
    gate_type_histogram: Dict[str, int]
    qubit_count: int
    depth: int
    total_gate_count: int
    connectivity_density: float
    parameter_count: int
    measurement_count: int
    parameter_signature: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CircuitFingerprintEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, CircuitFingerprint):
            return obj.to_dict()
        return super().default(obj)


def fingerprint_cirq_circuit(circuit: Any) -> CircuitFingerprint:
    """Extract structural fingerprint from a live cirq.Circuit."""
    if not _CIRQ_AVAILABLE:
        raise RuntimeError(
            "cirq is not installed; use fingerprint_from_metadata instead"
        )

    gate_hist: Dict[str, int] = {}
    total_gates = 0
    param_count = 0
    measurement_count = 0
    two_qubit_gates = 0
    param_values: list = []

    for op in circuit.all_operations():
        gate = op.gate
        gate_name = type(gate).__name__ if gate is not None else "unknown"
        gate_hist[gate_name] = gate_hist.get(gate_name, 0) + 1
        total_gates += 1

        if len(op.qubits) >= 2:
            two_qubit_gates += 1

        if isinstance(gate, cirq.MeasurementGate):
            measurement_count += 1

        if hasattr(gate, "_exponent"):
            param_count += 1
            param_values.append(float(gate._exponent))
        elif hasattr(gate, "exponent"):
            param_count += 1
            try:
                param_values.append(float(gate.exponent))
            except (TypeError, ValueError):
                pass

    all_qubits = sorted(circuit.all_qubits())
    qubit_count = len(all_qubits)
    depth = len(circuit)

    max_edges = qubit_count * (qubit_count - 1) / 2 if qubit_count > 1 else 1.0
    connectivity_density = two_qubit_gates / max_edges if max_edges > 0 else 0.0

    sig_raw = json.dumps(sorted(param_values), default=str)
    parameter_signature = hashlib.sha256(sig_raw.encode()).hexdigest()[:16]

    return CircuitFingerprint(
        gate_type_histogram=gate_hist,
        qubit_count=qubit_count,
        depth=depth,
        total_gate_count=total_gates,
        connectivity_density=round(connectivity_density, 6),
        parameter_count=param_count,
        measurement_count=measurement_count,
        parameter_signature=parameter_signature,
    )


def fingerprint_from_metadata(metadata: Dict[str, Any]) -> CircuitFingerprint:
    """Build a fingerprint from the metadata dict that CirqEngine returns.

    Expected keys: n_qubits, gate_count, circuit_depth, prob_ancilla_one.
    """
    n_qubits = int(metadata.get("n_qubits", metadata.get("qubit_count", 4)))
    gate_count = int(metadata.get("gate_count", metadata.get("total_gate_count", 0)))
    depth = int(metadata.get("circuit_depth", metadata.get("depth", 0)))
    prob_ancilla = float(metadata.get("prob_ancilla_one", 0.0))

    gate_hist = metadata.get("gate_type_histogram", {})
    if not gate_hist:
        n_states = 2**n_qubits
        gate_hist = {
            "MatrixGate": 1,
            "X": max(1, gate_count - n_states - 2),
            "ControlledGate": max(1, n_states),
            "MeasurementGate": 1,
        }
        hist_total = sum(gate_hist.values())
        if hist_total > 0 and gate_count > 0:
            scale = gate_count / hist_total
            gate_hist = {k: max(1, int(v * scale)) for k, v in gate_hist.items()}

    measurement_count = int(
        metadata.get("measurement_count", gate_hist.get("MeasurementGate", 1))
    )
    parameter_count = int(
        metadata.get("parameter_count", gate_hist.get("ControlledGate", 0))
    )

    max_edges = n_qubits * (n_qubits - 1) / 2 if n_qubits > 1 else 1.0
    two_q_est = gate_hist.get("ControlledGate", 0)
    connectivity_density = float(
        metadata.get(
            "connectivity_density",
            round(two_q_est / max_edges, 6) if max_edges > 0 else 0.0,
        )
    )

    sig_input = f"{n_qubits}|{gate_count}|{depth}|{prob_ancilla:.8f}"
    parameter_signature = hashlib.sha256(sig_input.encode()).hexdigest()[:16]

    return CircuitFingerprint(
        gate_type_histogram=gate_hist,
        qubit_count=n_qubits,
        depth=depth,
        total_gate_count=gate_count,
        connectivity_density=round(connectivity_density, 6),
        parameter_count=parameter_count,
        measurement_count=measurement_count,
        parameter_signature=parameter_signature,
    )


def _weighted_jaccard(hist_a: Dict[str, int], hist_b: Dict[str, int]) -> float:
    """Weighted Jaccard similarity: sum(min) / sum(max) over all gate types."""
    all_keys = set(hist_a) | set(hist_b)
    if not all_keys:
        return 1.0
    intersection_sum = 0.0
    union_sum = 0.0
    for k in all_keys:
        a = hist_a.get(k, 0)
        b = hist_b.get(k, 0)
        intersection_sum += min(a, b)
        union_sum += max(a, b)
    return intersection_sum / union_sum if union_sum > 0 else 1.0


def _proximity(a: float, b: float) -> float:
    """1.0 when equal, approaches 0 as values diverge."""
    denom = max(abs(a), abs(b), 1.0)
    return max(0.0, 1.0 - abs(a - b) / denom)


def compute_structural_similarity(
    fp1: CircuitFingerprint,
    fp2: CircuitFingerprint,
) -> Tuple[float, Dict[str, float]]:
    """Weighted structural similarity between two circuit fingerprints.

    Returns (overall_score, component_scores) where overall_score is in [0, 1].
    Weights: gate histogram 0.30, depth 0.25, qubits 0.20,
    connectivity 0.15, parameters 0.10.
    """
    components: Dict[str, float] = {}

    components["gate_histogram_jaccard"] = _weighted_jaccard(
        fp1.gate_type_histogram, fp2.gate_type_histogram
    )
    components["depth_proximity"] = _proximity(fp1.depth, fp2.depth)
    components["qubit_count_proximity"] = _proximity(fp1.qubit_count, fp2.qubit_count)
    components["connectivity_density_proximity"] = _proximity(
        fp1.connectivity_density, fp2.connectivity_density
    )
    components["parameter_count_proximity"] = _proximity(
        fp1.parameter_count, fp2.parameter_count
    )

    weights = {
        "gate_histogram_jaccard": 0.30,
        "depth_proximity": 0.25,
        "qubit_count_proximity": 0.20,
        "connectivity_density_proximity": 0.15,
        "parameter_count_proximity": 0.10,
    }

    overall = sum(weights[k] * components[k] for k in weights)
    return overall, components
