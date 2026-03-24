# PMU Validation Plan (Future x86/HPC)

This plan maps PMU metrics to already-implemented workload families.

## Why PMU work is later

- Mac-side workload proxies are useful for structure, not hardware proof.
- PMU collection requires x86/HPC execution context.

## Workload families and PMU focus

- Event workloads:
  - L1/L2/L3 misses
  - TLB pressure
  - prefetch behavior for window scans
- Feature-panel workloads:
  - cache misses during feature matrix construction
  - prefetch and TLB pressure for high-dimensional traversal
- Portfolio-risk workloads:
  - cache misses during scenario recomputation
  - NUMA/remote-hit for distributed slices
  - false-sharing/cache-line-bounce in aggregation paths
- Pricing workloads:
  - cache misses in batch/Greeks loops
  - prefetch and TLB behavior in simulation sweeps

## Output anchor

- `pmu_validation_priority.csv`
- `pmu_validation_manifest.json`

Status label for this plan: `ready for x86/HPC validation`.

