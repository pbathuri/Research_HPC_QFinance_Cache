# Event book design

## What an event book is in this project

An **event book** is a **prioritized library of high-risk market windows**: each entry defines a **time range**, optional **symbol subset**, **category** (crash, liquidity stress, rate shock, etc.), and **local storage path** to extracted TAQ-style (or normalized tick) data. Entries carry **metadata** (`EventBookEntry`, `EventBookSummary`) and are registered in the **dataset registry** with completion status (`complete`, `partial`, `pending`, `optional_skipped`).

The event book is **not** a scrape of arbitrary academic HTML; it is a **curated stress dataset** aligned with quant research practice: known crisis intervals, high volatility, and policy/event-heavy dates.

## How daily-universe data differs from event-window data

| Aspect | Daily universe layer | Event book layer |
|--------|----------------------|------------------|
| **Source** | Databento (primary) daily OHLCV + reference | Local TAQ-style flat files (ingestion only) |
| **Frequency** | End-of-day bars | Intraday timestamps (tick or bar) |
| **Goal** | Broad cross-section, long history, panel analytics | **Tail risk** and **microstructure stress** windows |
| **Storage budget (target)** | ~10–15 GB | ~25–30 GB |
| **Typical use** | Betas, vol surfaces over time, universe-level VaR on returns | Spike liquidity, gap risk, realized vol intraday |

Both layers are **partitioned on disk**; neither requires holding the full universe and full event book in RAM at once.

## How this helps later cache-policy and quantum/HPC research

- **Cache policy / similarity**: Daily panels and event windows produce **distinct access patterns** (sequential full-universe scans vs localized high-resolution bursts). Registry entries and batch ids give **natural keys** for reuse experiments.
- **HPC / quantum workload modeling**: Event windows define **spiky, high-cardinality** workloads; the daily layer defines **embarrassingly parallel** batch jobs. Recorded **row counts**, **disk bytes**, and **ingestion times** support future **cost models** without running clusters in this phase.

## Priority order (default)

1. `covid_crash`  
2. `march_2020_liquidity_stress`  
3. `2022_rate_shock`  
4. `banking_stress_2023`  
5. `major_cpi_release_placeholder`  
6. `fomc_high_volatility_placeholder`  
7. `earnings_shock_placeholder`  
8. `commodity_spike_placeholder`  
9. `flash_crash_style_placeholder`  

If time or disk budget is exhausted, ingestion **stops after the last fully completed event** and marks lower-priority entries **pending** in the manifest and registry.
