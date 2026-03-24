"""Quantum Monte Carlo Integration (QMCI) engine using Google Cirq.

Encodes the log-normal distribution of the terminal stock price into qubit
amplitudes, applies Ry rotations for payoff-function encoding, and extracts
the option price from ancilla measurement statistics.  This is a *simulation*
of the quantum algorithm (run on Cirq's state-vector simulator), not a
hardware execution.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from qhpc_cache.quantum_engines.base_engine import SimulationEngine, SimulationResult


class CirqEngine(SimulationEngine):
    """QMCI-style European call pricer on a Cirq simulator."""

    def __init__(self, n_qubits: int = 8) -> None:
        self._n_qubits = n_qubits

    @property
    def name(self) -> str:
        return f"Cirq-QMCI-{self._n_qubits}q"

    @property
    def engine_type(self) -> str:
        return "cirq_qmci"

    @classmethod
    def available(cls) -> bool:
        try:
            import cirq  # noqa: F401
            return True
        except ImportError:
            return False

    # ------------------------------------------------------------------

    def price(
        self,
        S0: float,
        K: float,
        r: float,
        sigma: float,
        T: float,
        num_paths: int,
        seed: Optional[int] = None,
    ) -> SimulationResult:
        t0 = self._start_timer()
        try:
            import cirq

            n = self._n_qubits
            num_shots = num_paths

            mu = math.log(S0) + (r - 0.5 * sigma**2) * T
            vol = sigma * math.sqrt(T)
            N = 2**n

            S_min = S0 * math.exp((r - 0.5 * sigma**2) * T - 4.0 * vol)
            S_max = S0 * math.exp((r - 0.5 * sigma**2) * T + 4.0 * vol)
            S_vals = np.linspace(S_min, S_max, N)

            log_S = np.log(np.maximum(S_vals, 1e-12))
            pdf = np.exp(-0.5 * ((log_S - mu) / vol) ** 2) / (
                S_vals * vol * math.sqrt(2.0 * math.pi)
            )
            pdf = np.maximum(pdf, 0.0)
            norm = np.sum(pdf)
            if norm < 1e-30:
                return self._error_result(
                    "PDF normalization failed", S0, K, r, sigma, T, num_paths,
                    self._elapsed_ms(t0),
                )
            amplitudes = np.sqrt(pdf / norm)

            payoff_raw = np.maximum(S_vals - K, 0.0)
            payoff_max = np.max(payoff_raw)
            if payoff_max < 1e-30:
                wall_ms = self._elapsed_ms(t0)
                return self._make_result(
                    price=0.0, std_error=0.0, paths_used=num_shots,
                    wall_clock_ms=wall_ms,
                    S0=S0, K=K, r=r, sigma=sigma, T=T, num_paths=num_paths,
                    metadata={"note": "payoff identically zero", "n_qubits": n},
                )
            payoff_angles = np.arcsin(np.sqrt(payoff_raw / payoff_max))

            price_qubits = cirq.LineQubit.range(n)
            ancilla = cirq.LineQubit(n)

            circuit = cirq.Circuit()

            target_state = amplitudes.tolist()
            gate = cirq.MatrixGate(
                _unitary_from_first_column(target_state)
            )
            circuit.append(gate.on(*price_qubits))

            for i in range(N):
                angle = 2.0 * payoff_angles[i]
                if abs(angle) < 1e-12:
                    continue
                controls = []
                for bit_idx in range(n):
                    if (i >> bit_idx) & 1:
                        controls.append(price_qubits[bit_idx])
                    else:
                        circuit.append(cirq.X(price_qubits[bit_idx]))
                        controls.append(price_qubits[bit_idx])

                controlled_ry = cirq.ry(angle).controlled(num_controls=n)
                circuit.append(controlled_ry.on(*controls, ancilla))

                for bit_idx in range(n):
                    if not ((i >> bit_idx) & 1):
                        circuit.append(cirq.X(price_qubits[bit_idx]))

            circuit.append(cirq.measure(ancilla, key="payoff"))

            simulator = cirq.Simulator(seed=seed)
            run_result = simulator.run(circuit, repetitions=num_shots)
            counts = run_result.histogram(key="payoff")
            prob_one = counts.get(1, 0) / num_shots

            discount = math.exp(-r * T)
            estimated_price = discount * prob_one * payoff_max
            std_error = (
                discount
                * payoff_max
                * math.sqrt(prob_one * (1.0 - prob_one) / num_shots)
            )

            gate_count = len(list(circuit.all_operations()))
            depth = len(circuit)

            wall_ms = self._elapsed_ms(t0)
            return self._make_result(
                price=estimated_price,
                std_error=std_error,
                paths_used=num_shots,
                wall_clock_ms=wall_ms,
                S0=S0, K=K, r=r, sigma=sigma, T=T, num_paths=num_paths,
                metadata={
                    "n_qubits": n,
                    "gate_count": gate_count,
                    "circuit_depth": depth,
                    "prob_ancilla_one": prob_one,
                },
            )
        except Exception as exc:
            return self._error_result(
                str(exc), S0, K, r, sigma, T, num_paths, self._elapsed_ms(t0)
            )


def _unitary_from_first_column(col: list[float]) -> np.ndarray:
    """Build a unitary whose first column matches *col* (real, normalised).

    Uses QR decomposition: place the target vector as the first column of a
    matrix, then QR gives an orthogonal basis starting from that vector.
    """
    n = len(col)
    a = np.zeros((n, n), dtype=np.complex128)
    a[:, 0] = np.array(col, dtype=np.complex128)
    rng = np.random.RandomState(0)
    a[:, 1:] = rng.randn(n, n - 1) + 1j * rng.randn(n, n - 1)
    q, _ = np.linalg.qr(a)
    if np.real(q[0, 0]) * col[0] < 0:
        q[:, 0] *= -1
    return q


if __name__ == "__main__":
    engine = CirqEngine(n_qubits=4)
    print(f"Cirq available: {engine.available()}")

    result = engine.price(
        S0=100.0, K=105.0, r=0.05, sigma=0.2, T=1.0,
        num_paths=4096, seed=42,
    )
    print(f"QMCI price: {result.price:.4f}  (std_error={result.std_error:.4f})")
    print(f"Wall time : {result.wall_clock_ms:.1f} ms")
    print(f"Metadata  : {result.metadata}")
    print("cirq_engine self-test passed.")
