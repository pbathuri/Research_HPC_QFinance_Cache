# Multi-agent research workflow visualization

## What is modeled

The module **`qhpc_cache.research_agents`** defines a **simulation** of how work could be partitioned across named roles:

- **FinanceModelAgent** — `pricing.py`, GBM, payoffs, analytic checks  
- **RiskMetricsAgent** — `risk_metrics.py`, `portfolio.py`  
- **QuantumMappingAgent** — `quantum_mapping.py`, `quantum_workflow.py` (planning only)  
- **CachePolicyAgent** — cache policies, circuit cache, similarity  
- **LiteratureReviewAgent** — `docs/`, paper-to-code mapping  
- **ExperimentAgent** — `experiment_runner.py`, configs, reporting  
- **VisualizationAgent** — trace export and Pixel Agents bridge  

This is **not** an LLM multi-agent runtime. It is a **data model + demo timeline** so humans (and tools) can see **stages, files, and task IDs** in one place.

## How Pixel Agents fits in

| Layer | Role |
|--------|------|
| **Pixel Agents (VS Code)** | Observes **Claude Code** JSONL while you code; characters animate by tool type. |
| **qhpc bridge (`tools/pixel_agents_bridge/`)** | Exports **qhpc-specific** JSON + JSONL + optional **Claude-shaped** shim lines. |
| **Integration** | **Event trace bridge (Strategy A)** — see `docs/pixel_agents_integration_decision.md`. |

**Implemented now**

- `research_agents.py` — profiles, tasks, events, `build_demo_simulation_trace()`  
- `run_research_workflow_demo.py` — console summary + writes under `outputs/research_workflow/`  
- Bridge exporters + adapter (shim JSONL)  
- `integrations/pixel_agents_integration.py` — pointers only  

**Optional / manual**

- Loading qhpc JSONL into Pixel Agents **without** upstream extension changes  
- Wiring Codex or other CLIs into the same trace format (custom logging)  

**Future work**

- A small VS Code command or webview that reads **qhpc** trace files  
- Deeper agent-agnostic adapter in Pixel Agents upstream  

## Extending the visualization

1. Add **tasks** in `build_default_research_task_set()` with real `related_module_names` and paper labels.  
2. Append **events** in `build_demo_simulation_trace()` or build traces from your own runner.  
3. Call `trace_exporter` / `pixel_agents_adapter` from notebooks or CI to archive runs.  

Undergraduate tip: run **`python3 run_research_workflow_demo.py`** and diff `research_workflow_summary.txt` before/after a sprint to see how you described progress.
