"""Accepted-similarity control-recomputation and validation.

When similarity reuse is accepted, this module provides control paths that
recompute the result and record the actual error, producing first-class
research artifacts rather than debug logs.
"""

from __future__ import annotations

import csv
import json
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from random import Random
from typing import Any, Dict, List, Optional, Sequence


TOLERANCE_PROFILES: Dict[str, float] = {
    "strict": 0.01,
    "moderate": 0.05,
    "exploratory": 0.10,
}

FAMILY_DEFAULT_TOLERANCES: Dict[str, str] = {
    "exact_repeat_pricing": "strict",
    "near_repeat_pricing": "moderate",
    "path_ladder_pricing": "moderate",
    "portfolio_cluster_condensation": "moderate",
    "overlapping_event_window_rebuild": "moderate",
    "stress_churn_pricing": "exploratory",
    "intraday_scenario_ladder": "moderate",
    "cross_sectional_basket": "moderate",
    "rolling_horizon_refresh": "moderate",
    "hotset_coldset_mixed": "moderate",
    "parameter_shock_grid": "exploratory",
}


@dataclass
class ValidationConfig:
    """Controls when and how similarity reuse is validated by recomputation.

    Modes:
      - off: no validation
      - sampled: probabilistic sampling (alias for probabilistic)
      - always: validate every reuse event
      - family_conditioned: use per_family_overrides or family defaults
      - regime_conditioned: use per_regime_overrides or defaults
      - probabilistic: legacy alias for sampled
      - deterministic: legacy alias for always
    """

    mode: str = "sampled"
    validation_rate: float = 0.20
    seed: int = 42
    tolerance_profile: str = "moderate"
    per_family_overrides: Dict[str, float] = field(default_factory=dict)
    per_family_tolerance: Dict[str, str] = field(default_factory=dict)
    per_regime_overrides: Dict[str, float] = field(default_factory=dict)

    def effective_rate(self, family: str, regime: str = "") -> float:
        resolved_mode = self._resolve_mode()
        if resolved_mode == "off":
            return 0.0
        if resolved_mode in ("always", "deterministic"):
            return 1.0
        if resolved_mode == "family_conditioned":
            return self.per_family_overrides.get(family, self.validation_rate)
        if resolved_mode == "regime_conditioned":
            return self.per_regime_overrides.get(regime, self.validation_rate)
        return self.per_family_overrides.get(family, self.validation_rate)

    def effective_tolerance(self, family: str) -> float:
        profile = self.per_family_tolerance.get(
            family,
            FAMILY_DEFAULT_TOLERANCES.get(family, self.tolerance_profile),
        )
        return TOLERANCE_PROFILES.get(profile, TOLERANCE_PROFILES["moderate"])

    def _resolve_mode(self) -> str:
        if self.mode in ("probabilistic", "sampled"):
            return "sampled"
        if self.mode in ("deterministic", "always"):
            return "always"
        return self.mode

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "resolved_mode": self._resolve_mode(),
            "validation_rate": self.validation_rate,
            "seed": self.seed,
            "tolerance_profile": self.tolerance_profile,
            "per_family_overrides": dict(self.per_family_overrides),
            "per_family_tolerance": dict(self.per_family_tolerance),
            "per_regime_overrides": dict(self.per_regime_overrides),
            "available_tolerance_profiles": dict(TOLERANCE_PROFILES),
        }


