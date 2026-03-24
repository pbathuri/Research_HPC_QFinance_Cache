"""Workload-signature summaries for event-library comparison runs.

This is a first structured cache-study substrate for event windows. It captures
Mac-executable proxies (timings, join widths, repetition markers, alignment
quality) without claiming full microarchitectural PMU coverage.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Mapping, Sequence

from qhpc_cache.workload_signatures import (
    WORKLOAD_SPINE_EVENT_WINDOW,
    model_family_label,
    portfolio_family_label,
    workload_family_label,
)


def _quantile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(float(v) for v in values)
    if len(s) == 1:
        return s[0]
    idx = (len(s) - 1) * q
    lo = int(idx)
    hi = min(lo + 1, len(s) - 1)
    w = idx - lo
    return s[lo] * (1.0 - w) + s[hi] * w


def _col_or_default(frame: Any, name: str, default_value: Any) -> List[Any]:
    if name in frame.columns:
        return list(frame[name])
    return [default_value] * len(frame)


def _build_workload_family(event_set_id: str, window_family: str, intraday_slice: str) -> str:
    pf = portfolio_family_label(universe_name=event_set_id, n_symbols=0, book_tag=window_family)
    mf = model_family_label(engine_or_model="event_alignment", path_bucket=intraday_slice, phase="compare")
    return workload_family_label(
        pipeline_stage=WORKLOAD_SPINE_EVENT_WINDOW,
        portfolio_family=pf,
        model_family=mf,
        event_stress=True,
    )


def compute_event_workload_signatures(normalized_event_rows: Any) -> Any:
    """Aggregate normalized event rows into event-workload signatures.

    Expected normalized columns (best effort / optional):
      - event_set_id, window_family_label, intraday_slice_label
      - permno
      - join_width
      - alignment_match_quality
      - normalized_window_id
      - join_pattern_id
      - derived_structure_id
      - stage_timing_ms
    """
    import pandas as pd

    if normalized_event_rows is None or len(normalized_event_rows) == 0:
        return pd.DataFrame(
            columns=[
                "event_set_id",
                "window_family_label",
                "intraday_slice_label",
                "row_count",
                "aligned_permno_count",
                "join_width",
                "identifier_match_quality",
                "repeated_event_window_reconstruction_markers",
                "repeated_join_pattern_markers",
                "reusable_derived_structure_markers",
                "workload_spine_id",
                "workload_family_label",
                "timing_p50_ms",
                "timing_p90_ms",
                "timing_p99_ms",
                "timing_p999_ms",
                "cache_proxy_reuse_density",
                "cache_proxy_locality_hint",
                "cache_proxy_alignment_penalty",
            ]
        )

    df = normalized_event_rows.copy()
    if "event_set_id" not in df.columns:
        raise ValueError("normalized_event_rows must include event_set_id")
    if "window_family_label" not in df.columns:
        raise ValueError("normalized_event_rows must include window_family_label")
    if "intraday_slice_label" not in df.columns:
        df["intraday_slice_label"] = "none"

    key_cols = ["event_set_id", "window_family_label", "intraday_slice_label"]
    out_rows: List[Dict[str, Any]] = []
    for key, grp in df.groupby(key_cols, dropna=False):
        event_set_id, window_family, intraday_slice = key
        row_count = int(len(grp))
        aligned_permno_count = int(grp["permno"].dropna().nunique()) if "permno" in grp.columns else 0
        join_width = int(grp["join_width"].fillna(0).max()) if "join_width" in grp.columns else int(len(grp.columns))
        id_quality = float(grp["alignment_match_quality"].fillna(0.0).mean()) if "alignment_match_quality" in grp.columns else 0.0

        win_ids = _col_or_default(grp, "normalized_window_id", "")
        win_counts: Dict[str, int] = {}
        for wid in win_ids:
            if wid:
                win_counts[str(wid)] = win_counts.get(str(wid), 0) + 1
        repeated_recon = sum(1 for _, c in win_counts.items() if c > 1)

        join_patterns = _col_or_default(grp, "join_pattern_id", "")
        j_counts: Dict[str, int] = {}
        for jp in join_patterns:
            if jp:
                j_counts[str(jp)] = j_counts.get(str(jp), 0) + 1
        repeated_join_patterns = sum(1 for _, c in j_counts.items() if c > 1)

        derived_ids = _col_or_default(grp, "derived_structure_id", "")
        d_counts: Dict[str, int] = {}
        for did in derived_ids:
            if did:
                d_counts[str(did)] = d_counts.get(str(did), 0) + 1
        reusable_structures = sum(1 for _, c in d_counts.items() if c > 1)

        tms = [float(x) for x in _col_or_default(grp, "stage_timing_ms", 0.0)]
        t50 = _quantile(tms, 0.50)
        t90 = _quantile(tms, 0.90)
        t99 = _quantile(tms, 0.99)
        t999 = _quantile(tms, 0.999)

        reuse_density = float(repeated_recon + repeated_join_patterns + reusable_structures) / max(1, row_count)
        locality_hint = 1.0 / (1.0 + max(0.0, float(join_width)) / 100.0)
        alignment_penalty = max(0.0, 1.0 - id_quality)

        out_rows.append(
            {
                "event_set_id": str(event_set_id),
                "window_family_label": str(window_family),
                "intraday_slice_label": str(intraday_slice),
                "row_count": row_count,
                "aligned_permno_count": aligned_permno_count,
                "join_width": join_width,
                "identifier_match_quality": id_quality,
                "repeated_event_window_reconstruction_markers": int(repeated_recon),
                "repeated_join_pattern_markers": int(repeated_join_patterns),
                "reusable_derived_structure_markers": int(reusable_structures),
                "workload_spine_id": WORKLOAD_SPINE_EVENT_WINDOW,
                "workload_family_label": _build_workload_family(
                    str(event_set_id), str(window_family), str(intraday_slice)
                ),
                "timing_p50_ms": t50,
                "timing_p90_ms": t90,
                "timing_p99_ms": t99,
                "timing_p999_ms": t999,
                "cache_proxy_reuse_density": reuse_density,
                "cache_proxy_locality_hint": locality_hint,
                "cache_proxy_alignment_penalty": alignment_penalty,
            }
        )
    return pd.DataFrame(out_rows)


def summarize_timing_distribution(signature_rows: Any) -> Any:
    """Return compact timing distribution summary by event set."""
    import pandas as pd

    if signature_rows is None or len(signature_rows) == 0:
        return pd.DataFrame(columns=["event_set_id", "timing_p50_ms", "timing_p90_ms", "timing_p99_ms", "timing_p999_ms"])
    grp = signature_rows.groupby("event_set_id", dropna=False).agg(
        timing_p50_ms=("timing_p50_ms", "mean"),
        timing_p90_ms=("timing_p90_ms", "mean"),
        timing_p99_ms=("timing_p99_ms", "mean"),
        timing_p999_ms=("timing_p999_ms", "mean"),
    )
    return grp.reset_index()


def summarize_cache_proxies(signature_rows: Any) -> Any:
    """Return compact cache-proxy summary by event set."""
    import pandas as pd

    if signature_rows is None or len(signature_rows) == 0:
        return pd.DataFrame(
            columns=[
                "event_set_id",
                "cache_proxy_reuse_density",
                "cache_proxy_locality_hint",
                "cache_proxy_alignment_penalty",
            ]
        )
    grp = signature_rows.groupby("event_set_id", dropna=False).agg(
        cache_proxy_reuse_density=("cache_proxy_reuse_density", "mean"),
        cache_proxy_locality_hint=("cache_proxy_locality_hint", "mean"),
        cache_proxy_alignment_penalty=("cache_proxy_alignment_penalty", "mean"),
    )
    return grp.reset_index()


def join_pattern_id_from_row(row: Mapping[str, Any]) -> str:
    """Create deterministic join-pattern marker from source + width."""
    source = str(row.get("source_datasets", ""))
    width = int(row.get("join_width", 0) or 0)
    payload = f"{source}|{width}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
