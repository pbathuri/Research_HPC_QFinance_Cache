# Broad daily universe design

## Why Databento is primary

- **Vendor-neutral API** with documented schemas (e.g. `ohlcv-1d`) suitable for batch historical pulls.
- **Symbol-level** requests map cleanly to **deterministic batches** and registry keys.
- **Reference/definition** data can be pulled alongside OHLCV when the account supports it.

The implementation defaults to dataset `EQUS.MINI` (sample US equities) unless `QHPC_DATABENTO_DAILY_DATASET` overrides it. **Your** broadest US equity/ETF universe is whichever dataset your subscription allows; the pipeline does not hardcode entitlements.

## Batching and budgets

- **Time budget:** `QHPC_PIPELINE_TIME_BUDGET_SEC` (default ~90% of 2 hours).
- **Disk budget:** `QHPC_PIPELINE_DISK_BUDGET_BYTES` (default 45 GB soft cap for new bytes under the data root during orchestration).
- **Batch sizing:** `universe_builder.recommend_batch_size_for_budget` scales down symbol batch size when scope estimates threaten budgets.
- **Checkpoints:** `broad_universe_partial_complete` after each successful batch; `broad_universe_complete` when all planned batches finish.

## Synthetic fallback

If `DATABENTO_API_KEY` is absent and `allow_synthetic_fallback=True` (demo default via `QHPC_ALLOW_SYNTHETIC_DEMO`), the pipeline writes a **small labeled synthetic** OHLCV CSV for teaching **only**. Registry notes mark `SYNTHETIC_FALLBACK`.

## Storage layout

- Daily files live under `QHPC_DATA_ROOT/daily_universe/` with deterministic names from `data_storage.build_storage_path`.
- Sidecar `*.metadata.json` records schema, row counts, and batch ids.

See also: `docs/data_source_setup.md`, `src/qhpc_cache/universe_builder.py`, `src/qhpc_cache/data_ingestion.py`.
