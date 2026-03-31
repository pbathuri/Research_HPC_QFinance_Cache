# Demo and pipeline entrypoints

Run from repository **`jk/`** with `PYTHONPATH=src` unless you use `pip install -e .`.

**Operator-focused checklist (setup, WRDS, spine-ordered experiments):** `docs/operator_entrypoints.md`.

## Workload priority (observability)

| Priority | Area | How to run |
|----------|------|------------|
| 1 | Feature panels / large universe | Imports: `historical_returns`, `alpha_features`, `universe_analysis`; often after `run_data_ingestion_event_book_demo.py` |
| 2 | Portfolio risk / VaR–CVaR | `portfolio`, `risk_metrics`, `historical_risk` |
| 3 | Option pricing | `pricing_workloads.py` bundle APIs (or `run_demo.py` for legacy MC-only demo) |
| 4 | Event windows | Inside `run_data_ingestion_event_book_demo.py` + `event_book` |

When CRSP event tags and TAQ windows matter, **implementation order** is still:
`event_alignment` first, then `feature_panel`. See `docs/core_research_spine.md`.

## Canonical event-library comparison phase (new)

Use library entrypoints (no new script sprawl):

```python
from qhpc_cache.event_set_library import export_event_set_manifest
from qhpc_cache.event_library_compare import run_event_set_comparison, export_event_library_comparison
from qhpc_cache.event_workload_signatures import compute_event_workload_signatures
from qhpc_cache.cache_study_analysis import run_cache_study_analysis, export_cache_study_analysis
from qhpc_cache.feature_panel_compare import (
    build_feature_panel_comparison_bundle,
    export_feature_panel_comparison_bundle,
)
from qhpc_cache.portfolio_risk_workloads import (
    run_portfolio_risk_workload_bundle,
    export_portfolio_risk_workload_bundle,
)
from qhpc_cache.pricing_workloads import (
    run_pricing_workload_bundle,
    export_pricing_workload_bundle,
)
from qhpc_cache.unified_observability import (
    run_unified_observability_bundle,
    export_unified_observability_bundle,
)
from qhpc_cache.similarity_cache_hypothesis import (
    run_similarity_caching_hypothesis_bundle,
    export_similarity_caching_hypothesis_bundle,
)
from qhpc_cache.guided_cache_hypothesis import (
    run_guided_cache_hypothesis_bundle,
    export_guided_cache_hypothesis_bundle,
    export_research_direction_bridge,
)
from qhpc_cache.paper_artifacts import (
    run_paper_packaging_bundle,
    export_paper_packaging_bundle,
)
from qhpc_cache.future_extension_planner import (
    run_future_extension_planning_bundle,
    export_future_extension_planning_bundle,
)

export_event_set_manifest("outputs/event_library/event_set_manifest.json")
result = run_event_set_comparison(raw_event_rows=normalized_aligned_rows)
paths = export_event_library_comparison(
    comparison_result=result,
    output_dir="outputs/event_library_comparison",
)
sig = compute_event_workload_signatures(result["event_window_manifest"])
analysis = run_cache_study_analysis(normalized_event_rows=result["event_window_manifest"])
cache_study_paths = export_cache_study_analysis(
    analysis_result=analysis,
    output_dir="outputs/cache_study_analysis",
)
panel_bundle = build_feature_panel_comparison_bundle(
    ohlcv_long=crsp_like_daily_long,
    panel_key_base="feature_panel_compare_phase",
    rates_frame=rates_frame,
    event_tags=event_tags_frame,
)
panel_paths = export_feature_panel_comparison_bundle(
    bundle=panel_bundle,
    output_dir="outputs/feature_panel_comparison_phase",
)
risk_bundle = run_portfolio_risk_workload_bundle(
    daily_panel=crsp_like_daily_long,
    rates_frame=rates_frame,
    event_tags=event_tags_frame,
)
risk_paths = export_portfolio_risk_workload_bundle(
    bundle=risk_bundle,
    output_dir="outputs/portfolio_risk_workloads_phase",
)
pricing_bundle = run_pricing_workload_bundle(
    rates_frame=rates_frame,
    batch_sizes=(16, 32, 64),
)
pricing_paths = export_pricing_workload_bundle(
    bundle=pricing_bundle,
    output_dir="outputs/pricing_workload_family_phase",
)
unified_bundle = run_unified_observability_bundle(
    event_comparison_result=result,
    cache_study_result=analysis,
    feature_panel_bundle=panel_bundle,
    portfolio_risk_bundle=risk_bundle,
    pricing_bundle=pricing_bundle,
)
unified_paths = export_unified_observability_bundle(
    bundle=unified_bundle,
    output_dir="outputs/unified_observability_phase",
)
similarity_bundle = run_similarity_caching_hypothesis_bundle(
    unified_bundle=unified_bundle,
)
similarity_paths = export_similarity_caching_hypothesis_bundle(
    bundle=similarity_bundle,
    output_dir="outputs/similarity_caching_hypothesis_phase",
)
guided_bundle = run_guided_cache_hypothesis_bundle(
    outputs_root="outputs",
)
guided_paths = export_guided_cache_hypothesis_bundle(
    bundle=guided_bundle,
    output_dir="outputs/guided_cache_hypothesis_phase",
)
export_research_direction_bridge(
    bundle=guided_bundle,
    output_path="outputs/guided_cache_hypothesis_phase/research_direction_bridge.md",
)
paper_bundle = run_paper_packaging_bundle(
    outputs_root="outputs",
)
paper_paths = export_paper_packaging_bundle(
    bundle=paper_bundle,
    output_dir="outputs/formal_paper_packaging_phase",
)
future_bundle = run_future_extension_planning_bundle(
    outputs_root="outputs",
)
future_paths = export_future_extension_planning_bundle(
    bundle=future_bundle,
    output_dir="outputs/future_extension_planning_phase",
)
```

