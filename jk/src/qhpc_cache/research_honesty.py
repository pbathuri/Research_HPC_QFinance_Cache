"""Research honesty manifest: explicit statement of what is and is not true about a run.

Machine-readable and human-readable artifact that prevents silent degradation,
unstated fallbacks, and misleading claims.
"""

from __future__ import annotations

import json
import os
import platform
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class HonestyFlag:
    """One truth/status assertion about a run."""

    flag_id: str
    description: str
    status: str  # "true" | "false" | "partial" | "skipped" | "unavailable"
    detail: str = ""
    category: str = ""  # "engine" | "data" | "metric" | "execution" | "evidence"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "flag_id": self.flag_id,
            "description": self.description,
            "status": self.status,
            "detail": self.detail,
            "category": self.category,
        }


def build_honesty_manifest(
    *,
    engines_available: List[str],
    engines_skipped: Dict[str, str],
    similarity_validated: bool = False,
    validation_coverage: float = 0.0,
    parquet_native: bool = True,
    gan_fallback: bool = False,
    pmu_proxy: bool = True,
    cpu_only: bool = True,
    single_node: bool = True,
    slurm_job_id: str = "",
    requested_backend: str = "cpu_local",
    run_label: str = "",
    exclusions_applied: Optional[List[Dict[str, str]]] = None,
    primary_evidence_artifacts: Optional[List[str]] = None,
    claims_supported: Optional[List[str]] = None,
    claims_unsupported: Optional[List[str]] = None,
    claims_provisional: Optional[List[str]] = None,
    eligible_for_aggregate: bool = True,
    aggregate_exclusion_reason: str = "",
) -> Dict[str, Any]:
    """Build the complete honesty manifest for one run."""
    flags: List[HonestyFlag] = []

    for eng in engines_available:
        flags.append(HonestyFlag(
            flag_id=f"engine_available_{eng}",
            description=f"Engine {eng} was available and used.",
            status="true",
            category="engine",
        ))
    for eng, reason in engines_skipped.items():
        flags.append(HonestyFlag(
            flag_id=f"engine_skipped_{eng}",
            description=f"Engine {eng} was skipped.",
            status="true",
            detail=reason,
            category="engine",
        ))

    flags.append(HonestyFlag(
        flag_id="cpu_only_execution",
        description="Run used only CPU computation (no GPU/QPU).",
        status="true" if cpu_only else "false",
        category="execution",
    ))
    flags.append(HonestyFlag(
        flag_id="single_node_execution",
        description="Run executed on a single node (no MPI distribution).",
        status="true" if single_node else "false",
        category="execution",
    ))
    flags.append(HonestyFlag(
        flag_id="pmu_metrics_are_proxy",
        description="PMU-like metrics are proxy/derived, not hardware counters.",
        status="true" if pmu_proxy else "false",
        category="metric",
    ))
    flags.append(HonestyFlag(
        flag_id="parquet_native",
        description="Parquet I/O used native pyarrow (not fallback).",
        status="true" if parquet_native else "false",
        detail="" if parquet_native else "pyarrow was not available; CSV fallback used.",
        category="data",
    ))
    flags.append(HonestyFlag(
        flag_id="gan_native",
        description="GAN phase used native torch path (not fallback).",
        status="false" if gan_fallback else "true",
        detail="GAN used numpy fallback." if gan_fallback else "",
        category="data",
    ))
    flags.append(HonestyFlag(
        flag_id="similarity_control_validated",
        description="Similarity reuse decisions were control-validated by recomputation.",
        status="true" if similarity_validated else "false",
        detail=f"Validation coverage: {validation_coverage:.1%}" if similarity_validated else "No control recomputation performed.",
        category="evidence",
    ))

    is_hpc = bool(slurm_job_id) or requested_backend.startswith("bigred") or requested_backend.startswith("slurm")
    flags.append(HonestyFlag(
        flag_id="hpc_execution",
        description="Run executed on HPC cluster (BigRed200 or similar).",
        status="true" if is_hpc else "false",
        detail=f"SLURM_JOB_ID={slurm_job_id}" if slurm_job_id else "Local execution.",
        category="execution",
    ))
    flags.append(HonestyFlag(
        flag_id="eligible_for_aggregate_research",
        description="Run is eligible for inclusion in aggregate research summaries.",
        status="true" if eligible_for_aggregate else "false",
        detail=aggregate_exclusion_reason if not eligible_for_aggregate else "",
        category="evidence",
    ))

    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "run_label": run_label,
        "requested_backend": requested_backend,
        "execution_host": platform.node(),
        "flags": [f.to_dict() for f in flags],
        "engines_available": engines_available,
        "engines_skipped": engines_skipped,
        "primary_evidence_artifacts": primary_evidence_artifacts or [],
        "secondary_debug_artifacts": [],
        "claims_supported": claims_supported or [],
        "claims_unsupported": claims_unsupported or [],
        "claims_provisional": claims_provisional or [],
        "exclusions_applied": exclusions_applied or [],
        "summary": {
            "total_flags": len(flags),
            "true_count": sum(1 for f in flags if f.status == "true"),
            "false_count": sum(1 for f in flags if f.status == "false"),
            "categories": list(set(f.category for f in flags)),
        },
    }


def write_honesty_manifest(
    manifest_data: Dict[str, Any],
    output_dir: Path,
) -> Dict[str, str]:
    """Write research_honesty_manifest.json and .md companion."""
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "research_honesty_manifest.json"
    json_path.write_text(json.dumps(manifest_data, indent=2))

    lines = [
        "# Research Honesty Manifest",
        "",
        f"Generated: {manifest_data['generated_utc']}",
        f"Run: {manifest_data.get('run_label', '')}",
        f"Host: {manifest_data.get('execution_host', '')}",
        f"Backend: {manifest_data.get('requested_backend', '')}",
        "",
        "## Status Flags",
        "",
        "| Flag | Status | Detail |",
        "|------|--------|--------|",
    ]
    for f in manifest_data.get("flags", []):
        status_str = f["status"].upper()
        lines.append(f"| {f['flag_id']} | {status_str} | {f.get('detail', '')} |")

    lines.extend([
        "",
        "## Engines",
        "",
        f"Available: {', '.join(manifest_data.get('engines_available', []))}",
        "",
    ])
    skipped = manifest_data.get("engines_skipped", {})
    if skipped:
        lines.append("Skipped:")
        for eng, reason in skipped.items():
            lines.append(f"- {eng}: {reason}")
        lines.append("")

    lines.extend([
        "## Evidence Eligibility",
        "",
        f"Eligible for aggregate research: "
        f"{'YES' if any(f['flag_id'] == 'eligible_for_aggregate_research' and f['status'] == 'true' for f in manifest_data.get('flags', [])) else 'NO'}",
        "",
    ])

    md_path = output_dir / "research_honesty_manifest.md"
    md_path.write_text("\n".join(lines))

    return {"json": str(json_path), "md": str(md_path)}
