# BigRed200 Execution Plan (Planning-Only)

This document captures planning assumptions for later BigRed200-scale studies.

## Scope

- Planning-level candidate selection and partitioning strategy.
- No Slurm or cluster execution logic is implemented in this phase.

## Candidate families

- Event workloads (event-set x window-family partitions)
- Feature-panel workloads (date-chunk x security-slice partitions)
- Portfolio-risk workloads (scenario-family x slice partitions)
- Pricing workloads (model-family x contract-batch partitions)

## Planning outputs

- `bigred200_candidate_workloads.csv`
- `bigred200_plan_manifest.json`

## Initial out-of-scope

- cluster job scripts
- production scheduler integration
- PMU instrumentation implementation on cluster nodes

Status label for this plan: `ready for BigRed200 execution planning`.

