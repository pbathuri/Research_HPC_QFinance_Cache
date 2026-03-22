# Codex development helpers

Optional utilities for using the **Codex CLI** alongside this repository.

- `invoke_codex.py` — run `codex exec` with defaults suited to audit/planning (read-only sandbox, `-C` repo root).
- `optional_langchain_hook.py` — optional LangChain `Runnable` factory when `pip install -e ".[ai-workflow]"` is used.

Nothing here is imported by `src/qhpc_cache`.
