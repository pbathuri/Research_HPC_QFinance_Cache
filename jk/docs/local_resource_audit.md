# Local resource audit

Paths inspected on the developer machine (reference only for this repo’s design). **The qhpc_cache runtime does not depend on these directories.**

## Summary table

| Path | Purpose | Type | Relevance | Level | Recommendation |
|------|---------|------|-----------|-------|----------------|
| `/Users/prady/Desktop/autoresearch-macos` | Autonomous overnight LLM training experiments driven by `program.md` | Python / uv project | Experiment *culture*, not finance-specific | **A** | Reference / optional note-taking |
| `/Users/prady/Desktop/research_dire/AutoResearchClaw` | Autonomous “research paper” agent framework | Python (large test suite) | Literature / workflow automation ideas | **A** | Ignore for runtime; optional external notes |
| `/Users/prady/Desktop/proof_math/lean4` | Lean 4 formal mathematics | Lean | Optional rigor for future proofs, not pricing | **A** | Ignore for this codebase |
| `/Users/prady/Desktop/arXiv_llm_lite/arxiv-sanity-lite` | arXiv polling, tagging, SVM recommendations | Python + web UI | Literature triage for the human researcher | **B** | Optional: use offline to curate papers; no import |
| `/Users/prady/Desktop/agents/agency-agents` | Collection of agent personas / workflows | Docs + agents | General agent patterns | **A** | Ignore for core |
| `/Users/prady/Desktop/langchain` | LangChain / LangGraph monorepo | Python/TS | Heavy orchestration stack | **A** | Do not wire into `src/qhpc_cache` |

## Per-resource detail

### autoresearch-macos

- **Purpose**: Self-modifying training loop with `program.md` as “org chart” for agents.
- **Relevance**: Teaches experiment logging and iteration discipline; **not** derivative pricing.
- **Risks**: Would pull focus toward LLM training, not Monte Carlo / quantum mapping.
- **Integration level**: **A** — reference only.

### AutoResearchClaw (under research_dire)

- **Purpose**: End-to-end autonomous research / paper generation.
- **Relevance**: High-level research automation; could inspire **optional** tooling under `tools/` only.
- **Risks**: Huge dependency surface; opaque to undergrad readers if embedded in core.
- **Integration level**: **A** (optional **B** only for a tiny note-generator script, not default).

### proof_math / lean4

- **Purpose**: Formal proof development.
- **Relevance**: None for current classical MC pricing milestones.
- **Integration level**: **A**.

### arxiv-sanity-lite

- **Purpose**: Local arXiv mirror workflow and paper recommendations.
- **Relevance**: Excellent **human** tool for quantum finance / QMCI literature.
- **Risks**: Web stack and DB not needed inside qhpc_cache.
- **Integration level**: **B** — use externally; optional scripts could read exported tags as plain text.

### agency-agents

- **Purpose**: Pre-built agent personas for general tasks.
- **Relevance**: Low for transparent numeric pricing code.
- **Integration level**: **A**.

### langchain

- **Purpose**: Application framework for LLM chains and graphs.
- **Relevance**: Could summarize docs **outside** this package.
- **Risks**: Framework assumptions, dependency weight, reduced explainability for students.
- **Integration level**: **A** ( **B** only if an optional summarizer lives under `tools/` and is never imported from `src/qhpc_cache`).

## Usefulness scoring (framework from spec)

Scores are on 0–5 (higher is better except **dependency_risk** where lower risk is better). **integration_cost** is scored as “ease” (higher = cheaper to integrate).

| Resource | context | integration_cost | explainability | maintenance | modularity | dependency_risk | research_leverage |
|----------|---------|------------------|----------------|-------------|------------|-----------------|-------------------|
| autoresearch-macos | 1 | 2 | 2 | 2 | 3 | 1 | 2 |
| AutoResearchClaw | 2 | 1 | 1 | 1 | 2 | 0 | 3 |
| lean4 | 0 | 0 | 2 | 2 | 2 | 2 | 0 |
| arxiv-sanity-lite | 2 | 2 | 4 | 3 | 4 | 2 | 4 |
| agency-agents | 1 | 1 | 2 | 2 | 2 | 1 | 1 |
| langchain | 1 | 0 | 1 | 1 | 2 | 0 | 2 |

**Formula (as specified):**  
`usefulness = 0.25*CR + 0.20*EX + 0.15*MOD + 0.20*RL + 0.10*MT + 0.10*IC`  
Penalties: −0.20 if `dependency_risk <= 2`, −0.15 if `explainability <= 2`, −0.15 if `modularity <= 2`.

Interpretation for **this** project: all listed resources fall into **Level A (reference)** or **Level B (optional tooling)**. None are adopted as **core runtime** dependencies. See `docs/dependency_decisions.md`.
