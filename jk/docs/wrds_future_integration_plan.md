# WRDS / CRSP future integration plan

## Current rule

The pipeline **runs without WRDS**. Treasury/rates use local CSV (``QHPC_CRSP_TREASURY_PATH``) when present, or an explicit **constant fallback** labeled in ``rates_data``.

## Placeholder code

- ``qhpc_cache.wrds_placeholder`` defines ``WrdsIntegrationState`` and an ordered **roadmap** of dataset slots (no network calls).
- Demo writes ``outputs/data_ingestion_event_book/wrds_future_state.json``.

## Priority order (when access is active)

1. CRSP Treasury / Index Treasury and Inflation  
2. TAQ CRSP Link / Daily TAQ CRSP Link  
3. CRSP Stock — security files and corporate events  
4. CRSP / Compustat merged  
5. Fama–French and liquidity-style factors  
6. WRDS intraday indicators  
7. Event study / Eventus tooling  

## Integration sketch (future PRs)

1. Add ``wrds_connection.py`` (or vendor SDK) **outside** ``qhpc_cache`` core optional imports, mirroring ``data-pipeline`` extras.
2. Map each roadmap slot to a **registry** ``dataset_kind`` and deterministic paths under ``QHPC_DATA_ROOT``.
3. Reuse ``data_registry.py`` checkpoint pattern for long downloads.
4. Never imply WRDS data is live until ``WrdsIntegrationState.access_status`` moves to ``active`` with audit notes.

## Research honesty

Until WRDS is connected, cite **Databento + local kdb-taq** as the operational data path in methods sections; mention WRDS only as **planned enrichment**.
