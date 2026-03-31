"""Tests for final pre-BigRed hardening pass.

Covers:
  1. Artifact contract layer
  2. Decision overhead accounting
  3. Speedup bounds
  4. Similarity validation control surface
  5. Full-pipeline parity (unit-level)
  6. Cross-run aggregation with overhead
  7. SLM export schema completeness
  8. BigRed wave preset existence
  9. Artifact contract manifest completeness
"""

from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

import pytest


# ── S1: Artifact contract ──

def test_artifact_contract_tracks_all_canonical_artifacts():
    from qhpc_cache.artifact_contract import (
        ArtifactContract,
        CANONICAL_RESEARCH_ARTIFACTS,
        CANONICAL_SLM_ARTIFACTS,
    )
    contract = ArtifactContract(run_path="test")
    summary = contract.summary()
    total_expected = len(CANONICAL_RESEARCH_ARTIFACTS) + len(CANONICAL_SLM_ARTIFACTS)
    assert summary["total"] == total_expected
    assert summary["pending"] == total_expected
    assert summary["generated"] == 0


def test_artifact_contract_mark_generated():
    from qhpc_cache.artifact_contract import ArtifactContract
    contract = ArtifactContract()
    contract.mark_generated("cacheability_summary")
    contract.mark_skipped("portfolio_overlap", "not applicable in this path")
    contract.mark_unavailable("slm_training_jsonl", "zero pricings")
    s = contract.summary()
    assert s["generated"] == 1
    assert s["skipped"] == 1
    assert s["unavailable"] == 1


def test_artifact_contract_write_and_placeholder():
    from qhpc_cache.artifact_contract import ArtifactContract
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        contract = ArtifactContract()
        contract.mark_generated("expanded_metrics")
        contract.write_skipped_placeholder(out, "portfolio_overlap", "not applicable")
        contract.write(out)

        assert (out / "artifact_contract.json").exists()
        placeholder = out / "research" / "portfolio_overlap.json"
        assert placeholder.exists()
        data = json.loads(placeholder.read_text())
        assert data["status"] == "skipped"
        assert data["reason"] == "not applicable"


# ── S2: Overhead accounting ──

def test_overhead_accounting_computes_fields():
    from qhpc_cache.overhead_accounting import compute_overhead_accounting, summarize_overhead
    rows = [
        {
            "request_id": "r1",
            "workload_family": "exact_repeat_pricing",
            "engine": "classical_mc",
            "total_runtime_ms": 50.0,
            "pricing_compute_time_ms": 40.0,
            "compute_avoided_proxy": 0.0,
            "time_saved_proxy": 30.0,
            "cache_hit": True,
        },
        {
            "request_id": "r2",
            "workload_family": "stress_churn_pricing",
            "engine": "classical_mc",
            "total_runtime_ms": 100.0,
            "pricing_compute_time_ms": 90.0,
            "compute_avoided_proxy": 0.0,
            "time_saved_proxy": 0.0,
            "cache_hit": False,
        },
    ]
    overhead_rows = compute_overhead_accounting(rows)
    assert len(overhead_rows) == 2
    assert overhead_rows[0].request_id == "r1"
    assert overhead_rows[0].gross_runtime_saved_ms == 30.0
    assert overhead_rows[0].decision_overhead_ms > 0
    assert overhead_rows[0].net_utility_ms <= 30.0

    summary = summarize_overhead(overhead_rows)
    assert summary["total_requests"] == 2
    assert "by_family" in summary
    assert "exact_repeat_pricing" in summary["by_family"]
    assert "stress_churn_pricing" in summary["by_family"]


def test_overhead_empty_rows():
    from qhpc_cache.overhead_accounting import compute_overhead_accounting, summarize_overhead
    rows = compute_overhead_accounting([])
    assert rows == []
    s = summarize_overhead(rows)
    assert s["status"] == "no_data"


def test_net_utility_summary_write():
    from qhpc_cache.overhead_accounting import write_net_utility_summary
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        write_net_utility_summary({"total_requests": 5, "net_utility_positive": True}, out)
        assert (out / "net_utility_summary.json").exists()


# ── S3: Speedup bounds ──

