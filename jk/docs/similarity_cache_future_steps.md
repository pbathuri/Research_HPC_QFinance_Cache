# Similarity Cache Status and Future Steps

This prototype now has two distinct layers:

- active pricing path (`MonteCarloPricer.price_option`): exact-match cache only
- explicit replay experiment path: threshold-gated similarity reuse

## What is active now

- Exact-match key-based reuse in `SimpleCacheStore`.
- Policy-gated decision stubs in `cache_policy.py`.
- Replay-level similarity experiment:
  - `run_similarity_cache_replay_experiment(...)`
  - reports exact hits, similarity hits, misses, runtimes, and error vs no-cache
  - supports fail-loud quality gating (`fail_on_low_similarity_quality=True`)
  - emits execution-evidence status fields and valid-evidence filtering metadata

## What is future work (still not wired in active pricing flow)

- Near-match key neighborhoods
- Similarity threshold selection
- Similarity-aware cache admission/routing
- Integrating near-match routing directly inside `MonteCarloPricer.price_option`
- Similarity admission policies that combine score + estimated error bounds
- Adaptive threshold tuning from observed replay error distributions

## Minimal next-step schema (for next implementation step)

Candidate fields for future near-match experiments:

- `instrument_type`
- `S0`, `K`, `r`, `sigma`, `T`
- `num_paths`
- normalized distance metrics (e.g., strike distance, maturity distance, vol distance)
- expected reuse confidence
- realized absolute error from replay validation

## No-hallucination note

This document does **not** claim similarity caching is implemented in the active
Monte Carlo pricing path. Current similarity logic exists in experiment replay
only and is explicitly labeled as such in outputs/manifests.