Set E in this phase is ruleset-generated as a broad mixed institutional stress library (~39 curated events, slightly overweight macro/rates and crisis).

See:

- `docs/event_set_library.md`
- `docs/event_library_comparison.md`
- `docs/event_workload_signatures.md`
- `docs/cache_study_analysis.md`
- `docs/feature_panel_comparison.md`
- `docs/portfolio_risk_workloads.md`
- `docs/pricing_workload_family.md`
- `docs/unified_observability.md`
- `docs/similarity_caching_hypothesis.md`
- `docs/guided_cache_architecture_hypothesis.md`
- `docs/research_direction_bridge.md`
- `docs/paper_packaging_plan.md`
- `docs/paper_narrative.md`
- `docs/paper_methods.md`
- `docs/paper_results.md`
- `docs/paper_limitations.md`
- `docs/paper_future_work.md`
- `docs/proposal_to_paper_bridge.md`
- `docs/hpc_future_extension_plan.md`
- `docs/pmu_validation_plan.md`
- `docs/bigred200_execution_plan.md`
- `docs/qhpc_relevance_plan.md`
- `docs/finance_to_qhpc_mapping.md`
- `docs/phase2_research_program.md`
- `docs/proposal_continuity_bridge.md`
- `docs/mac_vs_hpc_observability.md`

## Canonical data ingestion + event book

| Script | Purpose |
|--------|---------|
| **`run_data_ingestion_event_book_demo.py`** | Daily universe pull (Databento when key present), registry, rates, event-book / TAQ paths, universe analytics, critical cache export. |

```bash
PYTHONPATH=src python3 run_data_ingestion_event_book_demo.py
```

## Optional full research pipeline (non-spine definition)

| Script | Purpose |
|--------|---------|
| **`run_full_research_pipeline.py`** | Staged pipeline: env check, ingestion when configured, QMC/cache, literature, matplotlib/seaborn visualization, reporting. |

```bash
PYTHONPATH=src python3 run_full_research_pipeline.py --budget=30
```

## Canonical repeated-workload cache study (new)

Purpose: strengthen local reuse-rich cache evidence beyond mostly-unique full-pipeline streams.

```bash
PYTHONPATH=src python3 run_repeated_workload_study.py --lane both --scale-label standard
```

See `docs/repeated_workload_study.md` for workload families, lane policy, outlier handling, and outputs.

## BigRed200 Slurm-first artifact generation (new)

Generate submission artifacts without pretending to execute HPC locally:

```bash
PYTHONPATH=src python3 run_full_research_pipeline.py \
  --mode experiment_batch \
  --requested-backend bigred200_mpi_batch \
  --defer-execution-to-hpc \
  --slurm-job-name qhpc_qmc_mpi \
  --slurm-walltime 02:00:00 \
  --slurm-partition general \
  --slurm-nodes 2 \
  --slurm-ntasks 64 \
  --slurm-cpus-per-task 1 \
  --slurm-mem 128G
```

See:

- `docs/bigred200_execution_plan.md`
- `docs/bigred200_operator_guide.md`
- `docs/cuda_porting_candidates.md`

Inspect latest run deterministically (mtime-based resolver):

```bash
PYTHONPATH=src python3 run_full_research_pipeline.py --latest-only-summary --output-root outputs
```

CLI help now prints usage and exits without running the pipeline:

```bash
PYTHONPATH=src python3 run_full_research_pipeline.py --help
```

## Visualization (matplotlib / seaborn)

| Script | Purpose |
|--------|---------|
| **`run_research_visualization_demo.py`** | Market overview, microstructure-style plots, alpha diagnostics, simulation comparison (see script header for flags). |

## Finance baseline (teaching / cache demo)

| Script | Purpose |
|--------|---------|
| **`run_demo.py`** | Monte Carlo + cache hit/miss demo, small experiment runner touchpoints. |

## Secondary / legacy

| Script | Notes |
|--------|--------|
| `run_research_workflow_demo.py` | **Legacy** simulated workflow; exports JSON/JSONL/txt via `research_workflow_export` only (no Pixel bridge). |
| `monte_carlo_cache_baseline.py` | Legacy monolith-style baseline; prefer `run_demo.py` + package imports. |
| `monte_FSS.py` | Separate experiment script; treat as **legacy** unless your lab standardizes on it. |

## WRDS utilities (library / notebook)

- **`qhpc_cache.wrds_provider`**, **`wrds_queries.WRDS_INTEGRATION_ROADMAP`**, **`wrds_registry.pull_and_register_crsp_treasury()`** — see `docs/wrds_active_integration.md`.

## Documentation index

- Core spine: `docs/core_research_spine.md`
- Simplification plan: `docs/repo_simplification_plan.md`
- Module map: `docs/module_consolidation_map.md`
- Research alignment: `docs/research_alignment_checkpoint.md`
- Module ownership: `docs/current_canonical_module_map.md`
- Open questions: `docs/open_research_questions.md`
