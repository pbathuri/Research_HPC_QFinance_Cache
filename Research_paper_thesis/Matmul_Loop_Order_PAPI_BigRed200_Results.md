# Effect of Loop Nesting Order and Memory Layout on Cache Misses and Throughput in Naive Dense Matrix Multiplication on Big Red 200

**Authors:** Pradyot Bathuri, IUB Undergraduate Student
**Date:** April 2026  
**Data and code:** `bigred200_results/results.csv`, `mm_papi.c` (Indiana University Big Red 200)

---

## Abstract

Dense matrix multiplication implemented as a single triply nested loop remains a standard vehicle for studying how memory access patterns interact with processor caches. We present an empirical study on **Big Red 200** in which we fix a naive single-precision general matrix multiply (GEMM) kernel and vary only **(i)** row-major versus column-major storage layouts and **(ii)** all six permutations of the loop indices \((i,j,k)\). We instrument the multiply region with **PAPI** to record **L1 data cache misses** and derive **GFLOPS** from wall-clock time. For small problem sizes, loop order and layout produce **indistinguishable** L1 miss counts and timings, consistent with a small working set and strong compiler optimization. For large \(N\), performance and L1 misses **diverge strongly**: under **row-major** storage, the **`ikj`** order achieves the highest throughput at \(N=5000\) (approximately **6.12 GFLOPS**) with about **\(1.19\times10^{10}\)** L1D misses, while **`kij`** reaches about **4.45 GFLOPS** and **\(1.58\times10^{10}\)** misses. Under **column-major** storage at the same size, **`jki`** leads (approximately **6.12 GFLOPS**, **\(1.19\times10^{10}\)** misses) versus **`kji`** (approximately **4.48 GFLOPS**, **\(1.58\times10^{10}\)** misses). These pairs exhibit a **consistent** relationship: the faster variant incurs roughly **25% fewer** L1 data misses than the slower one at \(N=5000\). We discuss non-monotonic throughput versus \(N\), the limits of L1-only metrics, and natural extensions including tiling, additional cache levels, and roofline analysis.

**Keywords:** matrix multiplication, loop interchange, cache misses, PAPI, HPC, memory layout, Big Red 200

---

## 1. Introduction

The performance of floating-point kernels on modern CPUs is often limited not by arithmetic throughput but by **memory hierarchy** behavior. For matrix multiplication \(C \leftarrow C + AB\), the order of the three loops determines **reuse** of elements of \(A\), \(B\), and \(C\) in registers and caches, while **storage layout** (row-major vs. column-major) determines **stride** when a given index advances. Textbook guidance often recommends a particular order for row-major layouts (e.g. maximizing contiguous access in the innermost loop), but that guidance is typically stated for **large** problems and often assumes **blocked** implementations.

This work asks a narrower, measurement-driven question: **For a deliberately naive, unblocked GEMM in single precision, how do layout and loop permutation jointly affect L1 data misses and observed GFLOPS on a production university cluster?** We answer it using controlled batch jobs on **Big Red 200**, separate compilations per \((\text{layout}, \text{order})\), and a sweep over matrix dimension \(N\) for square matrices.

**Contributions:**

1. A full **\(2 \times 6 \times |N|\)** experimental matrix with consistent PAPI timing methodology.
2. Quantitative **large-\(N\)** comparison showing **layout-dependent** “winning” orders and a clear **L1 miss vs. throughput** relationship for head-to-head pairs at \(N=5000\).
3. Documentation of **small-\(N\) degeneracy** (identical metrics across all six orders at \(N=100\)), motivating discussion of compiler effects and measurement scale.

---

## 2. Background

### 2.1 Loop orders and reuse

For \(C_{ij} = \sum_k A_{ik} B_{kj}\), each permutation of \((i,j,k)\) fixes which index advances in the innermost loop. The innermost stride is critical for **spatial locality** on caches; outer loops determine **temporal reuse** of rows, columns, or blocks of \(A\), \(B\), and \(C\).

### 2.2 Row-major vs. column-major indexing

In **row-major** layout, increasing the last index moves to consecutive addresses. In **column-major** layout, the stride along a row of a matrix may be large. The **same** loop nest text therefore implies **different** memory access patterns depending on layout.

### 2.3 PAPI and L1 data misses

The **Performance API (PAPI)** exposes hardware counters. We report **PAPI_L1_DCM** (or equivalent L1 data miss events as configured for the platform) inside a high-level region bracketing only the **multiply** loop nest, excluding allocation and initialization.

---

## 3. Methodology

### 3.1 Platform

Experiments were run on **Indiana University Big Red 200** under the **Slurm** scheduler. Jobs execute user-compiled binaries; exact node type, compiler version, and CPU model should be inserted from job logs or system documentation for reproducibility.

