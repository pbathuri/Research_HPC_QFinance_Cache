# Similarity-Caching Hypothesis (Canonical)

Owner modules:

- `src/qhpc_cache/workload_similarity.py`
- `src/qhpc_cache/similarity_cache_hypothesis.py`

This phase formalizes a disciplined similarity-caching hypothesis layer on top of
unified workload observability.

It does **not** claim:

- a production similarity cache is implemented
- hardware-cache performance is proven
- PMU-level microarchitectural behavior is demonstrated

## Explicit evidence labels

Every major claim is labeled as one of:

- `measured`
- `derived`
- `proxy-supported`
- `hypothesis`
- `deferred`

## Operational similarity definitions

Similarity relationships are operationalized as:

- `exact_identity_similarity`
- `near_identity_structural_similarity`
- `same_family_similarity`
- `parameter_neighborhood_similarity`
- `weak_similarity`

Family-specific operational types:

- event: window-shape similarity
- feature panel: panel-shape similarity
- portfolio risk: scenario-family similarity
- pricing: pricing-batch similarity

## Similarity keys/signatures

Candidate signature artifacts:

- `exact_identity_signature`
- `near_identity_signature`
- `family_signature`
- `neighborhood_signature`
- `timing_signature`
- `reuse_signature`

These are research keys for hypothesis-building, not production cache keys.

## Canonical APIs

Signature and similarity primitives:

- `build_similarity_signature(...)`
- `build_similarity_signature_table(...)`
- `build_family_similarity_signature(...)`
- `compare_similarity_signatures(...)`
- `classify_similarity_relationship(...)`
- `summarize_similarity_neighbors(...)`
- `analyze_similarity_within_family(...)`
- `analyze_similarity_across_families(...)`
- `find_high_value_similarity_clusters(...)`
- `rank_similarity_candidates(...)`

Hypothesis orchestration:

- `run_similarity_caching_hypothesis_bundle(...)`
- `export_similarity_caching_hypothesis_bundle(...)`

Hypothesis claim layer:

- `summarize_similarity_caching_hypothesis(...)`
- `identify_supported_similarity_claims(...)`
- `identify_unsupported_or_deferred_claims(...)`
- `rank_similarity_hypothesis_strength(...)`

## Primary outputs (CSV/JSON first)

CSV:

- `similarity_signature_table.csv`
- `similarity_candidate_summary.csv`
- `similarity_cluster_summary.csv`
- `similarity_within_family_summary.csv`
- `similarity_cross_family_summary.csv`
- `similarity_hypothesis_rankings.csv`

JSON:

- `similarity_signature_manifest.json`
- `similarity_candidate_manifest.json`
- `similarity_hypothesis_manifest.json`

## Secondary outputs

Markdown:

- `similarity_caching_hypothesis.md`
- `similarity_candidate_summary.md`
- `similarity_rankings_summary.md`

Plots:

- within-family similarity
- cross-family similarity
- similarity clusters
- similarity candidate rankings
- exact-match vs near-match comparison

## Mac vs HPC discipline

Mac-side evidence supports operational workload similarity and proxy-based
reuse hypotheses.

Later HPC/x86 PMU runs are required for:

- validating hardware cache hit/miss implications
- validating prefetch/TLB/NUMA effects
- confirming whether similarity retrieval improves real hardware behavior

