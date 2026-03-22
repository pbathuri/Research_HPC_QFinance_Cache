"""High-level analytics across daily universe and event book."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from qhpc_cache.data_registry import load_dataset_registry
from qhpc_cache.event_book import EventBookSummary, summarize_event_book
from qhpc_cache.historical_returns import (
    align_return_panel,
    compute_cross_sectional_summary,
    compute_log_returns,
    compute_rolling_volatility,
)
from qhpc_cache.historical_risk import summarize_historical_risk
from qhpc_cache.data_storage import load_saved_dataset

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None  # type: ignore


def normalize_ohlcv_panel(frame: "pd.DataFrame") -> "pd.DataFrame":
    """Map common Databento-style columns to teaching schema ``date,symbol,close,...``."""
    if pd is None:
        raise RuntimeError("pandas required")
    out = frame.copy()
    if "date" not in out.columns and "ts_event" in out.columns:
        out["date"] = pd.to_datetime(out["ts_event"], utc=True, errors="coerce").dt.date.astype(str)
    if "symbol" not in out.columns:
        for candidate in ("raw_symbol", "symbol", "ticker"):
            if candidate in out.columns:
                out["symbol"] = out[candidate].astype(str)
                break
    if "close" not in out.columns and "Close" in out.columns:
        out["close"] = out["Close"]
    return out


def analyze_large_universe_daily_layer(
    data_root: str,
    *,
    max_rows_per_file: Optional[int] = None,
) -> Dict[str, Any]:
    """Load daily OHLCV registry entries and compute summaries (chunk-friendly)."""
    if pd is None:
        raise RuntimeError("pandas required")
    entries = load_dataset_registry(data_root)
    daily_paths: List[str] = []
    for entry in entries:
        if entry.dataset_kind == "daily_ohlcv":
            daily_paths.extend(entry.local_paths)
    if not daily_paths:
        return {"status": "no_daily_data", "summary": {}}

    frames = []
    for path_str in daily_paths:
        path = Path(path_str)
        if not path.exists():
            continue
        chunk = load_saved_dataset(path)
        if max_rows_per_file is not None:
            chunk = chunk.head(max_rows_per_file)
        frames.append(chunk)
    if not frames:
        return {"status": "no_files", "summary": {}}

    panel = pd.concat(frames, ignore_index=True)
    panel = normalize_ohlcv_panel(panel)
    if "close" not in panel.columns or "symbol" not in panel.columns:
        return {"status": "missing_columns", "columns": list(panel.columns)}
    returns = compute_log_returns(panel)
    wide = align_return_panel(returns)
    vol_21 = compute_rolling_volatility(wide, 21)
    cross = compute_cross_sectional_summary(wide)
    risk = summarize_historical_risk(wide)
    return {
        "status": "ok",
        "row_count": len(panel),
        "symbol_count": panel["symbol"].nunique() if "symbol" in panel.columns else None,
        "cross_section_latest": cross,
        "rolling_vol_shape": list(vol_21.shape),
        "historical_risk_keys": list(risk["per_symbol"].keys())[:20],
        "risk_summary_truncated": len(risk["per_symbol"]) > 20,
    }


def analyze_event_book(summary: EventBookSummary) -> Dict[str, Any]:
    """Summarize completed event book entries."""
    return summarize_event_book(summary)


def compare_event_windows(
    summaries: List[Dict[str, Any]],
    *,
    metric_key: str = "total_rows",
) -> Dict[str, Any]:
    """Lightweight comparison dict for multiple window summaries."""
    ranked = sorted(summaries, key=lambda row: row.get(metric_key, 0), reverse=True)
    return {"metric_key": metric_key, "ranked": ranked}


def summarize_universe_stress_behavior(
    daily_analysis: Dict[str, Any],
    event_analysis: Dict[str, Any],
) -> Dict[str, Any]:
    """Narrative-style bundle for reports."""
    return {
        "daily_layer": daily_analysis,
        "event_book": event_analysis,
        "note": "Stress library complements broad panel; interpret placeholders as catalog-only until TAQ ingested.",
    }
