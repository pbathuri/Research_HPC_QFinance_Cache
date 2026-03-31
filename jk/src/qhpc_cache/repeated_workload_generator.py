"""Deterministic repeated-workload generators for cache-research studies."""

from __future__ import annotations

import hashlib
import json
from random import Random
from typing import Any, Dict, List, Optional, Sequence

LANE_A_ID = "lane_a"
LANE_B_ID = "lane_b"
LANE_SELECTIONS = {"both", LANE_A_ID, LANE_B_ID}

REQUIRED_WORKLOAD_FAMILIES = [
    "exact_repeat_pricing",
    "near_repeat_pricing",
    "path_ladder_pricing",
    "portfolio_cluster_condensation",
    "overlapping_event_window_rebuild",
    "stress_churn_pricing",
    "intraday_scenario_ladder",
    "cross_sectional_basket",
    "rolling_horizon_refresh",
    "hotset_coldset_mixed",
    "parameter_shock_grid",
]
FAMILY_IDS = set(REQUIRED_WORKLOAD_FAMILIES)
FAMILY_ALIASES = {
    "exact_repeat_family": "exact_repeat_pricing",
    "clustered_near_repeat_family": "near_repeat_pricing",
    "bursty_hotset_family": "path_ladder_pricing",
    "regime_switch_family": "stress_churn_pricing",
    "intraday_ladder": "intraday_scenario_ladder",
    "basket_repricing": "cross_sectional_basket",
    "rolling_horizon": "rolling_horizon_refresh",
    "hotcold_mixed": "hotset_coldset_mixed",
    "shock_grid": "parameter_shock_grid",
}

TEMPLATE_BANK_ID_DEFAULT = "structured_template_bank_v2"

SCALE_PROFILES: Dict[str, Dict[str, int]] = {
    "smoke": {
        "exact_repeat_pricing": 18,
        "near_repeat_pricing": 24,
        "path_ladder_pricing": 24,
        "portfolio_cluster_condensation": 20,
        "overlapping_event_window_rebuild": 20,
        "stress_churn_pricing": 24,
        "intraday_scenario_ladder": 20,
        "cross_sectional_basket": 24,
        "rolling_horizon_refresh": 20,
        "hotset_coldset_mixed": 24,
        "parameter_shock_grid": 25,
    },
    "standard": {
        "exact_repeat_pricing": 160,
        "near_repeat_pricing": 220,
        "path_ladder_pricing": 240,
        "portfolio_cluster_condensation": 180,
        "overlapping_event_window_rebuild": 180,
        "stress_churn_pricing": 240,
        "intraday_scenario_ladder": 180,
        "cross_sectional_basket": 200,
        "rolling_horizon_refresh": 160,
        "hotset_coldset_mixed": 200,
        "parameter_shock_grid": 225,
    },
    "heavy": {
        "exact_repeat_pricing": 900,
        "near_repeat_pricing": 1200,
        "path_ladder_pricing": 1300,
        "portfolio_cluster_condensation": 950,
        "overlapping_event_window_rebuild": 950,
        "stress_churn_pricing": 1300,
        "intraday_scenario_ladder": 1000,
        "cross_sectional_basket": 1100,
        "rolling_horizon_refresh": 900,
        "hotset_coldset_mixed": 1100,
        "parameter_shock_grid": 1225,
    },
    "long_wave": {
        "exact_repeat_pricing": 1800,
        "near_repeat_pricing": 2400,
        "path_ladder_pricing": 2600,
        "portfolio_cluster_condensation": 1900,
        "overlapping_event_window_rebuild": 1900,
        "stress_churn_pricing": 2600,
        "intraday_scenario_ladder": 2000,
        "cross_sectional_basket": 2200,
        "rolling_horizon_refresh": 1800,
        "hotset_coldset_mixed": 2200,
        "parameter_shock_grid": 2450,
    },
    "locality_burst": {
        "exact_repeat_pricing": 600,
        "near_repeat_pricing": 400,
        "path_ladder_pricing": 400,
        "portfolio_cluster_condensation": 400,
        "overlapping_event_window_rebuild": 600,
        "stress_churn_pricing": 200,
        "intraday_scenario_ladder": 600,
        "cross_sectional_basket": 600,
        "rolling_horizon_refresh": 600,
        "hotset_coldset_mixed": 800,
        "parameter_shock_grid": 400,
    },
    "validation_heavy": {
        "exact_repeat_pricing": 300,
        "near_repeat_pricing": 500,
        "path_ladder_pricing": 500,
        "portfolio_cluster_condensation": 300,
        "overlapping_event_window_rebuild": 300,
        "stress_churn_pricing": 300,
        "intraday_scenario_ladder": 400,
        "cross_sectional_basket": 500,
        "rolling_horizon_refresh": 300,
        "hotset_coldset_mixed": 400,
        "parameter_shock_grid": 600,
    },
}


