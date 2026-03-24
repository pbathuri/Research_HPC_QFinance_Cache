# Cache Metric Definitions

Formal definitions for the research-grade cache metrics in `cache_metrics.py`.

## Exact Hit Rate

$$\text{ExactHR} = \frac{|\{i : \text{key}_i \in \mathcal{C}\}|}{N}$$

where $N$ is total lookups and $\mathcal{C}$ is the set of cached keys.

## Similarity Hit Rate

$$\text{SimHR} = \frac{|\{i : \exists k \in \mathcal{C}, d(\text{key}_i, k) \leq \epsilon\}|}{N}$$

where $d(\cdot, \cdot)$ is the similarity metric from `circuit_similarity.py` and
$\epsilon$ is the similarity threshold.

## Miss Rate

$$\text{MissR} = 1 - \text{ExactHR} - \text{SimHR}$$

## Reuse Distance

For a key $k$ accessed at position $i$ that was last accessed at position $j < i$:

$$\text{ReuseDistance}(k, i) = |\{k' : k' \text{ accessed at some } t, j < t < i, k' \neq k\}|$$

This counts distinct keys accessed between consecutive accesses to the same key.
Lower reuse distance indicates higher temporal locality.

## Locality Score

$$\text{Locality} = \frac{1}{1 + \overline{\text{ReuseDistance}}}$$

where $\overline{\text{ReuseDistance}}$ is the mean reuse distance.
Ranges from $(0, 1]$; higher is better.

## Cache Efficiency

$$\text{Efficiency} = \frac{\sum_{i \in \text{hits}} T_{\text{saved}}(i)}{\sum_{i=1}^{N} T_{\text{compute}}(i)}$$

where $T_{\text{saved}}(i)$ is compute time avoided on hit $i$ and $T_{\text{compute}}(i)$
is the full compute cost for request $i$.

## Critical Cache Window Score

For event-window workloads with $M$ high-priority lookups:

$$\text{CriticalCWS} = \frac{|\{i \in \text{event-window} : \text{hit}_i\}|}{M}$$

Measures how well the cache handles stress-scenario workloads.

## Per-Policy Comparison

The `compare_policies()` function produces a side-by-side table:

| Metric | Policy A | Policy B | ... |
|--------|----------|----------|-----|
| ExactHR | | | |
| SimHR | | | |
| MissR | | | |
| Locality | | | |
| Efficiency | | | |

## Workload-family observations

Rows in ``workload_cache_observations.csv`` (``WorkloadCacheObservationRow``) stratify cache metrics by:

- **workload_spine_id** / **workload_spine_rank** — locked spine families (1=feature panel, 2=portfolio risk, 3=option pricing, 4=event window); see ``workload_signatures.CORE_WORKLOAD_SPINE``
- **workload_family** — hash of pipeline stage + portfolio + model families (+ event stress flag)
- **portfolio_family** / **model_family** — opaque labels from ``workload_signatures.py``
- **feature_dim_before** / **feature_dim_after** — feature-space size around condensation
- **exact_hit_rate**, **similarity_hit_rate**, **miss_rate** — copied from ``CacheResearchTracker.summary()`` at snapshot time
- **rolling_locality_score**, **reuse_distance_approx** — locality/reuse from the same summary
- **working_set_pressure** — heuristic 0–1 pressure proxy (caller-supplied or from trace heuristics)
- **cache_efficiency_workload** — efficiency at snapshot
- **event_window_stress_flag** — whether the snapshot corresponds to high-risk event-window workloads

Use ``cache_workload_mapping.record_workload_cache_snapshot`` or ``cache_metrics.flush_workload_observation`` from pipeline stages (data ingestion, QMC, event book) without replacing aggregate ``cache_metrics.csv`` rows.

## Spine pipeline observations (event alignment + feature panels)

File: ``spine_pipeline_observations.csv`` (``SpinePipelineObservationRow`` via ``metrics_sink.log_spine_pipeline`` / ``cache_workload_mapping.record_spine_pipeline_observation``).

Captures **phase-local** stats (not full cache policy summaries):

- **workload_spine_id** / **workload_spine_rank** — e.g. ``event_window`` / ``feature_panel``
- **pipeline_phase** — ``event_alignment`` or ``feature_panel``
- **source_datasets** — semicolon-separated institutional sources touched
- **row_count_primary** / **row_count_after_join** — TAQ vs aligned / panel width
- **join_width_estimate** — column-count proxy for join explosion / width
- **feature_dim_before** / **feature_dim_after** — engineered vs condensed features (feature panel)
- **event_window_seconds** — request span (event alignment)
- **alignment_match_rate** — PERMNO match rate when applicable
- **reuse_alignment_opportunities** — hint for repeated link-table reuse (e.g. count of sources attempted)
