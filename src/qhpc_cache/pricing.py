"""Monte Carlo option pricing baseline for European options."""

from dataclasses import dataclass
import math
import random
from typing import Any, List, Tuple

from qhpc_cache.feature_builder import build_cache_features


@dataclass
class MonteCarloPricer:
    """Classical Monte Carlo pricer for European options.

    This class estimates the price of a European option by simulating
    random paths of the underlying asset price using geometric Brownian
    motion.  The pricing logic is simple and serves as a baseline for
    comparing to more advanced (quantum or hybrid) methods in the future.

    Parameters
    ----------
    S0: float
        Initial stock price.
    K: float
        Strike price of the option.
    r: float
        Risk‑free interest rate (annualized).
    sigma: float
        Volatility of the underlying asset (annualized).
    T: float
        Time to maturity in years.
    num_paths: int
        Number of Monte Carlo paths to simulate.
    cache_policy: Any, optional
        Optional cache policy; used with cache_store to decide reuse.
    cache_store: Any, optional
        Optional cache store; used to store and retrieve (mean, variance).
    """

    S0: float
    K: float
    r: float
    sigma: float
    T: float
    num_paths: int
    cache_policy: Any = None
    cache_store: Any = None

    def simulate_paths(self) -> List[float]:
        """Simulate asset price paths using geometric Brownian motion.

        Returns
        -------
        List[float]
            A list of terminal asset prices at time T.
        """
        dt = self.T
        # Precompute constants for efficiency
        drift = (self.r - 0.5 * self.sigma ** 2) * dt
        diffusion = self.sigma * math.sqrt(dt)
        prices: List[float] = []
        for _ in range(self.num_paths):
            # Generate a random sample from the standard normal distribution
            z = random.gauss(0.0, 1.0)
            # Simulate the terminal price using GBM
            ST = self.S0 * math.exp(drift + diffusion * z)
            prices.append(ST)
        return prices

    def payoff(self, ST: float) -> float:
        """Compute the payoff of a European call option.

        Parameters
        ----------
        ST: float
            Terminal asset price at maturity.

        Returns
        -------
        float
            Payoff of the call option, max(ST - K, 0).
        """
        return max(ST - self.K, 0.0)

    def price_option(self) -> Tuple[float, float]:
        """Estimate the option price and variance via Monte Carlo simulation.

        This method simulates a set of terminal asset prices, computes the
        corresponding option payoffs, discounts them back to present
        value, and returns the mean and variance of the discounted
        payoffs.

        Returns
        -------
        Tuple[float, float]
            Estimated option price and variance of the discounted payoffs.
        """
        features = build_cache_features(
            "call_option", self.num_paths, self.sigma, self.T
        )

        if self.cache_policy is not None and self.cache_store is not None:
            if self.cache_policy.decide(features) and self.cache_store.has(
                features
            ):
                return self.cache_store.get(features)

        prices = self.simulate_paths()
        discounted_payoffs: List[float] = []
        for ST in prices:
            payoff_value = self.payoff(ST)
            discounted_payoff = math.exp(-self.r * self.T) * payoff_value
            discounted_payoffs.append(discounted_payoff)
        n = len(discounted_payoffs)
        mean = sum(discounted_payoffs) / n
        # Future: Fourier control variate (analytic or COS price) could reduce variance here.
        variance = (
            sum((x - mean) ** 2 for x in discounted_payoffs) / (n - 1)
            if n > 1
            else 0.0
        )

        if self.cache_store is not None:
            self.cache_store.put(features, (mean, variance))

        return mean, variance
