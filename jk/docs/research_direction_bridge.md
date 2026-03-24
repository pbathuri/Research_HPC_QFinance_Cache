# Research Direction Bridge

This document bridges the current repository state back to the original research
direction in an explicit, evidence-bounded way.

## What stayed constant

- Finance workloads remain the empirical core:
  - event-window workflows
  - feature-panel workflows
  - portfolio-risk workflows
  - option-pricing workflows
- Cache/reuse remains the architectural focus.
- HPC/QHPC relevance remains a planned later-stage objective.

## What became more disciplined

- The project moved from broad architecture ambition to staged evidence-building:
  - family-level workload artifacts
  - unified observability schema
  - similarity-caching hypothesis
  - guided-cache architecture hypothesis
- Claims are now typed explicitly as:
  - `measured`
  - `derived`
  - `proxy-supported`
  - `hypothesis`
  - `deferred`
- Mac-side evidence and HPC/PMU validation are separated by policy.

## Current architecture-hypothesis status

- Supported now:
  - workload-signature grouping
  - exact-match reuse candidates
  - similarity-aware candidate tables
  - ranked escalation targets
- Not yet proven:
  - production guided-routing behavior
  - low-level hardware-cache improvement claims
  - admission/placement policy optimality
- Deferred:
  - PMU-backed microarchitectural confirmation
  - BigRed200-scale deployment behavior
  - hybrid QHPC coupling behavior

## Honest path back to the original proposal

1. Keep finance workloads as the benchmark substrate.
2. Validate architecture hypotheses with controlled replay/routing studies.
3. Escalate strongest candidates to HPC PMU-backed experiments.
4. Use validated HPC evidence to guide any future hybrid QHPC mapping.
5. Keep quantum-finance mapping as a later stage, contingent on validated
   workload/caching evidence rather than assumed performance gains.

