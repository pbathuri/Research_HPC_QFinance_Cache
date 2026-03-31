"""Artifact contract layer: prevents silent omission of required research outputs.

Defines the canonical set of research artifacts that every run path
(repeated-workload or full-pipeline) must either produce or explicitly
mark as skipped/unavailable with a reason.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ArtifactEntry:
    artifact_id: str
    path_suffix: str
    status: str = "pending"  # "generated" | "skipped" | "unavailable" | "pending"
    reason: str = ""
    source_stage: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "path_suffix": self.path_suffix,
            "status": self.status,
            "reason": self.reason,
            "source_stage": self.source_stage,
        }


CANONICAL_RESEARCH_ARTIFACTS = [
    ("cacheability_summary", "research/cacheability_summary.json"),
    ("utility_summary", "research/utility_summary.json"),
    ("portfolio_overlap", "research/portfolio_overlap.json"),
    ("hpc_utilization", "research/hpc_utilization.json"),
    ("similarity_validation_summary", "research/similarity_validation_summary.json"),
    ("similarity_validation_examples", "research/similarity_validation_examples.csv"),
    ("expanded_metrics", "research/expanded_metrics.json"),
    ("research_claims_json", "research/research_claims_manifest.json"),
    ("research_claims_md", "research/research_claims_manifest.md"),
    ("research_honesty_json", "research/research_honesty_manifest.json"),
    ("research_honesty_md", "research/research_honesty_manifest.md"),
    ("speedup_bounds", "research/speedup_bounds.json"),
    ("net_utility_summary", "research/net_utility_summary.json"),
]

CANONICAL_SLM_ARTIFACTS = [
    ("slm_training_jsonl", "slm_datasets/slm_training_examples.jsonl"),
    ("reuse_decision_csv", "slm_datasets/reuse_decision_dataset.csv"),
    ("workload_family_csv", "slm_datasets/workload_family_dataset.csv"),
    ("cacheability_labels_csv", "slm_datasets/cacheability_labels.csv"),
    ("slm_manifest", "slm_datasets/slm_export_manifest.json"),
]


class ArtifactContract:
    """Tracks which canonical artifacts were produced, skipped, or unavailable."""

    def __init__(self, run_path: str = "repeated_workload"):
        self.run_path = run_path
        self._entries: Dict[str, ArtifactEntry] = {}
        for aid, suffix in CANONICAL_RESEARCH_ARTIFACTS + CANONICAL_SLM_ARTIFACTS:
            self._entries[aid] = ArtifactEntry(
                artifact_id=aid, path_suffix=suffix, source_stage=run_path,
            )

    def mark_generated(self, artifact_id: str) -> None:
        if artifact_id in self._entries:
            self._entries[artifact_id].status = "generated"

    def mark_skipped(self, artifact_id: str, reason: str) -> None:
        if artifact_id in self._entries:
            self._entries[artifact_id].status = "skipped"
            self._entries[artifact_id].reason = reason

    def mark_unavailable(self, artifact_id: str, reason: str) -> None:
        if artifact_id in self._entries:
            self._entries[artifact_id].status = "unavailable"
            self._entries[artifact_id].reason = reason

    def summary(self) -> Dict[str, Any]:
        entries = list(self._entries.values())
        return {
            "run_path": self.run_path,
            "total": len(entries),
            "generated": sum(1 for e in entries if e.status == "generated"),
            "skipped": sum(1 for e in entries if e.status == "skipped"),
            "unavailable": sum(1 for e in entries if e.status == "unavailable"),
            "pending": sum(1 for e in entries if e.status == "pending"),
            "artifacts": [e.to_dict() for e in entries],
        }

    def write(self, output_dir: Path) -> str:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "artifact_contract.json"
        path.write_text(json.dumps(self.summary(), indent=2))
        return str(path)

    def write_skipped_placeholder(self, output_dir: Path, artifact_id: str, reason: str) -> None:
        """Write a machine-readable placeholder for a skipped artifact."""
        entry = self._entries.get(artifact_id)
        if not entry:
            return
        self.mark_skipped(artifact_id, reason)
        target = output_dir / entry.path_suffix
        target.parent.mkdir(parents=True, exist_ok=True)
        placeholder = {
            "artifact_id": artifact_id,
            "status": "skipped",
            "reason": reason,
            "generated_utc": datetime.now(timezone.utc).isoformat(),
        }
        target.write_text(json.dumps(placeholder, indent=2))
