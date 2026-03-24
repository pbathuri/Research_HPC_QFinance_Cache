# Repo keep / merge / deprecate

## KEEP

- `src/qhpc_cache/wrds_queries.py`
- `src/qhpc_cache/wrds_provider.py`
- `src/qhpc_cache/wrds_registry.py`
- `src/qhpc_cache/rates_data.py`
- `src/qhpc_cache/taq_kdb_adapter.py`
- `src/qhpc_cache/event_book.py`
- `src/qhpc_cache/event_alignment.py`
- `src/qhpc_cache/taq_event_pipeline.py`
- `src/qhpc_cache/feature_panel.py`
- `src/qhpc_cache/alpha_features.py`
- `src/qhpc_cache/data_registry.py`
- `src/qhpc_cache/data_storage.py`
- `src/qhpc_cache/metrics_sink.py`
- `src/qhpc_cache/cache_metrics.py`
- `src/qhpc_cache/cache_workload_mapping.py`
- `src/qhpc_cache/workload_signatures.py`
- `src/qhpc_cache/knowledge_cache.py`
- `src/qhpc_cache/research_memory.py`
- `run_data_ingestion_event_book_demo.py`
- `run_demo.py`
- `docs/operator_entrypoints.md`
- `docs/core_research_spine.md`

## MERGE

- `src/qhpc_cache/event_alignment_registry.py` -> `src/qhpc_cache/taq_event_pipeline.py`
  Status: merged in this pass; aligned-event registration now lives with the owning pipeline.
- `src/qhpc_cache/feature_panel_registry.py` -> `src/qhpc_cache/feature_panel.py`
  Status: merged in this pass; feature-panel registration now lives with the owning pipeline.
- Canonical entrypoint narrative in `README.md` -> align with `docs/operator_entrypoints.md` and `docs/demo_entrypoints.md`
  Status: updated in this pass to reduce operator confusion about primary vs optional vs legacy scripts.

## DEPRECATE

- `run_research_workflow_demo.py`
  Status: keep executable, but teaching-only / legacy.
- `docs/agentic_workflow.md`
  Status: historical architecture note; not current trace/export contract.
- `docs/multiagent_visualization_workflow.md`
  Status: historical note; no longer an active Pixel bridge instruction source.
- `src/qhpc_cache/wrds_placeholder.py`
  Status: keep as a thin legacy shim only.
- `monte_carlo_cache_baseline.py`
  Status: legacy baseline sketch; `run_demo.py` is canonical.
- `monte_FSS.py`
  Status: legacy / optional experiment script.

## LEAVE FOR LATER

- `src/qhpc_cache/qmc_simulation.py`
  Large, stable trace / simulation contract; not a thinning target in this pass.
- `src/qhpc_cache/orchestrator.py`
  Optional full-stack path; clarify docs now, restructure later only if needed.
- `src/qhpc_cache/feature_builder.py`
  Narrow cache-policy helper; not part of the CRSP feature-panel spine, but not harmful enough to merge now.
- `src/qhpc_cache/feature_condenser.py`
  Used by QMC paths and tests; conceptually distinct from `feature_panel.compute_condensed_feature_panel`.
- `src/qhpc_cache/literature_agent.py`
  Non-spine but bounded; document optional status rather than change code now.
- `src/qhpc_cache/visualization/`
  Keep matplotlib / seaborn outputs; avoid a larger visualization cleanup in this pass.
- `docs/current_canonical_module_map.md`
  Useful, but broader doc synchronization can follow once this consolidation pass settles.
