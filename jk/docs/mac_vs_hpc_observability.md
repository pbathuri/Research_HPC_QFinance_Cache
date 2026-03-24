# Mac vs HPC Observability Policy

This document separates immediate Mac-compatible observability from later HPC/x86 PMU layers.

## Immediate Mac-compatible observability (current phase)

Use these now:

- Stage timings (`stage_timing_ms`, per-stage elapsed times)
- Distribution summaries (`p50`, `p90`, `p99`, `p99.9` where meaningful)
- Row-count and join-width scaling signals
- Feature/workload dimensionality summaries
- Reuse and locality proxies:
  - repeated event-window reconstruction markers
  - repeated join-pattern markers
  - reusable derived-structure markers
- Alignment quality fields (`identifier_match_quality`, match rates)
- Workload signature summary tables for event-library comparison
- Within-set and cross-set cache-study tables (`cache_study_*` outputs)
- Feature-panel comparison tables (`feature_panel_*` outputs)
- Portfolio-risk workload tables (`portfolio_risk_*` outputs)
- Option-pricing workload tables (`pricing_*` outputs)
- Unified cross-family observability tables (`unified_workload_*` outputs)
- Similarity-caching hypothesis tables (`similarity_*` outputs)
- Guided-cache architecture hypothesis tables (`guided_cache_*` outputs)
- Formal paper-packaging tables/manifests (`paper_*` outputs)
- Optional future-extension planning tables/manifests (`future_extension_*`, `pmu_*`, `bigred200_*`, `qhpc_*`)

## Later HPC/x86 PMU observability (deferred)

Do not force these onto the Mac critical path in this phase:

- L1/L2/L3 miss counters
- Hardware prefetch counters
- TLB miss/pressure counters
- NUMA/remote-hit metrics
- False-sharing/cache-line-bounce focused counters

These belong to dedicated HPC runs (e.g., BigRed200) once workload signatures and event-library comparisons are stable.

For cache-study analysis specifically, PMU-style metrics are documented as deferred in
`docs/cache_study_analysis.md` and should not be backported into the Mac-critical path.

For unified cross-family observability, the `variant_mac_vs_hpc_priority` ranking is a
Mac-side escalation heuristic only; PMU-backed validation remains an HPC follow-up step.

For similarity-caching hypothesis outputs, similarity relationships and clusters are
workload-structure evidence only. PMU-backed hardware validation is deferred.

For guided-cache architecture hypothesis outputs, component/routing/hardware-aware
layers are claim-typed synthesis artifacts. Hardware-aware validation remains
deferred to HPC/x86 PMU phases.

For formal paper-packaging outputs, any figure/table claim remains bounded by the
underlying evidence label and does not upgrade deferred claims to measured claims.

For optional future-extension planning outputs, status labels indicate planning
readiness only and do not indicate completed PMU/HPC/QHPC execution.

## Execution policy

- Push Mac M4 Pro for long but meaningful workloads.
- If scope becomes too large on Mac:
  - degrade scope sensibly,
  - record deferred workloads explicitly,
  - mark them as HPC-targeted.
- Do not treat Mac and HPC as equivalent environments.
