# Rates source priority

The research codebase distinguishes **tiers** of risk-free / Treasury context. The **canonical institutional** path on WRDS is fixed to CRSP zero-coupon Treasury files.

## 1. Institutional-grade (primary) — WRDS CRSP

**Order inside WRDS (``rates_data.load_risk_free_rate_series_priority`` when ``try_wrds=True``):**

1. **``crsp.tfz_dly``** — daily Treasury / discounting context (`wrds_provider.load_crsp_treasury_daily`)
2. **``crsp.tfz_mth``** — monthly if daily is empty (`wrds_provider.load_crsp_treasury_monthly`)

Requires:

- ``WRDS_USERNAME`` set and ``wrds`` package connects  
- **Do not** use ``crsp.treasuries`` or legacy placeholder Treasury table names.

``RatesSourceSummary.source_label`` will be ``wrds_crsp_tfz_dly`` or ``wrds_crsp_tfz_mth`` with ``tier="institutional"``.

## 2. Secondary institutional

- **Federal Reserve Board** (WRDS-hosted FRB extracts) when available: ``load_frb_rates_if_available`` in ``wrds_provider.py``
- Labeled with ``tier="secondary"``.

## 3. Explicit fallback

- **Local file** — ``QHPC_CRSP_TREASURY_PATH`` / ``crsp_path`` via ``CrspTreasuryFileProvider`` (institutional *only if* the file is a verified export)
- **Flat constant rate** — teaching-only; **must** be ``flat_fallback_not_crsp`` and ``is_fallback=True``

## Implementation

Single entry: ``rates_data.load_risk_free_rate_series_priority(...)`` tries, in order:

1. WRDS **tfz_dly**
2. WRDS **tfz_mth**
3. WRDS FRB candidates
4. Local CRSP file
5. Flat fallback

Optional: ``wrds_treasury_limit`` caps rows pulled from WRDS (default 100k).

Pass ``try_wrds=False`` to skip live WRDS and use file/fallback only.

## Mathematical honesty

- Never label flat synthetic series as CRSP.
- When WRDS is unreachable, record the tier actually used in summary metadata and registry notes.

---

*Code: ``rates_data.py``, ``wrds_queries.CANONICAL_CRSP_TFZ_DLY`` / ``CANONICAL_CRSP_TFZ_MTH``.*
