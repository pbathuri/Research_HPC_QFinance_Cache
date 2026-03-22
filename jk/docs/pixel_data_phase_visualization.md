# Pixel Agents visualization — data ingestion phase

## What gets exported

`run_data_ingestion_event_book_demo.py` emits `WorkflowEvent` rows (see `src/qhpc_cache/workflow_events.py`) covering:

- environment / provider checks,
- Databento credential state,
- broad universe batch progress,
- reference (may be skipped in demo),
- TAQ event-window start/complete,
- rates loaded or fallback,
- daily and event-book validation,
- historical risk analytics,
- Pixel JSONL export.

Files under `outputs/data_ingestion_event_book/`:

| File | Content |
|------|---------|
| `data_phase_workflow.jsonl` | Pixel-shaped lines via `pixel_mapping.workflow_event_to_pixel_row` |
| `data_phase_run_summary.json` | Runtime, disk, checkpoints, deferred work |
| `event_book_manifest.json` | Event book entries + deferred ids |

## Isolation from Pixel Agents

The core package **does not import** the Pixel Agents VS Code extension or local repo. `tools/pixel_agents_bridge/pixel_trace_exporter.py` only writes JSON/JSONL for offline review and future adapters (same philosophy as the research-workflow bridge).

## Local Pixel Agents repo

The project at `/Users/prady/Desktop/pixel-agents` remains a **reference** for transcript shape. Loading qhpc exports into that extension is **not** built-in; compare with `docs/pixel_agents_integration_decision.md`.

See also: `tools/pixel_agents_bridge/README.md`, `tools/pixel_agents_bridge/sample_trace.jsonl`.
