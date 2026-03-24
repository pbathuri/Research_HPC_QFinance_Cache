"""Historical data providers: Databento, local TAQ files, optional CRSP Treasury files."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from qhpc_cache.data_models import DailyUniverseRequest, EventWindowRequest, RatesDataRequest

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None  # type: ignore


def _trading_days_approx(start: date, end: date) -> int:
    """Rough business-day count (lower bound for sizing)."""
    if end < start:
        return 0
    days = (end - start).days + 1
    return max(1, int(days * 5 / 7))


class BaseHistoricalDataProvider(ABC):
    """Abstract provider for historical pulls."""

    name: str = "base"

    @abstractmethod
    def describe(self) -> str:
        raise NotImplementedError


class DatabentoProvider(BaseHistoricalDataProvider):
    """Databento Historical API for daily OHLCV and definition (reference) data."""

    name = "databento"

    def __init__(
        self,
        *,
        dataset_id: Optional[str] = None,
        schema_daily: str = "ohlcv-1d",
        stype_in: str = "raw_symbol",
    ) -> None:
        self.dataset_id = dataset_id or os.environ.get("QHPC_DATABENTO_DAILY_DATASET", "EQUS.MINI")
        self.schema_daily = os.environ.get("QHPC_DATABENTO_SCHEMA", schema_daily)
        self.stype_in = stype_in

    def describe(self) -> str:
        return f"Databento dataset={self.dataset_id!r} schema={self.schema_daily!r}"

    @staticmethod
    def api_key_present() -> bool:
        return bool(os.environ.get("DATABENTO_API_KEY", "").strip())

    def _client(self) -> Any:
        try:
            import databento as db  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Install the Databento client: pip install -e '.[data-pipeline]'"
            ) from exc
        key = os.environ.get("DATABENTO_API_KEY", "").strip()
        if not key:
            raise RuntimeError("DATABENTO_API_KEY is not set; export it before downloading.")
        return db.Historical(key=key)

    @staticmethod
    def estimate_request_scope(
        symbols: Sequence[str],
        start: date,
        end: date,
        *,
        bytes_per_row_estimate: int = 96,
    ) -> Dict[str, Any]:
        """Heuristic row count, disk, and wall-clock estimates before a full pull."""
        symbol_count = len(symbols)
        day_count = _trading_days_approx(start, end)
        row_count = symbol_count * day_count
        disk_bytes = row_count * bytes_per_row_estimate
        seconds_per_thousand_rows = 2.5
        runtime_seconds = max(30.0, (row_count / 1000.0) * seconds_per_thousand_rows)
        return {
            "symbol_count": symbol_count,
            "approx_trading_days": day_count,
            "estimated_row_count": row_count,
            "estimated_disk_bytes": disk_bytes,
            "estimated_runtime_seconds": runtime_seconds,
        }

    def verify_api_connectivity(self) -> Dict[str, Any]:
        """Quick connectivity probe: authenticate and list a small metadata call."""
        if not self.api_key_present():
            return {"ok": False, "error": "DATABENTO_API_KEY not set"}
        try:
            client = self._client()
            meta = client.metadata.list_datasets()
            return {"ok": True, "datasets_available": len(meta) if meta else 0}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    @staticmethod
    def validate_databento_response(frame: "pd.DataFrame", *, min_rows: int = 0) -> bool:
        if pd is None or frame is None:
            return False
        if len(frame) < min_rows:
            return min_rows == 0 and len(frame) == 0
        return True

    def fetch_daily_ohlcv_data(
        self,
        request: DailyUniverseRequest,
        batch_symbols: Sequence[str],
    ) -> "pd.DataFrame":
        """Download one symbol batch; caller persists and registers."""
        if pd is None:
            raise RuntimeError("pandas required; pip install -e '.[data-pipeline]'")
        client = self._client()
        start = request.start_date.isoformat()
        end = request.end_date.isoformat()
        data = client.timeseries.get_range(
            dataset=self.dataset_id,
            symbols=list(batch_symbols),
            schema=self.schema_daily,
            start=start,
            end=end,
            stype_in=self.stype_in,
        )
        frame = data.to_df()
        if not isinstance(frame, pd.DataFrame):
            raise RuntimeError("Unexpected Databento response: expected DataFrame.")
        return frame

    def fetch_reference_data(
        self,
        request: DailyUniverseRequest,
        batch_symbols: Sequence[str],
    ) -> "pd.DataFrame":
        """Fetch definition-style metadata for symbols (best-effort)."""
        if pd is None:
            raise RuntimeError("pandas required; pip install -e '.[data-pipeline]'")
        client = self._client()
        start = request.start_date.isoformat()
        end = request.end_date.isoformat()
        try:
            data = client.timeseries.get_range(
                dataset=self.dataset_id,
                symbols=list(batch_symbols),
                schema="definition",
                start=start,
                end=end,
                stype_in=self.stype_in,
            )
            frame = data.to_df()
        except Exception:
            return pd.DataFrame()
        if not isinstance(frame, pd.DataFrame):
            return pd.DataFrame()
        return frame


class NyseTaqFileProvider(BaseHistoricalDataProvider):
    """Local TAQ-style flat files only (no live API)."""

    name = "nyse_taq_files"

    def describe(self) -> str:
        return "Local TAQ-style CSV/Parquet ingestion"

    @staticmethod
    def discover_available_taq_files(root: Union[str, Path]) -> List[Path]:
        root_path = Path(root)
        if not root_path.is_dir():
            return []
        patterns = ("*.csv", "*.parquet", "*.txt")
        found: List[Path] = []
        for pattern in patterns:
            found.extend(sorted(root_path.rglob(pattern)))
        return found

    @staticmethod
    def _detect_time_column(frame: "pd.DataFrame") -> str:
        candidates = (
            "timestamp",
            "ts_event",
            "datetime",
            "time",
            "date_time",
            "DateTime",
        )
        lower_map = {column.lower(): column for column in frame.columns}
        for candidate in candidates:
            if candidate.lower() in lower_map:
                return lower_map[candidate.lower()]
        raise ValueError(f"No time column found; columns={list(frame.columns)}")

    @staticmethod
    def _detect_symbol_column(frame: "pd.DataFrame") -> Optional[str]:
        candidates = ("symbol", "ticker", "sym_root", "root", "SYM_ROOT")
        lower_map = {column.lower(): column for column in frame.columns}
        for candidate in candidates:
            if candidate.lower() in lower_map:
                return lower_map[candidate.lower()]
        return None

    def load_taq_window(
        self,
        path: Union[str, Path],
        *,
        chunksize: Optional[int] = 250_000,
    ) -> "pd.DataFrame":
        """Load a single file; uses chunked CSV reads when ``chunksize`` is set."""
        if pd is None:
            raise RuntimeError("pandas required; pip install -e '.[data-pipeline]'")
        path = Path(path)
        if path.suffix.lower() == ".parquet":
            return pd.read_parquet(path)
        if chunksize:
            parts: List[pd.DataFrame] = []
            for chunk in pd.read_csv(path, chunksize=chunksize):
                parts.append(chunk)
            if not parts:
                return pd.DataFrame()
            return pd.concat(parts, ignore_index=True)
        return pd.read_csv(path)

    def extract_event_window(
        self,
        frame: "pd.DataFrame",
        request: EventWindowRequest,
    ) -> "pd.DataFrame":
        """Filter to ``[start, end]`` and symbols."""
        time_column = self._detect_time_column(frame)
        time_series = pd.to_datetime(frame[time_column], utc=True, errors="coerce")

        def to_utc(moment: datetime) -> "pd.Timestamp":
            stamp = pd.Timestamp(moment)
            if stamp.tzinfo is None:
                return stamp.tz_localize(timezone.utc)
            return stamp.tz_convert(timezone.utc)

        start_utc = to_utc(request.start_timestamp)
        end_utc = to_utc(request.end_timestamp)
        mask = (time_series >= start_utc) & (time_series <= end_utc)
        filtered = frame.loc[mask].copy()
        filtered[time_column] = time_series[mask]
        symbol_column = self._detect_symbol_column(filtered)
        if symbol_column and request.symbols:
            sym_set = {symbol.strip().upper() for symbol in request.symbols}
            filtered[symbol_column] = filtered[symbol_column].astype(str).str.upper()
            filtered = filtered[filtered[symbol_column].isin(sym_set)]
        return filtered

    def validate_taq_window(self, frame: "pd.DataFrame", request: EventWindowRequest) -> Tuple[bool, str]:
        if pd is None or frame is None:
            return False, "empty_or_no_pandas"
        if len(frame) == 0:
            return False, "zero_rows"
        try:
            self._detect_time_column(frame)
        except ValueError as exc:
            return False, str(exc)
        return True, "ok"


class CrspTreasuryFileProvider(BaseHistoricalDataProvider):
    """Optional Treasury yields from local CRSP/WRDS-style CSV."""

    name = "crsp_treasury_file"

    def describe(self) -> str:
        return "CRSP/WRDS-exported Treasury CSV (optional)"

    def load_treasury_rates(
        self,
        request: RatesDataRequest,
    ) -> "pd.DataFrame":
        if pd is None:
            raise RuntimeError("pandas required; pip install -e '.[data-pipeline]'")
        path = Path(request.local_input_path)
        if path.is_dir():
            csv_files = sorted(path.glob("*.csv"))
            if not csv_files:
                raise FileNotFoundError(f"No CSV files under {path}")
            path = csv_files[0]
        if not path.is_file():
            raise FileNotFoundError(f"Treasury file not found: {path}")
        frame = pd.read_csv(path)
        return frame

    @staticmethod
    def validate_treasury_dataset(frame: "pd.DataFrame") -> Tuple[bool, str]:
        if pd is None or frame is None or len(frame) == 0:
            return False, "empty"
        return True, "ok"

    def build_risk_free_rate_series(
        self,
        frame: "pd.DataFrame",
        *,
        date_column_guess: Optional[str] = None,
        rate_column_guess: Optional[str] = None,
    ) -> "pd.DataFrame":
        """Return two-column DataFrame: date, risk_free_rate (decimal per year)."""
        if pd is None:
            raise RuntimeError("pandas required")
        date_candidates = ("date", "DATE", "caldt", "time_period", "Date")
        rate_candidates = ("yield", "yld", "tbill", "rf", "rate", "YIELD", "RF")
        lower_map = {column.lower(): column for column in frame.columns}
        date_column = date_column_guess
        if date_column is None:
            for candidate in date_candidates:
                key = candidate.lower()
                if key in lower_map:
                    date_column = lower_map[key]
                    break
        rate_column = rate_column_guess
        if rate_column is None:
            for candidate in rate_candidates:
                key = candidate.lower()
                if key in lower_map:
                    rate_column = lower_map[key]
                    break
        if date_column is None or rate_column is None:
            raise ValueError(
                "Could not infer date/yield columns; set metadata or rename columns. "
                f"Have: {list(frame.columns)}"
            )
        out = pd.DataFrame(
            {
                "date": pd.to_datetime(frame[date_column], utc=False).dt.date.astype(str),
                "risk_free_rate": pd.to_numeric(frame[rate_column], errors="coerce"),
            }
        )
        out = out.dropna()
        if out["risk_free_rate"].max() and out["risk_free_rate"].max() > 1.0:
            out["risk_free_rate"] = out["risk_free_rate"] / 100.0
        return out
