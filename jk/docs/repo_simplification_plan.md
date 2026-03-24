# Repository simplification plan (refocus phase)

**Goal:** Narrow the codebase around the **core research spine** (data → features → risk → pricing → events → cache observability) and reduce parallel “product demo” paths (Pixel-style traces, extra agent theater).

## Clearly core (keep and strengthen)

| Area | Modules |
|------|---------|
| Data ingestion & registry | `data_ingestion.py`, `data_registry.py`, `data_storage.py`, `data_models.py`, `data_sources.py` |
| WRDS / CRSP enrichment | `wrds_provider.py`, `wrds_registry.py`, `wrds_queries.py` |
| Rates | `rates_data.py` |
| Feature panels & universe | `historical_returns.py`, `alpha_features.py`, `universe_builder.py`, `universe_analysis.py` |
| Portfolio risk / VaR–CVaR | `portfolio.py`, `risk_metrics.py`, `historical_risk.py` |
| Option pricing families | `pricing.py`, `analytic_pricing.py`, `payoffs.py`, `experiment_runner.py`, `qmc_simulation.py`, `quantum_engines/` |
| Event book / TAQ | `event_book.py`, `taq_kdb_adapter.py`, `event_definitions.py` |
| Cache / workload observability | `cache_store.py`, `cache_metrics.py`, `metrics_sink.py`, `workload_signatures.py`, `cache_workload_mapping.py`, `qmc_simulation.py` (trace) |
| Research memory | `knowledge_cache.py`, `research_memory.py` |
| Reporting & plots | `reporting.py`, `visualization/` (matplotlib/seaborn), `visualization/cache_trace_plots.py` |
| Tests & docs | `tests/`, `docs/` |

## Fragmented or overlapping

| Issue | Action |
|-------|--------|
| `wrds_placeholder.py` vs `wrds_queries.py` | **Keep** placeholder as thin legacy shim; **canonical roadmap** = `wrds_queries.WRDS_INTEGRATION_ROADMAP`. |
| Multiple “workflow trace” stories | **Consolidated:** `research_workflow_export.py` in-package replaces removed `tools/pixel_agents_bridge/trace_exporter.py`. |
| `research_agents.py` vs orchestrator | **Orchestrator** = real pipeline; **research_agents** = optional **simulated** role trace for teaching—marked **non-critical** in docs. |
| LangGraph path vs internal | **Keep** optional LangGraph; document as **non-spine** in `operator_entrypoints.md`. |

## Redundant or legacy

| Item | Action |
|------|--------|
| `tools/pixel_agents_bridge/` | **Removed** (already absent); demo must not depend on it. |
| Pixel-specific output dir in `plot_utils` | **Renamed** to `optional_traces` (generic); Pixel not a first-class output concept. |
| `data_registry` checkpoint `pixel_trace_exported` | **Kept** for JSON compatibility; treated as **legacy name** (optional export checkpoint). |
| `run_research_workflow_demo.py` | **Legacy / optional**; writes JSON+JSONL+txt only (no Pixel shim). |

## Overbroad for current phase (de-emphasize, do not delete blindly)

| Item | Action |
|------|--------|
| `run_full_research_pipeline.py` (full agentic stack) | **Document** as “full stack”; **spine-first** flows prefer ingestion + feature/risk scripts (see `operator_entrypoints.md`). |
| `run_research_visualization_demo.py` | **Keep** for matplotlib/seaborn dashboards; not on critical path for WRDS/rates. |
| `literature_agent.py` | **Keep**; call from pipeline **optional**; spine does not require it. |
| Heavy quantum / HPC placeholders | **Keep** as bounded placeholders; explicit **later phase** in `core_research_spine.md`. |

## Merge decisions (this pass)

| From | To |
|------|-----|
| External `trace_exporter` | **`qhpc_cache.research_workflow_export`** |

## Deprecations (documented, not silent)

- **Pixel Agents JSONL shim** — no longer produced by `run_research_workflow_demo.py`. Use standard JSON/JSONL from `research_workflow_export` if you need traces.
- **`outputs/.../pixel`** directory key — use **`optional_traces`** from `ensure_output_dirs`.

---

*See also: `docs/core_research_spine.md`, `docs/module_consolidation_map.md`.*
