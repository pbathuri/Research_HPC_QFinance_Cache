# Operator entrypoints (canonical research spine)

Run from **`jk/`** with `PYTHONPATH=src` (or `pip install -e .`).

## 1. Canonical setup check

| Step | Command / action |
|------|------------------|
| Env + optional paths | `python3 scripts/check_env.py` |
| Data-phase oriented check | `python3 scripts/check_data_env.py` |

Verify: `WRDS_USERNAME` (if using WRDS), `DATABENTO_API_KEY` (if using live daily), `QHPC_DATA_ROOT`, optional `QHPC_KDB_TAQ_REPO`, `QHPC_CRSP_TREASURY_PATH`.

## 2. Canonical broad-universe ingestion

| Script | Role |
|--------|------|
| **`run_data_ingestion_event_book_demo.py`** | Daily universe (Databento or synthetic fallback), registry checkpoints, rates hook, event-book path, universe analytics, critical cache window export. |

```bash
PYTHONPATH=src python3 run_data_ingestion_event_book_demo.py
```

## 3. Canonical WRDS enrichment

No separate top-level WRDS script is required:

```python
from qhpc_cache.wrds_registry import pull_and_register_crsp_treasury
pull_and_register_crsp_treasury()
```

## 4. Canonical CRSP+TAQ aligned event pipeline (Phase 1)

```python
from qhpc_cache.taq_event_pipeline import run_aligned_event_pipeline
from qhpc_cache.data_models import EventWindowRequest
```

Use this path for PERMNO-sealed event windows before feature panels.

## 5. Canonical CRSP-backed feature panel (Phase 2)

```python
from qhpc_cache.feature_panel import build_feature_panel_with_observability
```

## 6. Canonical event-set library generation (new)

```python
from qhpc_cache.event_set_library import export_event_set_manifest

export_event_set_manifest("outputs/event_library/event_set_manifest.json")
```

This exports locked Sets A-E, including the ruleset-generated Set E mixed stress library (~39 events) plus manual-review composition metadata.

## 7. Canonical event-library comparison run (new)

```python
from qhpc_cache.event_library_compare import run_event_set_comparison, export_event_library_comparison

result = run_event_set_comparison(raw_event_rows=normalized_aligned_rows)
paths = export_event_library_comparison(
    comparison_result=result,
    output_dir="outputs/event_library_comparison",
)
```

## 8. Canonical event workload-signature run (new)

```python
from qhpc_cache.event_workload_signatures import compute_event_workload_signatures

signature_df = compute_event_workload_signatures(result["event_window_manifest"])
```

## 9. Researcher summary output generation (new)

Use `export_event_library_comparison(...)` outputs:

- CSV analysis tables
- JSON manifests
- markdown summaries
- matplotlib/seaborn plots

This avoids adding new top-level scripts; use canonical library entrypoints only.

## 10. Canonical cache-study analysis run (new)

```python
from qhpc_cache.cache_study_analysis import run_cache_study_analysis, export_cache_study_analysis

analysis = run_cache_study_analysis(
    normalized_event_rows=result["event_window_manifest"],
)
paths = export_cache_study_analysis(
    analysis_result=analysis,
    output_dir="outputs/cache_study_analysis",
)
```

Within-set analysis is executed first, then cross-set comparison.

## 11. Canonical cache/workload observation

- Metrics root: `QHPC_METRICS_DIR` (default `outputs/metrics/`).
- `workload_cache_observations.csv` via `cache_workload_mapping.record_workload_cache_snapshot`.
- `spine_pipeline_observations.csv` via `cache_workload_mapping.record_spine_pipeline_observation`.

## 12. Canonical feature-panel comparison bundle (new)

```python
from qhpc_cache.feature_panel_compare import (
    build_feature_panel_comparison_bundle,
    export_feature_panel_comparison_bundle,
)

bundle = build_feature_panel_comparison_bundle(
    ohlcv_long=crsp_like_daily_long,
    panel_key_base="feature_panel_compare_phase",
    rates_frame=rates_frame,
    event_tags=event_tags_frame,
)
paths = export_feature_panel_comparison_bundle(
    bundle=bundle,
    output_dir="outputs/feature_panel_comparison_phase",
)
```

This produces the four locked variants:
- non-event-aware raw
- non-event-aware PCA-condensed
- event-aware raw
- event-aware PCA-condensed

## 13. Canonical portfolio-risk workload bundle (new)