def _normalize_lane_selection(lane_selection: str) -> List[str]:
    lane = str(lane_selection).strip().lower()
    if lane not in LANE_SELECTIONS:
        raise ValueError(
            f"Invalid lane_selection {lane_selection!r}. Expected one of {sorted(LANE_SELECTIONS)}."
        )
    if lane == "both":
        return [LANE_A_ID, LANE_B_ID]
    return [lane]


def _validate_scale_label(scale_label: str) -> str:
    label = str(scale_label).strip().lower()
    if label not in SCALE_PROFILES:
        raise ValueError(
            f"Invalid scale_label {scale_label!r}. Expected one of {sorted(SCALE_PROFILES)}."
        )
    return label


def _normalize_family_selection(families: Optional[Sequence[str]]) -> List[str]:
    if not families:
        return list(REQUIRED_WORKLOAD_FAMILIES)
    resolved: List[str] = []
    for item in families:
        name = str(item).strip()
        if not name:
            continue
        canonical = FAMILY_ALIASES.get(name, name)
        if canonical not in FAMILY_IDS:
            raise ValueError(f"Invalid workload family value: {name!r}")
        if canonical not in resolved:
            resolved.append(canonical)
    return resolved


def _stable_hash(payload: Dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()


def _compute_parameter_hash(row: Dict[str, Any]) -> str:
    return _stable_hash(
        {
            "payoff_type": row["payoff_type"],
            "S0": round(float(row["S0"]), 6),
            "K": round(float(row["K"]), 6),
            "r": round(float(row["r"]), 6),
            "sigma": round(float(row["sigma"]), 6),
            "T": round(float(row["T"]), 6),
            "num_paths": int(row["num_paths"]),
            "simulation_mode": row.get("simulation_mode", "terminal"),
            "num_time_steps": int(row.get("num_time_steps", 12)),
            "random_seed": int(row["random_seed"]),
        }
    )


def _compute_feature_hash(row: Dict[str, Any]) -> str:
    paths_bucket = int(round(float(row["num_paths"]) / 2000.0) * 2000)
    return _stable_hash(
        {
            "payoff_type": row["payoff_type"],
            "S0_q": round(float(row["S0"]) / 2.0) * 2.0,
            "K_q": round(float(row["K"]) / 2.0) * 2.0,
            "sigma_q": round(float(row["sigma"]), 2),
            "T_q": round(float(row["T"]), 2),
            "num_paths_bucket": int(max(1, paths_bucket)),
        }
    )


def _build_template(
    *,
    template_id: str,
    s0: float,
    moneyness: float,
    sigma: float,
    maturity: float,
    num_paths: int,
    payoff_type: str,
) -> Dict[str, Any]:
    return {
        "template_id": template_id,
        "S0": float(s0),
        "K": round(float(s0) * float(moneyness), 6),
        "r": 0.05,
        "sigma": float(sigma),
        "T": float(maturity),
        "num_paths": int(num_paths),
        "payoff_type": str(payoff_type),
        "simulation_mode": "terminal",
        "num_time_steps": 12,
    }


def build_template_bank(*, template_bank_id: str = TEMPLATE_BANK_ID_DEFAULT) -> List[Dict[str, Any]]:
    if template_bank_id != TEMPLATE_BANK_ID_DEFAULT:
        raise ValueError(
            f"Unsupported template_bank_id {template_bank_id!r}. Expected {TEMPLATE_BANK_ID_DEFAULT!r}."
        )
    return [
        _build_template(
            template_id="tpl_otm_short_lowvol_call",
            s0=100.0,
            moneyness=1.10,
            sigma=0.16,
            maturity=0.25,
            num_paths=8_000,
            payoff_type="european_call",
        ),
        _build_template(
            template_id="tpl_atm_short_medvol_call",
            s0=100.0,
            moneyness=1.00,
            sigma=0.22,
            maturity=0.25,
            num_paths=10_000,
            payoff_type="european_call",
        ),
        _build_template(
            template_id="tpl_itm_short_highvol_call",
            s0=100.0,
            moneyness=0.92,
            sigma=0.34,
            maturity=0.25,
            num_paths=14_000,
            payoff_type="european_call",
        ),
        _build_template(
            template_id="tpl_atm_medium_medvol_call",
            s0=100.0,
            moneyness=1.00,
            sigma=0.22,
            maturity=1.00,
            num_paths=12_000,
            payoff_type="european_call",
        ),
        _build_template(
            template_id="tpl_otm_medium_highvol_call",
            s0=100.0,
            moneyness=1.08,
            sigma=0.35,
            maturity=1.00,
            num_paths=16_000,
            payoff_type="european_call",
        ),
        _build_template(
            template_id="tpl_itm_medium_lowvol_put",
            s0=100.0,
            moneyness=0.94,
            sigma=0.15,
            maturity=1.00,
            num_paths=12_000,
            payoff_type="european_put",
        ),
        _build_template(
            template_id="tpl_atm_long_highvol_call",
            s0=100.0,
            moneyness=1.00,
            sigma=0.39,
            maturity=2.00,
            num_paths=20_000,
            payoff_type="european_call",
        ),
        _build_template(
            template_id="tpl_itm_long_medvol_put",
            s0=100.0,
            moneyness=0.90,
            sigma=0.23,
            maturity=2.00,
            num_paths=18_000,
            payoff_type="european_put",
        ),
    ]


FAMILY_REGIME_MAP: Dict[str, str] = {
    "exact_repeat_pricing": "high_locality",
    "near_repeat_pricing": "clustered_event",
    "path_ladder_pricing": "calm",
    "portfolio_cluster_condensation": "overlap_heavy",
    "overlapping_event_window_rebuild": "overlap_heavy",
    "stress_churn_pricing": "churn_heavy",
    "intraday_scenario_ladder": "volatile",
    "cross_sectional_basket": "overlap_heavy",
    "rolling_horizon_refresh": "calm",
    "hotset_coldset_mixed": "high_locality",
    "parameter_shock_grid": "stress",
}


def _finalize_request(
    *,
    row: Dict[str, Any],
    lane_id: str,
    family: str,
    index: int,
) -> Dict[str, Any]:
    out = dict(row)
    out["lane"] = lane_id
    out["workload_family"] = family
    out["request_id"] = f"{lane_id}_{family}_{index:06d}"
    out["cluster_id"] = str(out.get("cluster_id", ""))
    out["exact_repeat_group_id"] = str(out.get("exact_repeat_group_id", ""))
    out["similarity_group_id"] = str(out.get("similarity_group_id", ""))
    out["event_window_id"] = str(out.get("event_window_id", ""))
    out["event_window_start"] = int(out.get("event_window_start", -1))
    out["event_window_end"] = int(out.get("event_window_end", -1))
    out["portfolio_id"] = str(out.get("portfolio_id", ""))
    out["parameter_hash"] = _compute_parameter_hash(out)
    out["feature_hash"] = _compute_feature_hash(out)
    out["workload_regime"] = out.get("workload_regime", FAMILY_REGIME_MAP.get(family, "unknown"))
    return out


def _make_base_request(template: Dict[str, Any], seed_value: int, contract_suffix: str) -> Dict[str, Any]:
    row = dict(template)
    row["contract_id"] = f"{template['template_id']}{contract_suffix}"
    row["deterministic_seed"] = int(seed_value)
    row["random_seed"] = int(seed_value)
    return row


def _generate_exact_repeat_pricing(
    *, lane_id: str, request_count: int, seed: int, template_bank: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    groups = 4 if lane_id == LANE_A_ID else 12
    anchors = template_bank[: max(4, min(len(template_bank), groups))]
    rows: List[Dict[str, Any]] = []
    for idx in range(int(request_count)):
        group_id = idx % groups
        tpl = anchors[group_id % len(anchors)]
        row = _make_base_request(
            tpl,
            seed_value=int(seed) + group_id,
            contract_suffix=f"_exact_{group_id:02d}",
        )
        row["cluster_id"] = f"exact_cluster_{group_id:02d}"
        row["exact_repeat_group_id"] = f"exact_group_{group_id:03d}"
        row["similarity_group_id"] = f"exact_group_{group_id:03d}"
        rows.append(_finalize_request(row=row, lane_id=lane_id, family="exact_repeat_pricing", index=idx))
    return rows


def _generate_near_repeat_pricing(
    *, lane_id: str, request_count: int, seed: int, template_bank: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    cluster_count = 4 if lane_id == LANE_A_ID else 10
    drift_scale = 0.006 if lane_id == LANE_A_ID else 0.045
    path_steps = [0, 500, 1_000] if lane_id == LANE_A_ID else [0, 2_000, 5_000, 8_000]
    rows: List[Dict[str, Any]] = []
    for idx in range(int(request_count)):
        cluster = idx % cluster_count
        tpl = template_bank[(cluster + 1) % len(template_bank)]
        drift_slot = (idx // cluster_count) % 5
        drift = (-2 + drift_slot) * drift_scale
        row = _make_base_request(
            tpl,
            seed_value=int(seed) + (cluster if lane_id == LANE_A_ID else idx),
            contract_suffix=f"_near_{cluster:02d}_{drift_slot:02d}",
        )
        row["S0"] = round(float(tpl["S0"]) * (1.0 + drift), 6)
        row["K"] = round(float(tpl["K"]) * (1.0 + drift * 1.1), 6)
        row["sigma"] = round(float(tpl["sigma"]) * (1.0 + drift * 1.4), 6)
        row["T"] = round(max(0.05, float(tpl["T"]) * (1.0 + drift * 0.8)), 6)
        row["num_paths"] = max(1, int(tpl["num_paths"]) + int(path_steps[drift_slot % len(path_steps)]))
        row["cluster_id"] = f"near_cluster_{cluster:02d}"
        row["similarity_group_id"] = f"near_cluster_{cluster:02d}"
        if lane_id == LANE_A_ID and drift_slot == 2:
            row["exact_repeat_group_id"] = f"near_exact_echo_{cluster:02d}"
            row["random_seed"] = int(seed) + cluster
        rows.append(_finalize_request(row=row, lane_id=lane_id, family="near_repeat_pricing", index=idx))
    return rows


def _generate_path_ladder_pricing(
    *, lane_id: str, request_count: int, seed: int, template_bank: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    ladder = [4_000, 8_000, 12_000, 16_000] if lane_id == LANE_A_ID else [2_000, 6_000, 12_000, 24_000, 48_000]
    rows: List[Dict[str, Any]] = []
    for idx in range(int(request_count)):
        tpl = template_bank[idx % len(template_bank)]
        ladder_idx = (idx // len(template_bank)) % len(ladder)
        row = _make_base_request(
            tpl,
            seed_value=int(seed) + (ladder_idx if lane_id == LANE_A_ID else idx),
            contract_suffix=f"_path_{ladder_idx:02d}",
        )
        row["num_paths"] = int(ladder[ladder_idx])
        row["cluster_id"] = f"path_ladder_{ladder_idx:02d}"
        row["similarity_group_id"] = f"path_ladder_{idx % 3:02d}" if lane_id == LANE_A_ID else ""
        if lane_id == LANE_A_ID and ladder_idx in (1, 2):
            row["exact_repeat_group_id"] = f"path_exact_{idx % 6:02d}"
        rows.append(_finalize_request(row=row, lane_id=lane_id, family="path_ladder_pricing", index=idx))
    return rows


def _generate_portfolio_cluster_condensation(
    *, lane_id: str, request_count: int, seed: int, template_bank: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    cluster_count = 5 if lane_id == LANE_A_ID else 12
    perturb = 0.01 if lane_id == LANE_A_ID else 0.06
    rows: List[Dict[str, Any]] = []
    for idx in range(int(request_count)):
        cluster = idx % cluster_count
        tpl = template_bank[(cluster + 2) % len(template_bank)]
        slot = (idx // cluster_count) % 4
        drift = (slot - 1.5) * perturb
        row = _make_base_request(
            tpl,
            seed_value=int(seed) + (cluster if lane_id == LANE_A_ID else idx),
            contract_suffix=f"_portfolio_{cluster:02d}_{slot:02d}",
        )
        row["S0"] = round(float(tpl["S0"]) * (1.0 + drift), 6)
        row["K"] = round(float(tpl["K"]) * (1.0 + drift * 1.2), 6)
        row["sigma"] = round(float(tpl["sigma"]) * (1.0 + drift * 0.7), 6)
        row["portfolio_id"] = f"portfolio_cluster_{cluster:02d}_member_{slot:02d}"
        row["cluster_id"] = f"portfolio_cluster_{cluster:02d}"
        row["similarity_group_id"] = f"portfolio_cluster_{cluster:02d}"
        if lane_id == LANE_A_ID and slot in (1, 2):
            row["exact_repeat_group_id"] = f"portfolio_repeat_{cluster:02d}"
        rows.append(
            _finalize_request(
                row=row,
                lane_id=lane_id,
                family="portfolio_cluster_condensation",
                index=idx,
            )
        )
    return rows


def _generate_overlapping_event_window_rebuild(
    *, lane_id: str, request_count: int, seed: int, template_bank: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    overlap_stride = 2 if lane_id == LANE_A_ID else 11
    window_len = 12 if lane_id == LANE_A_ID else 7
    stream_count = 3 if lane_id == LANE_A_ID else 10
    for idx in range(int(request_count)):
        stream_id = idx % stream_count
        tpl = template_bank[(stream_id + 3) % len(template_bank)]
        start = (idx * overlap_stride + stream_id) % 252
        end = min(252, start + window_len)
        row = _make_base_request(
            tpl,
            seed_value=int(seed) + (stream_id if lane_id == LANE_A_ID else idx),
            contract_suffix=f"_window_{stream_id:02d}_{start:03d}",
        )
        row["T"] = round(max(0.05, float(end - start) / 252.0), 6)
        row["sigma"] = round(float(tpl["sigma"]) * (1.0 + (stream_id * 0.01)), 6)
        row["event_window_id"] = f"stream_{stream_id:02d}:{start:03d}-{end:03d}"
        row["event_window_start"] = int(start)
        row["event_window_end"] = int(end)
        row["cluster_id"] = f"event_stream_{stream_id:02d}"
        row["similarity_group_id"] = f"event_stream_{stream_id:02d}" if lane_id == LANE_A_ID else ""
        if lane_id == LANE_A_ID and (idx % 6) in (0, 1):
            row["exact_repeat_group_id"] = f"event_repeat_{stream_id:02d}"
        rows.append(
            _finalize_request(
                row=row,
                lane_id=lane_id,
                family="overlapping_event_window_rebuild",
                index=idx,
            )
        )
    return rows


def _generate_stress_churn_pricing(
    *, lane_id: str, request_count: int, seed: int, template_bank: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    rng = Random(int(seed) + (99 if lane_id == LANE_B_ID else 11))
    rows: List[Dict[str, Any]] = []
    for idx in range(int(request_count)):
        tpl = template_bank[rng.randrange(0, len(template_bank))]
        unique_seed = int(seed) + (idx if lane_id == LANE_B_ID else (idx % 9))
        drift_scale = 0.09 if lane_id == LANE_B_ID else 0.02
        drift = (rng.random() - 0.5) * 2.0 * drift_scale
        row = _make_base_request(
            tpl,
            seed_value=unique_seed,
            contract_suffix=f"_stress_{idx:05d}",
        )
        row["S0"] = round(float(tpl["S0"]) * (1.0 + drift), 6)
        row["K"] = round(float(tpl["K"]) * (1.0 - drift * 0.9), 6)
        row["sigma"] = round(max(0.05, float(tpl["sigma"]) * (1.0 + abs(drift) * 1.8)), 6)
        row["T"] = round(max(0.05, float(tpl["T"]) * (1.0 - drift * 0.5)), 6)
        row["num_paths"] = max(1, int(float(tpl["num_paths"]) * (1.0 + abs(drift) * (4.0 if lane_id == LANE_B_ID else 1.5))))
        row["cluster_id"] = "stress_churn"
        row["similarity_group_id"] = ""
        if lane_id == LANE_A_ID and (idx % 7) == 0:
            row["exact_repeat_group_id"] = "stress_anchor"
            row["random_seed"] = int(seed) + 3
        rows.append(_finalize_request(row=row, lane_id=lane_id, family="stress_churn_pricing", index=idx))
    return rows


def _generate_intraday_scenario_ladder(
    *, lane_id: str, request_count: int, seed: int, template_bank: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Intraday shock sequence: same book repriced under small successive market perturbations."""
    scenarios = 5 if lane_id == LANE_A_ID else 10
    books = 4 if lane_id == LANE_A_ID else 8
    shock_scale = 0.004 if lane_id == LANE_A_ID else 0.012
    rows: List[Dict[str, Any]] = []
    for idx in range(int(request_count)):
        book = idx % books
        scenario_step = (idx // books) % scenarios
        tpl = template_bank[book % len(template_bank)]
        shock = (scenario_step - scenarios // 2) * shock_scale
        row = _make_base_request(
            tpl,
            seed_value=int(seed) + (book if lane_id == LANE_A_ID else idx),
            contract_suffix=f"_intra_{book:02d}_{scenario_step:02d}",
        )
        row["S0"] = round(float(tpl["S0"]) * (1.0 + shock), 6)
        row["K"] = round(float(tpl["K"]) * (1.0 + shock * 0.3), 6)
        row["sigma"] = round(max(0.05, float(tpl["sigma"]) * (1.0 + abs(shock) * 2.0)), 6)
        row["cluster_id"] = f"intraday_book_{book:02d}"
        row["similarity_group_id"] = f"intraday_book_{book:02d}"
        if scenario_step == 0:
            row["exact_repeat_group_id"] = f"intraday_anchor_{book:02d}"
        rows.append(_finalize_request(row=row, lane_id=lane_id, family="intraday_scenario_ladder", index=idx))
    return rows


def _generate_cross_sectional_basket(
    *, lane_id: str, request_count: int, seed: int, template_bank: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Basket repricing: many assets with shared factors and partial overlap."""
    basket_size = 6 if lane_id == LANE_A_ID else 15
    factor_groups = 3 if lane_id == LANE_A_ID else 6
    rng = Random(int(seed) + 77)
    rows: List[Dict[str, Any]] = []
    for idx in range(int(request_count)):
        asset_idx = idx % basket_size
        factor_group = asset_idx % factor_groups
        tpl = template_bank[(asset_idx + factor_group) % len(template_bank)]
        asset_drift = (rng.random() - 0.5) * 0.02
        row = _make_base_request(
            tpl,
            seed_value=int(seed) + (factor_group if lane_id == LANE_A_ID else idx),
            contract_suffix=f"_basket_{asset_idx:02d}_{idx // basket_size:03d}",
        )
        row["S0"] = round(float(tpl["S0"]) * (1.0 + asset_drift), 6)
        row["K"] = round(float(tpl["K"]) * (1.0 + asset_drift * 0.8), 6)
        row["sigma"] = round(max(0.05, float(tpl["sigma"]) * (1.0 + abs(asset_drift))), 6)
        row["portfolio_id"] = f"basket_factor_{factor_group:02d}"
        row["cluster_id"] = f"basket_factor_{factor_group:02d}"
        row["similarity_group_id"] = f"basket_factor_{factor_group:02d}"
        if lane_id == LANE_A_ID and (idx // basket_size) > 0 and asset_drift < 0.005:
            row["exact_repeat_group_id"] = f"basket_repeat_{factor_group:02d}"
        rows.append(_finalize_request(row=row, lane_id=lane_id, family="cross_sectional_basket", index=idx))
    return rows


def _generate_rolling_horizon_refresh(
    *, lane_id: str, request_count: int, seed: int, template_bank: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Rolling horizon: repeated recomputation over advancing time windows with carry-forward."""
    horizon_step = 5 if lane_id == LANE_A_ID else 10
    instruments = 4 if lane_id == LANE_A_ID else 8
    rows: List[Dict[str, Any]] = []
    for idx in range(int(request_count)):
        instrument = idx % instruments
        horizon_idx = (idx // instruments) % 20
        tpl = template_bank[instrument % len(template_bank)]
        start_day = horizon_idx * horizon_step
        end_day = start_day + horizon_step + (10 if lane_id == LANE_A_ID else 20)
        overlap_ratio = round(float(horizon_step) / float(end_day - start_day), 4)
        row = _make_base_request(
            tpl,
            seed_value=int(seed) + (instrument if lane_id == LANE_A_ID else idx),
            contract_suffix=f"_roll_{instrument:02d}_{horizon_idx:02d}",
        )
        row["T"] = round(max(0.05, float(end_day - start_day) / 252.0), 6)
        row["event_window_id"] = f"roll_{instrument:02d}:{start_day:03d}-{end_day:03d}"
        row["event_window_start"] = int(start_day)
        row["event_window_end"] = int(end_day)
        row["cluster_id"] = f"roll_instrument_{instrument:02d}"
        row["similarity_group_id"] = f"roll_instrument_{instrument:02d}"
        if horizon_idx > 0 and lane_id == LANE_A_ID:
            row["exact_repeat_group_id"] = f"roll_carry_{instrument:02d}"
        rows.append(_finalize_request(row=row, lane_id=lane_id, family="rolling_horizon_refresh", index=idx))
    return rows


def _generate_hotset_coldset_mixed(
    *, lane_id: str, request_count: int, seed: int, template_bank: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Hotset/coldset: stable hot keys that recur frequently, cold keys that appear intermittently."""
    hot_count = 3 if lane_id == LANE_A_ID else 5
    cold_count = 5 if lane_id == LANE_A_ID else 12
    hot_fraction = 0.70 if lane_id == LANE_A_ID else 0.55
    rng = Random(int(seed) + 33)
    hot_templates = template_bank[:hot_count]
    cold_templates = template_bank[hot_count: hot_count + cold_count]
    if not cold_templates:
        cold_templates = template_bank
    rows: List[Dict[str, Any]] = []
    for idx in range(int(request_count)):
        is_hot = rng.random() < hot_fraction
        if is_hot:
            hot_idx = idx % hot_count
            tpl = hot_templates[hot_idx % len(hot_templates)]
            row = _make_base_request(
                tpl,
                seed_value=int(seed) + hot_idx,
                contract_suffix=f"_hot_{hot_idx:02d}",
            )
            row["cluster_id"] = f"hotset_{hot_idx:02d}"
            row["exact_repeat_group_id"] = f"hotset_{hot_idx:02d}"
            row["similarity_group_id"] = f"hotset_{hot_idx:02d}"
        else:
            cold_idx = rng.randrange(0, cold_count)
            tpl = cold_templates[cold_idx % len(cold_templates)]
            cold_drift = (rng.random() - 0.5) * 0.03
            row = _make_base_request(
                tpl,
                seed_value=int(seed) + cold_count + idx,
                contract_suffix=f"_cold_{cold_idx:02d}_{idx:05d}",
            )
            row["S0"] = round(float(tpl["S0"]) * (1.0 + cold_drift), 6)
            row["sigma"] = round(max(0.05, float(tpl["sigma"]) * (1.0 + abs(cold_drift))), 6)
            row["cluster_id"] = f"coldset_{cold_idx:02d}"
            row["similarity_group_id"] = ""
        rows.append(_finalize_request(row=row, lane_id=lane_id, family="hotset_coldset_mixed", index=idx))
    return rows


def _generate_parameter_shock_grid(
    *, lane_id: str, request_count: int, seed: int, template_bank: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Systematic grid over pricing parameters: ideal for tolerance studies and near-neighbor analysis."""
    sigma_steps = [0.10, 0.20, 0.30, 0.40, 0.50] if lane_id == LANE_A_ID else [0.08, 0.15, 0.22, 0.30, 0.40, 0.55]
    s0_offsets = [-5.0, -2.0, 0.0, 2.0, 5.0] if lane_id == LANE_A_ID else [-8.0, -4.0, -1.0, 0.0, 1.0, 4.0, 8.0]
    anchor_tpl = template_bank[0]
    rows: List[Dict[str, Any]] = []
    for idx in range(int(request_count)):
        sigma_idx = idx % len(sigma_steps)
        s0_idx = (idx // len(sigma_steps)) % len(s0_offsets)
        grid_cell = f"g{sigma_idx}_{s0_idx}"
        row = _make_base_request(
            anchor_tpl,
            seed_value=int(seed) + (sigma_idx * 10 + s0_idx if lane_id == LANE_A_ID else idx),
            contract_suffix=f"_grid_{grid_cell}",
        )
        row["S0"] = round(float(anchor_tpl["S0"]) + s0_offsets[s0_idx], 6)
        row["K"] = float(anchor_tpl["K"])
        row["sigma"] = sigma_steps[sigma_idx]
        row["cluster_id"] = f"grid_sigma_{sigma_idx:02d}"
        row["similarity_group_id"] = f"grid_sigma_{sigma_idx:02d}"
        if s0_idx == len(s0_offsets) // 2:
            row["exact_repeat_group_id"] = f"grid_anchor_sigma_{sigma_idx:02d}"
        rows.append(_finalize_request(row=row, lane_id=lane_id, family="parameter_shock_grid", index=idx))
    return rows


def generate_repeated_workload_requests(
    *,
    scale_label: str = "standard",
    seed: int = 123,
    lane_selection: str = "both",
    template_bank_id: str = TEMPLATE_BANK_ID_DEFAULT,
    workload_families: Optional[Sequence[str]] = None,
) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """Generate deterministic workload families grouped by lane then family."""
    resolved_scale = _validate_scale_label(scale_label)
    selected_lanes = _normalize_lane_selection(lane_selection)
    selected_families = _normalize_family_selection(workload_families)
    template_bank = build_template_bank(template_bank_id=template_bank_id)

    out: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    for lane_idx, lane_id in enumerate(selected_lanes, start=1):
        lane_payload: Dict[str, List[Dict[str, Any]]] = {}
        for family_idx, family in enumerate(selected_families, start=1):
            request_count = int(SCALE_PROFILES[resolved_scale][family])
            family_seed = int(seed) + lane_idx * 1_000 + family_idx * 37
            if family == "exact_repeat_pricing":
                rows = _generate_exact_repeat_pricing(
                    lane_id=lane_id,
                    request_count=request_count,
                    seed=family_seed,
                    template_bank=template_bank,
                )
            elif family == "near_repeat_pricing":
                rows = _generate_near_repeat_pricing(
                    lane_id=lane_id,
                    request_count=request_count,
                    seed=family_seed,
                    template_bank=template_bank,
                )
            elif family == "path_ladder_pricing":
                rows = _generate_path_ladder_pricing(
                    lane_id=lane_id,
                    request_count=request_count,
                    seed=family_seed,
                    template_bank=template_bank,
                )
            elif family == "portfolio_cluster_condensation":
                rows = _generate_portfolio_cluster_condensation(
                    lane_id=lane_id,
                    request_count=request_count,
                    seed=family_seed,
                    template_bank=template_bank,
                )
            elif family == "overlapping_event_window_rebuild":
                rows = _generate_overlapping_event_window_rebuild(
                    lane_id=lane_id,
                    request_count=request_count,
                    seed=family_seed,
                    template_bank=template_bank,
                )
            elif family == "stress_churn_pricing":
                rows = _generate_stress_churn_pricing(
                    lane_id=lane_id,
                    request_count=request_count,
                    seed=family_seed,
                    template_bank=template_bank,
                )
            elif family == "intraday_scenario_ladder":
                rows = _generate_intraday_scenario_ladder(
                    lane_id=lane_id,
                    request_count=request_count,
                    seed=family_seed,
                    template_bank=template_bank,
                )
            elif family == "cross_sectional_basket":
                rows = _generate_cross_sectional_basket(
                    lane_id=lane_id,
                    request_count=request_count,
                    seed=family_seed,
                    template_bank=template_bank,
                )
            elif family == "rolling_horizon_refresh":
                rows = _generate_rolling_horizon_refresh(
                    lane_id=lane_id,
                    request_count=request_count,
                    seed=family_seed,
                    template_bank=template_bank,
                )
            elif family == "hotset_coldset_mixed":
                rows = _generate_hotset_coldset_mixed(
                    lane_id=lane_id,
                    request_count=request_count,
                    seed=family_seed,
                    template_bank=template_bank,
                )
            elif family == "parameter_shock_grid":
                rows = _generate_parameter_shock_grid(
                    lane_id=lane_id,
                    request_count=request_count,
                    seed=family_seed,
                    template_bank=template_bank,
                )
            else:
                raise ValueError(f"Unsupported workload family {family!r}")
            lane_payload[family] = rows
        out[lane_id] = lane_payload
    return out

