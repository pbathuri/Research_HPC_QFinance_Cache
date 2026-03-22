"""Pluggable risk-free rate series: CRSP/WRDS file preferred; explicit fallback."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Optional, Sequence, Tuple

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None  # type: ignore


@dataclass
class RatesSourceSummary:
    """Human-readable description of which rates path was used."""

    source_label: str
    is_fallback: bool
    row_count: int
    date_start: str
    date_end: str
    notes: str


def build_flat_rate_fallback(
    *,
    annual_rate: float,
    calendar_dates: Sequence[str],
    label: str = "flat_fallback",
) -> "pd.DataFrame":
    """Constant annualized rate (decimal, e.g. 0.04 for 4%). **Not** CRSP."""
    if pd is None:
        raise RuntimeError("pandas required; pip install -e '.[data-pipeline]'")
    return pd.DataFrame(
        {
            "date": list(calendar_dates),
            "risk_free_rate": [float(annual_rate)] * len(calendar_dates),
            "source": [label] * len(calendar_dates),
        }
    )


def load_pluggable_risk_free_rate_series(
    *,
    crsp_path: Optional[str],
    calendar_dates: Sequence[str],
    fallback_annual_rate: float = 0.03,
) -> Tuple["pd.DataFrame", RatesSourceSummary]:
    """Load Treasury series from file if present; else flat fallback (explicitly labeled)."""
    if pd is None:
        raise RuntimeError("pandas required")
    from pathlib import Path

    from qhpc_cache.data_models import RatesDataRequest
    from qhpc_cache.data_sources import CrspTreasuryFileProvider

    if crsp_path and Path(crsp_path).exists() and calendar_dates:
        request = RatesDataRequest(
            source_name="crsp_treasury_file",
            start_date=date.fromisoformat(str(calendar_dates[0])[:10]),
            end_date=date.fromisoformat(str(calendar_dates[-1])[:10]),
            local_input_path=crsp_path,
            use_if_available=True,
        )
        provider = CrspTreasuryFileProvider()
        raw = provider.load_treasury_rates(request)
        series = provider.build_risk_free_rate_series(raw)
        summary = RatesSourceSummary(
            source_label="crsp_treasury_file",
            is_fallback=False,
            row_count=len(series),
            date_start=str(series["date"].iloc[0]) if len(series) else "",
            date_end=str(series["date"].iloc[-1]) if len(series) else "",
            notes="Loaded from local CRSP/WRDS-style file; verify units in metadata.",
        )
        return series, summary

    frame = build_flat_rate_fallback(
        annual_rate=fallback_annual_rate,
        calendar_dates=calendar_dates,
        label="flat_fallback_not_crsp",
    )
    summary = RatesSourceSummary(
        source_label="flat_fallback_not_crsp",
        is_fallback=True,
        row_count=len(frame),
        date_start=str(calendar_dates[0]) if calendar_dates else "",
        date_end=str(calendar_dates[-1]) if calendar_dates else "",
        notes="No CRSP file at QHPC_CRSP_TREASURY_PATH — using constant rate for teaching only.",
    )
    return frame, summary


def align_rates_to_daily_universe(
    rates_frame: "pd.DataFrame",
    daily_frame: "pd.DataFrame",
    *,
    date_column_daily: str = "date",
    date_column_rates: str = "date",
) -> "pd.DataFrame":
    """Left-merge rates onto daily OHLCV panel by calendar date."""
    if pd is None:
        raise RuntimeError("pandas required")
    daily = daily_frame.copy()
    rates = rates_frame.copy()
    daily["date_key"] = pd.to_datetime(daily[date_column_daily], errors="coerce").dt.normalize()
    rates["date_key"] = pd.to_datetime(rates[date_column_rates], errors="coerce").dt.normalize()
    rate_cols = ["date_key", "risk_free_rate"]
    if "source" in rates.columns:
        rate_cols.append("source")
    merged = daily.merge(rates[rate_cols], on="date_key", how="left")
    merged.drop(columns=["date_key"], inplace=True)
    return merged


def summarize_rates_source(summary: RatesSourceSummary) -> Dict[str, Any]:
    return {
        "source_label": summary.source_label,
        "is_fallback": summary.is_fallback,
        "row_count": summary.row_count,
        "date_start": summary.date_start,
        "date_end": summary.date_end,
        "notes": summary.notes,
    }
