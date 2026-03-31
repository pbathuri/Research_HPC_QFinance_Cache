# Agentic Workflow Architecture

> Historical / optional note: this document describes the LangGraph-style full-stack
> runner. It is **not** the canonical operator source of truth for the research
> spine. Use `docs/operator_entrypoints.md` for primary entrypoints.

## Overview

The research pipeline uses a LangGraph-style stateful orchestrator (`orchestrator.py`).
Each agent is a typed function that reads and mutates shared `PipelineState`.
The orchestrator runs agents sequentially, respects dependencies, handles failures,
and logs metrics and events at each transition.

## Agent Roles

| Agent | Role | Inputs | Outputs |
|-------|------|--------|---------|
| EnvironmentAgent | Validate local resources | (none) | capabilities dict |
| DataIngestionAgent | Load/generate daily market data | environment_check | daily panel metadata |
| CacheResearchAgent | Run cache experiments, log metrics | environment_check | cache metrics CSV |
| LiteratureReviewAgent | Seed references, export research queue | (none) | paper index, hypothesis map |
| VisualizationAgent | Generate research figures | data_ingestion | figure files |
| ReportAgent | Write summary report | data_ingestion, cache_experiment | JSON + Markdown report |

## State Machine

```
[start] → EnvironmentAgent → DataIngestionAgent → CacheResearchAgent
                                    ↓                      ↓
                           VisualizationAgent        LiteratureReviewAgent
                                    ↓                      ↓
                               ReportAgent ← ─ ─ ─ ─ ─ ─ ─┘
                                    ↓
                                 [end]
```

## Run Modes

| Mode | Stages Run |
|------|------------|
| `full` | All agents |
| `data_refresh` | environment, data_ingestion, reporting |
| `experiment_batch` | environment, cache_experiment, reporting |
| `research_expansion` | literature_review, reporting |
| `visualization_only` | visualization, reporting |
| `dry_run` | Print plan only |

## Event Tracing

Every agent emits `WorkflowEvent` objects to `state.events`. These are
JSON-serializable audit records; current in-repo workflow trace export uses
`qhpc_cache.research_workflow_export` for the **legacy simulated** workflow demo,
not a Pixel bridge.

## Metrics

- `outputs/metrics/runtime_metrics.csv` — per-stage wall-clock times
- `outputs/metrics/agent_metrics.csv` — per-agent status, retries, artifact counts
- `outputs/metrics/cache_metrics.csv` — cache research metrics per run
- `outputs/metrics/experiment_metrics.csv` — experiment parameter hashes and results

## Extending the Pipeline

```python
from qhpc_cache.orchestrator import AgentNode, build_default_pipeline

orch = build_default_pipeline()
orch.add_agent(AgentNode("my_stage", "MyAgent", my_agent_fn, inputs=["data_ingestion"]))
state = orch.run()
```
