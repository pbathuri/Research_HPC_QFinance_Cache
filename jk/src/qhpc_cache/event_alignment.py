"""CRSP + TAQ event alignment: PERMNO linkage, security master, CRSP events, normalized outputs.

Canonical WRDS tables (see ``wrds_queries`` / ``docs/wrds_active_integration.md``):

- ``crsp.stocknames``, ``crsp.dse``, ``crsp.mse``
- ``wrdsapps_link_crsp_taq.tclink``, ``wrdsapps_link_crsp_taqm.taqmclink``,
  ``wrdsapps_link_crsp_taqm.taqmclink_cusip_2010``

This module is **Phase 1** of the research spine: institutionally clean identifiers
before large-scale feature panels.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

# Match priority: daily TAQ link first, then ms, then CUSIP map
LINK_PRIORITY = ("tclink", "taqmclink", "cusip_2010")


def deterministic_event_label(
    *,
    event_identifier: str,
    window_start_iso: str,
    window_end_iso: str,
    symbols: Sequence[str],
) -> str:
    """Stable hash label for reproducible reconstruction (sorted symbols)."""
    payload = {
        "event_identifier": event_identifier,
        "window_start": window_start_iso,
        "window_end": window_end_iso,
        "symbols": sorted(str(s) for s in symbols),
    }
    raw = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def normalize_taq_symbol_root(raw: str) -> str:
    """Normalize TAQ-style symbol for linking (root / class suffix handling).

    - Uppercase, strip
    - Take segment before ``.`` (common share-class suffix)
    - For hyphenated roots (e.g. ``BRK-A``), keep full token unless overridden by link table
    """
    s = str(raw).strip().upper()
    if not s:
        return s
    if "." in s:
        s = s.split(".", 1)[0]
    return s


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _pick_column(frame: "pd.DataFrame", candidates: Sequence[str]) -> Optional[str]:
    lower_map = {str(c).lower(): c for c in frame.columns}
    for cand in candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    for col in frame.columns:
        cl = str(col).lower()
        for cand in candidates:
            if cand.lower() in cl:
                return col
    return None


def _pick_permno_column(frame: "pd.DataFrame") -> Optional[str]:
    return _pick_column(frame, ("permno", "perm_no", "lpermno", "crsp_permno"))


def _pick_symbol_column(frame: "pd.DataFrame") -> Optional[str]:
    return _pick_column(frame, ("symbol", "sym_root", "ticker", "tic", "root", "sym"))


def _pick_cusip_column(frame: "pd.DataFrame") -> Optional[str]:
    return _pick_column(frame, ("cusip", "ncusip", "ncusip8", "cusip8"))


def fetch_canonical_wrds_alignment_frames(
    db: Any,
    *,
    link_limit: int = 200_000,
    security_limit: int = 500_000,
    events_limit: int = 200_000,
) -> Dict[str, Any]:
    """Pull canonical link + master + event tables (live WRDS connection required)."""
    from qhpc_cache.wrds_provider import (
        load_crsp_daily_stock_events,
        load_crsp_monthly_stock_events,
        load_crsp_security_master,
        load_taq_crsp_link_cusip_map,
        load_taq_crsp_link_daily,
        load_taq_crsp_link_millisecond,
    )

    return {
        "tclink": load_taq_crsp_link_daily(db, limit=link_limit),
        "taqmclink": load_taq_crsp_link_millisecond(db, limit=link_limit),
        "cusip_2010": load_taq_crsp_link_cusip_map(db, limit=link_limit),
        "stocknames": load_crsp_security_master(db, limit=security_limit),
        "dse": load_crsp_daily_stock_events(db, limit=events_limit),
        "mse": load_crsp_monthly_stock_events(db, limit=events_limit),
    }


def align_taq_window_to_crsp_permno(
    taq_df: "pd.DataFrame",
    *,
    link_frames: Dict[str, Optional["pd.DataFrame"]],
    taq_symbol_col: Optional[str] = None,
) -> Tuple["pd.DataFrame", Dict[str, Any]]:
    """Map TAQ rows to CRSP PERMNO using canonical link tables (sequential fill).

    Adds columns:
      - ``qhpc_sym_root_norm``
      - ``permno`` (first successful link)
      - ``qhpc_link_source`` (tclink | taqmclink | cusip_2010)
      - ``qhpc_link_confidence`` (1.0 primary tables, 0.85 cusip map)
    """
    import pandas as pd

    if taq_df is None or len(taq_df) == 0:
        raise ValueError("taq_df must be non-empty")
    out = taq_df.copy()
    sym_col = taq_symbol_col or _pick_symbol_column(out)
    if sym_col is None:
        raise ValueError("Could not infer TAQ symbol column; set taq_symbol_col")
    out["qhpc_sym_root_norm"] = out[sym_col].map(normalize_taq_symbol_root)
    out["permno"] = pd.NA
    out["qhpc_link_source"] = ""
    out["qhpc_link_confidence"] = pd.NA

    meta: Dict[str, Any] = {"sources_attempted": [], "rows_matched_per_source": {}}

    for src in LINK_PRIORITY:
        lf = link_frames.get(src)
        if lf is None or not len(lf):
            continue
        meta["sources_attempted"].append(src)
        sym_l = _pick_symbol_column(lf)
        perm_l = _pick_permno_column(lf)
        cusip_l = _pick_cusip_column(lf)
        conf = 0.85 if src == "cusip_2010" else 1.0
        mask = out["permno"].isna()
        if not mask.any():
            break
        sub = out.loc[mask]
        if sym_l and perm_l:
            link_sub = lf[[sym_l, perm_l]].drop_duplicates()
            link_sub = link_sub.rename(columns={sym_l: "_sym", perm_l: "_perm"})
            link_sub["_sym_norm"] = link_sub["_sym"].map(normalize_taq_symbol_root)
            link_unique = link_sub.drop_duplicates(subset=["_sym_norm"], keep="last")
            pmap = dict(zip(link_unique["_sym_norm"], link_unique["_perm"]))
            new_perm = sub["qhpc_sym_root_norm"].map(pmap)
            hit = new_perm.notna()
            idx_hit = new_perm.index[hit]
            out.loc[idx_hit, "permno"] = new_perm.loc[idx_hit].values
            out.loc[idx_hit, "qhpc_link_source"] = src
            out.loc[idx_hit, "qhpc_link_confidence"] = conf
            meta["rows_matched_per_source"][src] = int(hit.sum())
        elif cusip_l and perm_l:
            tc = _pick_cusip_column(out)
            if tc:
                link_sub = lf[[cusip_l, perm_l]].drop_duplicates().rename(
                    columns={cusip_l: "_cusip", perm_l: "_perm"}
                )
                cmap = dict(zip(link_sub["_cusip"], link_sub["_perm"]))
                new_perm = sub[tc].map(cmap)
                hit = new_perm.notna()
                idx_hit = new_perm.index[hit]
                out.loc[idx_hit, "permno"] = new_perm.loc[idx_hit].values
                out.loc[idx_hit, "qhpc_link_source"] = src
                out.loc[idx_hit, "qhpc_link_confidence"] = conf
                meta["rows_matched_per_source"][src] = int(hit.sum())

    matched = int(out["permno"].notna().sum())
    meta["permno_match_rate"] = matched / max(1, len(out))
    meta["aligned_row_count"] = len(out)
    return out, meta


def attach_crsp_security_master_to_event_window(
    aligned_taq_df: "pd.DataFrame",
    stocknames_df: "pd.DataFrame",
    *,
    permno_col: str = "permno",
) -> Tuple["pd.DataFrame", Dict[str, Any]]:
    """Left-join ``crsp.stocknames`` (or subset) onto aligned TAQ rows on PERMNO."""
    import pandas as pd

    if permno_col not in aligned_taq_df.columns:
        raise ValueError(f"missing {permno_col}")
    pcol = _pick_permno_column(stocknames_df)
    if pcol is None:
        raise ValueError("stocknames frame missing permno-like column")
    sn = stocknames_df.drop_duplicates(subset=[pcol], keep="last")
    sn = sn.rename(columns={pcol: "_permno_master"})
    merged = aligned_taq_df.merge(
        sn,
        left_on=permno_col,
        right_on="_permno_master",
        how="left",
        suffixes=("", "_stocknames"),
    )
    n = int(merged["_permno_master"].notna().sum()) if "_permno_master" in merged.columns else 0
    return merged, {"security_master_rows_matched": n, "stocknames_permno_col": pcol}


def _event_date_column(frame: "pd.DataFrame") -> Optional[str]:
    return _pick_column(frame, ("date", "caldt", "event_date", "effdate", "namedt", "begdt"))


def attach_crsp_events_to_event_window(
    aligned_taq_df: "pd.DataFrame",
    dse_df: Optional["pd.DataFrame"],
    mse_df: Optional["pd.DataFrame"],
    *,
    permno_col: str = "permno",
    timestamp_col: Optional[str] = None,
) -> Tuple["pd.DataFrame", Dict[str, Any]]:
    """Attach daily (dse) / monthly (mse) CRSP event flags relative to TAQ calendar date."""
    import pandas as pd

    out = aligned_taq_df.copy()
    ts_col = timestamp_col or _pick_column(out, ("timestamp", "time", "datetime", "ts"))
    if ts_col is None:
        out["qhpc_calendar_date"] = pd.NaT
    else:
        out["qhpc_calendar_date"] = pd.to_datetime(out[ts_col], errors="coerce").dt.normalize()

    meta: Dict[str, Any] = {"dse_hits": 0, "mse_hits": 0}

    for name, evdf in (("dse", dse_df), ("mse", mse_df)):
        if evdf is None or len(evdf) == 0:
            continue
        p_ev = _pick_permno_column(evdf)
        d_ev = _event_date_column(evdf)
        if not p_ev or not d_ev:
            continue
        ev = evdf[[p_ev, d_ev]].copy()
        ev = ev.rename(columns={p_ev: "_e_perm", d_ev: "_e_date"})
        ev["_e_date"] = pd.to_datetime(ev["_e_date"], errors="coerce").dt.normalize()
        ev = ev.drop_duplicates(subset=["_e_perm", "_e_date"], keep="last")
        hit_col = f"qhpc_{name}_event_hit"
        merged = out.merge(
            ev,
            left_on=[permno_col, "qhpc_calendar_date"],
            right_on=["_e_perm", "_e_date"],
            how="left",
            indicator=True,
        )
        merged[hit_col] = (merged["_merge"] == "both").astype(int)
        drop_cols = [c for c in ("_e_perm", "_e_date", "_merge") if c in merged.columns]
        merged = merged.drop(columns=drop_cols, errors="ignore")
        out = merged
        meta[f"{name}_hits"] = int(out[hit_col].sum()) if hit_col in out.columns else 0

    return out, meta


def build_normalized_event_window(
    aligned_enriched_df: "pd.DataFrame",
    *,
    event_identifier: str,
    event_label: str,
    window_start_iso: str,
    window_end_iso: str,
    symbols: Sequence[str],
) -> Tuple["pd.DataFrame", Dict[str, Any]]:
    """Final column order + manifest dict (use with ``EventAlignmentManifest``)."""
    import pandas as pd

    label = deterministic_event_label(
        event_identifier=event_identifier,
        window_start_iso=window_start_iso,
        window_end_iso=window_end_iso,
        symbols=symbols,
    )
    frame = aligned_enriched_df.copy()
    frame["qhpc_event_identifier"] = event_identifier
    frame["qhpc_event_label"] = event_label
    frame["qhpc_deterministic_label"] = label
    frame["qhpc_aligned_at_utc"] = _utc_now()

    permno_rate = float(frame["permno"].notna().mean()) if "permno" in frame.columns else 0.0
    manifest_dict = {
        "deterministic_label": label,
        "taq_row_count": len(frame),
        "aligned_row_count": len(frame),
        "permno_match_rate": permno_rate,
        "window_start_utc": window_start_iso,
        "window_end_utc": window_end_iso,
    }
    return frame, manifest_dict
