"""Default US equity/ETF universe construction and deterministic batching."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import List, Sequence

from qhpc_cache.data_models import DailyUniverseRequest

DEFAULT_QUANT_RESEARCH_UNIVERSE_NAME = "us_equity_etf_quant_default_v1"

# Liquid large-cap + major ETFs: breadth sample without claiming full market coverage.
_DEFAULT_SYMBOLS: List[str] = [
    "AAPL",
    "MSFT",
    "AMZN",
    "GOOGL",
    "META",
    "NVDA",
    "JPM",
    "V",
    "JNJ",
    "WMT",
    "PG",
    "MA",
    "UNH",
    "HD",
    "DIS",
    "BAC",
    "XOM",
    "KO",
    "PFE",
    "CSCO",
    "SPY",
    "QQQ",
    "IWM",
    "DIA",
    "VTI",
    "EFA",
    "EEM",
    "TLT",
    "GLD",
    "XLF",
    "XLE",
    "XLV",
    "XLK",
    "XLY",
    "XLP",
    "XLI",
    "XLB",
    "XLU",
    "XLRE",
    "XLC",
    "SMH",
    "ARKK",
    "IEFA",
    "AGG",
    "LQD",
    "HYG",
    "VNQ",
    "SLV",
    "USO",
    "BND",
]


def filter_symbols_for_daily_layer(symbols: Sequence[str]) -> List[str]:
    """Normalize: strip, upper, dedupe, stable sort."""
    seen = set()
    ordered: List[str] = []
    for symbol in symbols:
        normalized = symbol.strip().upper()
        if normalized and normalized not in seen:
            seen.add(normalized)
            ordered.append(normalized)
    return sorted(ordered)


def split_universe_into_batches(symbols: Sequence[str], batch_size: int) -> List[List[str]]:
    """Deterministic batches of at most ``batch_size`` symbols."""
    ordered = filter_symbols_for_daily_layer(symbols)
    if batch_size <= 0:
        raise ValueError("batch_size must be positive.")
    return [ordered[index : index + batch_size] for index in range(0, len(ordered), batch_size)]


def build_default_quant_research_universe() -> List[str]:
    """Return the built-in default symbol list (override with ``QHPC_UNIVERSE_SYMBOLS_FILE``)."""
    path = os.environ.get("QHPC_UNIVERSE_SYMBOLS_FILE", "").strip()
    if path:
        file_path = Path(path)
        if not file_path.is_file():
            raise FileNotFoundError(f"QHPC_UNIVERSE_SYMBOLS_FILE not found: {path}")
        lines = file_path.read_text(encoding="utf-8").splitlines()
        return filter_symbols_for_daily_layer(line for line in lines if line.strip() and not line.strip().startswith("#"))
    return list(_DEFAULT_SYMBOLS)


def build_large_us_equity_etf_universe_request(
    *,
    start_date: date,
    end_date: date,
    local_output_directory: str,
    include_reference_data: bool = True,
    provider_name: str = "databento",
) -> DailyUniverseRequest:
    """Build a ``DailyUniverseRequest`` for the default quant research universe."""
    symbols = build_default_quant_research_universe()
    return DailyUniverseRequest(
        universe_name=DEFAULT_QUANT_RESEARCH_UNIVERSE_NAME,
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        adjusted_prices_required=True,
        include_reference_data=include_reference_data,
        provider_name=provider_name,
        local_output_directory=local_output_directory,
        notes="Default breadth-first US equity + ETF list; expand via QHPC_UNIVERSE_SYMBOLS_FILE.",
    )


def recommend_batch_size_for_budget(
    symbols: Sequence[str],
    start: date,
    end: date,
    *,
    disk_budget_bytes: int,
    time_budget_seconds: float,
) -> int:
    """Lower batch size (more batches) when estimates exceed budgets."""
    from qhpc_cache.data_sources import DatabentoProvider

    symbol_count = len(filter_symbols_for_daily_layer(symbols))
    if symbol_count == 0:
        return 1
    scope = DatabentoProvider.estimate_request_scope(symbols, start, end)
    per_symbol_disk = scope["estimated_disk_bytes"] / max(1, symbol_count)
    per_symbol_time = scope["estimated_runtime_seconds"] / max(1, symbol_count)
    max_by_disk = max(1, int((disk_budget_bytes * 0.25) / max(1, per_symbol_disk)))
    max_by_time = max(1, int((time_budget_seconds * 0.2) / max(1, per_symbol_time)))
    return max(1, min(symbol_count, min(max_by_disk, max_by_time, 80)))
