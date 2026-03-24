# Event alignment design (Phase 1 — CRSP + TAQ)

## Why this phase is first (locked)

Research requires **institutionally clean identifiers** before large-scale feature work:

1. **Reproducible event windows** — same `event_identifier`, timestamps, and symbol set must reconstruct the same normalized artifact.
2. **TAQ → CRSP PERMNO** — intraday microstructure lives in TAQ space; CRSP panels, events, and risk live in **PERMNO** space. Mixing without alignment biases cache and workload studies.
3. **Event metadata before features** — `dse` / `mse` flags and `stocknames` attributes should attach **before** momentum/volatility features so event-tag features are meaningful.

Therefore **event alignment precedes** the CRSP-backed feature panel pipeline (Phase 2).

## Canonical sources (WRDS)

| Role | Table |
|------|--------|
| Security master | `crsp.stocknames` |
| Daily events | `crsp.dse` |
| Monthly events | `crsp.mse` |
| TAQ↔CRSP daily link | `wrdsapps_link_crsp_taq.tclink` |
| TAQ↔CRSP ms link | `wrdsapps_link_crsp_taqm.taqmclink` |
| CUSIP-oriented map | `wrdsapps_link_crsp_taqm.taqmclink_cusip_2010` |

## Local TAQ extraction (kdb/q)

- Default repo resolution: `taq_kdb_adapter.default_kdb_taq_repo()` (e.g. `QHPC_KDB_TAQ_REPO`, `/Users/prady/Desktop/kdb-taq`).
- Extraction: `run_q_event_window_extraction` → CSV → pandas.
- **No** second parallel extraction framework: `event_book.extract_event_windows_from_taq` remains the **catalog batch** path; **aligned** end-to-end runs should prefer `taq_event_pipeline.run_aligned_event_pipeline` when WRDS + kdb are available.

## Module map

| Module | Responsibility |
|--------|----------------|
| `event_alignment.py` | Symbol normalization, PERMNO alignment, stocknames + dse/mse joins, `build_normalized_event_window` |
| `taq_event_pipeline.py` | `extract_local_taq_event_window`, `run_aligned_event_pipeline`, `register_aligned_event_window` (orchestration + disk + manifest + registry) |

## Determinism & quality metadata

- **Deterministic label:** `event_alignment.deterministic_event_label` — hash of event id, ISO window bounds, **sorted** symbols.
- **Match tracking:** `qhpc_link_source`, `qhpc_link_confidence` (1.0 primary tables, 0.85 CUSIP map tier).
- **Symbol roots:** `normalize_taq_symbol_root` strips common share-class suffixes (e.g. `.B`); refine per venue if your TAQ feed differs.
- **Manifest:** `EventAlignmentManifest` JSON sidecar next to normalized Parquet/CSV.

## Observability

- `cache_workload_mapping.record_spine_pipeline_observation` writes **`spine_pipeline_observations.csv`** with `workload_spine_id=event_window`, row counts, join width, match rate, window length.

## Relation to feature panels

Phase 2 consumes **paths or tag tables** derived here (`alignment_manifest_ref`, merged `permno` + calendar date keys). Do not build wide feature panels on raw TAQ symbols alone when CRSP integration is available.

---

*Spine: `docs/core_research_spine.md`.*
