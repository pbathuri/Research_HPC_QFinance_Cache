"""Focused tests for repeated-workload generator and study outputs."""

from __future__ import annotations

import csv
import unittest
import tempfile
from pathlib import Path

import run_repeated_workload_study as repeated_workload_cli
from qhpc_cache.repeated_workload_generator import (
    LANE_A_ID,
    LANE_B_ID,
    REQUIRED_WORKLOAD_FAMILIES,
    generate_repeated_workload_requests,
)
from qhpc_cache.repeated_workload_study import run_repeated_workload_study


class TestRepeatedWorkloadStudy(unittest.TestCase):
    def test_cli_alias_include_stress_lane(self) -> None:
        parser = repeated_workload_cli._build_parser()
        args = parser.parse_args(["--lane", "lane_a", "--include-stress-lane"])
        self.assertEqual(repeated_workload_cli._resolve_lane_selection(args), "both")
        self.assertIn("--include-stress-lane", parser.format_help())

    def test_lane_generation_correctness(self) -> None:
        generated = generate_repeated_workload_requests(
            scale_label="smoke",
            seed=123,
            lane_selection="both",
        )
        self.assertEqual(set(generated.keys()), {LANE_A_ID, LANE_B_ID})
        self.assertEqual(set(generated[LANE_A_ID].keys()), set(REQUIRED_WORKLOAD_FAMILIES))
        self.assertEqual(set(generated[LANE_B_ID].keys()), set(REQUIRED_WORKLOAD_FAMILIES))

        lane_a_all = [row for fam in generated[LANE_A_ID].values() for row in fam]
        lane_b_all = [row for fam in generated[LANE_B_ID].values() for row in fam]
        lane_a_unique_ratio = len({row["parameter_hash"] for row in lane_a_all}) / float(len(lane_a_all))
        lane_b_unique_ratio = len({row["parameter_hash"] for row in lane_b_all}) / float(len(lane_b_all))
        self.assertGreater(lane_b_unique_ratio, lane_a_unique_ratio)

    def test_exact_repeat_family_contains_true_repetition(self) -> None:
        generated = generate_repeated_workload_requests(
            scale_label="smoke",
            seed=321,
            lane_selection="lane_a",
            workload_families=["exact_repeat_pricing"],
        )
        rows = generated[LANE_A_ID]["exact_repeat_pricing"]
        parameter_hashes = [row["parameter_hash"] for row in rows]
        self.assertGreater(len(parameter_hashes), len(set(parameter_hashes)))
        groups = [row.get("exact_repeat_group_id", "") for row in rows]
        self.assertTrue(any(group for group in groups))
        self.assertGreater(max(groups.count(g) for g in set(groups) if g), 1)

    def test_near_repeat_family_contains_clustered_similarity(self) -> None:
        generated = generate_repeated_workload_requests(
            scale_label="smoke",
            seed=456,
            lane_selection="lane_a",
            workload_families=["near_repeat_pricing"],
        )
        rows = generated[LANE_A_ID]["near_repeat_pricing"]
        clusters = sorted({row.get("cluster_id", "") for row in rows if row.get("cluster_id", "")})
        self.assertGreaterEqual(len(clusters), 2)
        per_cluster_hashes = {}
        for row in rows:
            cluster_id = row.get("cluster_id", "")
            if not cluster_id:
                continue
            per_cluster_hashes.setdefault(cluster_id, set()).add(row["parameter_hash"])
        self.assertTrue(any(len(v) > 1 for v in per_cluster_hashes.values()))

    def test_manifest_outputs_rankings_and_schema(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td) / "repeated_workload_phase"
            run_repeated_workload_study(
                output_dir=out_dir,
                lane_selection="both",
                scale_label="smoke",
                seed=9,
                emit_plots=False,
                engine_allowlist_override=["classical_mc"],
            )
            expected_files = [
                "repeated_workload_manifest.json",
                "repeated_workload_summary.csv",
                "repeated_workload_rankings.csv",
                "repeated_workload_rankings_summary.md",
                "repeated_workload_timing_summary.csv",
                "repeated_workload_cache_summary.csv",
                "repeated_workload_family_comparison.csv",
            ]
            for name in expected_files:
                self.assertTrue((out_dir / name).exists(), msg=f"missing {name}")

            with (out_dir / "repeated_workload_summary.csv").open("r", newline="") as handle:
                reader = csv.DictReader(handle)
                fieldnames = set(reader.fieldnames or [])
                required_fields = {
                    "workload_family",
                    "lane_id",
                    "request_count",
                    "unique_request_keys",
                    "repeated_request_keys",
                    "exact_hit_rate",
                    "similarity_hit_rate",
                    "miss_rate",
                    "mean_reuse_distance",
                    "locality_score",
                    "approximate_working_set_size",
                    "total_runtime_ms",
                    "average_runtime_ms",
                    "p50_runtime_ms",
                    "p90_runtime_ms",
                    "p99_runtime_ms",
                    "compute_avoided_proxy",
                    "time_saved_proxy",
                    "outlier_count",
                }
                self.assertTrue(required_fields.issubset(fieldnames))


if __name__ == "__main__":
    unittest.main()

