# Critical cache window

## Purpose

The **critical cache window** is a **small, structured** set of research concepts (not a vector database or RAG stack). Each entry links:

- a **domain** (e.g. VaR/CVaR, COS, circuit caching),
- a **one-paragraph summary**,
- **module references** in this repo,
- optional **reading hints** and **pitfalls**.

## Implementation

- Data lives in ``knowledge_cache.BUILT_IN_CRITICAL_CONCEPTS``.
- ``research_memory.critical_window_with_modules()`` bundles concepts with any **document anchors** you register at runtime.
- ``run_data_ingestion_event_book_demo.py`` writes ``outputs/data_ingestion_event_book/critical_cache_window.json`` and emits workflow event ``critical_cache_window_built``.

## Domains covered

Market data sourcing, feature engineering, alpha research, overfitting/robustness, VaR/CVaR, volatility/time series, Black–Scholes, COS/Fourier, quantum finance mapping, QMCI/QAE, circuit caching, similarity caching, hybrid quantum/HPC.

## Editing policy

Add or tighten concepts as the research proposal evolves. Keep each ``summary`` short enough to skim in under a minute. Prefer **module pointers** over long prose.
