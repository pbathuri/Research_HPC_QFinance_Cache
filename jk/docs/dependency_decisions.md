# Dependency decisions

## Core package (`src/qhpc_cache`)

- **Decision**: Remain **standard-library-first** for pricing, risk, Fourier bridge (using `math`, `cmath`, `dataclasses`, `random`, etc.).
- **Rationale**: Undergraduate readability, zero install friction, matches original `requirements.txt` spirit.
- **NumPy / SciPy / pandas**: **Not** added as required dependencies. Arrays are plain Python lists for typical path counts in teaching and small experiments.
- **Quantum SDKs (Qiskit, Cirq, Q#)**: **Not** imported. Abstractions only.

## Local machine resources (Desktop paths)

- **Decision**: **No runtime imports** from `autoresearch-macos`, `AutoResearchClaw`, `lean4`, `arxiv-sanity-lite`, `agency-agents`, or `langchain`.
- **Rationale**: Those projects fail the adoption bar for *core* code: high integration cost, framework assumptions, or off-topic focus. See scoring in `docs/local_resource_audit.md`.
- **Optional tooling**: If a future `tools/research_agent/` script is added, it may read **files inside this repo** (e.g. `docs/*.md`) using only the standard library unless the maintainer explicitly opts in to extra packages in a separate `tools/requirements.txt`.

## How to disable anything optional

- There is **nothing to disable** in core: no optional heavy deps are wired in.
- Demos import only `qhpc_cache` and standard library.

## If a future maintainer insists on NumPy

- Add it in `pyproject.toml` / `requirements.txt` with a short note in this file: *why* (e.g. large-scale MC only), and keep a list-based code path for students without NumPy if feasible.

## Codex CLI and optional AI workflow (LangChain / LangGraph)

- **Codex CLI**: an **external** tool on `PATH`, not a Python package dependency. Use it for development, audits, and planning; **translate** any conclusions into normal Python and markdown in this repo (see `docs/codex_development.md`).
- **Core package**: still **must not** `import` Codex or LangChain.
- **Optional extra** `ai-workflow`: declared in `pyproject.toml` for `langchain-core` and `langgraph`. Install with `pip install -e ".[ai-workflow]"` only when using `tools/codex_dev/optional_langchain_hook.py` or similar **out-of-tree** orchestration.
- **Rationale**: keeps undergraduate-facing `qhpc_cache` readable while allowing advanced researchers to chain Codex-shaped steps in LangGraph without forking the core library.
