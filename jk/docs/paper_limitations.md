# Paper Limitations

This project explicitly separates evidence classes:

- `measured`: direct workload outputs and canonical tables
- `derived`: computed summaries/rankings from measured outputs
- `proxy-supported`: structural similarity/reuse proxies
- `hypothesis`: architecture/routing/admission concepts not experimentally proven
- `deferred`: PMU/HPC/QHPC-level claims pending future validation

## Current limits

- Mac-side evidence does not prove PMU-level cache behavior.
- Guided routing and similarity-threshold logic are not yet policy-engine proofs.
- No production cache-controller implementation is claimed.

## Required future validation

- x86/HPC PMU studies (L1/L2/L3, TLB, prefetch, NUMA, cache-line behavior)
- BigRed200-scale replay/validation
- deeper low-level controller interaction experiments

