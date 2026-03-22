# Local Desktop resources → research agent roles

This maps **repos on the researcher’s machine** (not Python dependencies) to the **modeled roles** in `qhpc_cache.research_agents`. Nothing here is imported by `qhpc_cache` at runtime unless you explicitly add it.

| Local path (typical) | Supports agent role | Relationship | How it helps the simulation / project |
|----------------------|---------------------|--------------|----------------------------------------|
| `~/Desktop/pixel-agents` | **VisualizationAgent** (live) | **Optional visualization** | VS Code extension + Claude Code JSONL; see `docs/pixel_agents_audit.md`. qhpc exports are **sidecar traces**. |
| `~/Desktop/research_dire` (AutoResearchClaw) | **LiteratureReviewAgent**, **ExperimentAgent** | **Reference / optional tooling** | Multi-language docs and claw-style automation ideas for task lists and lit review—not wired into qhpc imports. |
| `~/Desktop/autoresearch-macos` | **LiteratureReviewAgent** | **Optional research orchestration** | macOS-oriented autoresearch patterns; use to **author** `ResearchTask` descriptions offline. |
| `~/Desktop/arXiv_llm_lite` | **LiteratureReviewAgent** | **Reference / optional tooling** | arXiv-sanity-lite style workflows for paper discovery; map hits to `related_paper_labels` on tasks. |
| `~/Desktop/agents` (e.g. agency-agents) | **ExperimentAgent**, **VisualizationAgent** | **Optional orchestration experiments** | Multi-IDE agent integrations; compare patterns to our **simulation-only** `research_agents.py`. |
| `~/Desktop/langchain` | **ExperimentAgent** | **Reference / optional** | Framework for LLM chains; qhpc stays stdlib—use for **external** experiment drivers only. |
| `~/Desktop/proof_math` / Lean | **FinanceModelAgent** (informal) | **Reference only** | Formal proof work parallel to pricing math; **not** part of Monte Carlo runtime. |
| **Codex CLI** (terminal) | **FinanceModelAgent**, **CachePolicyAgent** | **Optional development tool** | Audits, refactors, tests—same as any editor assistant; emits no qhpc trace unless you log manually. |

## Usage principle

- **qhpc_cache** = finance-valid **reference implementation** (stdlib).
- **Local repos** = **ideas, papers, and optional tools** to populate tasks, docs, and future bridges.
- **Pixel Agents** = **live** coding agent animation (Claude Code); **qhpc bridge** = **exported** workflow narrative for the same research program.
