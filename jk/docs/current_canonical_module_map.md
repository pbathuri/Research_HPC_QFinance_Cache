# Current canonical module map

Single source of truth for **which module owns which responsibility**. Prefer importing and extending these paths; avoid new parallel packages.

## Data acquisition & registry

| Responsibility | Canonical module | Notes |
|----------------|------------------|--------|
| Daily universe / Databento pulls | `data_ingestion.py`, `data_sources.py` | Primary broad equity/ETF OHLCV path |
| Dataset registry / checkpoints | `data_registry.py` | JSON under `QHPC_DATA_ROOT` |
| Local storage layout | `data_storage.py` | Paths sidecars |
| **WRDS / CRSP (active)** | **`wrds_provider.py`**, **`wrds_queries.py`**, **`wrds_registry.py`** | Enrichment; registers via `data_registry.register_dataset` |
| WRDS roadmap placeholders (legacy re-exports) | `wrds_placeholder.py` | Prefer `wrds_provider` for live code |
| TAQ / kdb | `taq_kdb_adapter.py` | Local `/ kdb-taq` workflow |
| Request dataclasses | `data_models.py` | Shared shapes |

## Rates & reference curves

| Responsibility | Canonical module |
|----------------|------------------|
| Priority-ordered risk-free / Treasury | **`rates_data.py`** (WRDS → FRB → file → flat) |
| Legacy file-based CRSP Treasury file | `data_sources.CrspTreasuryFileProvider` (still used inside `rates_data` when file path set) |

## Event alignment & high-risk windows

| Responsibility | Canonical module |
|----------------|------------------|
| Event definitions | `event_definitions.py` |
| Event book persistence / batch catalog | `event_book.py` |
| TAQ -> CRSP PERMNO alignment + normalized output | `event_alignment.py`, `taq_event_pipeline.py` |
| Event-set A-E definitions + window policy | `event_set_library.py` |
| Cross-set comparison + normalized comparison schema | `event_library_compare.py` |
| Comparison output registration | `event_library_registry.py` |

## Returns, feature panels, risk, portfolio, alpha

| Responsibility | Canonical module |
|----------------|------------------|
| CRSP-backed feature panel pipeline | `feature_panel.py` |
| Four-variant panel comparison (event-aware/non-event-aware × raw/condensed) | `feature_panel_compare.py` |
| Return panels | `historical_returns.py` |
| Rolling risk / drawdown | `historical_risk.py`, `risk_metrics.py` |
| Portfolio scenarios | `portfolio.py` |
| Portfolio-risk workload bundle (historical + slices + scenario comparison) | `portfolio_risk_workloads.py` |
| Alpha features / eval | `alpha_features.py`, `alpha_evaluation.py` |
| Universe helpers | `universe_builder.py`, `universe_analysis.py` |

## Pricing, MC, experiments

| Responsibility | Canonical module |
|----------------|------------------|
| Baseline MC pricer | `pricing.py` |
| Canonical pricing workload family (model-family compare + contract-batch + Greeks) | `pricing_workloads.py` |
| Analytic benchmarks | `analytic_pricing.py` |
| Payoffs / variance | `payoffs.py`, `variance_reduction.py` |
| Cache policies / store | `cache_policy.py`, `cache_store.py` |
| Feature builder | `feature_builder.py` |
| Experiments | `experiment_runner.py`, `experiment_configs.py` |
| QMC multi-engine + trace | `qmc_simulation.py`, `trace_*.py`, `quantum_engines/` |

## Cache research & observability

| Responsibility | Canonical module |
|----------------|------------------|
| Metrics CSV sink | `metrics_sink.py` |
| Cache theory metrics | `cache_metrics.py` |
| **Workload ↔ cache mapping** | **`cache_workload_mapping.py`**, **`workload_signatures.py`** |
| Event-library workload signatures (event study substrate) | `event_workload_signatures.py` |
| Unified cross-family observability schema, ranking, and similarity | `unified_observability.py` |
| Unified workload-family output registration | `workload_family_registry.py` |
| Workload similarity signatures / relationship classifiers | `workload_similarity.py` |
| Similarity-caching hypothesis synthesis + export | `similarity_cache_hypothesis.py` |
| Guided-cache evidence synthesis | `evidence_synthesis.py` |
| Guided-cache architecture hypothesis + export | `guided_cache_hypothesis.py` |
| Formal paper packaging artifacts | `paper_artifacts.py` |
| Optional future x86/HPC/QHPC planning artifacts | `future_extension_planner.py` |
| Circuit / similarity (quantum-leaning) | `circuit_cache.py`, `circuit_similarity.py`, `cache_policy_features.py` |

## Orchestration & pipeline

| Responsibility | Canonical module |
|----------------|------------------|
| Agentic pipeline | `orchestrator.py` |
| Full research entry | `run_full_research_pipeline.py` (see `demo_entrypoints.md`) |
| Run output roots | `output_paths.py` |

## Research memory & literature

| Responsibility | Canonical module |
|----------------|------------------|
| Critical concepts / window | `knowledge_cache.py` |
| Document anchors + export | `research_memory.py` |
| Paper indexing / arXiv | `literature_agent.py` |
| Higher-level agents (optional) | `research_agents.py` |

## Visualization

| Responsibility | Canonical module |
|----------------|------------------|
| All plotting entry | `visualization/` package |
| Post-pipeline figures | Called from `run_full_research_pipeline.py` / demos |

## Backends & future HPC

| Responsibility | Canonical module |
|----------------|------------------|
| Backend interfaces | `backends/base.py`, `cpu_local.py`, placeholders |

## Duplication / drift to avoid

- **Do not** add a second global registry; use `data_registry.py` + WRDS helpers in `wrds_registry.py`.
- **Do not** fork `metrics_sink.py`; add new row types and filenames there.
- **Prefer** extending `rates_data.py` over ad-hoc Treasury logic in notebooks/scripts.

## Stable vs refactor targets

| Stable (extend carefully) | Refactor toward canonical |
|---------------------------|---------------------------|
| `data_registry.py`, `metrics_sink.py`, `orchestrator.py` | Scripts that hardcode `outputs/` without `output_paths` |
| `qmc_simulation.py` trace schemas | Duplicate rate-loading in one-off demos |
| `knowledge_cache` concept IDs | Scattered “module map” text not in `docs/` |

---

*See also: `docs/research_to_code_mapping.md`, `docs/book_to_module_mapping.md`, `docs/critical_cache_window.md`.*
