"""Canonical event-set library for event-window comparison workloads.

Defines locked Sets A-E, locked window policy, and a ruleset-driven Set E with
manual-review metadata for defensible comparison studies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


# Locked default multi-day subset (canonical default)
LOCKED_MULTI_DAY_WINDOWS: Tuple[str, ...] = (
    "d-1_to_d+1",
    "d-5_to_d+5",
    "d-10_to_d+10",
    "d-20_to_d+20",
)

# Intraday stress extensions (optional)
LOCKED_INTRADAY_SLICES: Tuple[str, ...] = (
    "full_day",
    "centered_2h_stress",
    "first_trading_hour",
    "last_trading_hour",
)

CATEGORY_CRISIS = "crisis / regime stress"
CATEGORY_MACRO = "macro / rates"
CATEGORY_BANKING = "banking / credit stress"
CATEGORY_LIQUIDITY = "liquidity dislocation"
CATEGORY_EARNINGS = "earnings shock"
CATEGORY_COMMODITY = "commodity / inflation shock"

# Target: 39 events with slight macro/rates + crisis overweight.
SET_E_RULESET_TARGETS: Tuple[Tuple[str, int], ...] = (
    (CATEGORY_CRISIS, 9),
    (CATEGORY_MACRO, 11),
    (CATEGORY_BANKING, 6),
    (CATEGORY_LIQUIDITY, 5),
    (CATEGORY_EARNINGS, 4),
    (CATEGORY_COMMODITY, 4),
)


@dataclass(frozen=True)
class EventSetMember:
    """One event definition inside an event set."""

    event_id: str
    event_label: str
    category_label: str
    anchor_start: str
    anchor_end: str
    default_window_family_labels: Tuple[str, ...] = field(default_factory=tuple)
    notes: str = ""
    symbol_universe_hint: Tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_label": self.event_label,
            "category_label": self.category_label,
            "anchor_start": self.anchor_start,
            "anchor_end": self.anchor_end,
            "default_window_family_labels": list(self.default_window_family_labels),
            "notes": self.notes,
            "symbol_universe_hint": list(self.symbol_universe_hint),
        }


@dataclass(frozen=True)
class EventSetDefinition:
    """Curated event set used for comparison and workload studies."""

    event_set_id: str
    event_set_label: str
    objective_note: str
    members: Tuple[EventSetMember, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_set_id": self.event_set_id,
            "event_set_label": self.event_set_label,
            "objective_note": self.objective_note,
            "members": [m.to_dict() for m in self.members],
        }


def _member(
    *,
    event_id: str,
    event_label: str,
    category_label: str,
    anchor_start: str,
    anchor_end: str,
    notes: str,
    symbols: Tuple[str, ...] = (),
) -> EventSetMember:
    return EventSetMember(
        event_id=event_id,
        event_label=event_label,
        category_label=category_label,
        anchor_start=anchor_start,
        anchor_end=anchor_end,
        default_window_family_labels=LOCKED_MULTI_DAY_WINDOWS,
        notes=notes,
        symbol_universe_hint=symbols,
    )


def _set_e_candidate_pool() -> Dict[str, Tuple[EventSetMember, ...]]:
    return {
        CATEGORY_CRISIS: (
            _member(
                event_id="gfc_lehman_collapse",
                event_label="Lehman collapse / GFC escalation",
                category_label=CATEGORY_CRISIS,
                anchor_start="2008-09-15",
                anchor_end="2008-10-10",
                notes="Systemic crisis benchmark for severe cross-asset stress.",
                symbols=("SPY", "XLF", "JPM", "BAC", "GS"),
            ),
            _member(
                event_id="us_debt_downgrade_2011",
                event_label="US debt downgrade and risk-off (2011)",
                category_label=CATEGORY_CRISIS,
                anchor_start="2011-07-29",
                anchor_end="2011-08-12",
                notes="Policy credibility shock with volatility expansion.",
                symbols=("SPY", "QQQ", "IWM", "TLT"),
            ),
            _member(
                event_id="euro_sovereign_crisis_2011",
                event_label="Euro sovereign crisis escalation (2011)",
                category_label=CATEGORY_CRISIS,
                anchor_start="2011-08-01",
                anchor_end="2011-10-04",
                notes="Global contagion stress with central-bank response risk.",
                symbols=("SPY", "FEZ", "EUFN", "TLT"),
            ),
            _member(
                event_id="china_devaluation_shock_2015",
                event_label="China devaluation shock (2015)",
                category_label=CATEGORY_CRISIS,
                anchor_start="2015-08-10",
                anchor_end="2015-08-31",
                notes="Risk-off regime transition with commodity spillover.",
                symbols=("SPY", "EEM", "FXI", "USO"),
            ),
            _member(
                event_id="global_growth_scare_2016",
                event_label="Global growth scare (Q1 2016)",
                category_label=CATEGORY_CRISIS,
                anchor_start="2016-01-04",
                anchor_end="2016-02-12",
                notes="Broad drawdown period with volatility clustering.",
                symbols=("SPY", "HYG", "XLE", "USO"),
            ),
            _member(
                event_id="volmageddon_2018",
                event_label="Volmageddon volatility shock (Feb 2018)",
                category_label=CATEGORY_CRISIS,
                anchor_start="2018-02-02",
                anchor_end="2018-02-09",
                notes="Short-vol unwind stress for nonlinear crash dynamics.",
                symbols=("SPY", "VXX"),
            ),
            _member(
                event_id="covid_crash",
                event_label="COVID-19 global equity crash",
                category_label=CATEGORY_CRISIS,
                anchor_start="2020-02-20",
                anchor_end="2020-03-23",
                notes="Core modern systemic crash benchmark.",
                symbols=("SPY", "QQQ", "XLF", "JPM", "BAC", "AAPL", "MSFT"),
            ),
            _member(
                event_id="uk_gilt_crisis_2022",
                event_label="UK gilt crisis and global spillover (2022)",
                category_label=CATEGORY_CRISIS,
                anchor_start="2022-09-22",
                anchor_end="2022-10-14",
                notes="Rates-vol feedback regime with liquidity fragility.",
                symbols=("TLT", "IEF", "SPY"),
            ),
            _member(
                event_id="middle_east_risk_off_2023",
                event_label="Middle East geopolitical risk-off wave (2023)",
                category_label=CATEGORY_CRISIS,
                anchor_start="2023-10-06",
                anchor_end="2023-10-16",
                notes="Geopolitical flight-to-quality repricing episode.",
                symbols=("SPY", "GLD", "USO"),
            ),
            _member(
                event_id="yen_carry_unwind_2024",
                event_label="Yen carry unwind volatility pulse (2024)",
                category_label=CATEGORY_CRISIS,
                anchor_start="2024-07-31",
                anchor_end="2024-08-08",
                notes="Reserve crisis candidate for future Set E variants.",
                symbols=("SPY", "IWM", "FXY"),
            ),
        ),
        CATEGORY_MACRO: (
            _member(
                event_id="ecb_whatever_it_takes_2012",
                event_label="ECB whatever-it-takes regime shift (2012)",
                category_label=CATEGORY_MACRO,
                anchor_start="2012-07-23",
                anchor_end="2012-08-03",
                notes="Policy communication shock with rates/credit repricing.",
                symbols=("SPY", "FEZ", "EUFN"),
            ),
            _member(
                event_id="taper_tantrum_2013",
                event_label="US taper tantrum (2013)",
                category_label=CATEGORY_MACRO,
                anchor_start="2013-05-20",
                anchor_end="2013-06-28",
                notes="Canonical duration shock and macro repricing.",
                symbols=("TLT", "IEF", "SPY", "EEM"),
            ),
            _member(
                event_id="fed_liftoff_2015",
                event_label="Fed first post-crisis rate hike (2015)",
                category_label=CATEGORY_MACRO,
                anchor_start="2015-12-14",
                anchor_end="2015-12-18",
                notes="Policy regime transition for rates-sensitive factors.",
                symbols=("TLT", "SPY", "XLF"),
            ),
            _member(
                event_id="reflation_repricing_2016",
                event_label="US election reflation repricing (2016)",
                category_label=CATEGORY_MACRO,
                anchor_start="2016-11-08",
                anchor_end="2016-11-18",
                notes="Macro rotation with sector and duration shifts.",
                symbols=("SPY", "XLF", "XLE", "TLT"),
            ),
            _member(
                event_id="q4_2018_fed_tightening",
                event_label="Q4 2018 Fed-tightening stress",
                category_label=CATEGORY_MACRO,
                anchor_start="2018-10-01",
                anchor_end="2018-12-24",
                notes="Late-cycle tightening stress and risk-premia expansion.",
                symbols=("SPY", "QQQ", "TLT"),
            ),
            _member(
                event_id="fomc_emergency_cut_2020",
                event_label="Emergency Fed cuts and policy reset (2020)",
                category_label=CATEGORY_MACRO,
                anchor_start="2020-03-03",
                anchor_end="2020-03-16",
                notes="Macro policy shock inside crisis response dynamics.",
                symbols=("SPY", "TLT", "IEF"),
            ),
            _member(
                event_id="cpi_surprise_jun2022",
                event_label="US CPI surprise and repricing (Jun 2022)",
                category_label=CATEGORY_MACRO,
                anchor_start="2022-06-09",
                anchor_end="2022-06-15",
                notes="Inflation surprise with rates-vol transmission.",
                symbols=("SPY", "QQQ", "TLT"),
            ),
            _member(
                event_id="2022_rate_shock",
                event_label="2022 policy-rate shock / duration sell-off",
                category_label=CATEGORY_MACRO,
                anchor_start="2022-06-10",
                anchor_end="2022-10-14",
                notes="Core tightening-cycle anchor for Set C and Set E.",
                symbols=("SPY", "QQQ", "TLT", "IEF", "SHY", "XLF", "XLE"),
            ),
            _member(
                event_id="jackson_hole_tightening_2022",
                event_label="Jackson Hole tightening signal (2022)",
                category_label=CATEGORY_MACRO,
                anchor_start="2022-08-25",
                anchor_end="2022-09-02",
                notes="Forward-guidance shock with sharp rates repricing.",
                symbols=("SPY", "QQQ", "TLT"),
            ),
            _member(
                event_id="boj_ycc_widening_2022",
                event_label="BoJ YCC band widening spillover (Dec 2022)",
                category_label=CATEGORY_MACRO,
                anchor_start="2022-12-19",
                anchor_end="2022-12-23",
                notes="Global rates shock from Japanese policy-constraint change.",
                symbols=("TLT", "IEF", "SPY"),
            ),
            _member(
                event_id="fed_higher_for_longer_2023",
                event_label="Fed higher-for-longer repricing (Sep-Oct 2023)",
                category_label=CATEGORY_MACRO,
                anchor_start="2023-09-18",
                anchor_end="2023-10-27",
                notes="Persistent term-premium repricing regime.",
                symbols=("TLT", "IEF", "SPY", "QQQ"),
            ),
            _member(
                event_id="treasury_supply_repricing_2023",
                event_label="US Treasury supply repricing wave (2023)",
                category_label=CATEGORY_MACRO,
                anchor_start="2023-07-31",
                anchor_end="2023-08-11",
                notes="Reserve macro candidate retained for future variants.",
                symbols=("TLT", "IEF"),
            ),
        ),
        CATEGORY_BANKING: (
            _member(
                event_id="banking_stress_2023",
                event_label="Regional banking stress (2023)",
                category_label=CATEGORY_BANKING,
                anchor_start="2023-03-08",
                anchor_end="2023-03-24",
                notes="Core banking stress anchor for Set D and Set E.",
                symbols=("KRE", "XLF", "JPM", "BAC", "GS", "MS"),
            ),
            _member(
                event_id="svb_failure_week_2023",
                event_label="SVB failure week and funding stress",
                category_label=CATEGORY_BANKING,
                anchor_start="2023-03-09",
                anchor_end="2023-03-17",
                notes="Acute banking-run dynamics and policy backstop transition.",
                symbols=("KRE", "XLF", "JPM"),
            ),
            _member(
                event_id="credit_suisse_at1_wipeout_2023",
                event_label="Credit Suisse AT1 wipeout contagion (2023)",
                category_label=CATEGORY_BANKING,
                anchor_start="2023-03-17",
                anchor_end="2023-03-24",
                notes="Cross-jurisdiction credit-capital repricing stress.",
                symbols=("XLF", "EUFN", "JPM", "GS"),
            ),
            _member(
                event_id="regional_bank_followthrough_may2023",
                event_label="US regional bank follow-through stress (May 2023)",
                category_label=CATEGORY_BANKING,
                anchor_start="2023-05-01",
                anchor_end="2023-05-10",
                notes="Second-wave confidence stress in regional banks.",
                symbols=("KRE", "XLF"),
            ),
            _member(
                event_id="covid_credit_gap_2020",
                event_label="COVID credit dislocation and spread widening (2020)",
                category_label=CATEGORY_BANKING,
                anchor_start="2020-03-09",
                anchor_end="2020-03-27",
                notes="Credit transmission from macro crisis into funding stress.",
                symbols=("HYG", "LQD", "XLF"),
            ),
            _member(
                event_id="china_property_credit_stress_2021",
                event_label="China property-credit stress wave (2021)",
                category_label=CATEGORY_BANKING,
                anchor_start="2021-09-15",
                anchor_end="2021-10-05",
                notes="Credit concentration stress with global risk appetite effects.",
                symbols=("EEM", "FXI", "SPY"),
            ),
            _member(
                event_id="energy_credit_drawdown_2016",
                event_label="Energy-credit drawdown pulse (2016)",
                category_label=CATEGORY_BANKING,
                anchor_start="2016-01-04",
                anchor_end="2016-02-12",
                notes="Reserve banking-credit candidate for future variants.",
                symbols=("HYG", "XLE"),
            ),
        ),
        CATEGORY_LIQUIDITY: (
            _member(
                event_id="march_2020_liquidity_stress",
                event_label="March 2020 liquidity / basis stress",
                category_label=CATEGORY_LIQUIDITY,
                anchor_start="2020-03-09",
                anchor_end="2020-03-20",
                notes="Core liquidity benchmark for Set B and Set E.",
                symbols=("SPY", "QQQ", "IWM", "XLF", "JPM", "BAC", "GS"),
            ),
            _member(
                event_id="flash_crash_may2010",
                event_label="US equity flash crash (May 2010)",
                category_label=CATEGORY_LIQUIDITY,
                anchor_start="2010-05-06",
                anchor_end="2010-05-07",
                notes="Microstructure liquidity-vacuum benchmark.",
                symbols=("SPY", "QQQ", "IWM"),
            ),
            _member(
                event_id="treasury_flash_rally_2014",
                event_label="US Treasury flash rally (Oct 2014)",
                category_label=CATEGORY_LIQUIDITY,
                anchor_start="2014-10-15",
                anchor_end="2014-10-17",
                notes="Rates-market depth shock for cross-asset studies.",
                symbols=("TLT", "IEF"),
            ),
            _member(
                event_id="repo_spike_sep2019",
                event_label="US repo spike and funding stress (Sep 2019)",
                category_label=CATEGORY_LIQUIDITY,
                anchor_start="2019-09-16",
                anchor_end="2019-09-20",
                notes="Short-term funding dislocation with policy intervention.",
                symbols=("SHY", "IEF", "XLF"),
            ),
            _member(
                event_id="uk_gilt_liquidity_gap_2022",
                event_label="UK gilt market liquidity gap (2022)",
                category_label=CATEGORY_LIQUIDITY,
                anchor_start="2022-09-26",
                anchor_end="2022-10-03",
                notes="Forced-liquidity event with convexity stress mechanics.",
                symbols=("TLT", "IEF"),
            ),
            _member(
                event_id="meme_stock_dislocation_2021",
                event_label="Meme-stock flow dislocation (Jan 2021)",
                category_label=CATEGORY_LIQUIDITY,
                anchor_start="2021-01-25",
                anchor_end="2021-02-02",
                notes="Reserve liquidity candidate for equity-desk extension.",
                symbols=("GME", "AMC", "SPY"),
            ),
        ),
        CATEGORY_EARNINGS: (
            _member(
                event_id="meta_earnings_gap_feb2022",
                event_label="META earnings gap-down shock (Feb 2022)",
                category_label=CATEGORY_EARNINGS,
                anchor_start="2022-02-02",
                anchor_end="2022-02-04",
                notes="Large-cap single-name earnings discontinuity benchmark.",
                symbols=("META", "QQQ", "SPY"),
            ),
            _member(
                event_id="nflx_subscriber_shock_apr2022",
                event_label="NFLX subscriber shock (Apr 2022)",
                category_label=CATEGORY_EARNINGS,
                anchor_start="2022-04-19",
                anchor_end="2022-04-22",
                notes="Idiosyncratic fundamental shock with factor spillover.",
                symbols=("NFLX", "QQQ"),
            ),
            _member(
                event_id="amd_guidance_cut_oct2022",
                event_label="AMD guidance cut and semis repricing (Oct 2022)",
                category_label=CATEGORY_EARNINGS,
                anchor_start="2022-10-06",
                anchor_end="2022-10-11",
                notes="Sector-linked earnings warning and propagation.",
                symbols=("AMD", "NVDA", "SOXX"),
            ),
            _member(
                event_id="nvda_guidance_repricing_may2023",
                event_label="NVDA guidance repricing and AI-beta jump (May 2023)",
                category_label=CATEGORY_EARNINGS,
                anchor_start="2023-05-24",
                anchor_end="2023-05-30",
                notes="Positive earnings shock with broad benchmark impact.",
                symbols=("NVDA", "SOXX", "QQQ"),
            ),
            _member(
                event_id="tsla_margin_surprise_apr2024",
                event_label="TSLA margin surprise repricing (Apr 2024)",
                category_label=CATEGORY_EARNINGS,
                anchor_start="2024-04-22",
                anchor_end="2024-04-26",
                notes="Reserve earnings candidate for future extensions.",
                symbols=("TSLA", "QQQ"),
            ),
        ),
        CATEGORY_COMMODITY: (
            _member(
                event_id="brent_oil_collapse_2014",
                event_label="Brent oil collapse wave (2014)",
                category_label=CATEGORY_COMMODITY,
                anchor_start="2014-11-03",
                anchor_end="2014-12-19",
                notes="Energy-led inflation regime break with credit spillover.",
                symbols=("USO", "XLE", "SPY"),
            ),
            _member(
                event_id="commodity_rebound_q1_2016",
                event_label="Commodity rebound and inflation turn (Q1 2016)",
                category_label=CATEGORY_COMMODITY,
                anchor_start="2016-02-11",
                anchor_end="2016-03-11",
                notes="Commodity beta rebound and inflation transition.",
                symbols=("USO", "GLD", "XLE"),
            ),
            _member(
                event_id="russia_ukraine_energy_shock_2022",
                event_label="Russia-Ukraine energy and inflation shock (2022)",
                category_label=CATEGORY_COMMODITY,
                anchor_start="2022-02-24",
                anchor_end="2022-03-11",
                notes="Acute commodity and inflation pass-through event.",
                symbols=("USO", "XLE", "GLD"),
            ),
            _member(
                event_id="commodity_spike_placeholder",
                event_label="Commodity spike / energy stress (placeholder)",
                category_label=CATEGORY_COMMODITY,
                anchor_start="2022-02-24",
                anchor_end="2022-03-04",
                notes="Compatibility placeholder retained from prior canonical state.",
                symbols=("XLE", "USO", "SPY"),
            ),
            _member(
                event_id="shipping_inflation_pulse_2021",
                event_label="Global shipping inflation pulse (2021)",
                category_label=CATEGORY_COMMODITY,
                anchor_start="2021-08-16",
                anchor_end="2021-09-15",
                notes="Reserve commodity/inflation candidate for future variants.",
                symbols=("XLI", "XLB", "SPY"),
            ),
        ),
    }


def _build_set_e_members_from_ruleset(
    *,
    ruleset_targets: Sequence[Tuple[str, int]],
    candidate_pool: Mapping[str, Sequence[EventSetMember]],
) -> Tuple[EventSetMember, ...]:
    selected: List[EventSetMember] = []
    for category, target in ruleset_targets:
        pool = list(candidate_pool.get(category, ()))
        if len(pool) < target:
            raise ValueError(f"Set E ruleset requires {target} events for {category}, found {len(pool)}")
        selected.extend(pool[:target])
    ids = [m.event_id for m in selected]
    if len(ids) != len(set(ids)):
        raise ValueError("Set E ruleset produced duplicate event_ids")
    return tuple(selected)


def set_e_manual_review_summary() -> Dict[str, Any]:
    """Manual-review summary for Set E composition and weighting checks."""
    members = _build_set_e_members_from_ruleset(
        ruleset_targets=SET_E_RULESET_TARGETS,
        candidate_pool=_set_e_candidate_pool(),
    )
    counts: Dict[str, int] = {}
    for m in members:
        counts[m.category_label] = counts.get(m.category_label, 0) + 1
    total = len(members)
    macro_plus_crisis = counts.get(CATEGORY_MACRO, 0) + counts.get(CATEGORY_CRISIS, 0)
    return {
        "target_event_count_range": "35-40",
        "selected_event_count": total,
        "category_counts": counts,
        "macro_plus_crisis_share": macro_plus_crisis / max(1, total),
        "composition_checks": {
            "within_target_range": 35 <= total <= 40,
            "all_required_categories_present": len(counts) == 6,
            "macro_crisis_overweight": macro_plus_crisis >= max(counts.values()),
        },
        "manual_review_note": (
            "Set E is generated from fixed category targets and reviewed for category "
            "balance. A later comparison-phase extension should add an equity-desk-style "
            "library with a larger earnings-shock share."
        ),
    }


def locked_window_policy_manifest() -> Dict[str, Any]:
    """Return the locked default window policy and intraday extensions."""
    return {
        "default_multi_day_windows": list(LOCKED_MULTI_DAY_WINDOWS),
        "intraday_slice_extensions": list(LOCKED_INTRADAY_SLICES),
        "default_policy_note": (
            "Canonical default is multi-day windows. Intraday slices are optional "
            "extensions for stress/microstructure/cache inspection."
        ),
    }


def canonical_event_set_library() -> Tuple[EventSetDefinition, ...]:
    """Five locked event sets (A-E) for event-library comparison."""
    set_e_members = _build_set_e_members_from_ruleset(
        ruleset_targets=SET_E_RULESET_TARGETS,
        candidate_pool=_set_e_candidate_pool(),
    )
    return (
        EventSetDefinition(
            event_set_id="set_a_covid_crash",
            event_set_label="Set A - COVID crash",
            objective_note="Anchor global crash regime baseline for stress alignment.",
            members=(
                _member(
                    event_id="covid_crash",
                    event_label="COVID-19 global equity crash",
                    category_label=CATEGORY_CRISIS,
                    anchor_start="2020-02-20",
                    anchor_end="2020-03-23",
                    notes="High-value systemic stress anchor with broad cross-asset spillover.",
                    symbols=("SPY", "QQQ", "XLF", "JPM", "BAC", "AAPL", "MSFT"),
                ),
            ),
        ),
        EventSetDefinition(
            event_set_id="set_b_march_2020_liquidity",
            event_set_label="Set B - March 2020 liquidity stress",
            objective_note="Liquidity dislocation and basis/market-depth stress anchor.",
            members=(
                _member(
                    event_id="march_2020_liquidity_stress",
                    event_label="March 2020 liquidity / basis stress",
                    category_label=CATEGORY_LIQUIDITY,
                    anchor_start="2020-03-09",
                    anchor_end="2020-03-20",
                    notes="Fed intervention period; intraday fragmentation and spread stress.",
                    symbols=("SPY", "QQQ", "IWM", "XLF", "JPM", "BAC", "GS"),
                ),
            ),
        ),
        EventSetDefinition(
            event_set_id="set_c_2022_rate_shock",
            event_set_label="Set C - 2022 rate shock",
            objective_note="Macro/rates tightening regime anchor.",
            members=(
                _member(
                    event_id="2022_rate_shock",
                    event_label="2022 policy-rate shock / duration sell-off",
                    category_label=CATEGORY_MACRO,
                    anchor_start="2022-06-10",
                    anchor_end="2022-10-14",
                    notes="Duration shock with growth/value rotation effects.",
                    symbols=("SPY", "QQQ", "TLT", "IEF", "SHY", "XLF", "XLE"),
                ),
            ),
        ),
        EventSetDefinition(
            event_set_id="set_d_2023_banking_stress",
            event_set_label="Set D - 2023 banking stress",
            objective_note="Banking/credit stress anchor with sector concentration.",
            members=(
                _member(
                    event_id="banking_stress_2023",
                    event_label="Regional banking stress (2023)",
                    category_label=CATEGORY_BANKING,
                    anchor_start="2023-03-08",
                    anchor_end="2023-03-24",
                    notes="SVB aftermath and deposit-flight stress profile.",
                    symbols=("KRE", "XLF", "JPM", "BAC", "GS", "MS"),
                ),
            ),
        ),
        EventSetDefinition(
            event_set_id="set_e_broad_institutional_stress_library",
            event_set_label="Set E - Broad mixed institutional stress library",
            objective_note=(
                "Ruleset-generated curated institutional library (target 35-40 events), "
                "slightly overweight macro/rates and crisis. Later extension should add "
                "an equity-desk-style library with more earnings shocks."
            ),
            members=set_e_members,
        ),
    )


def event_set_lookup() -> Dict[str, EventSetDefinition]:
    return {s.event_set_id: s for s in canonical_event_set_library()}


def flatten_event_library_rows(
    sets: Sequence[EventSetDefinition] | None = None,
) -> List[Dict[str, Any]]:
    """Flatten library definitions for tabular comparison / export."""
    out: List[Dict[str, Any]] = []
    for s in sets or canonical_event_set_library():
        for m in s.members:
            out.append(
                {
                    "event_set_id": s.event_set_id,
                    "event_set_label": s.event_set_label,
                    "event_id": m.event_id,
                    "event_label": m.event_label,
                    "category_label": m.category_label,
                    "anchor_start": m.anchor_start,
                    "anchor_end": m.anchor_end,
                    "default_window_family_labels": ";".join(m.default_window_family_labels),
                    "notes": m.notes,
                }
            )
    return out


def build_event_set_manifest(
    *,
    include_window_policy: bool = True,
) -> Dict[str, Any]:
    """Build canonical event-set manifest dict."""
    sets = canonical_event_set_library()
    payload: Dict[str, Any] = {
        "schema_version": "1.1",
        "event_sets": [s.to_dict() for s in sets],
        "set_e_ruleset_targets": [
            {"category_label": cat, "target_count": target}
            for cat, target in SET_E_RULESET_TARGETS
        ],
        "set_e_manual_review": set_e_manual_review_summary(),
    }
    if include_window_policy:
        payload["window_policy"] = locked_window_policy_manifest()
    return payload


def export_event_set_manifest(
    output_path: str | Path,
    *,
    include_window_policy: bool = True,
) -> Path:
    """Write canonical event-set manifest to JSON."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = build_event_set_manifest(include_window_policy=include_window_policy)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def ensure_required_sets(
    selected_set_ids: Iterable[str],
) -> Tuple[str, ...]:
    """Validate selected set IDs against locked A-E library."""
    lookup = event_set_lookup()
    bad = [sid for sid in selected_set_ids if sid not in lookup]
    if bad:
        raise ValueError(f"Unknown event set ids: {bad}")
    return tuple(selected_set_ids)
