# Multi-agent research workflow visualization

> Historical / legacy note: this document describes an older visualization story.
> The current repo does **not** depend on `tools/pixel_agents_bridge/` and the
> canonical trace export path is the in-package `qhpc_cache.research_workflow_export`.
> Keep this doc for context, not as an operator instruction source.

## What is modeled

The module **`qhpc_cache.research_agents`** defines a **simulation** of how work could be partitioned across named roles:

- **FinanceModelAgent** — `pricing.py`, GBM, payoffs, analytic checks  
- **RiskMetricsAgent** — `risk_metrics.py`, `portfolio.py`  
- **QuantumMappingAgent** — `quantum_mapping.py`, `quantum_workflow.py` (planning only)  
- **CachePolicyAgent** — cache policies, circuit cache, similarity  
- **LiteratureReviewAgent** — `docs/`, paper-to-code mapping  
- **ExperimentAgent** — `experiment_runner.py`, configs, reporting  
- **VisualizationAgent** — trace export and optional summaries  

This is **not** an LLM multi-agent runtime. It is a **data model + demo timeline** so humans (and tools) can see **stages, files, and task IDs** in one place.

## Current export status

| Layer | Role |
|--------|------|
| **`research_agents.py`** | Simulated workflow model (teaching / audit) |
| **`run_research_workflow_demo.py`** | Legacy demo that writes JSON / JSONL / text under `outputs/research_workflow/` |
| **`qhpc_cache.research_workflow_export`** | In-package export helper replacing the removed external bridge |

**Implemented now**

- `research_agents.py` — profiles, tasks, events, `build_demo_simulation_trace()`  
- `run_research_workflow_demo.py` — console summary + writes under `outputs/research_workflow/`  
- `research_workflow_export.py` — JSON / JSONL / text export  

**Optional / manual**

- Wiring additional local tools into the same JSON / JSONL trace format (if desired)  

**Future work**

- A lightweight local viewer for qhpc trace files if the research group needs one  

## Extending the visualization

1. Add **tasks** in `build_default_research_task_set()` with real `related_module_names` and paper labels.  
2. Append **events** in `build_demo_simulation_trace()` or build traces from your own runner.  
3. Call `research_workflow_export` or run `run_research_workflow_demo.py` to archive runs.  

Undergraduate tip: run **`python3 run_research_workflow_demo.py`** and diff `research_workflow_summary.txt` before/after a sprint to see how you described progress.