```python
from qhpc_cache.portfolio_risk_workloads import (
    run_portfolio_risk_workload_bundle,
    export_portfolio_risk_workload_bundle,
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
```

This covers both locked layers:
- broad-universe historical VaR/CVaR
- deterministic portfolio-slice scenario recomputation

## 14. Canonical option-pricing workload family bundle (new)

```python
from qhpc_cache.pricing_workloads import (
    run_pricing_workload_bundle,
    export_pricing_workload_bundle,
)

pricing_bundle = run_pricing_workload_bundle(
    rates_frame=rates_frame,   # optional; falls back to default rate
    batch_sizes=(16, 32, 64),
)
pricing_paths = export_pricing_workload_bundle(
    bundle=pricing_bundle,
    output_dir="outputs/pricing_workload_family_phase",
)
```

This enforces the locked model-family order:
- Black-Scholes closed-form
- Monte Carlo European
- Heston Monte Carlo
- CRR lattice

Then layers deterministic contract-batch and Greeks (`delta`, `gamma`, `vega`, `theta`) workloads on top.

## 15. Canonical unified observability across families (new)

```python
from qhpc_cache.unified_observability import (
    run_unified_observability_bundle,
    export_unified_observability_bundle,
)

unified = run_unified_observability_bundle(
    event_comparison_result=event_result,
    cache_study_result=cache_study_analysis,
    feature_panel_bundle=panel_bundle,
    portfolio_risk_bundle=risk_bundle,
    pricing_bundle=pricing_bundle,
)
unified_paths = export_unified_observability_bundle(
    bundle=unified,
    output_dir="outputs/unified_observability_phase",
)
```

This keeps ranking/similarity layered on top of one common schema table.

## 16. Canonical similarity-caching hypothesis bundle (new)

```python
from qhpc_cache.similarity_cache_hypothesis import (
    run_similarity_caching_hypothesis_bundle,
    export_similarity_caching_hypothesis_bundle,
)

similarity_bundle = run_similarity_caching_hypothesis_bundle(
    unified_bundle=unified,
)
similarity_paths = export_similarity_caching_hypothesis_bundle(
    bundle=similarity_bundle,
    output_dir="outputs/similarity_caching_hypothesis_phase",
)
```

This executes within-family similarity first, cross-family similarity second, and
exports explicit claim labels (`measured`, `derived`, `proxy-supported`, `hypothesis`, `deferred`).

## 17. Canonical guided-cache architecture hypothesis bundle (new)

```python
from qhpc_cache.guided_cache_hypothesis import (
    run_guided_cache_hypothesis_bundle,
    export_guided_cache_hypothesis_bundle,
    export_research_direction_bridge,
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
```

This keeps architecture statements evidence-bounded and claim-typed, without
claiming production cache-controller or PMU-level hardware proof.

## 18. Canonical formal paper-packaging bundle (new)

```python
from qhpc_cache.paper_artifacts import (
    run_paper_packaging_bundle,
    export_paper_packaging_bundle,
)

paper_bundle = run_paper_packaging_bundle(
    outputs_root="outputs",
)
paper_paths = export_paper_packaging_bundle(
    bundle=paper_bundle,
    output_dir="outputs/formal_paper_packaging_phase",
)
```

This produces curated paper-ready tables/figures/manifests and keeps all claims
explicitly typed (`measured`, `derived`, `proxy-supported`, `hypothesis`, `deferred`).

## 19. Canonical optional HPC/QHPC future-extension planning bundle (new)

```python
from qhpc_cache.future_extension_planner import (
    run_future_extension_planning_bundle,
    export_future_extension_planning_bundle,
)

future_bundle = run_future_extension_planning_bundle(
    outputs_root="outputs",
)
future_paths = export_future_extension_planning_bundle(
    bundle=future_bundle,
    output_dir="outputs/future_extension_planning_phase",
)
```

This is planning-only and uses explicit status labels:
`implemented now`, `ready for x86/HPC validation`, `ready for BigRed200 execution planning`,
`conceptually mappable to QHPC later`, `deferred / speculative`.

## Non-spine (optional)

| Item | Notes |
|------|------|
| **`run_research_visualization_demo.py`** | Matplotlib/seaborn diagnostics; useful inspection path. |
| **`run_research_workflow_demo.py`** | Legacy simulated multi-role trace. |
| **`run_full_research_pipeline.py`** | Optional orchestration; not spine correctness. |

---

*Demo-oriented index: `docs/demo_entrypoints.md`.*
