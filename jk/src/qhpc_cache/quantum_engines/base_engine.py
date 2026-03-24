"""Abstract base for all simulation engines and the shared result type.

Every engine -- classical MC, QuantLib, Cirq QMCI, PyQMC VMC, Monaco --
implements the same interface so callers never hard-code an execution strategy.
"""

from __future__ import annotations

import hashlib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

_VALID_ENGINE_TYPES = frozenset(
    {"classical_mc", "quantlib_mc", "cirq_qmci", "pyqmc_vmc", "monaco_mc"}
)


@dataclass
class SimulationResult:
    """Structured output returned by every engine's ``price()`` method."""

    price: float
    std_error: float
    paths_used: int
    wall_clock_ms: float
    engine_name: str
    engine_type: str
    cache_key: str
    metadata: Dict[str, Any] = field(default_factory=dict)


def build_cache_key(
    engine_type: str,
    S0: float,
    K: float,
    r: float,
    sigma: float,
    T: float,
    num_paths: int,
) -> str:
    """Deterministic SHA-256 digest of the pricing parameters."""
    raw = f"{engine_type}|{S0:.10f}|{K:.10f}|{r:.10f}|{sigma:.10f}|{T:.10f}|{num_paths}"
    return hashlib.sha256(raw.encode()).hexdigest()


class SimulationEngine(ABC):
    """Interface contract for all simulation / pricing engines."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable engine label."""
        ...

    @property
    @abstractmethod
    def engine_type(self) -> str:
        """One of the recognised engine-type tags (see ``_VALID_ENGINE_TYPES``)."""
        ...

    @abstractmethod
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
        """Run the simulation and return a structured result."""
        ...

    @classmethod
    @abstractmethod
    def available(cls) -> bool:
        """Return True if required third-party libraries are importable."""
        ...

    # ------------------------------------------------------------------
    # helpers shared by all concrete engines
    # ------------------------------------------------------------------

    def _start_timer(self) -> float:
        return time.perf_counter()

    def _elapsed_ms(self, start: float) -> float:
        return (time.perf_counter() - start) * 1000.0

    def _make_result(
        self,
        price: float,
        std_error: float,
        paths_used: int,
        wall_clock_ms: float,
        S0: float,
        K: float,
        r: float,
        sigma: float,
        T: float,
        num_paths: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SimulationResult:
        return SimulationResult(
            price=price,
            std_error=std_error,
            paths_used=paths_used,
            wall_clock_ms=wall_clock_ms,
            engine_name=self.name,
            engine_type=self.engine_type,
            cache_key=build_cache_key(
                self.engine_type, S0, K, r, sigma, T, num_paths
            ),
            metadata=metadata or {},
        )

    def _error_result(
        self,
        error_msg: str,
        S0: float,
        K: float,
        r: float,
        sigma: float,
        T: float,
        num_paths: int,
        wall_clock_ms: float = 0.0,
    ) -> SimulationResult:
        """Return a result that clearly signals failure via metadata."""
        return self._make_result(
            price=float("nan"),
            std_error=float("nan"),
            paths_used=0,
            wall_clock_ms=wall_clock_ms,
            S0=S0,
            K=K,
            r=r,
            sigma=sigma,
            T=T,
            num_paths=num_paths,
            metadata={"error": error_msg},
        )


if __name__ == "__main__":
    key = build_cache_key("classical_mc", 100.0, 105.0, 0.05, 0.2, 1.0, 100_000)
    print(f"cache_key sample: {key}")

    r = SimulationResult(
        price=10.45,
        std_error=0.03,
        paths_used=100_000,
        wall_clock_ms=42.7,
        engine_name="test",
        engine_type="classical_mc",
        cache_key=key,
    )
    print(f"SimulationResult: price={r.price}, std_error={r.std_error}, "
          f"engine={r.engine_name}, cache_key={r.cache_key[:16]}...")
    print("base_engine self-test passed.")
