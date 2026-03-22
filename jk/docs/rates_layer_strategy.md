# Rates layer strategy

## Goals

Provide a **discounting / risk-free context** for research workflows without pretending unsupported data is authoritative.

## Priority

1. **CRSP / WRDS-exported Treasury** CSV (or similar) via `QHPC_CRSP_TREASURY_PATH` → `CrspTreasuryFileProvider` + `data_ingestion.load_or_ingest_rates_data`.
2. If files are absent, **`rates_data.load_pluggable_risk_free_rate_series`** returns a **constant annual rate** via `build_flat_rate_fallback`, with `RatesSourceSummary.is_fallback=True` and explicit notes — **not equivalent to CRSP**.

## Alignment

`rates_data.align_rates_to_daily_universe` left-merges rates onto a daily OHLCV panel by normalized calendar date.

## Future work

WRDS automation, FRED series ids, and curve bootstrapping stay **out of scope** for this phase; the architecture keeps ingestion **pluggable** through `RatesDataRequest` and registry entries with `dataset_kind="rates"`.

See: `src/qhpc_cache/rates_data.py`, `docs/data_source_setup.md`.
