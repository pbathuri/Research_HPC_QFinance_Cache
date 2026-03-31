# Artifact Contract and Evidence Parity

## Purpose

Every research run (repeated-workload or full-pipeline) must produce a known set of research artifacts or explicitly mark them as skipped/unavailable with a structured reason. This prevents silent omission of evidence.

## Canonical Artifact Registry

The artifact contract layer (`src/qhpc_cache/artifact_contract.py`) defines two sets of canonical artifacts:

### Research Bundle Artifacts
| Artifact ID | Path | Description |
|-------------|------|-------------|
| cacheability_summary | research/cacheability_summary.json | Cache recall and label distribution |
| utility_summary | research/utility_summary.json | Reuse utility metrics |
| portfolio_overlap | research/portfolio_overlap.json | Portfolio/scenario overlap metrics |
| hpc_utilization | research/hpc_utilization.json | Compute decomposition |
| similarity_validation_summary | research/similarity_validation_summary.json | Validation pass/fail rates |
| similarity_validation_examples | research/similarity_validation_examples.csv | Per-validation detail |
| expanded_metrics | research/expanded_metrics.json | Per-family hit rates and metrics |
| research_claims_json | research/research_claims_manifest.json | Evaluated research claims |
| research_claims_md | research/research_claims_manifest.md | Human-readable claims |
| research_honesty_json | research/research_honesty_manifest.json | Honesty flags and provenance |
| research_honesty_md | research/research_honesty_manifest.md | Human-readable honesty |
| speedup_bounds | research/speedup_bounds.json | Amdahl/Gustafson analysis |
| net_utility_summary | research/net_utility_summary.json | Overhead and net utility |

### SLM Bundle Artifacts
| Artifact ID | Path | Description |
|-------------|------|-------------|
| slm_training_jsonl | slm_datasets/slm_training_examples.jsonl | Training records |
| reuse_decision_csv | slm_datasets/reuse_decision_dataset.csv | Decision-level dataset |
| workload_family_csv | slm_datasets/workload_family_dataset.csv | Family aggregates |
| cacheability_labels_csv | slm_datasets/cacheability_labels.csv | Ground-truth labels |
| slm_manifest | slm_datasets/slm_export_manifest.json | Export manifest |

## Artifact Statuses

Each artifact can be in one of four states:
- **generated**: Successfully produced with meaningful content
- **skipped**: Intentionally not produced, with documented reason
- **unavailable**: Could not be produced due to external constraints
- **pending**: Not yet processed (indicates a bug if seen in final output)

## Full-Pipeline Parity

The full pipeline now emits all canonical artifacts. Where per-request or per-family detail is unavailable (because the full pipeline does not use workload families directly), the artifact is generated with aggregate data and a note explaining the limitation. No artifact is silently omitted.

## Interpreting Skipped Artifacts

A skipped artifact produces a placeholder JSON file containing:
```json
{
  "artifact_id": "portfolio_overlap",
  "status": "skipped",
  "reason": "Full pipeline does not generate portfolio-level overlap metrics",
  "generated_utc": "2026-03-25T..."
}
```

This is intentional and honest. It indicates the artifact concept exists but does not apply to this run path.

## Usage

The `artifact_contract.json` file in each run directory contains the full contract summary. Check for `pending == 0` to confirm all artifacts were processed.
