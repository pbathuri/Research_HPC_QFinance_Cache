"""Tests for Pandora circuit cache and fingerprinting.

All tests use fingerprint_from_metadata and do not require cirq.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qhpc_cache.circuit_fingerprint import (
    CircuitFingerprint,
    CircuitFingerprintEncoder,
    compute_structural_similarity,
    fingerprint_from_metadata,
)
from qhpc_cache.pandora_circuit_cache import PandoraCircuitCache


def _sample_metadata(
    n_qubits: int = 6,
    gate_count: int = 130,
    depth: int = 66,
    prob: float = 0.15,
) -> dict:
    return {
        "n_qubits": n_qubits,
        "gate_count": gate_count,
        "circuit_depth": depth,
        "prob_ancilla_one": prob,
    }


class TestCircuitFingerprint:
    def test_fingerprint_creation(self):
        fp = CircuitFingerprint(
            gate_type_histogram={"X": 10, "H": 5},
            qubit_count=6,
            depth=20,
            total_gate_count=15,
            connectivity_density=0.5,
            parameter_count=3,
            measurement_count=1,
            parameter_signature="abc123",
        )
        assert fp.qubit_count == 6
        assert fp.depth == 20
        assert fp.total_gate_count == 15
        assert fp.gate_type_histogram["X"] == 10
        assert fp.connectivity_density == 0.5
        assert fp.parameter_count == 3
        assert fp.measurement_count == 1

    def test_fingerprint_from_metadata(self):
        meta = _sample_metadata()
        fp = fingerprint_from_metadata(meta)
        assert fp.qubit_count == 6
        assert fp.depth == 66
        assert fp.total_gate_count == 130
        assert isinstance(fp.gate_type_histogram, dict)
        assert len(fp.gate_type_histogram) > 0
        assert len(fp.parameter_signature) == 16

    def test_fingerprint_json_serialization(self):
        fp = fingerprint_from_metadata(_sample_metadata())
        encoded = json.dumps(fp, cls=CircuitFingerprintEncoder)
        decoded = json.loads(encoded)
        assert decoded["qubit_count"] == 6
        assert "gate_type_histogram" in decoded

    def test_fingerprint_to_dict(self):
        fp = fingerprint_from_metadata(_sample_metadata())
        d = fp.to_dict()
        assert d["qubit_count"] == 6
        assert isinstance(d["gate_type_histogram"], dict)


class TestStructuralSimilarity:
    def test_structural_similarity_identical(self):
        meta = _sample_metadata()
        fp = fingerprint_from_metadata(meta)
        score, components = compute_structural_similarity(fp, fp)
        assert score == pytest.approx(1.0, abs=1e-9)
        for v in components.values():
            assert v == pytest.approx(1.0, abs=1e-9)

    def test_structural_similarity_different(self):
        fp1 = fingerprint_from_metadata(
            _sample_metadata(n_qubits=4, gate_count=20, depth=10, prob=0.1)
        )
        fp2 = fingerprint_from_metadata(
            _sample_metadata(n_qubits=12, gate_count=5000, depth=4100, prob=0.9)
        )
        score, _ = compute_structural_similarity(fp1, fp2)
        assert score < 0.5

    def test_structural_similarity_similar(self):
        fp1 = fingerprint_from_metadata(
            _sample_metadata(n_qubits=6, gate_count=130, depth=66, prob=0.15)
        )
        fp2 = fingerprint_from_metadata(
            _sample_metadata(n_qubits=6, gate_count=135, depth=68, prob=0.16)
        )
        score, components = compute_structural_similarity(fp1, fp2)
        assert 0.5 < score < 1.0
        assert "gate_histogram_jaccard" in components
        assert "depth_proximity" in components

    def test_similarity_symmetry(self):
        fp1 = fingerprint_from_metadata(_sample_metadata(n_qubits=5, gate_count=80))
        fp2 = fingerprint_from_metadata(_sample_metadata(n_qubits=7, gate_count=200))
        s12, _ = compute_structural_similarity(fp1, fp2)
        s21, _ = compute_structural_similarity(fp2, fp1)
        assert s12 == pytest.approx(s21, abs=1e-9)


class TestPandoraCache:
    def test_pandora_cache_exact_hit(self):
        cache = PandoraCircuitCache(similarity_threshold=0.85)
        params = {
            "S0": 100.0, "K": 105.0, "sigma": 0.2,
            "T": 1.0, "r": 0.05, "num_paths": 4096,
        }
        fp = fingerprint_from_metadata(_sample_metadata())
        cache.store(params, fp, "circuit_repr_placeholder", 50.0)

        hit_type, entry = cache.lookup(params, fp)
        assert hit_type == "exact"
        assert entry is not None
        assert entry.reuse_count == 1

    def test_pandora_cache_structural_hit(self):
        cache = PandoraCircuitCache(similarity_threshold=0.80)
        params_a = {
            "S0": 100.0, "K": 105.0, "sigma": 0.2,
            "T": 1.0, "r": 0.05, "num_paths": 4096,
        }
        fp_a = fingerprint_from_metadata(
            _sample_metadata(n_qubits=6, gate_count=130, depth=66)
        )
        cache.store(params_a, fp_a, "repr_a", 50.0)

        params_b = {
            "S0": 101.0, "K": 106.0, "sigma": 0.21,
            "T": 1.0, "r": 0.05, "num_paths": 4096,
        }
        fp_b = fingerprint_from_metadata(
            _sample_metadata(n_qubits=6, gate_count=135, depth=68)
        )
        hit_type, entry = cache.lookup(params_b, fp_b)
        assert hit_type == "structural"
        assert entry is not None

    def test_pandora_cache_miss(self):
        cache = PandoraCircuitCache(similarity_threshold=0.95)
        params_a = {
            "S0": 100.0, "K": 105.0, "sigma": 0.2,
            "T": 1.0, "r": 0.05, "num_paths": 4096,
        }
        fp_a = fingerprint_from_metadata(
            _sample_metadata(n_qubits=4, gate_count=20, depth=10)
        )
        cache.store(params_a, fp_a, "repr_a", 50.0)

        params_b = {
            "S0": 200.0, "K": 50.0, "sigma": 0.6,
            "T": 3.0, "r": 0.01, "num_paths": 1024,
        }
        fp_b = fingerprint_from_metadata(
            _sample_metadata(n_qubits=12, gate_count=5000, depth=4100)
        )
        hit_type, entry = cache.lookup(params_b, fp_b)
        assert hit_type == "miss"
        assert entry is None

    def test_pandora_cache_metrics(self):
        cache = PandoraCircuitCache(similarity_threshold=0.85)
        params = {
            "S0": 100.0, "K": 105.0, "sigma": 0.2,
            "T": 1.0, "r": 0.05, "num_paths": 4096,
        }
        fp = fingerprint_from_metadata(_sample_metadata())
        cache.store(params, fp, "repr", 50.0)

        cache.lookup(params, fp)
        cache.lookup(params, fp)

        m = cache.metrics()
        assert m.exact_hits == 2
        assert m.total_lookups == 2
        assert m.entries == 1
        assert m.total_compilation_time_saved_ms > 0
        assert m.misses == 0

    def test_pandora_cache_clear(self):
        cache = PandoraCircuitCache()
        params = {"S0": 100.0, "K": 105.0, "sigma": 0.2, "T": 1.0, "r": 0.05, "num_paths": 4096}
        fp = fingerprint_from_metadata(_sample_metadata())
        cache.store(params, fp, "repr", 50.0)
        cache.clear()
        m = cache.metrics()
        assert m.entries == 0
        assert m.exact_hits == 0

    def test_pandora_cache_export_evidence(self, tmp_path: Path):
        cache = PandoraCircuitCache()
        params = {"S0": 100.0, "K": 105.0, "sigma": 0.2, "T": 1.0, "r": 0.05, "num_paths": 4096}
        fp = fingerprint_from_metadata(_sample_metadata())
        cache.store(params, fp, "repr", 50.0)
        cache.lookup(params, fp)

        paths = cache.export_evidence(tmp_path)
        evidence_path = Path(paths["pandora_cache_evidence"])
        assert evidence_path.exists()
        data = json.loads(evidence_path.read_text())
        assert data["exact_hits"] == 1
        assert len(data["entry_details"]) == 1


class TestPandoraStudy:
    def test_pandora_study_smoke(self, tmp_path: Path):
        from qhpc_cache.pandora_circuit_study import (
            PandoraStudyConfig,
            run_pandora_study,
        )

        config = PandoraStudyConfig(
            scale_label="smoke",
            similarity_threshold=0.85,
            n_qubits=4,
            output_dir=tmp_path / "pandora_smoke",
            seed=42,
        )
        summary = run_pandora_study(config)

        assert summary["total_problems"] == 20
        assert summary["misses"] >= 0
        assert summary["exact_hits"] >= 0
        assert (tmp_path / "pandora_smoke" / "pandora_study_results.csv").exists()
        assert (tmp_path / "pandora_smoke" / "pandora_cache_metrics.json").exists()
        assert (tmp_path / "pandora_smoke" / "pandora_compilation_savings.json").exists()
        assert (tmp_path / "pandora_smoke" / "pandora_cache_evidence.json").exists()
