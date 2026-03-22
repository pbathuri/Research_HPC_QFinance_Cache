# High-risk event book workflow

## Purpose

The **event book** is a **prioritized stress library**: curated windows (COVID, March 2020 liquidity, 2022 rates, 2023 banking stress, placeholders) extracted from **local TAQ-style** files. It is **not** a substitute for vendor-correct consolidated tape research; it is a **realistic ingestion interface** for high-frequency windows your license permits.

## Ingestion flow

1. Place licensed files under `QHPC_TAQ_ROOT` (or `data/qhpc_data/taq_incoming/` after bootstrap).
2. `event_definitions.default_event_catalog` defines windows in **priority order**.
3. `event_book.extract_event_windows_from_taq` scans files, filters timestamps and symbols, writes partitions under `event_book/`, and registers rows.
4. If time or disk budget is exhausted, remaining catalog ids appear in `deferred_identifiers` and the manifest.

## Querying later

Consumers can filter `EventBookEntry` records by:

- `event_category` (derived in code),
- time range (`time_window_start` / `time_window_end`),
- `symbols`,
- stress label (`event_label` / `event_identifier`).

## Relationship to daily layer

Daily OHLCV supports **cross-sectional** long-horizon analytics; the event book supports **localized stress** and future **cache similarity** experiments (burst reads vs sequential scans).

See: `src/qhpc_cache/event_book.py`, `docs/event_book_design.md`, `docs/manual_setup_steps.md`.
