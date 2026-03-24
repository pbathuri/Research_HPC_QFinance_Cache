# WRDS active integration

## Role in the stack

WRDS / CRSP is an **institutional** layer on top of:

- **Databento** — broad daily OHLCV universe pulls (`data_ingestion.py`); use **CRSP `stocknames`** as the canonical equity master and Databento as operational enrichment where needed.
- **kdb-taq** — local NYSE TAQ extraction (`taq_kdb_adapter.py`); use **TAQ↔CRSP link tables** below to connect windows to **PERMNO** for event-window analytics and cache/workload studies.

All WRDS pulls should:

1. Write artifacts under ``$QHPC_DATA_ROOT/wrds/<registry_key>/``
2. Register rows via ``data_registry.register_dataset`` (see ``wrds_registry.register_wrds_dataset``)
3. Record **exact** ``wrds_source_table``, row count, date range, identifier coverage, and role (**canonical** / **enrichment** / **optional**) in registry + sidecar JSON (never passwords)

## Authentication

- Set ``WRDS_USERNAME`` in the environment.
- Use WRDS-documented password storage (e.g. ``.pgpass``) — **do not** commit secrets.
- ``check_wrds_connection()`` validates without printing credentials.

## Canonical modules

| Module | Responsibility |
|--------|----------------|
| ``wrds_provider.py`` | Connection, ``run_wrds_sql_query``, **canonical loaders** (exact tables) |
| ``wrds_queries.py`` | Roadmap slots, SQL helpers, **verified** ``schema.table`` constants |
| ``wrds_registry.py`` | ``save_wrds_dataset``, ``register_wrds_dataset``, ``infer_wrds_identifier_coverage`` |

## Verified canonical tables (active)

### 1. Rates / Treasury

| Loader | Table |
|--------|--------|
| ``load_crsp_treasury_daily`` | **crsp.tfz_dly** |
| ``load_crsp_treasury_monthly`` | **crsp.tfz_mth** |

Do **not** use ``crsp.treasuries`` or deprecated placeholder Treasury names.

### 2. Security master / stock backbone

| Loader | Table |
|--------|--------|
| ``load_crsp_security_master`` | **crsp.stocknames** |
| ``load_crsp_daily_stock_panel`` | **crsp.dsf** |
| ``load_crsp_monthly_stock_panel`` | **crsp.msf** |

### 3. Stock events

| Loader | Table |
|--------|--------|
| ``load_crsp_daily_stock_events`` | **crsp.dse** |
| ``load_crsp_monthly_stock_events`` | **crsp.mse** |

Legacy ``load_crsp_stock_events`` tries **dse** then **mse**.

### 4. TAQ ↔ CRSP linking

| Loader | Table |
|--------|--------|
| ``load_taq_crsp_link_daily`` | **wrdsapps_link_crsp_taq.tclink** |
| ``load_taq_crsp_link_millisecond`` | **wrdsapps_link_crsp_taqm.taqmclink** |
| ``load_taq_crsp_link_cusip_map`` | **wrdsapps_link_crsp_taqm.taqmclink_cusip_2010** |

Legacy ``load_taq_crsp_links`` returns the first non-empty of the three (prefer explicit loaders for research).

## Priority datasets (locked WRDS order; matches ``wrds_queries.WRDS_INTEGRATION_ROADMAP``)

1. **Treasury** — ``load_crsp_treasury_daily`` / ``load_crsp_treasury_monthly``
2. **Stock master + panels + events** — ``load_crsp_security_master``, ``load_crsp_*_stock_panel``, ``load_crsp_*_stock_events``
3. **TAQ links** — ``load_taq_crsp_link_*``
4. **CRSP / Compustat merged** — ``load_crsp_compustat_merged`` (candidates in ``wrds_queries``)
5. **Fama-French & liquidity** — ``load_wrds_factor_data``
6. **WRDS intraday indicators** — extend when tables are fixed for your subscription
7. **Event study / Eventus** — ``load_event_study_if_available``

**Secondary rates (not tier 1):** ``load_frb_rates_if_available``; file + flat fallbacks in ``rates_data.load_risk_free_rate_series_priority``.

## Registry fields (WRDS)

``DatasetRegistryEntry`` includes:

- ``wrds_source_table`` — e.g. ``crsp.tfz_dly``
- ``wrds_dataset_role`` — ``canonical`` | ``enrichment`` | ``optional`` (also reflected in ``dataset_kind``: ``wrds_canonical``, etc.)
- ``symbol_coverage`` — populated from ``infer_wrds_identifier_coverage`` when registering pulls (e.g. ``permno,cusip``)

## Examples

```python
from qhpc_cache.wrds_provider import check_wrds_connection, load_crsp_treasury_daily

ok, msg, db = check_wrds_connection()
if ok:
    df, meta = load_crsp_treasury_daily(db, limit=10_000)
    print(meta["wrds_source_table"], len(df) if df is not None else 0)
```

```python
from qhpc_cache.wrds_registry import pull_and_register_crsp_treasury

pull_and_register_crsp_treasury()
```

---

*Legacy roadmap shim: ``wrds_placeholder.py`` — prefer ``wrds_queries.WRDS_INTEGRATION_ROADMAP``.*