def test_speedup_bounds_amdahl():
    from qhpc_cache.speedup_bounds import compute_speedup_bounds
    bounds = compute_speedup_bounds(
        total_wall_ms=1000.0,
        pricing_compute_ms=800.0,
        orchestration_ms=200.0,
        overhead_ms=10.0,
        gross_savings_ms=400.0,
        net_savings_ms=390.0,
        total_pricings=100,
        exact_hit_rate=0.5,
    )
    assert "amdahl_fixed_size_bounds" in bounds
    assert "gustafson_scaled_estimates" in bounds
    assert "realized_speedup" in bounds
    assert "measured_decomposition" in bounds
    assert bounds["measured_decomposition"]["pricing_fraction"] == 0.8


def test_speedup_bounds_weak_reuse_flag():
    from qhpc_cache.speedup_bounds import compute_speedup_bounds
    bounds = compute_speedup_bounds(
        total_wall_ms=1000.0,
        pricing_compute_ms=800.0,
        orchestration_ms=200.0,
        total_pricings=50,
        exact_hit_rate=0.02,
    )
    assert bounds["run_context"]["weak_reuse_flag"] is True
    assert "insufficient reuse" in bounds["honesty_note"].lower()


def test_speedup_bounds_write():
    from qhpc_cache.speedup_bounds import compute_speedup_bounds, write_speedup_bounds
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        bounds = compute_speedup_bounds(
            total_wall_ms=1000.0,
            pricing_compute_ms=500.0,
            orchestration_ms=500.0,
        )
        paths = write_speedup_bounds(bounds, out)
        assert (out / "speedup_bounds.json").exists()
        assert (out / "speedup_bounds.md").exists()


def test_speedup_bounds_zero_wall():
    from qhpc_cache.speedup_bounds import compute_speedup_bounds
    bounds = compute_speedup_bounds(
        total_wall_ms=0.0,
        pricing_compute_ms=0.0,
        orchestration_ms=0.0,
    )
    assert bounds["status"] == "insufficient_data"


# ── S4: Similarity validation control surface ──

def test_validation_config_tolerance_profiles():
    from qhpc_cache.similarity_validation import (
        ValidationConfig,
        TOLERANCE_PROFILES,
        FAMILY_DEFAULT_TOLERANCES,
    )
    assert "strict" in TOLERANCE_PROFILES
    assert "moderate" in TOLERANCE_PROFILES
    assert "exploratory" in TOLERANCE_PROFILES
    assert TOLERANCE_PROFILES["strict"] < TOLERANCE_PROFILES["moderate"] < TOLERANCE_PROFILES["exploratory"]

    config = ValidationConfig(tolerance_profile="strict")
    assert config.effective_tolerance("exact_repeat_pricing") == TOLERANCE_PROFILES["strict"]
    assert config.effective_tolerance("stress_churn_pricing") == TOLERANCE_PROFILES["exploratory"]


def test_validation_config_modes():
    from qhpc_cache.similarity_validation import ValidationConfig

    off = ValidationConfig(mode="off")
    assert off.effective_rate("any") == 0.0

    always = ValidationConfig(mode="always")
    assert always.effective_rate("any") == 1.0

    sampled = ValidationConfig(mode="sampled", validation_rate=0.5)
    rate = sampled.effective_rate("any")
    assert 0.0 <= rate <= 1.0

    family_cond = ValidationConfig(
        mode="family_conditioned",
        per_family_overrides={"exact_repeat_pricing": 1.0},
        validation_rate=0.1,
    )
    assert family_cond.effective_rate("exact_repeat_pricing") == 1.0
    assert family_cond.effective_rate("stress_churn_pricing") == 0.1


def test_validation_config_to_dict_includes_profiles():
    from qhpc_cache.similarity_validation import ValidationConfig
    config = ValidationConfig(mode="sampled", tolerance_profile="moderate")
    d = config.to_dict()
    assert "available_tolerance_profiles" in d
    assert "resolved_mode" in d
    assert d["resolved_mode"] == "sampled"


def test_validator_summary_includes_false_accepts():
    from qhpc_cache.similarity_validation import SimilarityValidator, ValidationConfig
    config = ValidationConfig(mode="always", tolerance_profile="moderate")
    v = SimilarityValidator(config)
    summary = v.summarize()
    assert summary["validation_count"] == 0
    assert summary["validation_mode"] == "always"


