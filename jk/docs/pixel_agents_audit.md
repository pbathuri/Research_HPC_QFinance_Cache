# Pixel Agents — inspection audit (local: `~/Desktop/pixel-agents`)

## Repo purpose

**Pixel Agents** is a **VS Code extension** that visualizes AI coding agents as pixel-art characters in an office scene. Each agent maps **1:1** to a terminal running **Claude Code**; live activity (reading files, editing, bash, subtasks) is inferred from **JSONL transcript files** that Claude Code writes under the user’s home directory.

The stated **long-term vision** is agent-agnostic, platform-agnostic orchestration; **today** the implementation is **tightly coupled** to Claude Code’s transcript format and file layout.

## Main architecture

| Layer | Role |
|--------|------|
| **Extension host** (`src/*.ts`) | VS Code API: terminals, webview, file watchers |
| **`agentManager.ts`** | Spawns terminals with `claude --session-id <uuid>`, registers expected JSONL path `~/.claude/projects/<sanitized-workspace>/<uuid>.jsonl` |
| **`fileWatcher.ts`** | Watches/polls JSONL; incremental reads |
| **`transcriptParser.ts`** | Parses **each line as JSON**; reacts to `type: assistant` / `user` / `progress` / `system` (`turn_duration`) |
| **Webview** (`webview-ui/`) | React + Canvas: characters, tool overlays, layout editor |

## Important source files

- `src/transcriptParser.ts` — **canonical contract** for transcript semantics (`tool_use`, `tool_result`, etc.)
- `src/agentManager.ts` — project dir resolution, terminal ↔ JSONL binding
- `src/types.ts` — `AgentState`, `PersistedAgent`
- `CLAUDE.md` — compressed internal architecture reference
- `README.md` — user-facing behavior and limitations

## Expected input / event format (Claude Code JSONL)

Pixel Agents does **not** define a separate public schema file; behavior is **implied** by `processTranscriptLine`:

- **One JSON object per line** (JSONL).
- **`assistant`** — `message.content` array; blocks with `type: "tool_use"`, `id`, `name` (tool name), `input` (e.g. `file_path`, `command`, `description` for Task).
- **`user`** — `message.content` with `type: "tool_result"`, `tool_use_id` marking tool completion.
- **`progress`** — nested structure for sub-agent tools (`parentToolUseID`, `data`, …).
- **`system`** with `subtype: "turn_duration"` — end of turn → agent shown as waiting.

Tool labels for the UI are derived via `formatToolStatus(toolName, input)` (Read/Edit/Write/Bash/Glob/Grep/…).

## Current assumptions and limitations

- **Claude Code CLI** required; transcripts live under **`~/.claude/projects/...`**.
- **Heuristic** waiting/permission detection; known to misfire (per README).
- **Windows-first** testing; macOS/Linux may differ for paths and terminals.
- **No generic “import arbitrary agent trace” API** in the extension today — consumption is **live file tail** of Claude’s JSONL.

## Best integration strategy for **Research_MonteCarloSim** (`jk/`)

1. **Keep `qhpc_cache` free** of Pixel Agents / VS Code / Node types.
2. **Emit a first-class research workflow trace** (`ResearchSimulationTrace`, JSON + JSONL) from this repo (`research_agents.py` + `tools/pixel_agents_bridge/`).
3. **Optional mapping** to **Claude-shaped JSONL lines** for experimentation or a **future** Pixel Agents adapter — documented as **best-effort**, not guaranteed to drive the extension without upstream changes.
4. **Human workflow**: researcher runs **Claude Code / Codex** as today with Pixel Agents for **live** coding agents; **side-by-side**, open exported **`qhpc`** traces in a viewer, diff tool, or future bridge — the trace answers “who is working on what stage” for **this** project’s modeled roles.

This matches **Strategy A (event trace bridge)** with a documented **compatibility shim** toward Claude-like lines where useful.