@dataclass
class ValidationResult:
    """One control-recomputation result."""

    request_id: str
    workload_family: str
    engine: str
    reuse_type: str  # "exact" | "similarity"
    reused_price: float
    reused_std_error: float
    recomputed_price: float
    recomputed_std_error: float
    absolute_error: float
    relative_error: float
    se_absolute_error: float
    tolerance_threshold: float
    tolerance_pass: bool
    feature_hash: str
    parameter_hash: str
    similarity_group_id: str
    regime_tag: str
    recompute_time_ms: float
    trigger_reason: str  # "policy" | "sampling" | "deterministic"
    eligible_for_summary: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "workload_family": self.workload_family,
            "engine": self.engine,
            "reuse_type": self.reuse_type,
            "reused_price": round(self.reused_price, 8),
            "reused_std_error": round(self.reused_std_error, 8),
            "recomputed_price": round(self.recomputed_price, 8),
            "recomputed_std_error": round(self.recomputed_std_error, 8),
            "absolute_error": round(self.absolute_error, 8),
            "relative_error": round(self.relative_error, 8),
            "se_absolute_error": round(self.se_absolute_error, 8),
            "tolerance_threshold": self.tolerance_threshold,
            "tolerance_pass": self.tolerance_pass,
            "feature_hash": self.feature_hash,
            "parameter_hash": self.parameter_hash,
            "similarity_group_id": self.similarity_group_id,
            "regime_tag": self.regime_tag,
            "recompute_time_ms": round(self.recompute_time_ms, 4),
            "trigger_reason": self.trigger_reason,
            "eligible_for_summary": self.eligible_for_summary,
        }


