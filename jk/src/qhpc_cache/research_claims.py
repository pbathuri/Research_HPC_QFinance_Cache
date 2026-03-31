"""Research claims manifest: prevents narrative drift and enforces scientific honesty.

Creates a canonical artifact listing each research claim, its support status,
supporting evidence files, caveats, and required next experiments.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


class ClaimStatus:
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    NOT_SUPPORTED = "not_supported"
    NOT_TESTED = "not_tested"


@dataclass
class ResearchClaim:
    """One research claim with evidence linkage."""

    claim_id: str
    claim_text: str
    support_status: str
    supporting_files: List[str] = field(default_factory=list)
    supporting_metrics: Dict[str, Any] = field(default_factory=dict)
    caveats: List[str] = field(default_factory=list)
    required_next_experiments: List[str] = field(default_factory=list)
    epistemic_status: str = "not_tested"
    last_evaluated: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "claim_text": self.claim_text,
            "support_status": self.support_status,
            "supporting_files": self.supporting_files,
            "supporting_metrics": self.supporting_metrics,
            "caveats": self.caveats,
            "required_next_experiments": self.required_next_experiments,
            "epistemic_status": self.epistemic_status,
            "last_evaluated": self.last_evaluated,
        }


CANONICAL_CLAIMS: List[ResearchClaim] = [
    ResearchClaim(
        claim_id="C1_exact_reuse_exists",
        claim_text="Exact-match computational reuse exists for repeated quantitative finance workloads.",
        support_status=ClaimStatus.NOT_TESTED,
        caveats=["Requires workload families with structural repetition."],
        required_next_experiments=["Run exact_repeat_pricing family with >100 requests."],
    ),
    ResearchClaim(
        claim_id="C2_similarity_reuse_controllable",
        claim_text="Similarity-based reuse can be made safe under controlled tolerance thresholds.",
        support_status=ClaimStatus.NOT_TESTED,
        caveats=["Safety depends on tolerance calibration.", "Requires pricing error validation."],
        required_next_experiments=["Run tolerance sweeps.", "Compare reuse error against recompute."],
    ),
    ResearchClaim(
        claim_id="C3_reuse_family_dependent",
        claim_text="Reuse utility depends on workload family, regime, and portfolio overlap.",
        support_status=ClaimStatus.NOT_TESTED,
        caveats=["Some families may show zero reuse by design (stress/churn)."],
        required_next_experiments=["Run all workload families.", "Compare utility across families."],
    ),
    ResearchClaim(
        claim_id="C4_speedup_insufficient",
        claim_text="Speedup alone is insufficient to evaluate reuse; joint price/risk error evaluation is required.",
        support_status=ClaimStatus.NOT_TESTED,
        caveats=["Greeks evaluation not yet implemented for all engines."],
        required_next_experiments=["Run utility framework with error penalties.", "Compare speed-only vs joint utility."],
    ),
    ResearchClaim(
        claim_id="C5_hpc_evidence",
        claim_text="BigRed200 execution produces evidence on parallelization opportunity and utilization.",
        support_status=ClaimStatus.NOT_TESTED,
        caveats=["Current runs are single-node only.", "Effective parallelism is low."],
        required_next_experiments=["Run utilization decomposition on cluster.", "Measure scaling projection."],
    ),
    ResearchClaim(
        claim_id="C6_regime_affects_reuse",
        claim_text="Market regime conditions affect cacheability and reuse structure.",
        support_status=ClaimStatus.NOT_TESTED,
        caveats=["Regimes are synthetic approximations of real market conditions."],
        required_next_experiments=["Generate regime-conditioned workloads.", "Compare reuse across regimes."],
    ),
    ResearchClaim(
        claim_id="C7_traces_slm_ready",
        claim_text="Produced traces and features are suitable as SLM training data for reuse prediction.",
        support_status=ClaimStatus.NOT_TESTED,
        caveats=["Schema completeness must be validated.", "Label quality depends on ground-truth accuracy."],
        required_next_experiments=["Export SLM datasets.", "Validate schema completeness.", "Run basic ML baseline."],
    ),
    ResearchClaim(
        claim_id="C8_portfolio_overlap_affects_reuse",
        claim_text="Portfolio-level parameter overlap affects aggregate reuse rates.",
        support_status=ClaimStatus.NOT_TESTED,
        caveats=["Portfolio structure is synthetic."],
        required_next_experiments=["Run portfolio overlap analysis.", "Correlate overlap with hit rate."],
    ),
]


def evaluate_claims(
    evidence: Dict[str, Any],
    *,
    claims: Optional[List[ResearchClaim]] = None,
) -> List[ResearchClaim]:
    """Evaluate research claims against observed evidence.

    Updates support_status based on available metrics and files.
    """
    if claims is None:
        claims = [ResearchClaim(**c.to_dict()) for c in CANONICAL_CLAIMS]

    now = datetime.now(timezone.utc).isoformat()

    exact_hit_rate = float(evidence.get("exact_hit_rate", 0.0))
    total_pricings = int(evidence.get("total_pricings", 0))
    families_tested = evidence.get("families_tested", [])
    utility_computed = bool(evidence.get("utility_summary"))
    regime_tested = bool(evidence.get("regime_metadata"))
    tolerance_swept = bool(evidence.get("tolerance_sweep"))
    hpc_decomposed = bool(evidence.get("utilization_breakdown"))
    slm_exported = bool(evidence.get("slm_export_path"))
    portfolio_analyzed = bool(evidence.get("portfolio_overlap"))

    for c in claims:
        c.last_evaluated = now

        if c.claim_id == "C1_exact_reuse_exists":
            if total_pricings > 0 and exact_hit_rate > 0:
                c.support_status = ClaimStatus.SUPPORTED
                c.supporting_metrics = {"exact_hit_rate": exact_hit_rate, "total_pricings": total_pricings}
            elif total_pricings > 0:
                c.support_status = ClaimStatus.NOT_SUPPORTED
                c.supporting_metrics = {"exact_hit_rate": 0.0, "total_pricings": total_pricings}

        elif c.claim_id == "C2_similarity_reuse_controllable":
            if tolerance_swept:
                c.support_status = ClaimStatus.PARTIALLY_SUPPORTED
            elif total_pricings > 0:
                c.support_status = ClaimStatus.NOT_TESTED

        elif c.claim_id == "C3_reuse_family_dependent":
            if len(families_tested) >= 3 and utility_computed:
                c.support_status = ClaimStatus.PARTIALLY_SUPPORTED
                c.supporting_metrics = {"families_tested": families_tested}
            elif len(families_tested) > 0:
                c.support_status = ClaimStatus.NOT_TESTED

        elif c.claim_id == "C4_speedup_insufficient":
            if utility_computed:
                c.support_status = ClaimStatus.PARTIALLY_SUPPORTED

        elif c.claim_id == "C5_hpc_evidence":
            if hpc_decomposed:
                c.support_status = ClaimStatus.PARTIALLY_SUPPORTED

        elif c.claim_id == "C6_regime_affects_reuse":
            if regime_tested:
                c.support_status = ClaimStatus.PARTIALLY_SUPPORTED

        elif c.claim_id == "C7_traces_slm_ready":
            if slm_exported:
                c.support_status = ClaimStatus.PARTIALLY_SUPPORTED

        elif c.claim_id == "C8_portfolio_overlap_affects_reuse":
            if portfolio_analyzed:
                c.support_status = ClaimStatus.PARTIALLY_SUPPORTED

    return claims


def write_claims_manifest(
    claims: Sequence[ResearchClaim],
    output_dir: Path,
) -> Dict[str, str]:
    """Write research_claims_manifest.json and .md companion."""
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "claims": [c.to_dict() for c in claims],
        "summary": {
            "total_claims": len(claims),
            "supported": sum(1 for c in claims if c.support_status == ClaimStatus.SUPPORTED),
            "partially_supported": sum(1 for c in claims if c.support_status == ClaimStatus.PARTIALLY_SUPPORTED),
            "not_supported": sum(1 for c in claims if c.support_status == ClaimStatus.NOT_SUPPORTED),
            "not_tested": sum(1 for c in claims if c.support_status == ClaimStatus.NOT_TESTED),
        },
    }

    json_path = output_dir / "research_claims_manifest.json"
    json_path.write_text(json.dumps(manifest, indent=2))

    md_lines = [
        "# Research Claims Manifest",
        "",
        f"Generated: {manifest['generated_utc']}",
        "",
        "## Summary",
        "",
        f"| Status | Count |",
        f"|--------|-------|",
        f"| Supported | {manifest['summary']['supported']} |",
        f"| Partially Supported | {manifest['summary']['partially_supported']} |",
        f"| Not Supported | {manifest['summary']['not_supported']} |",
        f"| Not Tested | {manifest['summary']['not_tested']} |",
        "",
        "## Claims",
        "",
    ]

    for c in claims:
        status_icon = {
            ClaimStatus.SUPPORTED: "SUPPORTED",
            ClaimStatus.PARTIALLY_SUPPORTED: "PARTIAL",
            ClaimStatus.NOT_SUPPORTED: "NOT SUPPORTED",
            ClaimStatus.NOT_TESTED: "NOT TESTED",
        }.get(c.support_status, "UNKNOWN")

        md_lines.append(f"### {c.claim_id} [{status_icon}]")
        md_lines.append(f"**{c.claim_text}**")
        md_lines.append("")
        if c.caveats:
            md_lines.append("Caveats:")
            for cav in c.caveats:
                md_lines.append(f"- {cav}")
            md_lines.append("")
        if c.required_next_experiments:
            md_lines.append("Required next experiments:")
            for exp in c.required_next_experiments:
                md_lines.append(f"- {exp}")
            md_lines.append("")

    md_path = output_dir / "research_claims_manifest.md"
    md_path.write_text("\n".join(md_lines))

    return {"json": str(json_path), "md": str(md_path)}
