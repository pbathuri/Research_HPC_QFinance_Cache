# Event Set Library (Canonical A-E)

This document defines the canonical event-library layer for event-window comparison and workload-signature research.

Owner module: `src/qhpc_cache/event_set_library.py`

## Locked event sets

The first five sets are fixed:

- `set_a_covid_crash` (Set A): COVID crash
- `set_b_march_2020_liquidity` (Set B): March 2020 liquidity stress
- `set_c_2022_rate_shock` (Set C): 2022 rate shock
- `set_d_2023_banking_stress` (Set D): 2023 banking stress
- `set_e_broad_institutional_stress_library` (Set E): curated mixed institutional stress library

Set E is deliberately balanced, with explicit category labels:

- `crisis / regime stress`
- `macro / rates`
- `banking / credit stress`
- `liquidity dislocation`
- `earnings shock`
- `commodity / inflation shock`

It is not intended to be a random grab-bag.

## Set E ruleset + manual review

This phase upgrades Set E from a small placeholder set to a ruleset-generated mixed institutional stress library targeting **~35-40** events.

Current ruleset targets:

- `crisis / regime stress`: 9
- `macro / rates`: 11
- `banking / credit stress`: 6
- `liquidity dislocation`: 5
- `earnings shock`: 4
- `commodity / inflation shock`: 4

Total target = **39**.

Design intent:

- Slight overweight toward `macro / rates` and `crisis / regime stress`.
- Explicit category balancing for interpretability.
- Reserve candidates are kept in code but not selected under current ruleset.

Manual review is surfaced in-code via:

- `set_e_manual_review_summary()`

and exported into `event_set_manifest.json` under:

- `set_e_ruleset_targets`
- `set_e_manual_review`

Planned extension note:

- A later comparison-phase extension should add an equity-desk-style library with a higher earnings-shock share.

## Locked window policy

Canonical default multi-day subset:

- `d-1_to_d+1`
- `d-5_to_d+5`
- `d-10_to_d+10`
- `d-20_to_d+20`

Intraday extensions (optional):

- `full_day`
- `centered_2h_stress`
- `first_trading_hour`
- `last_trading_hour`

## Event definition schema

Each event member includes:

- `event_id`
- `event_label`
- `category_label`
- `anchor_start` / `anchor_end`
- `default_window_family_labels`
- `notes`

## Canonical API

- `canonical_event_set_library()`: returns locked set definitions.
- `flatten_event_library_rows()`: tabular flattening for comparison and exports.
- `locked_window_policy_manifest()`: window policy manifest.
- `build_event_set_manifest()`: manifest payload.
- `export_event_set_manifest(path)`: JSON manifest export.
- `set_e_manual_review_summary()`: category composition checks for Set E.

## Manifest output

The event library can be exported to JSON for reproducibility:

```python
from qhpc_cache.event_set_library import export_event_set_manifest

export_event_set_manifest("outputs/event_library/event_set_manifest.json")
```
