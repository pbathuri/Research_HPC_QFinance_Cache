# Data source setup

This project’s **real-data phase** uses three **priority-ordered** sources. Only **Databento** can be fully exercised with an API key alone; TAQ-style windows and CRSP Treasury require **local files** you obtain separately.

## Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `DATABENTO_API_KEY` | For live Databento pulls | API key from [Databento](https://databento.com/) (never commit). |
| `QHPC_DATA_ROOT` | Optional | Root directory for pipeline data (default: `data/qhpc_data` under `jk/`). |
| `QHPC_DATABENTO_DAILY_DATASET` | Optional | Databento dataset id for daily OHLCV (default: `EQUS.MINI` — sample US equities; upgrade per your subscription). |
| `QHPC_DATABENTO_SCHEMA` | Optional | Bar schema (default: `ohlcv-1d`). |
| `QHPC_TAQ_ROOT` | Optional | Directory containing TAQ-style flat files for event-window ingestion (flat-file fallback). |
| `QHPC_KDB_TAQ_REPO` | Optional | Root of local **kdb-taq** checkout (defaults try `~/desktop/kdb-taq` and `~/Desktop/kdb-taq`). |
| `QHPC_KDB_EXTRACTION_COMMAND` | Optional | Shell template with `{spec_file}` and `{repo}` to run your q export script. |
| `QHPC_KDB_EXTRACTION_SCRIPT` | Optional | Relative path inside kdb-taq to a `.q` file (if not using command template). |
| `QHPC_KDB_Q_BINARY` | Optional | Path to `q` if not on `PATH`. |
| `QHPC_PREFER_KDB_TAQ` | Optional | Set `0` to skip kdb-first extraction and use flat files only. |
| `QHPC_CRSP_TREASURY_PATH` | Optional | File or directory of CRSP/WRDS-exported Treasury yields. |
| `QHPC_UNIVERSE_SYMBOLS_FILE` | Optional | Newline-separated symbols to override the built-in default universe. |
| `QHPC_PIPELINE_TIME_BUDGET_SEC` | Optional | Wall-clock budget for ingestion orchestration (default: `6480` ≈ 90% of 2 h). |
| `QHPC_PIPELINE_DISK_BUDGET_BYTES` | Optional | Soft cap for **new** bytes under `QHPC_DATA_ROOT` during a run (default: 45 GB). |

## Provider setup — Databento (priority 1)

1. Create a Databento account and generate an API key.
2. `export DATABENTO_API_KEY='...'` in your shell (or use a secrets manager and inject at runtime).
3. Install pipeline extras: `pip install -e ".[data-pipeline]"` from `jk/`.
4. Confirm access with `python3 scripts/check_data_env.py`.

**Note:** The broadest US equity/ETF history available to **you** depends on your **dataset entitlements**. The code defaults to `EQUS.MINI` for reproducibility on sample data; production breadth requires a dataset your account can query (set `QHPC_DATABENTO_DAILY_DATASET` accordingly).

## Provider setup — NYSE TAQ (priority 2): kdb-taq + flat fallback

There is **no** vendor TAQ **HTTP API** in this repo.

**Preferred path (local lab):** use your **kdb-taq** workspace and **q/kdb** to slice NYSE Daily TAQ into event windows. Python calls `taq_kdb_adapter.run_q_event_window_extraction`, which writes a JSON spec and invokes `q` (see `tools/kdb_bridge/README.md`). Outputs land as CSV, then move through the same **registry + Parquet/CSV** path as other layers.

**Fallback path:** place normalized CSV/Parquet under `QHPC_TAQ_ROOT`; `NyseTaqFileProvider` parses windows without q.

If neither kdb export succeeds nor flat files match, event windows remain **pending** in the manifest.

Supported flat layouts: `docs/manual_setup_steps.md`.

## Provider setup — CRSP Treasury (priority 3)

- If you have CRSP or WRDS access, export Treasury yields to CSV (see `docs/manual_setup_steps.md`).
- Point `QHPC_CRSP_TREASURY_PATH` at the file or folder.

If unavailable, the rates layer uses a **documented constant fallback** (`rates_data.build_flat_rate_fallback`) — explicitly **not** equivalent to CRSP.

## Optional vs required

| Component | Required for demo script to “do everything” | Required for minimal run |
|-----------|-----------------------------------------------|---------------------------|
| Databento API key | No (demo degrades to synthetic **tiny** panel + clear messages) | No |
| TAQ local files | No | No |
| CRSP Treasury files | No | No |
| `pip install -e ".[data-pipeline]"` | Yes, for Parquet + Databento + pandas | Recommended |

## Links and acquisition notes

- **Databento**: [https://databento.com/](https://databento.com/) — documentation for datasets, schemas, and Python client.
- **TAQ**: Typically via academic/commercial license; AWS hosts some historical market data products — confirm license before use.
- **CRSP / WRDS**: [https://wrds-www.wharton.upenn.edu/](https://wrds-www.wharton.upenn.edu/) — Treasury series often via CRSP or FRED exports used in place of CRSP when allowed.

See also: `docs/rates_layer_strategy.md`, `docs/high_risk_event_book_workflow.md`, `docs/broad_universe_design.md`.
