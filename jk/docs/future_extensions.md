# Future extensions (not implemented here)

This file lists **directions** consistent with the research narrative but intentionally out of scope for the current prototype.

## Quantum execution

- Integrate **Qiskit**, **Cirq**, or **Q#** behind a narrow adapter that consumes `QuantumCircuitRequest` and `QuantumResourceEstimate`.
- Prototype **amplitude estimation** on a toy payoff after state preparation is defined.

## Similarity and ML

- Replace hand-tuned weights in `circuit_similarity.py` with **validated** models, while keeping explainability (e.g. SHAP on tabular features).
- Train `AIAssistedCachePolicy` on logged decisions and outcomes; keep **fallback** to heuristics.

## Models beyond GBM

- **Stochastic volatility** or **jump** models for `market_models.py` and matching semi-analytic bridges.

## HPC / distributed execution

- **No** MPI/CUDA/Slurm in this repo by design. A future fork might add batch runners that **export** scenarios and results without changing core pricing APIs.

## Data and calibration

- Optional **pandas** pipelines for historical calibration (if added, isolate behind `integrations/` and keep core list-based for teaching).

## Formal methods

- Optional **Lean** notebooks external to this repo for formalizing discrete pricing statements — not wired into runtime.

## Compression and circuit caches

- Store **compressed** circuit representations in `CircuitCacheEntry.compiled_representation_placeholder` with versioning and migration notes.
