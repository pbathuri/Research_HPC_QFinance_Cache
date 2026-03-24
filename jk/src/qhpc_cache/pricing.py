"""Risk-neutral Monte Carlo option pricing under GBM.

Implements standard discounted-payoff estimation: terminal draws for vanillas
and digitals, path simulation for Asian-style averages, optional antithetic
normals, and an optional control variate (terminal spot vs its Q-mean) for
European vanillas. European prices can be compared to Black–Scholes for
validation.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, replace
from typing import Any, List, Optional

from qhpc_cache.analytic_pricing import (
    black_scholes_call_price,
    black_scholes_put_price,
)
from qhpc_cache.feature_builder import build_cache_features
from qhpc_cache.market_models import (
    simulate_gbm_price_path_using_increments,
    simulate_gbm_terminal_price,
)
from qhpc_cache import payoffs
from qhpc_cache.variance_reduction import (
    apply_antithetic_variates_to_normals,
    confidence_interval_from_standard_error,
    control_variate_adjustment,
    estimate_standard_error,
    estimate_standard_error_from_mean_variance,
)


@dataclass
class MonteCarloPricingResult:
    """Monte Carlo estimate of the risk-neutral option value (discounted payoff).

    ``estimated_price`` equals ``discounted_payoff_mean`` here (per-path discount
    factor exp(−rT)). ``analytic_reference_price`` is set only when the pricer
    requests a European Black–Scholes comparison in terminal mode.
    """

    estimated_price: float
    discounted_payoff_mean: float
    payoff_variance: float
    standard_error: float
    confidence_interval_low: float
    confidence_interval_high: float
    number_of_paths: int
    payoff_name: str
    used_path_simulation: bool
    used_antithetic_variates: bool
    used_control_variate: bool
    analytic_reference_price: Optional[float] = None
    total_runtime_ms: float = 0.0
    cache_lookup_time_ms: float = 0.0
    simulation_time_ms: float = 0.0
    payoff_aggregation_time_ms: float = 0.0
    cache_put_time_ms: float = 0.0
    cache_hit: bool = False


@dataclass
class MonteCarloPricer:
    """Monte Carlo engine: GBM paths, payoff dispatch, discounting, optional variance reduction.

    Field ``payoff_type`` selects the payoff (e.g. ``european_call``, ``asian_call``);
    the same string appears as ``payoff_name`` on the result object.
    """

    S0: float
    K: float
    r: float
    sigma: float
    T: float
    num_paths: int
    payoff_type: str = "european_call"
    simulation_mode: str = "terminal"
    num_time_steps: int = 12
    use_antithetic_variates: bool = False
    use_black_scholes_control_variate: bool = False
    compare_analytic_black_scholes: bool = False
    random_seed: Optional[int] = None
    confidence_level: float = 0.95
    digital_payout_amount: float = 1.0
    cache_policy: Any = None
    cache_store: Any = None

    def _validate_simulation_inputs(self) -> None:
        if self.num_paths < 1:
            raise ValueError(
                "num_paths must be at least 1 for Monte Carlo simulation."
            )
        if self.simulation_mode == "path" and self.num_time_steps < 1:
            raise ValueError(
                "num_time_steps must be at least 1 when simulation_mode is 'path'."
            )

    def price_option(self) -> MonteCarloPricingResult:
        """Run simulation, optionally consult cache, return structured result."""
        total_start = time.perf_counter()
        self._validate_simulation_inputs()
        features = build_cache_features(
            instrument_type=self.payoff_type,
            S0=self.S0,
            K=self.K,
            r=self.r,
            sigma=self.sigma,
            T=self.T,
            num_paths=self.num_paths,
            simulation_mode=self.simulation_mode,
            num_time_steps=self.num_time_steps,
            use_antithetic_variates=self.use_antithetic_variates,
            use_black_scholes_control_variate=self.use_black_scholes_control_variate,
            compare_analytic_black_scholes=self.compare_analytic_black_scholes,
            confidence_level=self.confidence_level,
            digital_payout_amount=self.digital_payout_amount,
            random_seed=self.random_seed,
        )
        cache_lookup_time_ms = 0.0
        cache_put_time_ms = 0.0

        if self.cache_store is not None:
            policy_allows_lookup = (
                True
                if self.cache_policy is None
                else bool(self.cache_policy.decide(features))
            )
            if policy_allows_lookup:
                lookup_start = time.perf_counter()
                if hasattr(self.cache_store, "try_get"):
                    hit, cached = self.cache_store.try_get(
                        features,
                        policy_approved_reuse=(self.cache_policy is not None),
                    )
                else:
                    try:
                        cached = self.cache_store.get(features)
                        hit = True
                    except KeyError:
                        cached = None
                        hit = False
                cache_lookup_time_ms = (time.perf_counter() - lookup_start) * 1000.0
                if hit:
                    if isinstance(cached, MonteCarloPricingResult):
                        return self._attach_runtime_metrics(
                            cached,
                            total_runtime_ms=(time.perf_counter() - total_start) * 1000.0,
                            cache_lookup_time_ms=cache_lookup_time_ms,
                            simulation_time_ms=0.0,
                            payoff_aggregation_time_ms=0.0,
                            cache_put_time_ms=0.0,
                            cache_hit=True,
                        )
                    if isinstance(cached, tuple) and len(cached) == 2:
                        mean_price, payoff_variance = float(cached[0]), float(cached[1])
                        result = self._result_from_mean_var(
                            mean_price, payoff_variance, analytic_override=None
                        )
                        return self._attach_runtime_metrics(
                            result,
                            total_runtime_ms=(time.perf_counter() - total_start) * 1000.0,
                            cache_lookup_time_ms=cache_lookup_time_ms,
                            simulation_time_ms=0.0,
                            payoff_aggregation_time_ms=0.0,
                            cache_put_time_ms=0.0,
                            cache_hit=True,
                        )

        result, simulation_time_ms, payoff_aggregation_time_ms = self._simulate_and_price()
        if self.cache_store is not None:
            put_start = time.perf_counter()
            self.cache_store.put(features, result)
            cache_put_time_ms = (time.perf_counter() - put_start) * 1000.0
        return self._attach_runtime_metrics(
            result,
            total_runtime_ms=(time.perf_counter() - total_start) * 1000.0,
            cache_lookup_time_ms=cache_lookup_time_ms,
            simulation_time_ms=simulation_time_ms,
            payoff_aggregation_time_ms=payoff_aggregation_time_ms,
            cache_put_time_ms=cache_put_time_ms,
            cache_hit=False,
        )

    @staticmethod
    def _attach_runtime_metrics(
        result: MonteCarloPricingResult,
        *,
        total_runtime_ms: float,
        cache_lookup_time_ms: float,
        simulation_time_ms: float,
        payoff_aggregation_time_ms: float,
        cache_put_time_ms: float,
        cache_hit: bool,
    ) -> MonteCarloPricingResult:
        return replace(
            result,
            total_runtime_ms=float(total_runtime_ms),
            cache_lookup_time_ms=float(cache_lookup_time_ms),
            simulation_time_ms=float(simulation_time_ms),
            payoff_aggregation_time_ms=float(payoff_aggregation_time_ms),
            cache_put_time_ms=float(cache_put_time_ms),
            cache_hit=bool(cache_hit),
        )

    def _result_from_mean_var(
        self,
        mean_price: float,
        payoff_variance: float,
        analytic_override: Optional[float],
    ) -> MonteCarloPricingResult:
        """Build result when only mean/variance known (e.g. cache tuple legacy)."""
        path_count = self._effective_path_count()
        standard_error = estimate_standard_error_from_mean_variance(
            mean_price, payoff_variance, path_count
        )
        low, high = confidence_interval_from_standard_error(
            mean_price, standard_error, self.confidence_level
        )
        analytic_reference = (
            analytic_override
            if analytic_override is not None
            else self._analytic_reference_optional()
        )
        used_path = self.simulation_mode == "path"
        return MonteCarloPricingResult(
            estimated_price=mean_price,
            discounted_payoff_mean=mean_price,
            payoff_variance=payoff_variance,
            standard_error=standard_error,
            confidence_interval_low=low,
            confidence_interval_high=high,
            number_of_paths=path_count,
            payoff_name=self.payoff_type,
            used_path_simulation=used_path,
            used_antithetic_variates=self.use_antithetic_variates,
            used_control_variate=self.use_black_scholes_control_variate,
            analytic_reference_price=analytic_reference,
        )

    def _effective_path_count(self) -> int:
        base = self.num_paths
        if self.use_antithetic_variates:
            return 2 * base
        return base

    def _analytic_reference_optional(self) -> Optional[float]:
        if not self.compare_analytic_black_scholes:
            return None
        if self.simulation_mode != "terminal":
            return None
        if self.payoff_type == "european_call":
            return black_scholes_call_price(
                self.S0, self.K, self.r, self.sigma, self.T
            )
        if self.payoff_type == "european_put":
            return black_scholes_put_price(
                self.S0, self.K, self.r, self.sigma, self.T
            )
        return None

    def _simulate_and_price(self) -> tuple[MonteCarloPricingResult, float, float]:
        rng = random.Random(self.random_seed)
        analytic_reference = self._analytic_reference_optional()

        if self.simulation_mode == "terminal":
            return self._price_terminal_paths(rng, analytic_reference)
        if self.simulation_mode == "path":
            return self._price_path_scenarios(rng, analytic_reference)
        raise ValueError("simulation_mode must be 'terminal' or 'path'.")

    def _finalize_terminal_result(
        self,
        mean_price: float,
        payoff_variance: float,
        path_count: int,
        analytic_reference: Optional[float],
        used_control: bool,
    ) -> MonteCarloPricingResult:
        standard_error = estimate_standard_error_from_mean_variance(
            mean_price, payoff_variance, path_count
        )
        low, high = confidence_interval_from_standard_error(
            mean_price, standard_error, self.confidence_level
        )
        return MonteCarloPricingResult(
            estimated_price=mean_price,
            discounted_payoff_mean=mean_price,
            payoff_variance=payoff_variance,
            standard_error=standard_error,
            confidence_interval_low=low,
            confidence_interval_high=high,
            number_of_paths=path_count,
            payoff_name=self.payoff_type,
            used_path_simulation=False,
            used_antithetic_variates=self.use_antithetic_variates,
            used_control_variate=used_control,
            analytic_reference_price=analytic_reference,
        )

    def _price_terminal_paths(
        self,
        rng: random.Random,
        analytic_reference: Optional[float],
    ) -> tuple[MonteCarloPricingResult, float, float]:
        simulation_start = time.perf_counter()
        base_draws = [
            rng.gauss(0.0, 1.0) for path_index in range(self.num_paths)
        ]
        if self.use_antithetic_variates:
            z_list = apply_antithetic_variates_to_normals(base_draws)
        else:
            z_list = base_draws

        terminal_spots: List[float] = []
        for draw_index in range(len(z_list)):
            z = z_list[draw_index]
            spot_terminal = simulate_gbm_terminal_price(
                self.S0, self.r, self.sigma, self.T, z
            )
            terminal_spots.append(spot_terminal)
        simulation_time_ms = (time.perf_counter() - simulation_start) * 1000.0

        payoff_start = time.perf_counter()
        discounted_payoffs: List[float] = []
        discount_factor = math.exp(-self.r * self.T)
        for spot_terminal in terminal_spots:
            payoff_terminal = self._terminal_payoff(spot_terminal)
            discounted_payoffs.append(discount_factor * payoff_terminal)

        used_control = (
            self.use_black_scholes_control_variate
            and self.payoff_type in ("european_call", "european_put")
        )
        if used_control:
            expected_spot = self.S0 * math.exp(self.r * self.T)
            cv_output = control_variate_adjustment(
                discounted_payoffs, terminal_spots, expected_spot
            )
            mean_price = cv_output[0]
            payoff_variance = cv_output[1]
        else:
            mean_price = self._mean(discounted_payoffs)
            payoff_variance = self._sample_variance(discounted_payoffs, mean_price)
        payoff_aggregation_time_ms = (time.perf_counter() - payoff_start) * 1000.0

        result = self._finalize_terminal_result(
            mean_price,
            payoff_variance,
            len(discounted_payoffs),
            analytic_reference,
            used_control,
        )
        return result, simulation_time_ms, payoff_aggregation_time_ms

    def _price_path_scenarios(
        self,
        rng: random.Random,
        analytic_reference: Optional[float],
    ) -> tuple[MonteCarloPricingResult, float, float]:
        if self.payoff_type not in ("asian_call", "asian_put"):
            raise ValueError(
                "Path simulation_mode is intended for asian_call / asian_put."
            )
        simulation_start = time.perf_counter()
        path_variants_all: List[List[float]] = []
        for path_index in range(self.num_paths):
            increments = [
                rng.gauss(0.0, 1.0)
                for step_index in range(self.num_time_steps)
            ]
            path_variants_all.append(
                simulate_gbm_price_path_using_increments(
                    self.S0,
                    self.r,
                    self.sigma,
                    self.T,
                    self.num_time_steps,
                    increments,
                )
            )
            if self.use_antithetic_variates:
                negated = [-z for z in increments]
                path_variants_all.append(
                    simulate_gbm_price_path_using_increments(
                        self.S0,
                        self.r,
                        self.sigma,
                        self.T,
                        self.num_time_steps,
                        negated,
                    )
                )
        simulation_time_ms = (time.perf_counter() - simulation_start) * 1000.0

        payoff_start = time.perf_counter()
        discounted_payoffs: List[float] = []
        discount_factor = math.exp(-self.r * self.T)
        for spot_path in path_variants_all:
            discounted_payoffs.append(discount_factor * self._path_payoff(spot_path))

        mean_price = self._mean(discounted_payoffs)
        payoff_variance = self._sample_variance(discounted_payoffs, mean_price)
        path_count = len(discounted_payoffs)
        standard_error = estimate_standard_error(discounted_payoffs)
        low, high = confidence_interval_from_standard_error(
            mean_price, standard_error, self.confidence_level
        )
        payoff_aggregation_time_ms = (time.perf_counter() - payoff_start) * 1000.0
        result = MonteCarloPricingResult(
            estimated_price=mean_price,
            discounted_payoff_mean=mean_price,
            payoff_variance=payoff_variance,
            standard_error=standard_error,
            confidence_interval_low=low,
            confidence_interval_high=high,
            number_of_paths=path_count,
            payoff_name=self.payoff_type,
            used_path_simulation=True,
            used_antithetic_variates=self.use_antithetic_variates,
            used_control_variate=False,
            analytic_reference_price=analytic_reference,
        )
        return result, simulation_time_ms, payoff_aggregation_time_ms

    def _terminal_payoff(self, terminal_spot_price: float) -> float:
        if self.payoff_type == "european_call":
            return payoffs.european_call_payoff(terminal_spot_price, self.K)
        if self.payoff_type == "european_put":
            return payoffs.european_put_payoff(terminal_spot_price, self.K)
        if self.payoff_type == "digital_call":
            return payoffs.digital_call_payoff(
                terminal_spot_price, self.K, self.digital_payout_amount
            )
        if self.payoff_type == "digital_put":
            return payoffs.digital_put_payoff(
                terminal_spot_price, self.K, self.digital_payout_amount
            )
        raise ValueError("Unknown payoff_type for terminal simulation.")

    def _path_payoff(self, spot_path: List[float]) -> float:
        if self.payoff_type == "asian_call":
            return payoffs.asian_call_payoff(spot_path, self.K)
        if self.payoff_type == "asian_put":
            return payoffs.asian_put_payoff(spot_path, self.K)
        raise ValueError("Unknown payoff_type for path simulation.")

    @staticmethod
    def _mean(values: List[float]) -> float:
        count = len(values)
        total = 0.0
        for index in range(count):
            total += values[index]
        return total / float(count)

    @staticmethod
    def _sample_variance(values: List[float], mean_value: float) -> float:
        count = len(values)
        if count < 2:
            return 0.0
        sum_sq = 0.0
        for index in range(count):
            diff = values[index] - mean_value
            sum_sq += diff * diff
        return sum_sq / float(count - 1)
