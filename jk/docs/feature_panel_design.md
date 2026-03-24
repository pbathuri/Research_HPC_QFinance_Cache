# Feature panel design (Phase 2 — CRSP-backed)

## Dependency on Phase 1

Feature panels are built on the **aligned institutional backbone**:

- Panel grain: **`permno` × `date`** (CRSP `dsf` / `msf`-shaped long tables).
- **Event tags** should come from Phase 1 outputs (manifest path + tag columns merged on `permno` + date), not ad-hoc string symbols.
- **Rates** attach via the same calendar date (`rates_data.align_rates_to_daily_universe`).

If Phase 1 is skipped, panels are still computable for teaching, but **identifiers and event metadata are not institutionally sealed** — avoid that for production cache/workload papers.

## Canonical modules

| Module | Responsibility |
|--------|----------------|
| `feature_panel.py` | `build_daily_feature_panel`, `attach_event_tags_to_feature_panel`, `attach_rates_context_to_feature_panel`, `compute_condensed_feature_panel`, `build_feature_panel_with_observability`, `manifest_from_build_dict`, `register_feature_panel` |
| `feature_panel_compare.py` | Four-variant comparison bundle (event-aware/non-event-aware × raw/condensed), primary CSV/JSON exports, secondary markdown/plot summaries |

## Initial feature set

Implemented (or delegated to `alpha_features` / simple groupbys):

- Momentum (lookback return)
- Rolling volatility (annualized from daily returns)
- Drawdown vs rolling window high
- Moving-average spread (fast − slow)
- Rolling z-score of returns
- Downside volatility (negatives only)
- Volume z-score (optional if `volume` present)
- Stress regime flag (`stress_high_vol` vs trailing median vol)
- **Event-tag columns** — supplied via Phase 1 merge (not invented here)

## Condensation

`compute_condensed_feature_panel` runs **PCA** when `sklearn` is available; otherwise it **passthrough**s the engineered columns (feature count after = before).

## Observability

- `record_spine_pipeline_observation` with `workload_spine_id=feature_panel`, feature dimensions before/after condensation, row counts, join width (column count proxy).

## Quantum / HPC later

Condensed panels reduce feature-space dimension for similarity / circuit-mapping studies while preserving interpretable tags for workload stratification.

---

*Alignment doc: `docs/event_alignment_design.md`.*