def test_should_validate_respects_mode():
    from qhpc_cache.similarity_validation import SimilarityValidator, ValidationConfig

    v_off = SimilarityValidator(ValidationConfig(mode="off"))
    assert v_off.should_validate("any") is False

    v_on = SimilarityValidator(ValidationConfig(mode="always"))
    assert v_on.should_validate("any") is True


# ── S5: Full-pipeline parity (contract-level) ──

def test_full_pipeline_contract_covers_all_artifacts():
    from qhpc_cache.artifact_contract import (
        ArtifactContract,
        CANONICAL_RESEARCH_ARTIFACTS,
        CANONICAL_SLM_ARTIFACTS,
    )
    contract = ArtifactContract(run_path="full_pipeline")
    all_ids = [a[0] for a in CANONICAL_RESEARCH_ARTIFACTS + CANONICAL_SLM_ARTIFACTS]

    for aid in all_ids:
        contract.mark_generated(aid)

    summary = contract.summary()
    assert summary["pending"] == 0
    assert summary["generated"] == len(all_ids)


def test_full_pipeline_skipped_artifact_honest():
    from qhpc_cache.artifact_contract import ArtifactContract
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        contract = ArtifactContract(run_path="full_pipeline")
        contract.write_skipped_placeholder(
            out, "similarity_validation_examples",
            "No per-request similarity validation in full pipeline"
        )
        placeholder = out / "research" / "similarity_validation_examples.csv"
        assert placeholder.exists()
        data = json.loads(placeholder.read_text())
        assert data["status"] == "skipped"


# ── S6: Cross-run aggregation with overhead ──

def test_aggregation_overhead_fields():
    from qhpc_cache.run_aggregation import aggregate_research_runs
    with tempfile.TemporaryDirectory() as td:
        run1 = Path(td) / "run1"
        run1.mkdir()
        research1 = run1 / "research"
        research1.mkdir()
        slm1 = run1 / "slm_datasets"
        slm1.mkdir()

        (run1 / "repeated_workload_manifest.json").write_text(json.dumps({
            "scale_label": "smoke",
            "deterministic_seed": 42,
            "lane_selection": "lane_a",
            "summary_rows_count": 10,
        }))
        (research1 / "expanded_metrics.json").write_text(json.dumps({
            "exact_hit_rate": 0.5, "similarity_hit_rate": 0.1,
            "useful_hit_rate": 0.4, "harmful_hit_rate": 0.0,
            "by_family": {},
        }))
        (research1 / "utility_summary.json").write_text(json.dumps({
            "total_utility": 10.0, "mean_utility": 1.0,
        }))
        (research1 / "cacheability_summary.json").write_text(json.dumps({
            "cache_recall_on_reusable": 0.5,
        }))
        (research1 / "hpc_utilization.json").write_text(json.dumps({
            "compute_fraction": 0.6,
        }))
        (research1 / "similarity_validation_summary.json").write_text(json.dumps({
            "tolerance_pass_rate": 1.0,
        }))
        (research1 / "research_claims_manifest.json").write_text(json.dumps({
            "claims": [{"claim_id": "c1", "support_status": "supported"}],
        }))
        (research1 / "research_honesty_manifest.json").write_text(json.dumps({
            "summary": {"engines": ["classical_mc"]},
        }))
        (research1 / "net_utility_summary.json").write_text(json.dumps({
            "total_overhead_ms": 5.0,
            "total_net_saved_ms": 15.0,
            "net_utility_positive": True,
            "beneficial_rate": 0.8,
            "harmful_rate": 0.0,
        }))
        (research1 / "speedup_bounds.json").write_text(json.dumps({
            "realized_speedup": {"realized_net_speedup": 1.2},
            "run_context": {"weak_reuse_flag": False},
        }))
        (run1 / "artifact_contract.json").write_text(json.dumps({
            "generated": 10, "skipped": 2,
        }))
        (slm1 / "slm_export_manifest.json").write_text(json.dumps({
            "files": {"a": "a.jsonl"},
        }))

        out_dir = Path(td) / "aggregate"
        result = aggregate_research_runs([run1], out_dir)

        assert result["run_count"] == 1
        assert "overhead_aggregate" in result
        assert result["overhead_aggregate"]["run_count"] == 1
        assert result["overhead_aggregate"]["mean_total_overhead_ms"] == 5.0
        assert (out_dir / "per_run_overhead.csv").exists()


