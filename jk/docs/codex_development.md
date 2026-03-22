# Codex CLI as a local development and research copilot

The **Codex CLI** (OpenAI) can assist with repository inspection, planning, test ideas, and audit-style reviews. It is **not** part of the `qhpc_cache` import graph: anything Codex suggests must be **merged by humans** into clear Python and docs in this repo.

## Prerequisites

- `codex` on your `PATH` (verify with `codex --version`).
- Authentication as required by your Codex install (`codex login` if needed).

This machine had Codex available at install time; your environment may differ.

## Typical uses (research workflow)

| Use | Suggestion |
|-----|------------|
| Repo tour | `codex -C /path/to/jk "Summarize qhpc_cache layers and suggest one extension."` |
| Non-interactive task | `codex exec -C jk --sandbox read-only "List unittest gaps for portfolio.py"` |
| Code review | `codex review` (see `codex review --help`) |
| Tests | Ask Codex for cases; **commit** only after translating to `unittest` in `tests/` |

## Policy: from Copilot output to repository truth

1. **Never** treat Codex output as authoritative for pricing, risk, or quantum claims.
2. **Always** translate conclusions into normal Python modules, docstrings, and `docs/`.
3. **Prefer** small, reviewable diffs over large automated patches (`codex apply` only after manual review).

## Helper script (stdlib)

`tools/codex_dev/invoke_codex.py` wraps `codex exec` with a safe default sandbox (`read-only`) and the repo root as working directory. It refuses to run if `codex` is missing.

Example:

```bash
cd jk
python3 tools/codex_dev/invoke_codex.py \
  --prompt "Propose two edge-case tests for risk_metrics.compute_value_at_risk without editing files."
```

## Optional LangChain / LangGraph bridge

If you want to orchestrate Codex from a LangChain-style pipeline (e.g. research notes → human review → code), install the optional extra:

```bash
pip install -e ".[ai-workflow]"
```

Then see `tools/codex_dev/optional_langchain_hook.py`: it exposes a small optional hook that **does not import** LangChain unless the extra is installed. The finance **core** remains standard-library-only.

## Relationship to `dependency_decisions.md`

- **Core package**: still no `codex`, no `langchain`, no `langgraph`.
- **Optional extra `ai-workflow`**: for `tools/` and notebooks only.
- See `docs/dependency_decisions.md` for the full policy.

## Example of translating Codex output into the repo

An audit prompt on **Asian path pricing** produced findings about missing tests and `num_paths=0` behavior. Those conclusions were implemented as:

- `docs/codex_audit_asian_path_followup.md`
- `tests/test_pricing_asian_path.py`
- `MonteCarloPricer._validate_simulation_inputs()` in `src/qhpc_cache/pricing.py`

Always prefer this pattern: **agent suggests → human verifies → tests and validation land in git**.
