# Pixel Agents integration — decision record

## Strategy chosen: **A — Event trace bridge** (with documented compatibility shim)

### Rationale

- **Pixel Agents** today ingests **live Claude Code JSONL** from a fixed directory layout and VS Code terminal lifecycle. It does **not** expose a stable, documented “import trace file” API for arbitrary projects.
- The **qhpc_cache** package must remain a **clean Python research baseline** with **no** dependency on the Pixel Agents extension, Node, or VS Code.
- The research need is to **see and reason about** multi-role workflow (finance, risk, quantum mapping, cache policy, literature) **in one place** — that is satisfied by:
  1. A **explicit workflow model** in Python (`research_agents.py`).
  2. **Exported artifacts** (JSON trace, JSONL event log, console summary) under `outputs/research_workflow/`.
  3. A **narrow bridge** (`tools/pixel_agents_bridge/`) that defines a **qhpc-specific event schema** and optionally **maps** events to **Claude-transcript-shaped** JSON lines for future tooling or forks.

### What we did *not* choose

- **Not Strategy B as primary**: we are not registering this repo as a native Pixel Agents “source” inside the extension (that would require TypeScript changes upstream).
- **Not Strategy C alone**: we still provide **Strategy A** traces as the main artifact; the adapter is **supplementary**.

### Optional shim

`pixel_agents_adapter.py` can emit lines structurally similar to `assistant` + `tool_use` records so that:

- Contributors can compare shapes to `pixel-agents/src/transcriptParser.ts`.
- A **future** script or extension fork could watch a **custom** JSONL file.

**Manual setup today**: running Pixel Agents still requires **Claude Code** in VS Code as documented in Pixel Agents’ README. **qhpc** exports do **not** auto-appear in Pixel Agents without additional work.