def test_aggregation_claim_safety():
    from qhpc_cache.run_aggregation import _compute_claim_safety
    matrix = {
        "c1": {"r1": "supported", "r2": "supported"},
        "c2": {"r1": "supported", "r2": "not_tested"},
        "c3": {"r1": "not_tested", "r2": "not_tested"},
    }
    records = [{"run_label": "r1"}, {"run_label": "r2"}]
    safety = _compute_claim_safety(matrix, records)
    assert "c1" in safety["safe_to_claim"]
    assert "c2" in safety["provisional"]
    assert "c3" in safety["not_yet_safe"]


# ── S7: SLM schema completeness ──

def test_slm_schema_includes_overhead_fields():
    from qhpc_cache.slm_exports import SLM_FEATURE_SCHEMA
    overhead_fields = [
        "decision_overhead_ms",
        "gross_runtime_saved_ms",
        "net_runtime_saved_ms",
        "net_utility_label",
    ]
    for f in overhead_fields:
        assert f in SLM_FEATURE_SCHEMA, f"Missing SLM field: {f}"


def test_slm_record_includes_overhead():
    from qhpc_cache.slm_exports import build_slm_record
    row = {
        "request_id": "t1",
        "workload_family": "exact_repeat_pricing",
        "engine": "classical_mc",
        "cache_hit": True,
    }
    record = build_slm_record(
        row,
        overhead_info={
            "decision_overhead_ms": 1.5,
            "gross_runtime_saved_ms": 20.0,
            "net_runtime_saved_ms": 18.5,
            "net_utility_label": "beneficial",
        },
    )
    assert record["decision_overhead_ms"] == 1.5
    assert record["net_runtime_saved_ms"] == 18.5
    assert record["net_utility_label"] == "beneficial"


# ── S8: BigRed wave presets ──

def test_scale_profiles_include_new_waves():
    from qhpc_cache.repeated_workload_generator import SCALE_PROFILES
    for profile in ("long_wave", "locality_burst", "validation_heavy"):
        assert profile in SCALE_PROFILES, f"Missing scale profile: {profile}"
        assert len(SCALE_PROFILES[profile]) == 11


def test_bigred_scripts_exist():
    scripts_dir = Path(__file__).parent.parent / "scripts"
    expected = [
        "bigred_repeated_standard.sh",
        "bigred_repeated_heavy.sh",
        "bigred_repeated_long_wave.sh",
        "bigred_validation_heavy.sh",
        "bigred_locality_burst.sh",
        "bigred_full_pipeline.sh",
        "bigred_full_long_budget.sh",
        "bigred_seed_array.sh",
    ]
    for name in expected:
        assert (scripts_dir / name).exists(), f"Missing BigRed script: {name}"


# ── S9: Integration smoke ──

def test_repeated_workload_emits_contract_and_overhead():
    """Quick smoke: repeated-workload study with 1 family emits artifact contract + overhead."""
    from qhpc_cache.repeated_workload_study import run_repeated_workload_study
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "smoke"
        result = run_repeated_workload_study(
            lane_selection="lane_a",
            scale_label="smoke",
            seed=42,
            output_dir=str(out),
            budget_minutes=2.0,
            emit_plots=False,
            workload_families=["exact_repeat_pricing"],
        )
        manifest = result["manifest"]
        assert "artifact_contract" in manifest
        assert manifest["artifact_contract"]["generated"] > 0

        assert "net_utility_summary" in manifest
        assert manifest["net_utility_summary"]["total_requests"] > 0

        assert "speedup_bounds" in manifest
        assert "measured_decomposition" in manifest["speedup_bounds"]

        assert (out / "artifact_contract.json").exists()
        assert (out / "research" / "net_utility_summary.json").exists()
        assert (out / "research" / "speedup_bounds.json").exists()
        assert (out / "research" / "speedup_bounds.md").exists()
