# Core research spine (canonical path)

This is the **intended order of research value** for this repository—not every script runs all steps in one invocation.

## End-to-end logical flow (implementation order)

1. **Broad daily universe** — Databento (or synthetic fallback): `data_ingestion.py`, `data_sources.py`, `universe_builder.py`.
2. **Rates / discounting context** — WRDS **``crsp.tfz_dly``** then **``crsp.tfz_mth``**, then FRB / file / flat: `rates_data.py`, `wrds_provider.py`, `wrds_registry.py`.
3. **CRSP + TAQ event alignment (Phase 1)** — **Before** large-scale feature panels: kdb/q TAQ extract → WRDS link tables → PERMNO → `stocknames` + `dse`/`mse` enrichment → normalized artifact + registry. Canonical: `event_alignment.py`, `taq_event_pipeline.py` (see `docs/event_alignment_design.md`). Batch catalog extraction remains `event_book.py` + `taq_kdb_adapter.py`.
4. **Event-library comparison substrate (current phase)** — Locked sets A-E, locked window subset, common normalized schema, workload-signature package: `event_set_library.py`, `event_library_compare.py`, `event_workload_signatures.py`.
5. **CRSP-backed feature panels (Phase 2)** — Daily panel (`crsp.dsf`-shaped), rates, **event tags from Phase 1**: `feature_panel.py` (`docs/feature_panel_design.md`). Reuses `alpha_features.py` / `historical_returns.py` patterns where appropriate.
6. **Portfolio risk workflows** — VaR/CVaR, scenarios: `portfolio.py`, `risk_metrics.py`, `historical_risk.py`, `portfolio_risk_workloads.py`.
7. **Option pricing families** — `pricing.py`, `pricing_workloads.py`, `qmc_simulation.py`, `quantum_engines/`.
8. **Event-window analytics (downstream)** — Stress tests and papers that **consume** aligned windows + feature tags; workload observability tag `event_window` still applies.
9. **Cache / workload observability** — `metrics_sink.py` (incl. `spine_pipeline_observations.csv`), `cache_workload_mapping.py`, `workload_signatures.py`, `event_workload_signatures.py`, `unified_observability.py`, `qmc_simulation.py` (trace). Cross-cutting.
10. **Similarity-caching hypothesis layer** — `workload_similarity.py`, `similarity_cache_hypothesis.py` over unified observability evidence.
11. **Guided-cache architecture hypothesis / evidence synthesis layer** — `evidence_synthesis.py`, `guided_cache_hypothesis.py` + research-direction bridge.
12. **Formal research-paper packaging layer** — `paper_artifacts.py` + `docs/paper_*` and `docs/proposal_to_paper_bridge.md`.
13. **Optional HPC/QHPC future-extension planning layer** — `future_extension_planner.py` + `docs/*_plan.md` continuity docs.
14. **Later: quantum / HPC** — `quantum_mapping.py`, `circuit_cache.py`, etc. — deferred until spine metrics stable.

### Pipeline order vs observability rank

- **Build order:** event alignment → feature panels (institutional IDs and event metadata first).
- **Observability rank** (for cache studies) remains the locked tuple in `workload_signatures.CORE_WORKLOAD_SPINE` (`feature_panel` = 1 … `event_window` = 4). Pipeline order and observability rank serve different purposes; both are documented.

## What is *not* the spine

- Pixel-style live visualization products.
- `research_agents.py` simulation — teaching only.
- LangGraph full pipeline — convenience, not correctness definition.

## Outputs policy

CSV, JSON, markdown, matplotlib/seaborn on the critical path.

## Canonical ownership (cache/reuse experiments)

- Canonical owner module: `src/qhpc_cache/experiment_runner.py`
- Canonical sweep entrypoint: `run_local_research_sweep(...)`
- Tier metadata owner: `get_experiment_ladder()`

Avoid parallel sidecar runners for the same experiment families; add new
experiment variants under the canonical owner unless separation is truly
required.

---

*Alignment: `docs/event_alignment_design.md` · Features: `docs/feature_panel_design.md`.*
