# Guided-Cache Architecture Hypothesis (Canonical)

Owner modules:

- `src/qhpc_cache/evidence_synthesis.py`
- `src/qhpc_cache/guided_cache_hypothesis.py`

This phase synthesizes existing workload evidence into a disciplined
guided-cache architecture hypothesis.

It does **not**:

- prove hardware cache behavior
- implement a production cache controller
- claim Mac-side proxies equal PMU-backed evidence

## Explicit claim typing

All major claims are labeled:

- `measured`
- `derived`
- `proxy-supported`
- `hypothesis`
- `deferred`

## Evidence synthesis APIs

- `load_canonical_evidence_tables(...)`
- `collect_family_evidence_summary(...)`
- `collect_similarity_hypothesis_summary(...)`
- `build_evidence_matrix(...)`
- `classify_supported_vs_deferred_claims(...)`
- `summarize_guided_cache_evidence(...)`

## Architecture hypothesis APIs

- `define_guided_cache_architecture(...)`
- `define_guided_cache_components(...)`
- `define_guided_cache_dataflow(...)`
- `map_similarity_evidence_to_guided_cache_components(...)`
- `identify_guided_cache_candidate_workloads(...)`
- `identify_architecture_risks_and_limitations(...)`
- `run_guided_cache_hypothesis_bundle(...)`
- `export_guided_cache_hypothesis_bundle(...)`
- `export_research_direction_bridge(...)`

## Architecture layers (conceptual)

- exact-match reuse layer
- similarity-aware reuse layer
- workload-signature layer
- routing / prioritization layer
- deferred hardware-aware layer
- deferred HPC/QHPC escalation layer

## Primary outputs (CSV/JSON first)

CSV:

- `guided_cache_evidence_matrix.csv`
- `guided_cache_supported_claims.csv`
- `guided_cache_deferred_claims.csv`
- `guided_cache_candidate_workloads.csv`
- `guided_cache_architecture_components.csv`
- `guided_cache_hypothesis_rankings.csv`

JSON:

- `guided_cache_hypothesis_manifest.json`
- `guided_cache_evidence_manifest.json`
- `guided_cache_architecture_manifest.json`

## Secondary outputs

Markdown:

- `guided_cache_architecture_hypothesis.md`
- `guided_cache_evidence_summary.md`
- `guided_cache_rankings_summary.md`
- `guided_cache_limitations_and_future_work.md`

Plots:

- supported vs deferred claim comparison
- candidate workload rankings
- cross-family evidence-strength
- exact-match vs similarity-aware candidates
- Mac-now vs HPC-later escalation

## Mac vs HPC / QHPC discipline

Supported now on Mac:

- workload-structure synthesis
- exact/near candidate mapping
- claim-typed architecture hypothesis artifacts

Deferred to HPC/QHPC:

- PMU-backed microarchitectural validation
- large-scale replay and routing validation
- hardware-aware cache-behavior confirmation
- BigRed200-scale workload replay and escalation validation

