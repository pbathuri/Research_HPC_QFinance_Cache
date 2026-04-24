<div align="center">

# Research_HPC_QFinance_Cache

**Research thread on cache behaviour in quantitative finance workflows — working notes, experiments, and feeder pipelines for the published studies.**

<br/>

<img src="https://img.shields.io/badge/Type-research%20notebook-0D1117?style=for-the-badge&labelColor=161B22&color=FFA657" />
<img src="https://img.shields.io/badge/Focus-HPC%20%C2%B7%20quant%20finance-0D1117?style=for-the-badge&labelColor=161B22&color=58A6FF" />
<img src="https://img.shields.io/badge/Counters-PAPI-0D1117?style=for-the-badge&labelColor=161B22&color=FFA657" />
<img src="https://img.shields.io/badge/Institution-Indiana%20University-0D1117?style=for-the-badge&labelColor=161B22&color=8B949E" />

</div>

---

## What this is

The working notebook behind my research on **cache-aware numerical methods for quantitative finance**. This is the messy upstream — experiments, rough benchmarks, architecture notes, reading lists — that feeds the polished downstream publications.

If you want the clean, published version of one line of this research, see [**finance-cache-hpc**](https://github.com/pbathuri/finance-cache-hpc) — the L1 cache characterisation study of Cholesky, Monte Carlo, GARCH and GEMM on AMD EPYC.

---

## Research questions I'm chasing

```mermaid
mindmap
  root((cache +<br/>quant))
    L1 characterisation
      Cholesky layout effects
      MC path dimensionality
      GARCH recurrence
      GEMM baseline
    Phase transitions
      L1 → L2 thresholds
      portfolio-dim cliffs
      associativity effects
    Heuristic caches
      workload-aware prefetch
      replacement policy tuning
    Cross-microarch
      EPYC Zen 2 vs 3
      Sapphire Rapids
      Apple Silicon
```

---

## How it connects

```mermaid
flowchart LR
    R[This repo<br/>Research_HPC_QFinance_Cache] -->|distils| F[finance-cache-hpc<br/>L1 study · EPYC · PAPI]
    R -->|distils| Q[QuantumMCL-Spring26 🔒<br/>heuristic cache mechanisms]
    R -->|reading list| QM[Quantitative-Modeling_Practice<br/>Wilmott-style exercises]
```

---

## Related public work

- [**finance-cache-hpc**](https://github.com/pbathuri/finance-cache-hpc) — published empirical L1 study
- [**Quantitative-Modeling_Practice**](https://github.com/pbathuri/Quantitative-Modeling_Practice) — modelling exercises that feed the kernel selection

## Related private work

- **QuantumMCL-Spring26** — heuristic cache mechanisms for finance workflows (available on request)

---

## Citing the downstream paper

```bibtex
@misc{bathuri2026cache,
  author       = {Pradyot Bathuri},
  title        = {Cache-Aware Computation for Quantitative Finance Workloads on {AMD} {EPYC}},
  year         = {2026},
  institution  = {Indiana University Bloomington},
  howpublished = {\url{https://github.com/pbathuri/finance-cache-hpc}}
}
```

---

<div align="center">
<sub>Graduate research at <b>Indiana University · Luddy School</b> · <a href="https://github.com/pbathuri">@pbathuri</a></sub>
</div>