### 3.2 Kernel and variants

The kernel is a standard triple loop implementing \(C \mathrel{+}= AB\) with **single-precision (`float`)** operands. Matrices are **dense** and **square** with dimension \(N\) (arguments \(M=N=K\)).

- **Layouts:** `ROW_MAJOR` and `COL_MAJOR` are implemented via C preprocessor macros that define index mappings \(A(i,k)\), \(B(k,j)\), \(C(i,j)\).
- **Orders:** Exactly one of `ORDER_IJK`, `ORDER_IKJ`, `ORDER_JIK`, `ORDER_JKI`, `ORDER_KIJ`, `ORDER_KJI` is defined at compile time, yielding six separate binaries per layout.

Initialization (random fill) is placed **outside** the PAPI-timed **multiply** region.

### 3.3 Metrics

- **L1 misses:** Total L1 data misses in the multiply region (as reported by PAPI for the run).
- **GFLOPS:** For \(N\times N\) multiply, we use \(2N^3\) floating-point operations (one multiply-add per inner update) divided by elapsed **seconds** in the multiply region.
- **Sweep:** \(N\) spans multiple values from small (e.g. 10) through 5000, enabling plots of GFLOPS vs. \(N\) and bar charts at selected \(N\).

### 3.4 Limitations

- **Single-threaded** naive code does not represent optimized BLAS; it isolates loop/layout effects.
- **L1 only** does not capture last-level cache or DRAM traffic, which may dominate at large \(N\).
- **Compiler optimization** (`-O3`, vectorization, loop interchange by the compiler) may reduce differences between nominally distinct source orders at small \(N\); we treat observed identity of metrics as a **result**, not noise.

---

## 4. Results

### 4.1 Small \(N\): degenerate behavior

At **\(N=10\)**, L1 data misses are **approximately 22** for every loop order under both layouts—differences in loop order are immaterial when the working set fits easily in cache and compulsory misses dominate.

At **\(N=100\)**, the CSV records **identical** `gflops`, `l1_miss`, and `seconds` to full floating-point precision **across all six loop orders** for both **row-major** and **column-major**. For example, each order reports **17642** L1 misses and **2.7895 GFLOPS** with the same elapsed time. This indicates that, at this scale, either **(a)** the optimizer produces equivalent code for all six compilation units, or **(b)** the effective memory access pattern converges so that counter totals match. In either case, **loop order cannot be distinguished by these metrics at \(N=100\)**.

### 4.2 Throughput vs. \(N\) (GFLOPS)

Plots of **GFLOPS vs. \(N\)** (separate figures for **rm** and **cm**) show:

- **High variability** at small and medium \(N\), including local peaks and sharp drops as \(N\) increases—consistent with crossing cache capacity boundaries, TLB effects, and alignment.
- **Layout-dependent leadership:** Under **row-major**, orders such as **`ikj`** and **`kij`** dominate at large \(N\) in the figure; under **column-major**, **`jki`** and **`kji`** extend to the largest \(N\) with the highest sustained GFLOPS among the plotted curves.

The **best order at \(N=1000\)** is not the same as at \(N=5000\)**for every series**, illustrating that **no single permutation is optimal across the full range** of \(N\) for naive code.

### 4.3 L1 misses at intermediate \(N\)

Where bar charts include all six orders (e.g. **\(N=500\)** under row-major), four orders cluster at high L1D miss counts while **`kij`** and **`kji`** show **substantially lower** L1D misses—an **order-of-magnitude** separation in the plotted data. This supports the interpretation that **inner-loop stride and reuse** have become decisive once \(N\) is large enough that the working set stresses the L1 cache.

### 4.4 Large \(N=5000\): paired comparison

At **\(N=5000\)**, the experimental log contains complete multiply-region results for the following head-to-head pairs (single run per configuration as recorded):

| Layout | Order A | GFLOPS | L1D misses | Seconds | Order B | GFLOPS | L1D misses | Seconds |
|--------|---------|--------|------------|---------|---------|--------|------------|---------|
| **rm** | **ikj** | 6.121 | \(1.1886\times10^{10}\) | 40.845 | **kij** | 4.449 | \(1.5762\times10^{10}\) | 56.198 |
| **cm** | **jki** | 6.119 | \(1.1887\times10^{10}\) | 40.858 | **kji** | 4.482 | \(1.5772\times10^{10}\) | 55.781 |

**Observations:**

1. **Throughput:** In both layouts, **Order A** achieves about **37% higher GFLOPS** than **Order B** (ratio \(\approx 6.12 / 4.45\)).
2. **L1 misses:** **Order A** incurs about **25% fewer** L1 data misses than **Order B** (\(\approx 1.19/1.58\)).
3. **Time:** Wall-clock time in the multiply region is shorter for **Order A** by a similar margin to GFLOPS (fewer operations are not being counted—the same \(2N^3\) work is done; faster time reflects better memory behavior and pipeline utilization).

