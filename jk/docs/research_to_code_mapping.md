# Research themes → code mapping

This document ties research directions (quantum finance, QMCI, caching, hybrid stacks) to **concrete modules** in this repository. It is a map for undergraduate researchers, not a literature review.

## Classical finance baseline

| Idea | Code location |
|------|----------------|
| GBM under risk-neutral measure | `market_models.py` — terminal and path simulation |
| European payoffs | `payoffs.py` |
| Black–Scholes price and Greeks | `analytic_pricing.py` |
| Monte Carlo engine with options | `pricing.py` — `MonteCarloPricer`, `MonteCarloPricingResult` |
| Portfolio aggregation | `portfolio.py` |

## Risk metrics

| Idea | Code location |
|------|----------------|
| P&L distribution from scenario portfolio values | `risk_metrics.py` — `compute_profit_and_loss_distribution(initial_portfolio_value, scenario_portfolio_values)`, `summarize_distribution` |
| VaR / CVaR from samples | `risk_metrics.py` |
| Portfolio-level risk summary | `portfolio.py` — `summarize_portfolio_risk` |

## Variance reduction

| Idea | Code location |
|------|----------------|
| Antithetic normals | `variance_reduction.py`, optional flag on `MonteCarloPricer` |
| Control variate (e.g. underlying terminal as control) | `variance_reduction.py`, `pricing.py` |
| Standard error and Gaussian CI | `variance_reduction.py`, fields on `MonteCarloPricingResult` |

## Fourier / COS bridge

| Idea | Code location |
|------|----------------|
| Log-price characteristic function (BS) | `fourier_placeholder.py` |
| COS / semi-analytic European call | `fourier_placeholder.py` — documented; compare to `analytic_pricing` |
| Analytic reference for control variate | `fourier_placeholder.py` + `analytic_pricing.py` |

## Quantum finance mapping

| Idea | Code location |
|------|----------------|
| Describe classical problem for “quantum later” | `quantum_mapping.py` — `FinanceProblemDescriptor` |
| Expectation / amplitude-estimation framing | `quantum_mapping.py` — `QuantumEstimationTask` |
| Circuit-shaped request (family, depth, qubits) | `quantum_mapping.py` — `QuantumCircuitRequest` |
| Honest resource placeholders | `quantum_mapping.py` — `QuantumResourceEstimate` |
| Orchestration glue | `quantum_workflow.py` |

**Non-goals**: no Qiskit/Cirq execution, no speedup claims.

## Circuit caching

| Idea | Code location |
|------|----------------|
| Exact keying | `circuit_cache.py` — `CircuitCacheStore.build_exact_cache_key` |
| Entry metadata (reuse count, compile placeholder) | `circuit_cache.py` — `CircuitCacheEntry` |
| Decision context for policies | `circuit_cache.py` — `CircuitCacheDecisionContext` |

## Similarity / AI cache policy

| Idea | Code location |
|------|----------------|
| Weighted, explainable similarity | `circuit_similarity.py` |
| Human-readable feature vectors for policies | `cache_policy_features.py` |
| Heuristic / logistic / AI-assisted policies | `cache_policy.py` |
| Classical result cache (Monte Carlo stats) | `cache_store.py` — `SimpleCacheStore` (retained) |

## Future HPC bridge (notes only)

- **No** MPI, CUDA, Slurm, or cluster code in this repo.
- Future work might add: batch scenario runners, export of experiment artifacts, or adapters to external schedulers — documented in `docs/future_extensions.md` only.

## Experiment and reporting

| Idea | Code location |
|------|----------------|
| Typed experiment configs | `experiment_configs.py` |
| Named scenarios | `research_scenarios.py` |
| Text / markdown reports | `reporting.py` |
| Runners | `experiment_runner.py` |

## Real market data & event book (kdb-taq + Databento)

| Idea | Code location |
|------|----------------|
| Databento daily OHLCV + batching | `data_sources.py` — `DatabentoProvider`, `data_ingestion.py` — `load_or_download_daily_universe` |
| Local kdb-taq extraction backend | `taq_kdb_adapter.py` — `run_q_event_window_extraction`, `inspect_kdb_taq_repo` |
| Event windows + hybrid kdb → flat fallback | `event_book.py` — `extract_event_windows_from_taq` |
| Dataset registry & checkpoints | `data_registry.py` |
| Treasury file vs fallback | `rates_data.py`, `data_ingestion.py` — `load_or_ingest_rates_data` |

## Research memory (non-RAG)

| Idea | Code location |
|------|----------------|
| Critical concept window | `knowledge_cache.py` — `CriticalConcept`, `get_critical_cache_window` |
| Document anchors + bundle for exports | `research_memory.py` — `register_document_anchor`, `critical_window_with_modules` |
| Book/paper → module index (narrative) | `docs/book_to_module_mapping.md` |

## WRDS / CRSP (future only)

| Idea | Code location |
|------|----------------|
| Roadmap + access placeholder | `wrds_placeholder.py`, `docs/wrds_future_integration_plan.md` |

## Workflow instrumentation

| Idea | Code location |
|------|----------------|
| Data-phase Pixel JSONL | `workflow_events.py`, `run_data_ingestion_event_book_demo.py`, `tools/pixel_agents_bridge/pixel_trace_exporter.py` |

## Historical analytics (returns, risk, alpha)

| Idea | Code location |
|------|----------------|
| Log/simple returns, panels, rolling vol, drawdown, Sharpe | `historical_returns.py` |
| Historical / event VaR-CVaR, drawdown on path | `historical_risk.py` |
| Universe + event book summaries | `universe_analysis.py` |
| Momentum, MA spread, z-score, volume change, vol features | `alpha_features.py` |
| Forward returns, IC, rank-IC, stability split | `alpha_evaluation.py` |

## Structured knowledge cache (books/papers → code)

| Idea | Code location |
|------|----------------|
| Critical concepts | `knowledge_cache.py` — `CriticalConcept`, `get_critical_cache_window` |
| Reference rows + notes + versioned window | `knowledge_cache.py` — `ResearchReference`, `ResearchConceptNote`, `CriticalCacheWindow`, `search_critical_cache_window` |
| Narrative mapping | `docs/book_to_module_mapping.md`, `docs/critical_cache_window.md` |
