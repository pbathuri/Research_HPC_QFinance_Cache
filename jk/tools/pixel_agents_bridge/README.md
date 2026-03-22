# Pixel Agents bridge (optional)

This directory is a **sidecar** for the `qhpc_cache` research project. It does **not** add a runtime dependency from the core package to [Pixel Agents](https://github.com/pablodelucca/pixel-agents).

## What it does

| File | Purpose |
|------|---------|
| `event_schema.py` | Version tag for exported JSON / JSONL |
| `trace_exporter.py` | `export_research_trace_to_json`, `…_jsonl`, `…_summary` |
| `pixel_agents_adapter.py` | Map research events → Claude-transcript-**shaped** lines (shim) |
| `pixel_trace_exporter.py` | Export **data-ingestion** `WorkflowEvent` logs + run summary JSON |
| `pixel_mapping.py` | Map `WorkflowEvent` → Pixel-style JSONL rows |
| `sample_*.json` / `.jsonl` | Small static examples (incl. `sample_trace.jsonl` for data phase) |

## Requirements

- Python 3.11+
- `PYTHONPATH` must include `jk/src` so `qhpc_cache` imports resolve (the exporter adds `jk/src` automatically when loaded from this folder).

## Usage (from `jk/`)

```bash
PYTHONPATH=src python3 run_research_workflow_demo.py
```

Or import in a notebook after `sys.path.insert(0, "src")` and `sys.path.insert(0, "tools/pixel_agents_bridge")`.

## Relationship to Pixel Agents

The VS Code extension reads **live** Claude Code JSONL. The **shim** JSONL here is for **documentation, diffing, and future adapters** — not a drop-in replacement for Claude’s session files without upstream changes.

See `docs/pixel_agents_audit.md` in the repo root (`jk/docs/`).
