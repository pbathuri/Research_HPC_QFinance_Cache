# Local resource usage — data phase

Guidance for the **historical ingestion + event-book** phase on a **MacBook-class** machine (24 GB RAM, ≤ 50 GB disk, ≤ 2 h wall time for first full pass).

## Budget envelope

| Layer | Target footprint | Notes |
|-------|------------------|--------|
| Broad daily universe | 10–15 GB | Databento OHLCV + Parquet/CSV; batched symbol lists |
| Event book (TAQ windows) | 25–30 GB | High-frequency extracts; highest-priority events first |
| Registry, rates, metadata, outputs | 2–5 GB | JSON registry, manifests, Pixel traces, summaries |
| Working / temp | 5–8 GB | Sort/spill; clear `tmp/` after successful batches |

**Cap**: 50 GB total under `QHPC_DATA_ROOT` (default `data/qhpc_data`) plus `outputs/`.

## Memory rules

- Do **not** concatenate the full daily panel with full event book in one DataFrame.
- Read **chunks** or **per-batch** files; write **immediately** after each batch.
- Use **Parquet** when `pyarrow` is installed for columnar, compressed IO.

## Runtime rules

- If a stage approaches the 2-hour budget, **stop after the current batch**, mark checkpoint `partial`, record deferred symbols/events in the registry.
- **Resumable**: re-running skips completed `registry_key` rows when implemented in ingestion (see `data_ingestion.py`).

## What counts toward “usage”

- Raw downloads, converted tables, sidecar JSON metadata, checkpoint files, demo exports under `outputs/data_ingestion_event_book/`, and temporary extraction artifacts.

## Environment variables (no secrets in repo)

- `DATABENTO_API_KEY` — Databento (never log the value).
- `QHPC_DATA_ROOT` — data root override.
- `QHPC_KDB_TAQ_REPO` — local kdb-taq checkout for q-assisted TAQ export.
- `QHPC_KDB_EXTRACTION_COMMAND` / `QHPC_KDB_Q_BINARY` — optional extraction hooks.

See also `docs/phase_master_plan.md` and `docs/manual_setup_steps.md`.
