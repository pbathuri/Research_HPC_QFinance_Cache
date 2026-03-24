# Module consolidation map

**Single canonical owner** per responsibility. Competing paths are **legacy**, **optional**, or **thin shims**.

## Data plane

| Responsibility | Canonical | Competing / notes |
|----------------|-----------|-------------------|
| Registry & checkpoints | `data_registry.py` | — |
| Ingestion orchestration | `data_ingestion.py` | — |
| Vendor pulls | `data_sources.py` | — |
| On-disk layout | `data_storage.py` | — |
| WRDS SQL + roadmap order | `wrds_queries.py`, `wrds_provider.py` | `wrds_placeholder.py` **shim only** |
| WRDS → disk + registry | `wrds_registry.py` | Registry rows carry `wrds_source_table`, `wrds_dataset_role`, coverage tags |

## Rates

| Responsibility | Canonical | Competing / notes |
|----------------|-----------|-------------------|
| Priority chain (**tfz_dly → tfz_mth** → FRB → file → flat) | `rates_data.py` | Verified tables in `wrds_queries.CANONICAL_CRSP_TFZ_*`; do not use `crsp.treasuries` |

## Event alignment (Phase 1 — before feature panels)

| Responsibility | Canonical | Competing / notes |
|----------------|-----------|-------------------|
| PERMNO alignment + CRSP enrich | `event_alignment.py` | — |
| kdb extract + aligned run + aligned registry | `taq_event_pipeline.py` | `event_book.py` = **batch catalog** path; use `run_aligned_event_pipeline` for sealed PERMNO outputs |
| kdb hooks | `taq_kdb_adapter.py` | Single q/CSV bridge |
| Event-set A-E definitions + locked window policy | `event_set_library.py` | One canonical set library (no parallel stress lists) |
| Event-library comparison + common normalized schema | `event_library_compare.py` | Owns CSV/JSON/MD/plot package export |
| Event-library registry rows | `event_library_registry.py` | Registers comparison package as canonical research artifact |

## Features & universe

| Responsibility | Canonical | Competing / notes |
|----------------|-----------|-------------------|
| **CRSP feature panel pipeline** | `feature_panel.py` | Builds on Phase 1 tags + `dsf`; owns registration too; do not fork a second panel stack |
| Feature-panel comparison bundle (4 locked variants) | `feature_panel_compare.py` | Compares event-aware/non-event-aware and raw/condensed in one canonical path |
| Return panels | `historical_returns.py` | Used by / alongside panels |
| Alpha / interpretable features | `alpha_features.py`, `alpha_evaluation.py` | **Called from** `feature_panel` for momentum / MA / z-score |
| Universe sizing / analysis | `universe_builder.py`, `universe_analysis.py` | — |
| Institutional equity master | `wrds_provider.load_crsp_security_master` (**crsp.stocknames**) | Databento = operational enrichment |

## Risk & portfolio

| Responsibility | Canonical | Competing / notes |
|----------------|-----------|-------------------|
| VaR/CVaR samples | `risk_metrics.py` | — |
| Historical/event risk | `historical_risk.py` | — |
| Portfolio scenarios | `portfolio.py` | — |
| Portfolio-risk workload family bundle | `portfolio_risk_workloads.py` | One canonical path for broad-universe risk + slice-scenario recomputation |

## Pricing

| Responsibility | Canonical | Competing / notes |
|----------------|-----------|-------------------|
| Baseline MC | `pricing.py` | `monte_carlo_cache_baseline.py` **legacy** |
| Option-pricing workload family bundle (locked model order + batch/Greeks comparison) | `pricing_workloads.py` | Canonical benchmark layer; avoid parallel pricing stacks |
| QMC multi-engine + trace | `qmc_simulation.py` | — |
| Engines | `quantum_engines/` | — |

## Events & TAQ

| Responsibility | Canonical | Competing / notes |
|----------------|-----------|-------------------|
| Event book (catalog + batch extract) | `event_book.py` | Prefer `taq_event_pipeline` when WRDS alignment is required |
| kdb / TAQ | `taq_kdb_adapter.py` | Shared with alignment pipeline |

## Cache & workload observability

| Responsibility | Canonical | Competing / notes |
|----------------|-----------|-------------------|
| CSV sinks | `metrics_sink.py` | Includes `spine_pipeline_observations.csv` (`SpinePipelineObservationRow`) |
| Cache theory tracker | `cache_metrics.py` | — |
| Spine workload IDs | `workload_signatures.py` | — |
| Workload rows | `cache_workload_mapping.py` | — |
| Event workload-signature summaries | `event_workload_signatures.py` | Event-library cache-study substrate (Mac proxies now, PMU later) |
| Unified cross-family observability schema + ranking/similarity | `unified_observability.py` | One common table across event/panel/risk/pricing; avoid ad hoc per-family comparison stacks |
| Unified observability registry helpers | `workload_family_registry.py` | Registers unified artifacts as canonical research datasets |
| Workload similarity signatures + pairwise comparators | `workload_similarity.py` | Candidate similarity keys only (research artifacts, not production cache keys) |
| Similarity-caching hypothesis synthesis | `similarity_cache_hypothesis.py` | Explicit claim labels: measured/derived/proxy-supported/hypothesis/deferred |
| Guided-cache evidence synthesis | `evidence_synthesis.py` | Ingests canonical outputs and builds claim-typed evidence matrix |
| Guided-cache architecture hypothesis | `guided_cache_hypothesis.py` | Maps evidence to architecture layers; exports supported/deferred claims and risks |
| Formal research-paper artifact packaging | `paper_artifacts.py` | Curated paper-ready tables/figures/manifests from canonical outputs only |
| Optional future x86/HPC/QHPC planning package | `future_extension_planner.py` | Planning-only roadmap artifacts; no PMU/HPC execution claims |

## Research memory

| Responsibility | Canonical | Competing / notes |
|----------------|-----------|-------------------|
| Critical concepts | `knowledge_cache.py` | — |
| Anchors | `research_memory.py` | — |

## Optional / non-spine

| Module | Role |
|--------|------|
| `research_agents.py` | Simulated workflow trace for teaching |
| `research_workflow_export.py` | JSON/JSONL export for that trace (**replaces removed bridge exporter**) |
| `orchestrator.py` + `run_full_research_pipeline.py` | Full staged runner (optional LangGraph) |
| `literature_agent.py` | Optional bibliography tooling |
| `run_research_workflow_demo.py` | **Legacy** demo; not spine |

## Merge / deprecate decisions (locked for this refocus)

| Decision |
|----------|
| **Merged:** trace JSON/JSONL export → `qhpc_cache.research_workflow_export` |
| **Deprecated:** dependency on `tools/pixel_agents_bridge/*` |
| **Renamed concept:** `plot_utils.ensure_output_dirs["pixel"]` → `optional_traces` |
| **Checkpoint name:** `pixel_trace_exported` kept in JSON for compatibility; treat as legacy label |

---

*Operator view: `docs/operator_entrypoints.md`.*
