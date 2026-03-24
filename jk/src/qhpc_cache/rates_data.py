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
    tier: str = "fallback"  # institutional | secondary | file_institutional | fallback


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
            tier="file_institutional",
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
        tier="fallback",
    )
    return frame, summary


def _normalize_wrds_treasury_frame(raw: "pd.DataFrame") -> "pd.DataFrame":
    """Best-effort: map CRSP/WRDS Treasury-like columns to date + risk_free_rate."""
    if pd is None or raw is None or len(raw) == 0:
        raise ValueError("invalid frame")
    df = raw.copy()
    date_col = None
    for c in ("date", "caldt", "time_avail_m", "yyyymm", "mcaldt"):
        if c in df.columns:
            date_col = c
            break
    if date_col is None:
        date_col = df.columns[0]
    rate_col = None
    for c in ("tmyield", "yield", "risk_free_rate", "rf", "tbill_yield", "rate"):
        if c in df.columns:
            rate_col = c
            break
    if rate_col is None:
        num = [c for c in df.columns if df[c].dtype.kind in "fiu"]
        rate_col = num[1] if len(num) > 1 else num[0]
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df[date_col], errors="coerce").dt.strftime("%Y-%m-%d"),
            "risk_free_rate": pd.to_numeric(df[rate_col], errors="coerce"),
            "source": "wrds_crsp_treasury_candidate",
        }
    )
    return out.dropna(subset=["date", "risk_free_rate"])


def load_risk_free_rate_series_priority(
    *,
    calendar_dates: Sequence[str],
    crsp_path: Optional[str] = None,
    fallback_annual_rate: float = 0.03,
    try_wrds: bool = True,
    wrds_username: Optional[str] = None,
    wrds_treasury_limit: int = 100_000,
) -> Tuple["pd.DataFrame", RatesSourceSummary]:
    """Load risk-free series with explicit priority (see ``docs/rates_source_priority.md``).

    Order when ``try_wrds`` is True:
      1. WRDS ``crsp.tfz_dly`` (institutional daily)
      2. WRDS ``crsp.tfz_mth`` (institutional monthly)
      3. WRDS FRB candidates (secondary)
      4. Local CRSP file via ``crsp_path`` or env
      5. Flat fallback
    """
    import os
    from pathlib import Path

    if pd is None:
        raise RuntimeError("pandas required")

    path_arg = crsp_path or os.environ.get("QHPC_CRSP_TREASURY_PATH", "")

    if try_wrds:
        try:
            from qhpc_cache.wrds_provider import (
                check_wrds_connection,
                load_crsp_treasury_daily,
                load_crsp_treasury_monthly,
                load_frb_rates_if_available,
            )

            ok, _, db = check_wrds_connection(wrds_username=wrds_username)
            if ok and db is not None:
                for loader, label in (
                    (load_crsp_treasury_daily, "wrds_crsp_tfz_dly"),
                    (load_crsp_treasury_monthly, "wrds_crsp_tfz_mth"),
                ):
                    df, meta = loader(db, limit=wrds_treasury_limit)
                    if df is not None and len(df) > 0:
                        try:
                            series = _normalize_wrds_treasury_frame(df)
                            if len(series) > 0:
                                tbl = meta.get("wrds_source_table", f'{meta.get("schema")}.{meta.get("table")}')
                                return series, RatesSourceSummary(
                                    source_label=label,
                                    is_fallback=False,
                                    row_count=len(series),
                                    date_start=str(series["date"].iloc[0]),
                                    date_end=str(series["date"].iloc[-1]),
                                    notes=f"WRDS canonical table {tbl}; verify yield units in CRSP docs.",
                                    tier="institutional",
                                )
                        except Exception:
                            pass  # noqa: S110 — try next tier

                df2, meta2 = load_frb_rates_if_available(db)
                if df2 is not None and len(df2) > 0:
                    try:
                        series2 = _normalize_wrds_treasury_frame(df2)
                        if len(series2) > 0:
                            return series2, RatesSourceSummary(
                                source_label="wrds_frb_rates",
                                is_fallback=False,
                                row_count=len(series2),
                                date_start=str(series2["date"].iloc[0]),
                                date_end=str(series2["date"].iloc[-1]),
                                notes=f"WRDS FRB candidate schema={meta2.get('schema')} table={meta2.get('table')}.",
                                tier="secondary",
                            )
                    except Exception:
                        pass
        except Exception:
            pass  # noqa: S110 — WRDS optional

    return load_pluggable_risk_free_rate_series(
        crsp_path=path_arg if path_arg and Path(path_arg).exists() else None,
        calendar_dates=calendar_dates,
        fallback_annual_rate=fallback_annual_rate,
    )


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
        "tier": summary.tier,
    }
