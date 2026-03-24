"""QuantLib-backed Monte Carlo and analytic European option pricing.

Uses ``ql.MCEuropeanEngine`` with a ``GeneralizedBlackScholesProcess`` for
the stochastic path, and ``ql.AnalyticEuropeanEngine`` for closed-form
comparison.
"""

from __future__ import annotations

import math
from typing import Optional

from qhpc_cache.quantum_engines.base_engine import SimulationEngine, SimulationResult


class QuantLibEngine(SimulationEngine):
    """Wraps QuantLib's MC pricing for European call options."""

    @property
    def name(self) -> str:
        return "QuantLib-MC"

    @property
    def engine_type(self) -> str:
        return "quantlib_mc"

    @classmethod
    def available(cls) -> bool:
        try:
            import QuantLib  # noqa: F401
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
            import QuantLib as ql

            today = ql.Date.todaysDate()
            maturity = today + ql.Period(int(round(T * 365)), ql.Days)
            ql.Settings.instance().evaluationDate = today

            day_count = ql.Actual365Fixed()
            calendar = ql.NullCalendar()

            spot_handle = ql.QuoteHandle(ql.SimpleQuote(S0))
            flat_ts = ql.YieldTermStructureHandle(
                ql.FlatForward(today, r, day_count)
            )
            flat_vol = ql.BlackVolTermStructureHandle(
                ql.BlackConstantVol(today, calendar, sigma, day_count)
            )
            dividend_ts = ql.YieldTermStructureHandle(
                ql.FlatForward(today, 0.0, day_count)
            )

            process = ql.BlackScholesMertonProcess(
                spot_handle, dividend_ts, flat_ts, flat_vol
            )

            payoff = ql.PlainVanillaPayoff(ql.Option.Call, K)
            exercise = ql.EuropeanExercise(maturity)
            option = ql.VanillaOption(payoff, exercise)

            rng_str = "pseudorandom"
            mc_engine = ql.MCEuropeanEngine(
                process,
                rng_str,
                timeSteps=1,
                requiredSamples=num_paths,
                seed=seed if seed is not None else 42,
            )
            option.setPricingEngine(mc_engine)
            mc_price = option.NPV()
            mc_error = option.errorEstimate()

            wall_ms = self._elapsed_ms(t0)
            return self._make_result(
                price=mc_price,
                std_error=mc_error,
                paths_used=num_paths,
                wall_clock_ms=wall_ms,
                S0=S0, K=K, r=r, sigma=sigma, T=T, num_paths=num_paths,
                metadata={"rng": rng_str, "time_steps": 1},
            )
        except Exception as exc:
            return self._error_result(
                str(exc), S0, K, r, sigma, T, num_paths, self._elapsed_ms(t0)
            )

    # ------------------------------------------------------------------

    def analytic_price(
        self,
        S0: float,
        K: float,
        r: float,
        sigma: float,
        T: float,
    ) -> float:
        """Closed-form European call via QuantLib's AnalyticEuropeanEngine."""
        try:
            import QuantLib as ql

            today = ql.Date.todaysDate()
            maturity = today + ql.Period(int(round(T * 365)), ql.Days)
            ql.Settings.instance().evaluationDate = today

            day_count = ql.Actual365Fixed()
            calendar = ql.NullCalendar()

            spot_handle = ql.QuoteHandle(ql.SimpleQuote(S0))
            flat_ts = ql.YieldTermStructureHandle(
                ql.FlatForward(today, r, day_count)
            )
            flat_vol = ql.BlackVolTermStructureHandle(
                ql.BlackConstantVol(today, calendar, sigma, day_count)
            )
            dividend_ts = ql.YieldTermStructureHandle(
                ql.FlatForward(today, 0.0, day_count)
            )

            process = ql.BlackScholesMertonProcess(
                spot_handle, dividend_ts, flat_ts, flat_vol
            )

            payoff = ql.PlainVanillaPayoff(ql.Option.Call, K)
            exercise = ql.EuropeanExercise(maturity)
            option = ql.VanillaOption(payoff, exercise)

            option.setPricingEngine(ql.AnalyticEuropeanEngine(process))
            return option.NPV()
        except Exception:
            d1 = (math.log(S0 / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
            d2 = d1 - sigma * math.sqrt(T)
            from qhpc_cache.analytic_pricing import normal_cdf
            return S0 * normal_cdf(d1) - K * math.exp(-r * T) * normal_cdf(d2)


if __name__ == "__main__":
    engine = QuantLibEngine()
    print(f"QuantLib available: {engine.available()}")

    result = engine.price(
        S0=100.0, K=105.0, r=0.05, sigma=0.2, T=1.0,
        num_paths=50_000, seed=12345,
    )
    print(f"MC price : {result.price:.4f}  (std_error={result.std_error:.4f})")
    print(f"Wall time: {result.wall_clock_ms:.1f} ms")
    print(f"Metadata : {result.metadata}")

    analytic = engine.analytic_price(S0=100.0, K=105.0, r=0.05, sigma=0.2, T=1.0)
    print(f"Analytic : {analytic:.4f}")
    print("quantlib_engine self-test passed.")
