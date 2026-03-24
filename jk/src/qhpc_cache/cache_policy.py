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

    Fallback behavior is explicit and consistent across code/docs/tests:

    - ``fallback_mode="heuristic"`` (default): use ``HeuristicCachePolicy``
    - ``fallback_mode="always_reuse"``: return ``True``
    - ``fallback_mode="no_reuse"``: return ``False``

    If ``model`` is absent or inference fails, fallback mode is applied.
    """

    VALID_FALLBACK_MODES = {"heuristic", "always_reuse", "no_reuse"}

    def __init__(self, model: Any = None, fallback_mode: str = "heuristic") -> None:
        if fallback_mode not in self.VALID_FALLBACK_MODES:
            raise ValueError(
                "Invalid fallback_mode. Expected one of "
                f"{sorted(self.VALID_FALLBACK_MODES)}, got {fallback_mode!r}."
            )
        self.model = model
        self.fallback_mode = str(fallback_mode)
        self._fallback = HeuristicCachePolicy()
        self.last_inference_error: str = ""
        self._decisions_total: int = 0
        self._model_inference_used_count: int = 0
        self._fallback_used_count: int = 0
        self._fallback_no_model_count: int = 0
        self._fallback_inference_error_count: int = 0
        self.last_decision_source: str = "none"

    def _fallback_decision(self, features: Dict[str, Any]) -> bool:
        mode = self.fallback_mode
        if mode == "heuristic":
            return self._fallback.decide(features)
        if mode == "always_reuse":
            return True
        if mode == "no_reuse":
            return False
        # Safe default if unsupported mode is provided.
        return self._fallback.decide(features)

    def decide(self, features: Dict[str, Any]) -> bool:
        self._decisions_total += 1
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
                self._model_inference_used_count += 1
                self.last_decision_source = "model"
                return prob > 0.5
            except Exception as exc:
                self.last_inference_error = str(exc)
                self._fallback_used_count += 1
                self._fallback_inference_error_count += 1
                self.last_decision_source = "fallback_inference_error"
                return self._fallback_decision(features)
        self._fallback_used_count += 1
        self._fallback_no_model_count += 1
        self.last_decision_source = "fallback_no_model"
        return self._fallback_decision(features)

    def diagnostics(self) -> Dict[str, Any]:
        """Return explicit policy decision diagnostics for experiment manifests."""
        return {
            "policy_name": self.__class__.__name__,
            "fallback_mode": self.fallback_mode,
            "has_model": self.model is not None,
            "decisions_total": self._decisions_total,
            "model_inference_used_count": self._model_inference_used_count,
            "fallback_used_count": self._fallback_used_count,
            "fallback_no_model_count": self._fallback_no_model_count,
            "fallback_inference_error_count": self._fallback_inference_error_count,
            "last_inference_error": self.last_inference_error,
            "last_decision_source": self.last_decision_source,
        }
