# CUDA Porting Candidates (Future-Only)

This document identifies the first kernels worth porting once a real GPU path is
implemented. No CUDA execution is claimed in the current phase.

## Candidate 1: Monte Carlo path simulation kernel

- Current location: pricing and QMC engine simulation loops
- Why: dominant arithmetic volume and straightforward SIMD/GPU parallel mapping
- Input contract:
  - per-contract parameters (`S0`, `K`, `r`, `sigma`, `T`)
  - path count
  - RNG seed stream descriptor
- Output contract:
  - terminal prices / payoff accumulators
  - partial sums for mean/std-error reduction

## Candidate 2: Payoff evaluation kernel

- Current location: payoff-family evaluation in pricing workloads
- Why: branch-limited vectorized math over large simulated path arrays
- Input contract:
  - simulated terminal/pathwise values
  - payoff-type parameters
- Output contract:
  - per-path payoff vector or reduced aggregate stats

## Candidate 3: Repeated-workload replay hotset kernel

- Current location: repeated workload families (`exact`, `near`, `path ladder`)
- Why: high-volume repeated pricing evaluations can benefit from GPU batching
- Input contract:
  - batched request tensors
  - lane/family metadata preserved externally
- Output contract:
  - stable per-request result rows preserving request IDs and hashes

## Candidate 4: Feature-panel condensation matrix ops

- Current location: feature condensation/comparison phases
- Why: matrix-heavy transforms and decomposition-friendly linear algebra
- Input contract:
  - feature matrix
  - selected transform configuration
- Output contract:
  - reduced feature matrix with stable schema metadata

## CUDA readiness boundary

- Current backend remains placeholder (`cuda_placeholder`).
- Porting should begin with candidate 1 (path simulation), then candidate 2.
- Output schemas must remain identical to CPU path for reproducibility and paper continuity.
