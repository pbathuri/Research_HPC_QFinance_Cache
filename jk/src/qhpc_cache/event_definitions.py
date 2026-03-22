"""Default prioritized event catalog (stress library, not unconstrained ingest).

Entries use UTC timestamps. ``symbols`` may be empty to mean "no symbol filter"
when extracting from local TAQ files (all symbols present in file).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from qhpc_cache.data_models import EventWindowRequest

_LIQUID_EQUITY_SUBSET = (
    "SPY",
    "QQQ",
    "IWM",
    "XLF",
    "JPM",
    "BAC",
    "GS",
    "MSFT",
    "AAPL",
    "AMZN",
    "NVDA",
    "XLE",
    "USO",
)


def default_event_catalog(
    *,
    taq_root: str,
    output_root: str,
    provider_name: str = "nyse_taq_files",
) -> List[EventWindowRequest]:
    """Return catalog in **mandatory priority order** (1 = highest)."""

    def window(
        event_identifier: str,
        event_label: str,
        start: datetime,
        end: datetime,
        symbols: tuple[str, ...],
        notes: str,
    ) -> EventWindowRequest:
        return EventWindowRequest(
            event_identifier=event_identifier,
            event_label=event_label,
            symbols=list(symbols),
            start_timestamp=start,
            end_timestamp=end,
            data_schema_label="taq_trades_or_quotes",
            provider_name=provider_name,
            local_input_path=taq_root,
            local_output_directory=output_root,
            notes=notes,
        )

    return [
        window(
            "covid_crash",
            "COVID-19 global equity crash",
            datetime(2020, 2, 20, 14, 30, tzinfo=timezone.utc),
            datetime(2020, 3, 23, 20, 0, tzinfo=timezone.utc),
            _LIQUID_EQUITY_SUBSET,
            "Broad risk-off; flight from equities and credit stress.",
        ),
        window(
            "march_2020_liquidity_stress",
            "March 2020 liquidity / basis stress",
            datetime(2020, 3, 9, 13, 30, tzinfo=timezone.utc),
            datetime(2020, 3, 20, 21, 0, tzinfo=timezone.utc),
            _LIQUID_EQUITY_SUBSET,
            "Fed interventions period; intraday liquidity fragmentation.",
        ),
        window(
            "2022_rate_shock",
            "2022 policy rate shock / duration sell-off",
            datetime(2022, 6, 10, 13, 30, tzinfo=timezone.utc),
            datetime(2022, 10, 14, 20, 0, tzinfo=timezone.utc),
            ("SPY", "QQQ", "TLT", "IEF", "SHY", "XLF", "XLE"),
            "Rising yields; growth vs value rotation; placeholder window bounds.",
        ),
        window(
            "banking_stress_2023",
            "Regional banking stress (2023)",
            datetime(2023, 3, 8, 14, 30, tzinfo=timezone.utc),
            datetime(2023, 3, 24, 20, 0, tzinfo=timezone.utc),
            ("SPY", "KRE", "XLF", "JPM", "BAC", "GS", "MS"),
            "SVB aftermath; sector ETF and money-center focus.",
        ),
        window(
            "major_cpi_release_placeholder",
            "Major CPI release (placeholder window)",
            datetime(2022, 6, 9, 12, 25, tzinfo=timezone.utc),
            datetime(2022, 6, 10, 16, 5, tzinfo=timezone.utc),
            ("SPY", "QQQ", "IWM", "TLT"),
            "Illustrative macro release; adjust to your licensed calendar.",
        ),
        window(
            "fomc_high_volatility_placeholder",
            "FOMC high-volatility placeholder",
            datetime(2023, 5, 2, 17, 0, tzinfo=timezone.utc),
            datetime(2023, 5, 3, 21, 0, tzinfo=timezone.utc),
            ("SPY", "QQQ", "IWM", "GLD", "TLT"),
            "Policy decision window; replace with exact FOMC dates you license.",
        ),
        window(
            "earnings_shock_placeholder",
            "Single-name earnings shock placeholder",
            datetime(2023, 2, 1, 21, 0, tzinfo=timezone.utc),
            datetime(2023, 2, 2, 4, 0, tzinfo=timezone.utc),
            ("META", "AMZN", "AAPL"),
            "After-hours earnings example; not tied to a single vendor tape.",
        ),
        window(
            "commodity_spike_placeholder",
            "Commodity spike / energy stress placeholder",
            datetime(2022, 2, 24, 14, 0, tzinfo=timezone.utc),
            datetime(2022, 3, 4, 21, 0, tzinfo=timezone.utc),
            ("XLE", "USO", "SPY"),
            "Geopolitical energy stress sketch.",
        ),
        window(
            "flash_crash_style_placeholder",
            "Flash-crash-style microstructure placeholder",
            datetime(2010, 5, 6, 13, 0, tzinfo=timezone.utc),
            datetime(2010, 5, 6, 17, 5, tzinfo=timezone.utc),
            ("SPY", "QQQ", "IWM"),
            "Classic flash crash date; requires licensed TAQ for full fidelity.",
        ),
    ]
