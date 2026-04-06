# Revised Research Proposal (Short Form)

## Cache-Aware Computation for Finance Workloads on Big Red 200: From Foundational Measurement to Portfolio-Scale Pipeline Design

**Pradyot Bathuri** · Indiana University Bloomington, Intelligent Systems Engineering  
**April 2026**

---

## 1. Original scope and how the project evolved

The initial proposal targeted an end-to-end system: AI-assisted, portfolio-aware quantum circuit compilation for Quantum Monte Carlo Integration (QMCI) finance workloads on Big Red 200, spanning OpenMP, MPI, CUDA, and a learned cache eviction policy trained on portfolio structure. That pipeline assumed circuit-level caching (Pandora/Cabaliser), GPU-accelerated transpilation, and MPI-distributed scheduling across 640 nodes — a system whose performance would ultimately depend on how well the underlying hardware cache hierarchy serves each computational kernel.

During early implementation, it became clear that the cache interaction layer — the part of the pipeline where memory layout decisions meet loop traversal patterns — needed empirical grounding before building higher-level components on top of it. Finance kernels like QMCI path-loading, GARCH volatility estimation, and Monte Carlo payoff accumulation all reduce, at their computational core, to dense linear algebra operations (matrix multiplies, Cholesky factorizations, covariance updates) whose performance is governed by the same layout-order-cache dynamics. Without measuring those dynamics on the actual target hardware, any claims about pipeline throughput would rest on assumptions rather than data.

The project therefore pivoted to a controlled, measurement-first study: characterize how memory layout and loop nesting order jointly affect L1 data cache misses and throughput for naive dense matrix multiplication on Big Red 200, using PAPI hardware counters as the instrument. This is not a retreat from the original vision but a deliberate narrowing to produce the foundational layer that the full pipeline requires.

---

## 2. What the experiment measures and why it matters for finance

### Kernel and variants

The kernel is a single-precision matrix multiply $C \mathrel{+}= AB$ compiled into twelve binaries: six loop permutations $(ijk, ikj, jik, jki, kij, kji)$ crossed with two storage layouts (row-major and column-major). Each binary is submitted via Slurm on Big Red 200 across a sweep of square matrix sizes ($N = 10$ through $5000$).

### PAPI instrumentation and cache tracking

PAPI (Performance Application Programming Interface) exposes hardware performance counters on the AMD EPYC 7713 processors in Big Red 200. We wrap only the **multiply region** with `PAPI_hl_region_begin` / `PAPI_hl_region_end`, excluding allocation and initialization, so that reported **L1 data cache misses** (`PAPI_L1_DCM`) and elapsed time reflect the compute kernel alone. GFLOPS is derived from $2N^3$ floating-point operations divided by wall-clock seconds in that region.

This setup isolates the cache mechanism at the first level of the memory hierarchy: every time the processor requests data that is not in L1, a miss is counted. By holding the arithmetic work constant ($2N^3$ operations for every run at a given $N$) and varying only layout and loop order, we attribute differences in miss count and throughput directly to how the traversal pattern interacts with cache line fetching, spatial locality, and temporal reuse.

### Connection to finance computation

The dense matrix multiply is not an arbitrary benchmark — it is the computational primitive underlying the finance models in the original proposal:

- **Quantum Monte Carlo Integration (QMCI):** Path-loading circuits encode correlated asset paths as matrix operations on amplitude registers. The classical pre-processing that generates and partitions these circuits performs repeated dense linear algebra whose cache behavior determines compilation throughput.
- **Monte Carlo simulation (classical baseline):** Generating correlated paths for a portfolio of $d$ assets requires Cholesky decomposition of a $d \times d$ covariance matrix and repeated matrix-vector products per timestep — both reducible to GEMM-class operations.
- **GARCH and stochastic volatility models:** Estimating time-varying volatility (e.g. GARCH(1,1) calibration via maximum likelihood) involves repeated covariance matrix updates and inversions over rolling windows. At portfolio scale ($d$ assets, $T$ timesteps), these become dense matrix operations whose layout-order sensitivity matches what we measure.
- **Portfolio-aware circuit caching:** The AI-driven cache policy in the original proposal must decide what to store and evict. The cost of a cache miss at the hardware level — which our experiment quantifies — is the same mechanism that makes software-level circuit cache misses expensive: a missed lookup forces a full transpilation pass whose latency depends on how well the underlying GEMM and graph operations use hardware caches.

