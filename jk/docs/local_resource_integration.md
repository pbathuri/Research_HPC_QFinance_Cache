# Local Resource Integration

## Detection and Fallback Strategy

Every external resource is probed at runtime.  Missing resources trigger graceful
degradation, not hard failure.

| Resource | Detection | Fallback |
|----------|-----------|----------|
| Databento API | `DATABENTO_API_KEY` env var | Synthetic GBM daily panel |
| kdb+ / q | `shutil.which("q")` | Skip TAQ extraction; synthetic intraday |
| kdb-taq repo | `QHPC_KDB_TAQ_REPO` path check | Report unavailable in summary |
| Pixel Agents | Path existence check | JSONL export only (no live integration) |
| WRDS / CRSP | `WRDS_USERNAME` env var | Explicit flat-rate fallback in rates_data.py |
| pandas / pyarrow | import check | CSV-only storage path |
| seaborn | import check | matplotlib-only plotting |
| langchain / langgraph | import check | Internal state machine (orchestrator.py) |
| cupy (CUDA) | import check | CPU-local backend |
| mpi4py (MPI) | import check | CPU-local backend |

## Environment Variables

See `.env.example` for the full list.  Key variables:

| Variable | Required | Purpose |
|----------|----------|---------|
| `DATABENTO_API_KEY` | For live data | Daily OHLCV ingestion |
| `QHPC_KDB_TAQ_REPO` | For TAQ | Local kdb-taq checkout path |
| `QHPC_KDB_Q_BINARY` | For TAQ | Override q executable path |
| `QHPC_PIXEL_AGENTS_REPO` | Optional | Pixel Agents repo for cross-reference |
| `QHPC_DATA_ROOT` | Optional | Default: `data/qhpc_data` |
| `QHPC_OUTPUT_ROOT` | Optional | Default: `outputs` |
| `QHPC_METRICS_DIR` | Optional | Default: `outputs/metrics` |

## Validation Commands

```bash
PYTHONPATH=src python3 scripts/check_env.py              # Quick report
PYTHONPATH=src python3 scripts/validate_local_resources.py  # Deep probe + JSON
PYTHONPATH=src python3 scripts/bootstrap_local_workspace.py # Create directories
```
