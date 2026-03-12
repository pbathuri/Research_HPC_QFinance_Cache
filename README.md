# qhpc_cache — Monte Carlo Pricing and Cache Prototype

Undergraduate research prototype for a classical Monte Carlo option pricer with scaffolding for future quantum/hybrid workflow caching.

## Project Overview

This repository provides a small, readable codebase to:

- Price European options using a classical Monte Carlo baseline (geometric Brownian motion).
- Experiment with an optional in-memory cache and a simple AI-assisted cache policy stub.
- Prepare extension points for circuit representation, similarity-based reuse, and Fourier-based pricing (not yet implemented).

The code is kept simple and modular so it can be extended step by step.

## Current Capabilities

- **Classical Monte Carlo pricing baseline** — `MonteCarloPricer` simulates asset paths and returns an estimated option price and variance. No quantum logic; serves as a reference for future methods.
- **AI-assisted cache policy stub** — `AIAssistedCachePolicy` decides whether to reuse a cached result based on a small feature set (e.g. num_paths, volatility, maturity). Logic is lightweight and placeholder; a real system would use a trained model.
- **Optional in-memory cache** — `SimpleCacheStore` stores and retrieves results by a key built from features. The pricer can optionally use it to avoid recomputation when the policy advises reuse.
- **Future circuit representation placeholders** — Dataclasses and feature builders in `placeholders.py` and `feature_builder.py` stub future circuit fragments, metadata, and similarity-style features. They are not wired into pricing yet.
- **Fourier technique scaffold** — `fourier_placeholder.py` stubs future Fourier-based pricing (characteristic function, COS method) and a control-variate reference for Monte Carlo variance reduction. Not wired into pricing yet.

## File Structure

```
project_root/
│
├── run_demo.py
├── requirements.txt
├── README.md
│
├── src/
│   └── qhpc_cache/
│       ├── __init__.py
│       ├── config.py
│       ├── pricing.py
│       ├── cache_policy.py
│       ├── cache_store.py
│       ├── feature_builder.py
│       ├── experiment_runner.py
│       ├── placeholders.py
│       └── fourier_placeholder.py
│
└── tests/
    ├── test_pricing.py
    └── test_cache_policy.py
```

## How to Run

From the project root, with your virtual environment activated, install the package once (editable):

```bash
pip install -e .
```

Then run the demo:

```bash
python3 run_demo.py
```

This runs a two-step cache demo (first run computes, second reuses cache) and then a short repeated-pricing experiment with cache stats.

To run the test suite:

```bash
python3 -m unittest discover -s tests
```

## Future Work

Planned or possible extensions (not implemented in this prototype):

- **Exact circuit caching** — Store and reuse compiled circuit representations keyed by structure or parameters.
- **Heuristic baseline activation** — Uncomment and tune the heuristic cache policy in `cache_policy.py` as a non-AI baseline.
- **Similarity-based reuse** — Use circuit or feature similarity (e.g. via placeholders) to decide when to reuse a cached result instead of recompiling.
- **Portfolio-aware experiments** — Run experiments across multiple instruments or parameter sets and aggregate cache and pricing metrics.
- **Fourier-based pricing and variance reduction** — Implement characteristic-function or COS-method pricing in `fourier_placeholder.py`; use as analytic reference or as control variate for Monte Carlo to improve accuracy and reduce variance.
- **Integration with hybrid quantum workflows** — Connect this baseline and cache scaffold to real quantum or hybrid backends when available.

This README describes a prototype; it does not report research results or claims beyond the current codebase.