class SimilarityValidator:
    """Manages control-recomputation for similarity-reuse validation."""

    def __init__(self, config: Optional[ValidationConfig] = None):
        self.config = config or ValidationConfig()
        self._rng = Random(self.config.seed)
        self._results: List[ValidationResult] = []

    @property
    def results(self) -> List[ValidationResult]:
        return list(self._results)

    def should_validate(self, family: str, regime: str = "") -> bool:
        mode = self.config._resolve_mode()
        if mode == "off":
            return False
        if mode == "always":
            return True
        rate = self.config.effective_rate(family, regime)
        return self._rng.random() < rate

    def validate_reuse(
        self,
        *,
        request: Dict[str, Any],
        engine: Any,
        reused_result: Dict[str, Any],
        reuse_type: str,
        engine_name: str,
        tolerance_threshold: Optional[float] = None,
    ) -> ValidationResult:
        """Recompute and compare against cached/reused result."""
        family = str(request.get("workload_family", ""))
        if tolerance_threshold is None:
            tolerance_threshold = self.config.effective_tolerance(family)

        t0 = time.perf_counter()
        recomputed = engine.price(
            S0=float(request["S0"]),
            K=float(request["K"]),
            r=float(request["r"]),
            sigma=float(request["sigma"]),
            T=float(request["T"]),
            num_paths=int(request["num_paths"]),
            seed=int(request["random_seed"]),
        )
        recompute_ms = (time.perf_counter() - t0) * 1000.0

        reused_price = float(reused_result.get("price", 0.0))
        reused_se = float(reused_result.get("std_error", 0.0))
        recomputed_price = float(recomputed.price)
        recomputed_se = float(recomputed.std_error)

        abs_err = abs(reused_price - recomputed_price)
        denom = max(abs(recomputed_price), 1e-10)
        rel_err = abs_err / denom
        se_err = abs(reused_se - recomputed_se)
        tol_pass = rel_err <= tolerance_threshold

        resolved = self.config._resolve_mode()
        trigger = (
            "deterministic" if resolved == "always"
            else "sampling"
        )

        vr = ValidationResult(
            request_id=str(request.get("request_id", "")),
            workload_family=str(request.get("workload_family", "")),
            engine=engine_name,
            reuse_type=reuse_type,
            reused_price=reused_price,
            reused_std_error=reused_se,
            recomputed_price=recomputed_price,
            recomputed_std_error=recomputed_se,
            absolute_error=abs_err,
            relative_error=rel_err,
            se_absolute_error=se_err,
            tolerance_threshold=tolerance_threshold,
            tolerance_pass=tol_pass,
            feature_hash=str(request.get("feature_hash", "")),
            parameter_hash=str(request.get("parameter_hash", "")),
            similarity_group_id=str(request.get("similarity_group_id", "")),
            regime_tag=str(request.get("regime_tag", "")),
            recompute_time_ms=recompute_ms,
            trigger_reason=trigger,
            eligible_for_summary=True,
        )
        self._results.append(vr)
        return vr

    def summarize(self) -> Dict[str, Any]:
        n = len(self._results)
        if n == 0:
            return {
                "validation_count": 0,
                "validation_mode": self.config.mode,
                "status": "no_validations_performed",
            }

        eligible = [r for r in self._results if r.eligible_for_summary]
        passes = sum(1 for r in eligible if r.tolerance_pass)
        fails = sum(1 for r in eligible if not r.tolerance_pass)
        errors = [r.relative_error for r in eligible]
        abs_errors = [r.absolute_error for r in eligible]

        by_family: Dict[str, List[ValidationResult]] = {}
        for r in eligible:
            by_family.setdefault(r.workload_family, []).append(r)

        family_summaries = {}
        for fam, fam_results in by_family.items():
            fam_err = [r.relative_error for r in fam_results]
            fam_pass = sum(1 for r in fam_results if r.tolerance_pass)
            family_summaries[fam] = {
                "count": len(fam_results),
                "pass_count": fam_pass,
                "fail_count": len(fam_results) - fam_pass,
                "pass_rate": round(fam_pass / len(fam_results), 6) if fam_results else 0.0,
                "mean_relative_error": round(sum(fam_err) / len(fam_err), 8) if fam_err else 0.0,
                "max_relative_error": round(max(fam_err), 8) if fam_err else 0.0,
            }

        sorted_errors = sorted(errors)

        exact_validated = sum(1 for r in eligible if r.reuse_type == "exact")
        sim_validated = sum(1 for r in eligible if r.reuse_type == "similarity")
        false_accepts = sum(
            1 for r in eligible
            if r.reuse_type == "similarity" and not r.tolerance_pass
        )

        return {
            "validation_count": n,
            "eligible_count": len(eligible),
            "validation_mode": self.config.mode,
            "resolved_mode": self.config._resolve_mode(),
            "validation_rate": self.config.validation_rate,
            "tolerance_profile": self.config.tolerance_profile,
            "config": self.config.to_dict(),
            "pass_count": passes,
            "fail_count": fails,
            "tolerance_pass_rate": round(passes / len(eligible), 6) if eligible else 0.0,
            "exact_reuse_validated": exact_validated,
            "similarity_reuse_validated": sim_validated,
            "false_accept_count": false_accepts,
            "mean_relative_error": round(sum(errors) / len(errors), 8) if errors else 0.0,
            "median_relative_error": round(sorted_errors[len(sorted_errors) // 2], 8) if sorted_errors else 0.0,
            "p90_relative_error": round(sorted_errors[int(len(sorted_errors) * 0.9)], 8) if len(sorted_errors) > 1 else 0.0,
            "p99_relative_error": round(sorted_errors[min(int(len(sorted_errors) * 0.99), len(sorted_errors) - 1)], 8) if sorted_errors else 0.0,
            "worst_case_relative_error": round(max(errors), 8) if errors else 0.0,
            "mean_absolute_error": round(sum(abs_errors) / len(abs_errors), 8) if abs_errors else 0.0,
            "worst_case_absolute_error": round(max(abs_errors), 8) if abs_errors else 0.0,
            "by_family": family_summaries,
            "validation_coverage_rate": round(n / max(1, n + len(self._results) - n), 6),
        }


def write_validation_artifacts(
    validator: SimilarityValidator,
    output_dir: Path,
) -> Dict[str, str]:
    """Write similarity validation summary and examples."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: Dict[str, str] = {}

    summary = validator.summarize()
    summary_path = output_dir / "similarity_validation_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    paths["summary"] = str(summary_path)

    results = validator.results
    if results:
        examples_path = output_dir / "similarity_validation_examples.csv"
        fields = list(results[0].to_dict().keys())
        with open(examples_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for r in results:
                writer.writerow(r.to_dict())
        paths["examples_csv"] = str(examples_path)

    return paths
