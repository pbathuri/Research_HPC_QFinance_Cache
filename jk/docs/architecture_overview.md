# Architecture Overview

## Layered Design

```
┌─────────────────────────────────────────────────────────────────┐
│  Orchestration Layer                                             │
│  orchestrator.py (LangGraph-style state machine)                │
│  run_full_research_pipeline.py                                   │
├─────────────────────────────────────────────────────────────────┤
│  Agent Roles                                                     │
│  EnvironmentAgent │ DataIngestionAgent │ CacheResearchAgent      │
│  LiteratureReviewAgent │ ExperimentAgent │ VisualizationAgent    │
│  ReportAgent │ QuantumPlanningAgent                              │
├─────────────────────────────────────────────────────────────────┤
│  Metrics / Observability                                         │
│  metrics_sink.py (CSV) │ workflow_events.py │ cache_metrics.py   │
├─────────────────────────────────────────────────────────────────┤
│  Research Extensions                                             │
│  literature_agent.py │ research_memory.py │ knowledge_cache.py   │
├─────────────────────────────────────────────────────────────────┤
│  Visualization                                                   │
│  visualization/ (market, microstructure, alpha, simulation,      │
│                  cache_dashboard, workflow_timeline, throughput)  │
├─────────────────────────────────────────────────────────────────┤
│  Data Layer                                                      │
│  data_ingestion │ data_sources │ data_storage │ data_registry    │
│  event_book │ taq_kdb_adapter │ rates_data │ universe_builder    │
├─────────────────────────────────────────────────────────────────┤
│  Cache Research Layer                                            │
│  cache_store │ cache_metrics │ cache_policy │ circuit_cache      │
│  circuit_similarity │ cache_policy_features                      │
├─────────────────────────────────────────────────────────────────┤
│  Quantum / Circuit Planning                                      │
│  quantum_mapping │ quantum_workflow │ placeholders               │
├─────────────────────────────────────────────────────────────────┤
│  Classical Finance Core                                          │
│  pricing │ analytic_pricing │ market_models │ payoffs            │
│  variance_reduction │ risk_metrics │ portfolio                   │
│  historical_returns │ historical_risk │ alpha_features           │
├─────────────────────────────────────────────────────────────────┤
│  Backend Interfaces                                              │
│  cpu_local (implemented) │ cuda_placeholder │ mpi_placeholder    │
│  slurm_bigred200 (template generation)                           │
└─────────────────────────────────────────────────────────────────┘
```

## Key Principles

1. **Local-first**: all core workflows run on a laptop without network access.
2. **Graceful degradation**: missing API keys, kdb, or packages are detected and handled.
3. **Mathematical honesty**: no fake quantum speedup claims; clear labels for what is classical, what is planning, what is scaffold.
4. **CSV-backed metrics**: every stage writes to append-only CSV for continuous tracking.
5. **Structured events**: all stages emit `WorkflowEvent` objects for JSON audit / reporting outputs.
6. **Backend-agnostic**: the same experiment can run on CPU today and GPU/MPI/Slurm later through the backend interface.

## Entry Points

| Script | Purpose |
|--------|---------|
| `run_full_research_pipeline.py` | Agentic orchestration of the full research workflow |
| `run_research_visualization_demo.py` | Visualization-focused demo with all figure types |
| `run_data_ingestion_event_book_demo.py` | Data pipeline with Databento + TAQ + events |
| `run_demo.py` | Classical finance baseline walkthrough |
| `scripts/check_env.py` | Environment validation report |
| `scripts/bootstrap_local_workspace.py` | Create directory structure and registry |
| `scripts/validate_local_resources.py` | Deep resource validation with JSON output |
