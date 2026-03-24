# Research alignment checkpoint

**Purpose:** Anchor what the repository is for, what it does well, where it drifted, and what to do next—before further large implementation waves.

## 1. What the repo already does well

- **Canonical pricing / cache research path:** `pricing.py`, `cache_store.py`, `cache_policy.py`, `experiment_runner.py`, `qmc_simulation.py` with trace observability, multi-engine harness, and run-scoped outputs.
- **Historical daily + event substrate:** `data_ingestion.py`, `data_registry.py`, `event_book.py`, Databento-oriented universe pulls, kdb-taq adapter for local NYSE TAQ workflows.
- **Risk / features / portfolio:** `historical_returns.py`, `historical_risk.py`, `risk_metrics.py`, `portfolio.py`, `alpha_features.py`, `alpha_evaluation.py`.
- **Orchestration:** `orchestrator.py` + `run_full_research_pipeline.py` with LangGraph when available, metrics via `metrics_sink.py`.
- **Visualization:** `visualization/` package for market, microstructure, cache dashboards, trace plots.
- **Literature / research scaffolding:** `literature_agent.py`, `knowledge_cache.py`, `research_memory.py`.
- **Future HPC / quantum placeholders:** `backends/`, `quantum_mapping.py`, `quantum_workflow.py`, `fourier_placeholder.py`—clearly bounded, not pretending to be production HPC.
- **Tests:** Broad coverage across pricing, cache, orchestrator, trace, QMC, and data adapters.

## 2. Where it has drifted from the core research objective

- **Institutional data was under-tooled vs ambition:** WRDS/CRSP was placeholder-only while Databento + kdb carried most of the “real data” story; rates were often file-or-flat fallback without a clear institutional priority chain.
- **Workload semantics vs cache metrics:** Trace/QMC metrics are strong for engine-level cache patterns, but naming “portfolio / model / feature condensation / event-window” workload families was not first-class in the same CSV/JSON sinks as generic cache metrics.
- **Operator story:** Multiple entrypoints (`run_demo.py`, `run_data_ingestion_event_book_demo.py`, `run_full_research_pipeline.py`, etc.) without a single “start here” map (now addressed in `demo_entrypoints.md`).
- **Research memory vs code:** Critical cache window and module map existed but did not yet systematically list WRDS datasets, Databento schemas, and TAQ/kdb paths alongside books/papers.

## 3. Next implementation phase (immediate focus)

1. **WRDS / CRSP as enrichment layer** — not a parallel stack; registry + local artifacts aligned with `data_registry.py`.
2. **Rates layer** — explicit priority: CRSP Treasury / Treasury–Inflation via WRDS → FRB (when available via WRDS) → flat fallback, with honest labeling.
3. **Workload-aware cache observability** — extend `metrics_sink` / `cache_metrics` / new mapping modules without replacing existing sinks.
4. **Research memory consolidation** — extend `knowledge_cache.py` + `research_memory.py`; refresh mapping docs.
5. **Demo / pipeline clarity** — one canonical full pipeline, documented alternatives as legacy or specialized.

## 4. What should explicitly be deferred

- Full production **OptionMetrics** or **Compustat Capital IQ** pipelines (schema-heavy; add only after treasury/security master/linking are stable).
- **BigRed200** real job submission (keep placeholders until benchmark questions in `open_research_questions.md` are resolved).
- **Pixel Agents** product integration (optional local path check only; not a research core).
- Replacing **Databento** with WRDS for broad daily OHLCV (WRDS remains enrichment/validation, not primary bulk vendor in this design).

## 5. Genuinely unresolved questions

See **`docs/open_research_questions.md`** and **`data/research/question_log.json`** for a living list (portfolio workload families, similarity-hit policy, rates conflicts, quantum benchmark priorities, etc.).

---

*Last updated: research-alignment pass (WRDS integration + workload observability + docs).*
