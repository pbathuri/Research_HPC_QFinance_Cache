# Canonical refactor plan

This pass is a **repo thinning + ownership clarification** pass. It builds on the
current working WRDS / event-alignment / feature-panel state and avoids new
parallel pathways.

## Canonical module per responsibility

| Responsibility | Canonical module | Notes |
|----------------|------------------|-------|
| WRDS table constants, roadmap, SQL helpers | `src/qhpc_cache/wrds_queries.py` | Canonical source of verified `schema.table` names |
| WRDS connection and exact loaders | `src/qhpc_cache/wrds_provider.py` | Runtime live-WRDS layer |
| WRDS persistence + registry rows | `src/qhpc_cache/wrds_registry.py` | Keeps `provider="wrds"` path separate from internal pipeline artifacts |
| Rates priority chain | `src/qhpc_cache/rates_data.py` | `tfz_dly -> tfz_mth -> FRB -> file -> flat` |
| TAQ / kdb subprocess boundary | `src/qhpc_cache/taq_kdb_adapter.py` | Single q / CSV bridge |
| Event catalog + budgeted batch extraction | `src/qhpc_cache/event_book.py` | Batch / catalog path, not PERMNO-sealed alignment owner |
| TAQ -> CRSP PERMNO alignment + CRSP enrich | `src/qhpc_cache/event_alignment.py` | Pure alignment / enrichment logic |
| Canonical aligned event pipeline | `src/qhpc_cache/taq_event_pipeline.py` | Single-run spine entrypoint |
| CRSP-backed feature panel pipeline | `src/qhpc_cache/feature_panel.py` | Owns panel build + tags + rates + condensation + registration |
| Reusable alpha transforms | `src/qhpc_cache/alpha_features.py` | Primitive feature functions called by `feature_panel.py` |
| Registry JSON + checkpoints | `src/qhpc_cache/data_registry.py` | Stable storage contract; do not fork |
| CSV sink row definitions | `src/qhpc_cache/metrics_sink.py` | Stable sink owner |
| Cache metrics algorithms | `src/qhpc_cache/cache_metrics.py` | In-memory tracker / summaries |
| Workload + spine mapping to CSV rows | `src/qhpc_cache/cache_workload_mapping.py` | Thin mapping layer above sinks |
| Research concept memory | `src/qhpc_cache/knowledge_cache.py` | Static concept layer |
| User / dataset anchors | `src/qhpc_cache/research_memory.py` | Optional annotation layer on top of concepts |
| Classical pricing baseline | `src/qhpc_cache/pricing.py` | Preserve as reference |
| QMC + trace contract | `src/qhpc_cache/qmc_simulation.py` | Preserve for stability |
| Canonical operator story | `docs/operator_entrypoints.md` | Primary operator doc |

## Where duplication currently exists

| Area | Duplication / ambiguity |
|------|-------------------------|
| Event alignment registration | Registry helper now lives in `taq_event_pipeline.py`; previous sidecar file was merged away in this pass |
| Feature panel registration | Registry helper now lives in `feature_panel.py`; previous sidecar file was merged away in this pass |
| Workflow trace docs | `README.md`, `docs/agentic_workflow.md`, and `docs/multiagent_visualization_workflow.md` still imply older or more first-class status than the current legacy/optional reality |
| Entry point narrative | `README.md`, `docs/demo_entrypoints.md`, and `docs/operator_entrypoints.md` do not tell exactly the same “primary vs optional vs legacy” story |
| Research memory framing | `knowledge_cache.py` and `research_memory.py` are separate for good reasons, but their boundary is under-documented and easy to misread as duplication |

## What should be merged now

1. Merged `src/qhpc_cache/event_alignment_registry.py` into `src/qhpc_cache/taq_event_pipeline.py`.
2. Merged `src/qhpc_cache/feature_panel_registry.py` into `src/qhpc_cache/feature_panel.py`.
3. Updated docs so `run_data_ingestion_event_book_demo.py` and `run_demo.py` are the clearest primary scripts, while `run_research_workflow_demo.py` is unambiguously legacy/optional.
4. Marked stale Pixel-oriented workflow docs as historical / legacy so they stop competing with current canonical docs.

## What should be deprecated now

| File / path | Status now |
|-------------|------------|
| `src/qhpc_cache/event_alignment_registry.py` | Removed after merge into `taq_event_pipeline.py` |
| `src/qhpc_cache/feature_panel_registry.py` | Removed after merge into `feature_panel.py` |
| `run_research_workflow_demo.py` | Keep, but clearly legacy / teaching-only |
| `docs/agentic_workflow.md` | Keep as historical architecture note, not operator source of truth |
| `docs/multiagent_visualization_workflow.md` | Keep as historical note, not active bridge instructions |

## What must be left alone for stability

| File | Why |
|------|-----|
| `src/qhpc_cache/data_registry.py` | Stable registry contract used broadly |
| `src/qhpc_cache/metrics_sink.py` | Stable CSV sink schema owner |
| `src/qhpc_cache/wrds_queries.py` / `wrds_provider.py` / `wrds_registry.py` | Current separation is clear and working |
| `src/qhpc_cache/qmc_simulation.py` | Large trace / config contract; not a consolidation target in this pass |
| `src/qhpc_cache/taq_kdb_adapter.py` | Good single-purpose boundary to external q / kdb |
| `run_data_ingestion_event_book_demo.py` | Primary data spine entrypoint |
| `run_demo.py` | Primary classical baseline entrypoint |

## Guiding decision for this pass

Merge only where the merge produces a **clearer canonical owner**. Document everything
else instead of creating new abstractions.
