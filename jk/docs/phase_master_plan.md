# Phase master plan — historical research substrate

This plan governs the **historical data + workload + analytics** phase for `qhpc_cache` (run from `jk/`). It aligns with undergraduate research goals: honest scope, resumable pipelines, and clear placeholders for WRDS/CRSP and future quantum/cache work.

## Hard constraints (laptop phase)

| Constraint | Target |
|------------|--------|
| RAM | ≤ 24 GB; never load full daily universe + full event book together |
| Initial full pipeline wall time | ≤ 2 hours (reasonable provider latency) |
| Total local data footprint | ≤ 50 GB (raw + converted + registry + outputs + temp) |
| Budget split (guidance) | Daily layer 10–15 GB; event book 25–30 GB; rates/registry/artifacts 2–5 GB; temp 5–8 GB |

## Implementation order

1. Environment + registry bootstrap (`scripts/check_data_env.py`, `scripts/bootstrap_data_phase.py`).
2. Data models, storage paths, JSON registry (`data_models.py`, `data_storage.py`, `data_registry.py`).
3. Providers: Databento (daily OHLCV + reference), NYSE TAQ + kdb/q adapter, rates (flat + optional CRSP files), WRDS placeholders.
4. Broad daily universe: deterministic batches, immediate disk flush, registry rows per batch (`universe_builder.py`, `data_ingestion.py`).
5. High-risk event book: prioritized catalog (`event_definitions.py`, `event_book.py`), TAQ extraction hooks, manifest + queries.
6. Rates / discounting context (`rates_data.py`, `wrds_placeholder.py`).
7. Analytics: returns, risk, universe + event summaries, alpha features + evaluation (`historical_returns.py`, `historical_risk.py`, `universe_analysis.py`, `alpha_features.py`, `alpha_evaluation.py`).
8. Knowledge cache + research memory (`knowledge_cache.py`, `research_memory.py`).
9. Workflow events + Pixel bridge (`workflow_events.py`, `tools/pixel_agents_bridge/`, `run_data_ingestion_event_book_demo.py`).
10. Tests (pure logic; no live network in default suite).
11. Documentation polish (`README.md`, design docs under `docs/`).

## Checkpoint strategy

Checkpoints live in `data/qhpc_data/registry/checkpoints.json` (override with `QHPC_DATA_ROOT`). Each completed stage updates the registry and sets checkpoint status. **Resumable**: skip completed batches when re-run.

Canonical checkpoint names include:

- `environment_verified`
- `registry_initialized`
- `broad_universe_partial_complete` / `broad_universe_complete`
- `reference_data_complete`
- `event_book_partial_complete` / `event_book_complete`
- `rates_layer_complete`
- `analytics_ready`
- `critical_cache_window_built`
- `pixel_trace_exported`

Granular **workflow events** (JSONL traces) use types such as `broad_universe_batch_completed`, `q_event_window_extraction_started`, etc. (see `workflow_events.py` and demo scripts).

## Broad-universe strategy

- **Source**: Databento daily OHLCV + definition/reference metadata where licensed.
- **Credentials**: read from environment only (e.g. `DATABENTO_API_KEY`); never commit secrets.
- **Batching**: split symbol lists into deterministic batches; estimate bytes/time per batch; defer lower-priority batches if caps hit.
- **Format**: Parquet preferred when `pyarrow` available; CSV fallback documented.
- **On cap exceed**: complete highest-value batches first; record deferred work in registry and demo summary.

## Event-book strategy

- **Catalog**: fixed priority list (COVID crash, March 2020 liquidity, 2022 rate shock, banking stress 2023, placeholders for CPI/FOMC/earnings/commodity/flash crash style windows).
- **Source**: local NYSE TAQ-style files + optional **kdb/q** extraction from `QHPC_KDB_TAQ_REPO` (default tries `~/desktop/kdb-taq` and common paths).
- **Output**: partitioned files under `data/.../event_book/` with registry entries and manifest JSON.
- **On cap exceed**: process events in catalog order; mark remainder `pending`.

## Rates strategy

- **Now**: flat risk-free curve or simple CSV fallback; clearly labeled in summaries.
- **Future**: optional local CRSP/WRSP Treasury files via pluggable loader (`rates_data.py`); `wrds_placeholder.py` documents integration order.

## Research-cache strategy

- Structured **concept window** in `knowledge_cache.py` (not a RAG stack): books/papers themes → module pointers.
- `research_memory.py` for optional document anchors.
- Export JSON for reports and Pixel traces.

## Visualization strategy

- **Pixel Agents**: optional; trace export only (`tools/pixel_agents_bridge/`). Core package does not import Pixel runtime.
- Demos write JSONL/JSON under `outputs/`.

## Deferred / out of scope

- CUDA, MPI, OpenMP, Slurm, live trading, broker APIs, real quantum execution, fake speedup claims, giant agent frameworks.
