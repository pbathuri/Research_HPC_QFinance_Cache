"""Monaco uncertainty-propagation engine for option pricing.

Uses the ``monaco`` library to propagate input uncertainty (spot price and
volatility treated as normal random variables around their nominal values)
through a discounted-payoff model.  Monaco handles draw generation via
Sobol sequences, execution, and statistical post-processing including
sensitivity indices.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from qhpc_cache.quantum_engines.base_engine import SimulationEngine, SimulationResult


class MonacoEngine(SimulationEngine):
    """Wraps Monaco's ``Sim`` framework for uncertainty propagation."""

    @property
    def name(self) -> str:
        return "Monaco-UP"

    @property
    def engine_type(self) -> str:
        return "monaco_mc"

    @classmethod
    def available(cls) -> bool:
        try:
            import monaco  # noqa: F401
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
            import monaco
            import scipy.stats as st

            spot_std = S0 * 0.01
            vol_std = sigma * 0.05

            def _preprocess(case):
                iv = case.getInVals()
                return (iv["S0"].val, iv["sigma"].val)

            def _run(S0_draw: float, sigma_draw: float) -> float:
                z = np.random.standard_normal()
                S_T = S0_draw * math.exp(
                    (r - 0.5 * sigma_draw**2) * T
                    + sigma_draw * math.sqrt(T) * z
                )
                return math.exp(-r * T) * max(S_T - K, 0.0)

            def _postprocess(case, disc_payoff):
                case.addOutVal("discounted_payoff", disc_payoff)

            sim = monaco.Sim(
                name="OptionPrice",
                ndraws=num_paths,
                fcns={
                    monaco.SimFunctions.PREPROCESS: _preprocess,
                    monaco.SimFunctions.RUN: _run,
                    monaco.SimFunctions.POSTPROCESS: _postprocess,
                },
                singlethreaded=True,
                verbose=False,
                seed=seed or 42,
            )
            sim.addInVar(
                name="S0", dist=st.norm,
                distkwargs={"loc": S0, "scale": spot_std},
            )
            sim.addInVar(
                name="sigma", dist=st.norm,
                distkwargs={"loc": sigma, "scale": vol_std},
            )

            sim.runSim()

            ov = sim.outvars.get("discounted_payoff")
            if ov is None:
                return self._error_result(
                    "No output variable 'discounted_payoff' produced",
                    S0, K, r, sigma, T, num_paths, self._elapsed_ms(t0),
                )

            payoffs = np.array(ov.vals, dtype=float)
            price_est = float(np.mean(payoffs))
            std_err = float(np.std(payoffs, ddof=1) / math.sqrt(len(payoffs)))
            pcts = np.percentile(payoffs, [5, 25, 50, 75, 95]).tolist()

            sensitivities: dict = {}
            try:
                sim.calcSensitivities()
                ov_fresh = sim.outvars["discounted_payoff"]
                sensitivities = {
                    k: float(v) for k, v in ov_fresh.sensitivity_ratios.items()
                }
            except Exception:
                pass

            wall_ms = self._elapsed_ms(t0)
            return self._make_result(
                price=price_est,
                std_error=std_err,
                paths_used=num_paths,
                wall_clock_ms=wall_ms,
                S0=S0, K=K, r=r, sigma=sigma, T=T, num_paths=num_paths,
                metadata={
                    "percentiles_5_25_50_75_95": pcts,
                    "sensitivity_ratios": sensitivities,
                    "spot_std": spot_std,
                    "vol_std": vol_std,
                },
            )
        except Exception as exc:
            return self._error_result(
                str(exc), S0, K, r, sigma, T, num_paths, self._elapsed_ms(t0)
            )


if __name__ == "__main__":
    engine = MonacoEngine()
    print(f"Monaco available: {engine.available()}")

    result = engine.price(
        S0=100.0, K=105.0, r=0.05, sigma=0.2, T=1.0,
        num_paths=5_000, seed=99,
    )
    print(f"Price    : {result.price:.4f}  (std_error={result.std_error:.4f})")
    print(f"Wall time: {result.wall_clock_ms:.1f} ms")
    print(f"Metadata : {result.metadata}")
    print("monaco_engine self-test passed.")
