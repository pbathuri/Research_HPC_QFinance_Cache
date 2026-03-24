"""Active WRDS integration: connection, discovery, and safe query execution.

Canonical CRSP / TAQ-link tables are fixed (see ``wrds_queries``); loaders use
those exact ``schema.table`` names verified on live WRDS.

Authentication:
  - Set ``WRDS_USERNAME`` in the environment (and use WRDS-supported password flow,
    e.g. ``.pgpass`` or interactive first-time setup per WRDS docs).
  - **Never** hardcode passwords or print credentials.

Requires: ``pip install wrds`` (not bundled as a hard dependency of the core package).
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_WRDS_MODULE: Any = None


def _get_wrds():
    global _WRDS_MODULE
    if _WRDS_MODULE is None:
        import importlib

        _WRDS_MODULE = importlib.import_module("wrds")
    return _WRDS_MODULE


def check_wrds_connection(
    *,
    wrds_username: Optional[str] = None,
) -> Tuple[bool, str, Any]:
    """Return ``(ok, message, connection_or_none)``.

    Does not log or print the username value beyond "set/not set".
    """
    user = wrds_username or os.environ.get("WRDS_USERNAME", "").strip()
    if not user:
        return False, "WRDS_USERNAME not set in environment", None
    try:
        wrds = _get_wrds()
        db = wrds.Connection(wrds_username=user)
        return True, "wrds.Connection established", db
    except Exception as exc:  # pragma: no cover - network/subscription dependent
        return False, f"{type(exc).__name__}: {exc}", None


def discover_wrds_dataset_access(db: Any) -> Dict[str, Any]:
    """List libraries (truncated) and any errors. Safe for logging."""
    out: Dict[str, Any] = {
        "ok": True,
        "libraries_count": 0,
        "libraries_sample": [],
        "errors": [],
    }
    try:
        libs = db.list_libraries()
        out["libraries_count"] = len(libs)
        out["libraries_sample"] = list(libs[:100])
    except Exception as exc:
        out["ok"] = False
        out["errors"].append(str(exc))
    return out


def _query_fingerprint(sql: str) -> str:
    return hashlib.sha256(sql.strip().encode("utf-8")).hexdigest()[:16]


def run_wrds_sql_query(
    db: Any,
    sql: str,
    *,
    max_rows_for_log: int = 0,
) -> Tuple[Optional[Any], Dict[str, Any]]:
    """Execute ``raw_sql`` and return ``(dataframe_or_none, meta)``.

    ``meta`` includes timing, row count, and a **non-sensitive** query fingerprint.
    """
    meta = {
        "query_fingerprint": _query_fingerprint(sql),
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "row_count": 0,
        "elapsed_seconds": 0.0,
        "error": "",
    }
    t0 = time.perf_counter()
    try:
        df = db.raw_sql(sql)
        meta["elapsed_seconds"] = round(time.perf_counter() - t0, 4)
        if df is not None:
            meta["row_count"] = int(len(df))
            if max_rows_for_log and meta["row_count"] > 0:
                logger.info(
                    "WRDS query fp=%s rows=%s sample_cols=%s",
                    meta["query_fingerprint"],
                    meta["row_count"],
                    list(df.columns)[:12],
                )
        return df, meta
    except Exception as exc:
        meta["elapsed_seconds"] = round(time.perf_counter() - t0, 4)
        meta["error"] = f"{type(exc).__name__}: {exc}"
        logger.warning("WRDS query failed fp=%s err=%s", meta["query_fingerprint"], meta["error"])
        return None, meta


def _load_exact_table(
    db: Any,
    schema: str,
    table: str,
    *,
    limit: int = 50_000,
    date_col: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> Tuple[Optional[Any], Dict[str, Any]]:
    """Run a single bounded ``SELECT *`` on a verified canonical table."""
    from qhpc_cache.wrds_queries import sql_select_star_limited, sql_treasury_date_bounded

    if date_col and start and end:
        sql = sql_treasury_date_bounded(schema, table, date_col, start, end, limit=limit)
    else:
        sql = sql_select_star_limited(schema, table, limit=limit)
    df, meta = run_wrds_sql_query(db, sql)
    full = f"{schema}.{table}"
    return df, {
        **meta,
        "schema": schema,
        "table": table,
        "wrds_source_table": full,
        "canonical_table": full,
    }


def _try_first_existing_table(
    db: Any,
    candidates: List[Tuple[str, str]],
    build_sql,
) -> Tuple[Optional[Any], Dict[str, Any]]:
    """Try candidates until one returns a non-empty dataframe or last error."""
    last_meta: Dict[str, Any] = {}
    for schema, table in candidates:
        sql = build_sql(schema, table)
        df, meta = run_wrds_sql_query(db, sql)
        last_meta = {**meta, "schema": schema, "table": table, "wrds_source_table": f"{schema}.{table}"}
        if df is not None and len(df) > 0:
            return df, last_meta
    return None, last_meta


# ── Rates / Treasury (canonical: tfz_dly, tfz_mth) ──────────────────────────


def load_crsp_treasury_daily(
    db: Any,
    *,
    limit: int = 50_000,
    date_col: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> Tuple[Optional[Any], Dict[str, Any]]:
    """Institutional daily Treasury / zero curve context: ``crsp.tfz_dly``."""
    from qhpc_cache.wrds_queries import CANONICAL_CRSP_TFZ_DLY

    sch, tbl = CANONICAL_CRSP_TFZ_DLY
    if start:
        start = validate_iso_date(start)
    if end:
        end = validate_iso_date(end)
    return _load_exact_table(db, sch, tbl, limit=limit, date_col=date_col, start=start, end=end)


def load_crsp_treasury_monthly(
    db: Any,
    *,
    limit: int = 50_000,
    date_col: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> Tuple[Optional[Any], Dict[str, Any]]:
    """Monthly Treasury context: ``crsp.tfz_mth``."""
    from qhpc_cache.wrds_queries import CANONICAL_CRSP_TFZ_MTH

    sch, tbl = CANONICAL_CRSP_TFZ_MTH
    if start:
        start = validate_iso_date(start)
    if end:
        end = validate_iso_date(end)
    return _load_exact_table(db, sch, tbl, limit=limit, date_col=date_col, start=start, end=end)


def load_crsp_treasury_context(
    db: Any,
    *,
    limit: int = 50_000,
) -> Tuple[Optional[Any], Dict[str, Any]]:
    """Backward-compatible: **daily first** (``tfz_dly``), then **monthly** (``tfz_mth``).

    Prefer calling ``load_crsp_treasury_daily`` / ``load_crsp_treasury_monthly`` explicitly.
    """
    df, meta = load_crsp_treasury_daily(db, limit=limit)
    if df is not None and len(df) > 0:
        return df, meta
    return load_crsp_treasury_monthly(db, limit=limit)


# ── Security master & stock panels ────────────────────────────────────────────


def load_crsp_security_master(
    db: Any,
    *,
    limit: int = 500_000,
    date_col: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> Tuple[Optional[Any], Dict[str, Any]]:
    """Canonical equity identity master: ``crsp.stocknames`` (pair with Databento symbols operationally)."""
    from qhpc_cache.wrds_queries import CANONICAL_CRSP_STOCKNAMES

    sch, tbl = CANONICAL_CRSP_STOCKNAMES
    if start:
        start = validate_iso_date(start)
    if end:
        end = validate_iso_date(end)
    return _load_exact_table(db, sch, tbl, limit=limit, date_col=date_col, start=start, end=end)


def load_crsp_daily_stock_panel(
    db: Any,
    *,
    limit: int = 50_000,
    date_col: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> Tuple[Optional[Any], Dict[str, Any]]:
    """Daily stock panel: ``crsp.dsf`` — use date bounds for production-scale pulls."""
    from qhpc_cache.wrds_queries import CANONICAL_CRSP_DSF

    sch, tbl = CANONICAL_CRSP_DSF
    if start:
        start = validate_iso_date(start)
    if end:
        end = validate_iso_date(end)
    return _load_exact_table(db, sch, tbl, limit=limit, date_col=date_col, start=start, end=end)


def load_crsp_monthly_stock_panel(
    db: Any,
    *,
    limit: int = 50_000,
    date_col: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> Tuple[Optional[Any], Dict[str, Any]]:
    """Monthly stock panel: ``crsp.msf``."""
    from qhpc_cache.wrds_queries import CANONICAL_CRSP_MSF

    sch, tbl = CANONICAL_CRSP_MSF
    if start:
        start = validate_iso_date(start)
    if end:
        end = validate_iso_date(end)
    return _load_exact_table(db, sch, tbl, limit=limit, date_col=date_col, start=start, end=end)


# ── Stock events (canonical dse / mse) ──────────────────────────────────────


def load_crsp_daily_stock_events(
    db: Any,
    *,
    limit: int = 50_000,
    date_col: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> Tuple[Optional[Any], Dict[str, Any]]:
    """Daily stock events: ``crsp.dse``."""
    from qhpc_cache.wrds_queries import CANONICAL_CRSP_DSE

    sch, tbl = CANONICAL_CRSP_DSE
    if start:
        start = validate_iso_date(start)
    if end:
        end = validate_iso_date(end)
    return _load_exact_table(db, sch, tbl, limit=limit, date_col=date_col, start=start, end=end)


def load_crsp_monthly_stock_events(
    db: Any,
    *,
    limit: int = 50_000,
    date_col: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> Tuple[Optional[Any], Dict[str, Any]]:
    """Monthly stock events: ``crsp.mse``."""
    from qhpc_cache.wrds_queries import CANONICAL_CRSP_MSE

    sch, tbl = CANONICAL_CRSP_MSE
    if start:
        start = validate_iso_date(start)
    if end:
        end = validate_iso_date(end)
    return _load_exact_table(db, sch, tbl, limit=limit, date_col=date_col, start=start, end=end)


def load_crsp_stock_events(
    db: Any,
    *,
    limit: int = 50_000,
) -> Tuple[Optional[Any], Dict[str, Any]]:
    """Legacy: try ``dse`` then ``mse``. Prefer explicit daily/monthly loaders."""
    df, meta = load_crsp_daily_stock_events(db, limit=limit)
    if df is not None and len(df) > 0:
        return df, meta
    return load_crsp_monthly_stock_events(db, limit=limit)


# ── TAQ ↔ CRSP linking (canonical) ──────────────────────────────────────────


def load_taq_crsp_link_daily(
    db: Any,
    *,
    limit: int = 50_000,
    date_col: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> Tuple[Optional[Any], Dict[str, Any]]:
    """Daily TAQ–CRSP bridge: ``wrdsapps_link_crsp_taq.tclink`` (PERMNO linkage for event windows)."""
    from qhpc_cache.wrds_queries import CANONICAL_TAQ_CRSP_TCLINK

    sch, tbl = CANONICAL_TAQ_CRSP_TCLINK
    if start:
        start = validate_iso_date(start)
    if end:
        end = validate_iso_date(end)
    return _load_exact_table(db, sch, tbl, limit=limit, date_col=date_col, start=start, end=end)


def load_taq_crsp_link_millisecond(
    db: Any,
    *,
    limit: int = 50_000,
    date_col: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> Tuple[Optional[Any], Dict[str, Any]]:
    """Millisecond TAQ–CRSP bridge: ``wrdsapps_link_crsp_taqm.taqmclink``."""
    from qhpc_cache.wrds_queries import CANONICAL_TAQ_CRSP_TAQMCLINK

    sch, tbl = CANONICAL_TAQ_CRSP_TAQMCLINK
    if start:
        start = validate_iso_date(start)
    if end:
        end = validate_iso_date(end)
    return _load_exact_table(db, sch, tbl, limit=limit, date_col=date_col, start=start, end=end)


def load_taq_crsp_link_cusip_map(
    db: Any,
    *,
    limit: int = 50_000,
    date_col: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> Tuple[Optional[Any], Dict[str, Any]]:
    """CUSIP-oriented TAQ–CRSP map: ``wrdsapps_link_crsp_taqm.taqmclink_cusip_2010``."""
    from qhpc_cache.wrds_queries import CANONICAL_TAQ_CRSP_CUSIP_2010

    sch, tbl = CANONICAL_TAQ_CRSP_CUSIP_2010
    if start:
        start = validate_iso_date(start)
    if end:
        end = validate_iso_date(end)
    return _load_exact_table(db, sch, tbl, limit=limit, date_col=date_col, start=start, end=end)


def load_taq_crsp_links(
    db: Any,
    *,
    limit: int = 50_000,
) -> Tuple[Optional[Any], Dict[str, Any]]:
    """Legacy aggregate: first non-empty among tclink → taqmclink → cusip_2010.

    Prefer the three explicit loaders for event-window / cache studies.
    """
    last_meta: Dict[str, Any] = {}
    for fn in (
        load_taq_crsp_link_daily,
        load_taq_crsp_link_millisecond,
        load_taq_crsp_link_cusip_map,
    ):
        df, meta = fn(db, limit=limit)
        last_meta = meta
        if df is not None and len(df) > 0:
            return df, meta
    return None, last_meta


# ── Tiers 4–7 & secondary rates (candidate lists) ───────────────────────────


def load_wrds_factor_data(
    db: Any,
    *,
    limit: int = 20_000,
) -> Tuple[Optional[Any], Dict[str, Any]]:
    """Fama-French-style tables first, then liquidity-style candidates (tier 5)."""
    from qhpc_cache.wrds_queries import (
        FAMA_FRENCH_CANDIDATES,
        LIQUIDITY_STYLE_CANDIDATES,
        sql_fama_french_sample,
    )

    candidates = list(FAMA_FRENCH_CANDIDATES) + list(LIQUIDITY_STYLE_CANDIDATES)

    def _sql(sch: str, tbl: str) -> str:
        return sql_fama_french_sample(sch, tbl, limit=limit)

    return _try_first_existing_table(db, candidates, _sql)


def load_crsp_compustat_merged(
    db: Any,
    *,
    limit: int = 50_000,
) -> Tuple[Optional[Any], Dict[str, Any]]:
    from qhpc_cache.wrds_queries import CRSP_COMPUSTAT_MERGED_CANDIDATES, sql_select_star_limited

    def _sql(sch: str, tbl: str) -> str:
        return sql_select_star_limited(sch, tbl, limit=limit)

    return _try_first_existing_table(db, list(CRSP_COMPUSTAT_MERGED_CANDIDATES), _sql)


def load_event_study_if_available(
    db: Any,
    *,
    limit: int = 20_000,
) -> Tuple[Optional[Any], Dict[str, Any]]:
    """Tier 7 — Eventus / event-study tables; configure ``EVENT_STUDY_CANDIDATES`` when licensed."""
    from qhpc_cache.wrds_queries import EVENT_STUDY_CANDIDATES, sql_select_star_limited

    if not EVENT_STUDY_CANDIDATES:
        return None, {
            "error": "EVENT_STUDY_CANDIDATES is empty — add schema.table in wrds_queries.py when Eventus is available",
        }

    def _sql(sch: str, tbl: str) -> str:
        return sql_select_star_limited(sch, tbl, limit=limit)

    return _try_first_existing_table(db, list(EVENT_STUDY_CANDIDATES), _sql)


def load_frb_rates_if_available(
    db: Any,
    *,
    limit: int = 20_000,
) -> Tuple[Optional[Any], Dict[str, Any]]:
    from qhpc_cache.wrds_queries import FRB_RATE_CANDIDATES

    def _sql(sch: str, tbl: str) -> str:
        return f'SELECT * FROM "{sch}"."{tbl}" LIMIT {int(limit)}'

    return _try_first_existing_table(db, list(FRB_RATE_CANDIDATES), _sql)


def validate_iso_date(d: str) -> str:
    return date.fromisoformat(d[:10]).isoformat()
