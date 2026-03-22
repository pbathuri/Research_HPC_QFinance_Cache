"""Cache policies: transparent heuristics, logistic score, and **placeholder** AI hook.

Decisions only gate reuse of stored estimates; they do not replace pricing math.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Optional


class BaseCachePolicy:
    """Base class for cache policies."""

    def decide(self, features: Dict[str, Any]) -> bool:
        raise NotImplementedError("CachePolicy subclasses must implement decide()")


@dataclass
class LogisticPolicyWeights:
    """Readable weights for numeric features in the logistic policy."""

    weight_num_paths: float = -1e-4
    weight_volatility: float = -1.0
    weight_maturity_years: float = -0.5
    weight_similarity_score: float = 1.25
    weight_exact_match_flag: float = 2.0
    bias: float = 0.0


class LogisticCachePolicy(BaseCachePolicy):
    """Linear score + sigmoid; all constants live in ``LogisticPolicyWeights``."""

    def __init__(self, weights: Optional[LogisticPolicyWeights] = None) -> None:
        self.weights = weights or LogisticPolicyWeights()

    def decide(self, features: Dict[str, Any]) -> bool:
        linear_sum = self.weights.bias
        linear_sum += self.weights.weight_num_paths * float(
            features.get("num_paths", 0)
        )
        linear_sum += self.weights.weight_volatility * float(
            features.get("volatility", 0.0)
        )
        linear_sum += self.weights.weight_maturity_years * float(
            features.get("maturity_in_years", features.get("maturity", 0.0))
        )
        linear_sum += self.weights.weight_similarity_score * float(
            features.get("similarity_score", 0.0)
        )
        if features.get("exact_match_exists", False):
            linear_sum += self.weights.weight_exact_match_flag
        probability = 1.0 / (1.0 + math.exp(-linear_sum))
        return probability > 0.5


class HeuristicCachePolicy(BaseCachePolicy):
    """Rule-based policy with explicit priority order (easy to edit in research)."""

    def decide(self, features: Dict[str, Any]) -> bool:
        if features.get("exact_match_exists", False) is True:
            return True

        similarity_score = features.get("similarity_score")
        if isinstance(similarity_score, (int, float)) and similarity_score < 0.35:
            return False

        num_paths = features.get("num_paths", 0)
        volatility = features.get("volatility", 0.0)
        if not isinstance(num_paths, (int, float)) or not isinstance(
            volatility, (int, float)
        ):
            return False
        return (num_paths <= 100_000) and (volatility < 0.30)


class AIAssistedCachePolicy(BaseCachePolicy):
    """Optional external model hook; **not** a production finance classifier.

    If ``model`` is absent or inference fails, falls back to
    ``HeuristicCachePolicy`` so experiments stay runnable offline.
    """

    def __init__(self, model: Any = None) -> None:
        self.model = model
        self._fallback = HeuristicCachePolicy()

    def decide(self, features: Dict[str, Any]) -> bool:
        if self.model is not None:
            try:
                ordered_keys = sorted(features.keys())
                feature_vector = []
                for key in ordered_keys:
                    value = features[key]
                    if isinstance(value, bool):
                        feature_vector.append(1.0 if value else 0.0)
                    elif isinstance(value, (int, float)):
                        feature_vector.append(float(value))
                    else:
                        feature_vector.append(0.0)
                prob = float(self.model.predict_proba([feature_vector])[0][1])
                return prob > 0.5
            except Exception as exc:
                print(
                    "Warning: AIAssistedCachePolicy model inference failed "
                    f"({exc}); falling back to heuristic policy."
                )
        return self._fallback.decide(features)
