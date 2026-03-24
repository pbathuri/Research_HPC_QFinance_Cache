# Prototype Stabilization Audit

This audit covers the current compact prototype modules:

- `src/qhpc_cache/pricing.py`
- `src/qhpc_cache/cache_store.py`
- `src/qhpc_cache/cache_policy.py`
- `src/qhpc_cache/feature_builder.py`
- `src/qhpc_cache/experiment_runner.py`
- `src/qhpc_cache/config.py`
- `src/qhpc_cache/placeholders.py`
- `src/qhpc_cache/fourier_placeholder.py`
- `run_demo.py`
- `tests/` (prototype-relevant subset and stabilization tests)

## Current actual capabilities

- Classical Monte Carlo pricing under GBM for:
  - `european_call`, `european_put`
  - `digital_call`, `digital_put`
  - `asian_call`, `asian_put` (path mode)
- Exact-match in-memory cache reuse via `SimpleCacheStore` using deterministic JSON keys.
- Policy-gated reuse with:
  - `HeuristicCachePolicy`
  - `LogisticCachePolicy`
  - `AIAssistedCachePolicy` (stub model hook with explicit fallback modes)
- Reproducible seeded Monte Carlo via `random_seed` in `MonteCarloPricer`.
- Lightweight timing instrumentation in pricing results:
  - total runtime
  - cache lookup time
  - simulation time
  - payoff aggregation time
  - cache put time
- Structured experiment summaries and a canonical exact-match cache experiment runner.
- Explicit similarity-cache replay experiment (`no_cache` vs `exact_cache` vs
  `similarity_cache`) with runtime and approximation-error reporting.
- Evidence-integrity status labels in structured outputs:
  - `execution_status`, `evidence_valid`, `excluded_from_summary`,
    `exclusion_reason`
- Long-run local execution support:
  - explicit `smoke`/`standard`/`heavy` scale labels
  - incremental progress JSONL artifacts
  - checkpoint-based resumability at condition/stage level
- Tiered experiment ladder for disciplined prioritization:
  - Tier 1 / Tier 2 executed by default in local sweep
  - Tier 3 / Tier 4 tracked as optional lower-priority extensions
- Circuit metadata placeholders and Fourier/COS benchmark hooks are present as extension scaffolds.

## Current non-capabilities (explicit)

- No similarity-cache implementation in the active pricing path.
- No production cache admission/routing engine.
- No PMU/x86 hardware counter instrumentation in this prototype path.
- No BigRed200 execution integration.
- No real quantum backend execution.

## Correctness bugs identified and fixed in this stabilization phase

1. **Incomplete cache key risk**
   - Previous active key used only instrument type, path count, volatility, maturity.
   - Fixed by including full pricing inputs required for exact-match correctness
     (`instrument_type`, `S0`, `K`, `r`, `sigma`, `T`, `num_paths`, plus other active flags).

2. **Double lookup pattern (`has` then `get`)**
   - Could cause unnecessary repeated key work and obscured miss accounting.
   - Fixed by adding single-lookup `try_get(...)` and using it in active experiment/pricing flow.

3. **Policy/docs fallback ambiguity**
   - Fallback behavior for `AIAssistedCachePolicy` was implicit in code path.
   - Fixed by explicit `fallback_mode` (`heuristic`, `always_reuse`, `no_reuse`) and consistent behavior.

4. **Missing timing fields for cache experiments**
   - No structured phase timing in pricing results.
   - Fixed with explicit runtime diagnostics attached to `MonteCarloPricingResult`.

5. **Insufficient cache diagnostics**
   - Basic hits/misses/entries only.
   - Extended with `put_count`, `overwrite_count`, `lookup_count`, `hit_rate`,
     `miss_rate`, per-key access counts, and `miss_after_policy_approved_count`.

## Instrumentation gaps (post-fix)

- Policy decision timing is still not tracked separately.
- No allocator/memory RSS tracking in core result structure.
- No hardware-level cache/NUMA counter support (intentionally deferred).

## Reproducibility gaps (post-fix)

- Reproducibility is deterministic for seeded pricers, but experiment-level seed
  management policy is still lightweight and manual.

## Research-readiness gaps (post-fix)

- Exact-match cache baseline is now reproducible and instrumented.
- Similarity-aware replay experiment is implemented and measurable; direct
  pricing-path similarity routing remains future work.
- PMU/HPC and QHPC relevance remain planning-level only in this prototype path.
