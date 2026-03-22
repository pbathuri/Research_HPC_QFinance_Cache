# Manual setup steps (user-supplied data)

Follow these steps when the automated pipeline reports **missing local artifacts**. Paths are relative to `jk/` unless noted.

## Databento API key

1. Obtain an API key from [Databento](https://databento.com/).
2. In your shell: `export DATABENTO_API_KEY='your_key_here'`.
3. Re-run `python3 scripts/check_data_env.py`.

## Broad universe symbol list (optional)

1. Create a text file with **one ticker per line** (e.g. `AAPL`, `MSFT`).
2. `export QHPC_UNIVERSE_SYMBOLS_FILE='/absolute/path/to/symbols.txt'`.
3. Re-run the demo or ingestion orchestration.

## TAQ-style event-window files

1. Acquire licensed TAQ or vendor-normalized tick/bar files (CSV, Parquet, or pipe-delimited).
2. Create a directory, e.g. `data/taq_local/`.
3. `export QHPC_TAQ_ROOT='/absolute/path/to/taq_local'`.

**Expected patterns (flexible):**

- Filenames: `*.csv`, `*.parquet`, `*.txt`.
- **Time column** (one of): `timestamp`, `ts_event`, `datetime`, `time`, `date_time` (case-insensitive match attempted).
- **Symbol column** (one of): `symbol`, `ticker`, `sym_root`, `root`.

If your files use other names, add a note in `EventWindowRequest.notes` and extend column mapping in `NyseTaqFileProvider` (small change in `data_sources.py`).

## kdb-taq + q (preferred TAQ path)

1. Keep your **kdb-taq** checkout outside this repo (e.g. `~/desktop/kdb-taq` or `~/Desktop/kdb-taq`).
2. `export QHPC_KDB_TAQ_REPO='/absolute/path/to/kdb-taq'` if defaults do not find it.
3. Ensure `q` is on `PATH` (or `export QHPC_KDB_Q_BINARY=/path/to/q`).
4. Provide either:
   - `export QHPC_KDB_EXTRACTION_COMMAND='q {repo}/scripts/your_export.q -spec {spec_file}'` (example only), **or**
   - add `scripts/qhpc_export_window.q` in kdb-taq that reads the JSON spec and writes `output_csv` (see `tools/kdb_bridge/README.md`).

Python only orchestrates; **all TAQ table logic stays in q**.

## CRSP / WRDS Treasury export

1. Export Treasury yields to CSV (daily or monthly; see your WRDS guide).
2. Place the file at e.g. `data/crsp/treasury_yields.csv`.
3. `export QHPC_CRSP_TREASURY_PATH='/absolute/path/to/treasury_yields.csv'`.

**Minimal CSV columns (flexible names):**

- Date: `date`, `DATE`, `caldt`, `time_period`.
- Yield: `yield`, `yld`, `tbill`, `rf`, `rate` (interpreted as percent or decimal per file — document in sidecar `metadata.json` if nonstandard).

If columns differ, normalize externally or add a one-off mapping row in metadata.

## Output and data roots

- Default data root: `data/qhpc_data/` (created by `scripts/bootstrap_data_phase.py`).
- Demo outputs: `outputs/data_ingestion_event_book/`.
- Override with `QHPC_DATA_ROOT`.

## Verification

```bash
cd jk
python3 scripts/check_data_env.py
python3 scripts/bootstrap_data_phase.py
```
