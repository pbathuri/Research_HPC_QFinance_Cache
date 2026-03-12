"""Cache policy base and AI-assisted policy for future circuit/cache integration."""

import math
from typing import Any, Dict


class BaseCachePolicy:
    """Base class for cache policies.

    A cache policy controls when to reuse precomputed results (e.g. compiled
    quantum circuits) and when to recompute or compile fresh.  Used by
    MonteCarloPricer together with a cache_store when both are provided.
    Concrete subclasses should implement the ``decide`` method.
    """

    def decide(self, features: Dict[str, Any]) -> bool:
        """Decide whether to reuse a cached result based on input features.

        Parameters
        ----------
        features: Dict[str, Any]
            A dictionary of domain‑specific features that describe the
            computation request.  For example, in a quantum circuit
            context, features might include the size of the circuit,
            expected depth, error tolerance, or asset model parameters.

        Returns
        -------
        bool
            True if the cached result should be reused; False otherwise.
        """
        raise NotImplementedError("CachePolicy subclasses must implement decide()")


class AIAssistedCachePolicy(BaseCachePolicy):
    """A simple AI‑assisted cache policy.

    This class provides a stub for an AI‑based policy that decides
    whether to reuse a cached computation.  It accepts a pre‑trained
    model (optional) and features describing the current computation.
    Currently the logic uses a logistic function on a linear combination
    of features as a demonstration.  In practice, you would train a
    classifier or regression model on historical data to predict the
    utility of reuse.
    """

    def __init__(self, model: Any = None) -> None:
        self.model = model

    def decide(self, features: Dict[str, Any]) -> bool:
        """Return whether to reuse a cached result.

        The decision is currently made by a simple linear model
        followed by a logistic (sigmoid) activation to produce a
        probability.  The weights used here are placeholders and
        should be replaced with learned parameters.  This function
        always returns True if no model is provided.

        Parameters
        ----------
        features: Dict[str, Any]
            Descriptive features of the computation request.

        Returns
        -------
        bool
            True if reuse is advised; otherwise False.
        """
        # If an external model is provided, delegate decision to it
        if self.model is not None:
            try:
                # Convert features to a vector in a deterministic order
                ordered_keys = sorted(features.keys())
                feature_vector = [features[key] for key in ordered_keys]
                prob = float(self.model.predict_proba([feature_vector])[0][1])
                return prob > 0.5
            except Exception as e:
                # In the event of failure, log and fall back to default behavior
                print(
                    f"Warning: model inference failed ({e}); falling back to default reuse policy."
                )

        # Default behavior: simple heuristic logistic function
        # Normalize numeric features and assign weights
        weight_map: Dict[str, float] = {
            "num_paths": 1e-4,      # small weight for number of paths
            "volatility": -1.0,     # higher volatility reduces reuse likelihood
            "maturity": -0.5,       # longer maturities reduce reuse likelihood
            "instrument_type": 0.0  # non‑numeric; ignored in linear model
        }
        linear_sum = 0.0
        for key, value in features.items():
            w = weight_map.get(key, 0.0)
            # Only include numeric values in the linear combination
            if isinstance(value, (int, float)):
                linear_sum += w * float(value)
        # Logistic (sigmoid) activation
        prob = 1.0 / (1.0 + math.exp(-linear_sum))
        return prob > 0.5


class HeuristicCachePolicy(BaseCachePolicy):
    """Rule-based cache policy: reuse only if num_paths <= 100000 and volatility < 0.30."""

    def decide(self, features: Dict[str, Any]) -> bool:
        """Return True to reuse cache if num_paths <= 100000 and volatility < 0.30."""
        num_paths = features.get("num_paths", 0)
        volatility = features.get("volatility", 0.0)
        if not isinstance(num_paths, (int, float)) or not isinstance(
            volatility, (int, float)
        ):
            return False
        return (num_paths <= 100_000) and (volatility < 0.30)