In short, the PAPI-measured L1 miss penalty we observe (25% more misses causing 38% throughput loss at $N=5000$) propagates upward through every layer of the proposed pipeline.

---

## 3. Compromises and adaptations

| Original plan | What was adapted | Reason |
|---------------|-----------------|--------|
| Full OpenMP + MPI + CUDA pipeline | Single-threaded PAPI measurement | Isolate cache effects without threading noise; parallelism is a later layer |
| AI-driven cache eviction policy | Hardware cache characterization via PAPI | Must quantify the cost of a miss before training a policy to avoid misses |
| Quantum circuit caching (Pandora/Cabaliser) | Dense matrix multiply as proxy kernel | GEMM is the computational core shared by QMCI, Monte Carlo, and GARCH — results transfer |
| 640-node scaling study | Single-node sweep over $N$ | Cache behavior is a per-core phenomenon; scaling adds communication, not cache insight |
| Finance-specific portfolio benchmarks | Square matrix size sweep ($N = 10$–$5000$) | Establishes the layout-order interaction before specializing to portfolio-shaped matrices |
| L1 through LLC and DRAM counters | L1 data misses only | PAPI high-level API on the platform; extending to L2/LLC is identified as next step |

These are scope reductions, not abandonments. Each adaptation preserves the research question (does layout-order pairing affect cache-sensitive throughput?) while making the measurement tractable within the semester.

---

## 4. Results obtained so far

- **Small $N$ ($\leq 100$):** All six loop orders produce identical L1 miss counts (22 at $N=10$; 17,642 at $N=100$) and identical GFLOPS across both layouts — consistent with trivial cache residency and/or compiler-level loop interchange.
- **Large $N = 5000$:** Row-major `ikj` reaches 6.12 GFLOPS with $\sim 1.19 \times 10^{10}$ L1 misses; `kij` reaches 4.45 GFLOPS with $\sim 1.58 \times 10^{10}$ misses. Column-major `jki` vs `kji` mirrors these numbers. The faster order in each layout runs 38% higher throughput with 25% fewer L1 misses.
- **Mid-range:** Non-monotonic GFLOPS and order-of-magnitude L1 separations at $N=500$ confirm cache-boundary effects.
- **Key finding:** Layout and loop order interact and must be co-optimized — a result directly applicable to finance kernels where data layout is often fixed by a portfolio data model while computational traversal is dictated by the numerical method.

---

## 5. Remaining work and path back to the full pipeline

| Step | Description | Status |
|------|-------------|--------|
| Hardware documentation | CPU model, compiler flags, Slurm config for reproducibility | Todo |
| Replicated runs | Median/spread for statistical confidence | Optional next |
| L2/LLC counters | Extend PAPI to deeper cache levels | Planned extension |
| Tiled/blocked GEMM | Contrast naive vs optimized to show tiling recovers throughput | Planned extension |
| OpenMP parallelism | Multi-threaded GEMM to study shared-cache contention | Future |
| Finance kernel specialization | Apply findings to GARCH covariance update and Monte Carlo path generation | Future |
| Circuit-level caching | Use cache cost model from this study to inform AI eviction policy | Returns to original proposal |

---

## 6. References

1. Herman, D. et al. (2023). Quantum computing for finance. arXiv:2307.11230.
2. Yi, H. et al. (2026). Quantum speedups for derivative pricing. arXiv:2602.03725.
3. Akhalwaya, I. et al. (2023). A modular engine for quantum Monte Carlo integration. arXiv:2308.06081.
4. Mohseni, M. et al. (2025). How to build a quantum supercomputer. arXiv:2411.10406v2.
5. Moflic, I. et al. (2025). Quantum circuit caches and compressors. arXiv:2507.20677v1.
6. Weaver, V. et al. (2012). PAPI: Cross-platform interface to hardware performance counters.
7. Williams, S., Waterman, A., Patterson, D. (2009). Roofline: an insightful visual performance model.
