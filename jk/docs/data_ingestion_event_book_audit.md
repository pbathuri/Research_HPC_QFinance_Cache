# Data ingestion and event-book phase — repository audit

This document records the state of `jk/` **before** the real-data pipeline phase and what was added to close the gap.

## Current repo strengths (pre-phase baseline)

- **Finance core**: GBM simulation (`market_models.py`), payoffs, Black–Scholes (`analytic_pricing.py`), Monte Carlo pricing with variance reduction (`pricing.py`, `variance_reduction.py`).
- **Risk teaching layer**: Sample VaR/CVaR from P&L scenarios (`risk_metrics.py`), small portfolio types (`portfolio.py`).
- **Research scaffolding**: Quantum-shaped mapping (`quantum_mapping.py`), circuit cache/similarity, cache policies, experiments (`experiment_runner.py`).
- **Workflow visualization (simulated)**: `research_agents.py` and `research_workflow_export.py` can export JSON/JSONL traces without coupling to external visualization products.
- **Discipline**: Core package stayed stdlib-only; optional tooling lives under `tools/` and optional extras in `pyproject.toml`.

## Missing real-data capabilities (addressed in this phase)

- No connection to **market data APIs** (Databento or other) for historical OHLCV.
- No **local partitioned storage** (Parquet/CSV + sidecar metadata) for large panels.
- No **dataset registry** tracking provider, paths, completeness, disk usage, ingestion time, checkpoints.
- No **resumable batch orchestration** with explicit resource budgets (runtime, disk).

## Missing event-window capabilities (addressed in this phase)

- No **TAQ-style** local file ingestion or extraction of **high-frequency windows** around stress episodes.
- No **prioritized event catalog** (COVID, March 2020 liquidity, 2022 rates, 2023 banking stress, placeholders) with registry-backed pending vs complete state.

## Missing rates capabilities (addressed in this phase)

- No **Treasury / risk-free** series aligned to the daily panel.
- No **pluggable** file-based path for CRSP (or WRDS-exported) yields with a clearly labeled **fallback** when files are absent.

## What remains out of scope (this phase)

- CUDA, MPI, OpenMP, Slurm, distributed schedulers, Big Red 200–specific job scripts.
- Real quantum hardware or vendor runtime execution.
- Large multi-agent LLM frameworks; live Pixel-style visualization products on the critical path.
- Regulatory production risk engines, best execution, or compliance reporting.
- Guaranteed completion of **full** broad-universe + full TAQ event book within 2 hours — the pipeline **estimates**, **batches**, **checkpoints**, and **defers** remainder with documented next steps.

## Where the real-data layer connects

- **Downstream**: `historical_returns.py`, `historical_risk.py`, and `universe_analysis.py` consume saved partitions and registry entries; they reuse **sign conventions** and quantile VaR/CVaR ideas from `risk_metrics.py` where appropriate.
- **Visualization / audit trail**: `workflow_events.py` emits structured steps; JSON / markdown outputs remain the canonical inspection path.
- **Configuration**: Environment variables and optional `QHPC_DATA_ROOT` (see `docs/data_source_setup.md`).