The **near symmetry** of GFLOPS and L1 totals between **(rm: ikj/kij)** and **(cm: jki/kji)** at \(N=5000\) suggests a deep duality: the roles of indices relative to layout differ, but the **qualitative** ranking (one order strongly preferred) persists.

---

## 5. Discussion

### 5.1 Layout–order interaction

The study confirms that **storage layout and loop order must be analyzed together**. An order that is favorable under row-major is not automatically favorable under column-major at large \(N\); the measured winners at \(N=5000\) (**`ikj`** vs **`kij`** for rm; **`jki`** vs **`kji`** for cm) align with how each nest touches strides in \(A\), \(B\), and \(C\) for that layout.

### 5.2 Why L1 misses and GFLOPS move together—but only partly

At \(N=5000\), lower L1D misses coincide with higher GFLOPS for the compared pairs. However, **total** work is identical in floating-point operations; the kernel is **memory-bound** in the naive form, so reducing misses in the first-level cache is plausibly correlated with better overall behavior, yet **L2/LLC/DRAM** events could still differ between orders. Extending instrumentation to **last-level cache misses** would strengthen causal claims.

### 5.3 Compiler and small-\(N\) identity

The **bitwise-identical** results across six orders at \(N=100\) warrant either disassembly or compilation with optimization disabled for a **sanity** variant, to separate “optimizer unified the loops” from “source differences remain but counters match.” Regardless, reporting this fact honestly strengthens the paper: **not every \(N\)** is informative for comparing loop orders.

### 5.4 Non-monotonic GFLOPS vs. \(N\)**

The “cliffs” and recoveries in GFLOPS as \(N\) increases are expected for naive matmul without tiling. They should be discussed as **hierarchy effects** rather than anomalies; optional **cache-size estimates** (per-matrix footprint in bytes) can be related to L1/L2 sizes for the target CPU.

---

## 6. Conclusion and future work

We presented a Slurm-driven experimental campaign measuring **L1 data misses** and **GFLOPS** for naive single-precision matrix multiplication on **Big Red 200** across **two layouts** and **six loop permutations** over a wide range of \(N\). At small \(N\), metrics collapse across orders; at **\(N=5000\)**, we observe **large, consistent gaps** between paired orders, with the faster order showing **~25% fewer L1D misses** and **~37% higher GFLOPS** in the logged data.

**Future work:** (1) **Tiled/blocking** GEMM with the same instrumentation to show recovery toward hardware peak. (2) **Roofline** plots for operational intensity vs. achieved GFLOPS. (3) **L2 and LLC** counters or **perf**/**LIKWID** on the same kernels. (4) **Multiple runs** with median and confidence intervals. (5) **Double precision** and **OpenMP** scaling once the single-core story is complete.

---

## Acknowledgments

Compute time on **Indiana University Big Red 200** and support from [lab/course/advisor] are gratefully acknowledged. [Fill in.]

---

## References

1. J. Dongarra et al., “An updated set of basic linear algebra subprograms (BLAS),” *ACM Trans. Math. Softw.*, 2002.  
2. D. S. Wise, “Ahnentafel indexing into Hilbert curves,” *ACM Trans. Math. Softw.*, 2000. (Background on layout and locality—adjust to your course readings.)  
3. V. Weaver et al., “PAPI: Cross-platform interface to hardware performance counters,” *Tools for High Performance Computing*, Springer, 2012.  
4. S. Williams, A. Waterman, D. Patterson, “Roofline: an insightful visual performance model for multicore architectures,” *Communications of the ACM*, 2009.  
5. Intel Corporation, *Intel® 64 and IA-32 Architectures Optimization Reference Manual* (cache hierarchy, prefetching—cite edition used).

---

## Appendix A: Data availability

Primary results are available in comma-separated form as **`results.csv`** with columns:

`layout, order, N, gflops, l1_miss, seconds`

Source for the instrumented kernel is provided as **`mm_papi.c`**.

---

## Appendix B: Placeholder checklist for camera-ready revision

- [ ] Insert **exact** Big Red 200 node model, CPU SKU, base/turbo frequency, L1/L2/L3 sizes.  
- [ ] Insert **compiler command line** (e.g. `module load`, `gcc`/`icx` version, flags).  
- [ ] Insert **Slurm** script excerpt (`#SBATCH`, cores, binding).  
- [ ] Replace bracketed author/affiliation and acknowledgments.  
- [ ] Add **figures** (embed exported PNGs from `bigred200_results/`) with captions cross-referencing section 4.  
- [ ] Run **statistical repeats** if required by venue.
