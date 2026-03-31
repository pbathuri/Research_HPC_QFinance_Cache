"""BigRed200 run profiles and budget utilization tracking.

Defines ready-to-use run profiles for different research objectives,
budget-aware workload scaling, and post-run aggregation utilities.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class BudgetUtilization:
    """Tracks budget utilization truthfully."""

    requested_budget_minutes: float
    actual_runtime_minutes: float = 0.0
    budget_utilization_fraction: float = 0.0
    termination_reason: str = ""
    workload_limited_flag: bool = False
    budget_limited_flag: bool = False
    pricing_cap_reached: bool = False
    contract_cap_reached: bool = False
    engine_pool_limited_flag: bool = False

    def finalize(self, runtime_seconds: float, *, total_pricings: int, max_pricings: int) -> None:
        self.actual_runtime_minutes = runtime_seconds / 60.0
        if self.requested_budget_minutes > 0:
            self.budget_utilization_fraction = min(
                1.0, self.actual_runtime_minutes / self.requested_budget_minutes
            )
        else:
            self.budget_utilization_fraction = 0.0

        if self.actual_runtime_minutes >= self.requested_budget_minutes * 0.95:
            self.budget_limited_flag = True
            self.termination_reason = "budget_exhausted"
        elif total_pricings >= max_pricings:
            self.pricing_cap_reached = True
            self.termination_reason = "pricing_cap_reached"
        else:
            self.workload_limited_flag = True
            self.termination_reason = "workload_exhausted_before_budget"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requested_budget_minutes": round(self.requested_budget_minutes, 2),
            "actual_runtime_minutes": round(self.actual_runtime_minutes, 4),
            "budget_utilization_fraction": round(self.budget_utilization_fraction, 4),
            "termination_reason": self.termination_reason,
            "workload_limited_flag": self.workload_limited_flag,
            "budget_limited_flag": self.budget_limited_flag,
            "pricing_cap_reached": self.pricing_cap_reached,
            "contract_cap_reached": self.contract_cap_reached,
            "engine_pool_limited_flag": self.engine_pool_limited_flag,
        }


@dataclass
class WorkloadScalingConfig:
    """Principled workload volume scaling parameters."""

    num_contracts: int = 8
    scenario_multiplier: int = 1
    family_repeat_multiplier: int = 1
    convergence_ladder_multiplier: int = 1
    seed_sweep_count: int = 1
    max_pricings_total: int = 100_000
    max_windows_total: int = 50

    def to_dict(self) -> Dict[str, Any]:
        return {
            "num_contracts": self.num_contracts,
            "scenario_multiplier": self.scenario_multiplier,
            "family_repeat_multiplier": self.family_repeat_multiplier,
            "convergence_ladder_multiplier": self.convergence_ladder_multiplier,
            "seed_sweep_count": self.seed_sweep_count,
            "max_pricings_total": self.max_pricings_total,
            "max_windows_total": self.max_windows_total,
        }


RUN_PROFILES: Dict[str, Dict[str, Any]] = {
    "smoke_cluster_validation": {
        "description": "Quick cluster validation: verify engines load, cache works, outputs are written.",
        "scale_label": "smoke",
        "lane_selection": "lane_a",
        "seed": 42,
        "budget_minutes": 5,
        "emit_plots": False,
        "scaling": WorkloadScalingConfig(
            num_contracts=4,
            scenario_multiplier=1,
            max_pricings_total=500,
        ),
        "slurm": {
            "job_name": "qhpc_smoke",
            "walltime": "00:10:00",
            "partition": "general",
            "nodes": 1,
            "ntasks": 1,
            "cpus_per_task": 4,
            "mem": "8G",
        },
    },
    "finance_reuse_standard": {
        "description": "Standard finance-reuse study: all families, both lanes, standard scale.",
        "scale_label": "standard",
        "lane_selection": "both",
        "seed": 123,
        "budget_minutes": 30,
        "emit_plots": True,
        "scaling": WorkloadScalingConfig(
            num_contracts=8,
            scenario_multiplier=1,
            max_pricings_total=10_000,
        ),
        "slurm": {
            "job_name": "qhpc_reuse_std",
            "walltime": "00:45:00",
            "partition": "general",
            "nodes": 1,
            "ntasks": 1,
            "cpus_per_task": 16,
            "mem": "32G",
        },
    },
    "finance_reuse_heavy": {
        "description": "Heavy finance-reuse study: all families, both lanes, heavy scale.",
        "scale_label": "heavy",
        "lane_selection": "both",
        "seed": 123,
        "budget_minutes": 120,
        "emit_plots": True,
        "scaling": WorkloadScalingConfig(
            num_contracts=8,
            scenario_multiplier=2,
            family_repeat_multiplier=2,
            max_pricings_total=50_000,
        ),
        "slurm": {
            "job_name": "qhpc_reuse_heavy",
            "walltime": "02:30:00",
            "partition": "general",
            "nodes": 1,
            "ntasks": 1,
            "cpus_per_task": 32,
            "mem": "64G",
        },
    },
    "similarity_validation_grid": {
        "description": "Focused similarity-cache validation: near-repeat and portfolio families only.",
        "scale_label": "heavy",
        "lane_selection": "both",
        "seed": 456,
        "budget_minutes": 60,
        "emit_plots": True,
        "families": ["near_repeat_pricing", "portfolio_cluster_condensation"],
        "scaling": WorkloadScalingConfig(
            num_contracts=8,
            scenario_multiplier=3,
            max_pricings_total=20_000,
        ),
        "slurm": {
            "job_name": "qhpc_sim_valid",
            "walltime": "01:15:00",
            "partition": "general",
            "nodes": 1,
            "ntasks": 1,
            "cpus_per_task": 16,
            "mem": "32G",
        },
    },
    "long_budget_full": {
        "description": "Long-budget full study: tests budget utilization and workload exhaustion.",
        "scale_label": "heavy",
        "lane_selection": "both",
        "seed": 789,
        "budget_minutes": 240,
        "emit_plots": True,
        "scaling": WorkloadScalingConfig(
            num_contracts=8,
            scenario_multiplier=3,
            family_repeat_multiplier=3,
            convergence_ladder_multiplier=2,
            max_pricings_total=100_000,
        ),
        "slurm": {
            "job_name": "qhpc_long_full",
            "walltime": "04:30:00",
            "partition": "general",
            "nodes": 1,
            "ntasks": 1,
            "cpus_per_task": 32,
            "mem": "64G",
        },
    },
    "repeated_array_seed_sweep": {
        "description": "Slurm array job: sweep seeds for ensemble statistics.",
        "scale_label": "standard",
        "lane_selection": "both",
        "seed": 100,  # base seed; array tasks add SLURM_ARRAY_TASK_ID
        "budget_minutes": 30,
        "emit_plots": True,
        "is_array_job": True,
        "array_range": "0-9",
        "scaling": WorkloadScalingConfig(
            seed_sweep_count=10,
            max_pricings_total=10_000,
        ),
        "slurm": {
            "job_name": "qhpc_seed_sweep",
            "walltime": "00:45:00",
            "partition": "general",
            "nodes": 1,
            "ntasks": 1,
            "cpus_per_task": 8,
            "mem": "16G",
            "array": "0-9",
        },
    },
    "locality_profile_bundle": {
        "description": "Targeted locality profiling across all families.",
        "scale_label": "standard",
        "lane_selection": "both",
        "seed": 321,
        "budget_minutes": 45,
        "emit_plots": True,
        "scaling": WorkloadScalingConfig(
            num_contracts=8,
            max_pricings_total=15_000,
        ),
        "slurm": {
            "job_name": "qhpc_locality",
            "walltime": "01:00:00",
            "partition": "general",
            "nodes": 1,
            "ntasks": 1,
            "cpus_per_task": 16,
            "mem": "32G",
        },
    },
}


def get_profile(name: str) -> Dict[str, Any]:
    if name not in RUN_PROFILES:
        raise KeyError(
            f"Unknown run profile {name!r}. Available: {sorted(RUN_PROFILES.keys())}"
        )
    return dict(RUN_PROFILES[name])


def list_profiles() -> List[Dict[str, str]]:
    return [
        {"name": name, "description": profile["description"]}
        for name, profile in RUN_PROFILES.items()
    ]


def generate_slurm_script(
    profile_name: str,
    *,
    output_dir: str = "outputs",
    email: str = "",
    account: str = "",
    extra_modules: Optional[List[str]] = None,
) -> str:
    """Generate a Slurm batch script for a given run profile."""
    profile = get_profile(profile_name)
    slurm = profile.get("slurm", {})
    is_array = profile.get("is_array_job", False)

    lines = [
        "#!/bin/bash",
        f"#SBATCH --job-name={slurm.get('job_name', 'qhpc_run')}",
        f"#SBATCH --time={slurm.get('walltime', '01:00:00')}",
        f"#SBATCH --partition={slurm.get('partition', 'general')}",
        f"#SBATCH --nodes={slurm.get('nodes', 1)}",
        f"#SBATCH --ntasks={slurm.get('ntasks', 1)}",
        f"#SBATCH --cpus-per-task={slurm.get('cpus_per_task', 1)}",
        f"#SBATCH --mem={slurm.get('mem', '16G')}",
        f"#SBATCH --output=slurm_{profile_name}_%j.out",
        f"#SBATCH --error=slurm_{profile_name}_%j.err",
    ]
    if is_array:
        lines.append(f"#SBATCH --array={slurm.get('array', '0-9')}")
    if email:
        lines.extend([
            f"#SBATCH --mail-user={email}",
            "#SBATCH --mail-type=BEGIN,END,FAIL",
        ])
    if account:
        lines.append(f"#SBATCH --account={account}")

    lines.extend([
        "",
        "set -euo pipefail",
        "",
        "echo '=== Environment ==='",
        "hostname",
        "date",
        "echo \"SLURM_JOB_ID=$SLURM_JOB_ID\"",
        "echo \"SLURM_ARRAY_TASK_ID=${SLURM_ARRAY_TASK_ID:-none}\"",
        "python3 --version",
        "",
    ])

    if extra_modules:
        for mod in extra_modules:
            lines.append(f"module load {mod}")
        lines.append("")

    lines.extend([
        "cd $SLURM_SUBMIT_DIR",
        "",
    ])

    seed = profile.get("seed", 123)
    if is_array:
        lines.append("SEED=$((${SLURM_ARRAY_TASK_ID} + " + str(seed) + "))")
        lines.append(f"OUT_DIR={output_dir}/repeated_workload_seed_${{SLURM_ARRAY_TASK_ID}}")
    else:
        lines.append(f"SEED={seed}")
        lines.append(f"OUT_DIR={output_dir}/repeated_workload_{profile_name}")

    families_arg = ""
    if profile.get("families"):
        families_arg = f"--families '{','.join(profile['families'])}'"

    lines.extend([
        "",
        "PYTHONPATH=src python3 run_repeated_workload_study.py \\",
        f"  --lane {profile.get('lane_selection', 'both')} \\",
        f"  --scale-label {profile.get('scale_label', 'standard')} \\",
        f"  --seed $SEED \\",
        f"  --output-root $OUT_DIR \\",
        f"  --budget-minutes {profile.get('budget_minutes', 30)} \\",
        f"  {families_arg}".rstrip(),
        "",
        "echo '=== Complete ==='",
        "date",
    ])

    return "\n".join(lines) + "\n"


def aggregate_runs(
    run_dirs: Sequence[str | Path],
    output_dir: str | Path,
) -> Dict[str, Any]:
    """Aggregate evidence from multiple BigRed200 runs into one comparative pack."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    runs_data: List[Dict[str, Any]] = []

    for rd in run_dirs:
        rd_path = Path(rd)
        evidence_json = rd_path / "cache_evidence_summary.json"
        manifest_json = rd_path / "repeated_workload_manifest.json"

        entry: Dict[str, Any] = {"run_dir": str(rd_path)}
        if evidence_json.exists():
            entry["evidence"] = json.loads(evidence_json.read_text(encoding="utf-8"))
        if manifest_json.exists():
            entry["manifest"] = json.loads(manifest_json.read_text(encoding="utf-8"))
        runs_data.append(entry)

    comparison: Dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_count": len(runs_data),
        "runs": [],
    }

    for entry in runs_data:
        evidence = entry.get("evidence", {})
        manifest = entry.get("manifest", {})
        econ = evidence.get("aggregate_economics", {})
        loc = evidence.get("aggregate_locality", {})

        comparison["runs"].append({
            "run_dir": entry["run_dir"],
            "seed": manifest.get("deterministic_seed"),
            "scale_label": manifest.get("scale_label"),
            "summary_rows_count": manifest.get("summary_rows_count", 0),
            "net_cache_value_ms": econ.get("net_cache_value_ms", 0),
            "exact_hits": econ.get("exact_hits", 0),
            "similarity_hits": econ.get("similarity_hits", 0),
            "misses": econ.get("misses", 0),
            "locality_regime": loc.get("locality_regime", ""),
            "temporal_locality_score": loc.get("temporal_locality_score", 0),
        })

    agg_json = out / "aggregated_evidence_comparison.json"
    agg_json.write_text(json.dumps(comparison, indent=2, default=str), encoding="utf-8")

    agg_md = out / "aggregated_evidence_comparison.md"
    lines = [
        "# Aggregated Evidence Comparison",
        "",
        f"- runs: {len(runs_data)}",
        f"- generated: `{comparison['generated_at_utc']}`",
        "",
        "| run | seed | scale | exact_hits | sim_hits | misses | net_value_ms | locality_regime |",
        "|---|---|---|---:|---:|---:|---:|---|",
    ]
    for r in comparison["runs"]:
        lines.append(
            f"| {Path(r['run_dir']).name} | {r.get('seed', '')} | "
            f"{r.get('scale_label', '')} | {r.get('exact_hits', 0)} | "
            f"{r.get('similarity_hits', 0)} | {r.get('misses', 0)} | "
            f"{r.get('net_cache_value_ms', 0):.2f} | {r.get('locality_regime', '')} |"
        )
    lines.append("")
    agg_md.write_text("\n".join(lines), encoding="utf-8")

    return {
        "comparison_json": str(agg_json),
        "comparison_md": str(agg_md),
        "run_count": len(runs_data),
    }
