# Formal Research-Paper Packaging Plan

This phase packages existing canonical artifacts into paper-ready outputs without
fabricating evidence.

## Primary objective

1. Formalize paper narrative and methods.
2. Curate strongest results into reproducible tables/figures.
3. Preserve explicit claim typing:
   - `measured`
   - `derived`
   - `proxy-supported`
   - `hypothesis`
   - `deferred`
4. Keep Mac-vs-HPC boundaries explicit.
5. Bridge proposal intent to current empirical scope.

## Canonical owner

- `src/qhpc_cache/paper_artifacts.py`

## Primary packaging artifacts

CSV:

- `paper_results_tables.csv`
- `paper_claims_matrix.csv`
- `paper_section_mapping.csv`
- `paper_artifact_index.csv`

JSON:

- `paper_results_manifest.json`
- `paper_figure_manifest.json`
- `paper_claims_manifest.json`
- `paper_packaging_manifest.json`

Paper-ready tables:

- `table_research_scope_summary.csv`
- `table_data_and_workload_summary.csv`
- `table_event_library_summary.csv`
- `table_feature_panel_comparison.csv`
- `table_portfolio_risk_summary.csv`
- `table_pricing_workload_summary.csv`
- `table_unified_observability_summary.csv`
- `table_similarity_hypothesis_summary.csv`
- `table_guided_cache_claims_summary.csv`

Paper-ready figures:

- `figure_event_library_comparison.png`
- `figure_cache_study_rankings.png`
- `figure_feature_panel_comparison.png`
- `figure_portfolio_risk_workloads.png`
- `figure_pricing_workload_comparison.png`
- `figure_unified_observability.png`
- `figure_similarity_candidates.png`
- `figure_guided_cache_evidence.png`

