# Paper Narrative

Research motivation:

- Quantitative finance workloads are structurally repetitive and expensive enough
  to motivate disciplined caching/reuse studies.

Problem framing:

- The project evaluates workload structure first, then builds architecture
  hypotheses from evidence.
- It does not claim low-level cache-controller correctness from proxy data.

Why these workload families:

- Event workflows reveal window reconstruction and join-pattern repetition.
- Feature-panel workflows reveal dimensional and attachment-driven reuse.
- Portfolio-risk workflows reveal repeated scenario recomputation structure.
- Pricing workflows reveal repeated model/batch/Greeks computation structure.

Why similarity-caching first:

- Exact-match-only reuse is often too strict for practical workload variation.
- Similarity-aware retrieval provides a defensible intermediate hypothesis layer.

Why guided-cache remains hypothesis-level:

- Current evidence is primarily measured/derived/proxy-supported workload
  structure.
- Hardware-cache behavior requires deferred PMU-backed HPC validation.

