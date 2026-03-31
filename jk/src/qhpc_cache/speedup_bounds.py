"""Measured Amdahl/Gustafson speedup bound analysis.

Computes speedup bounds from actual run metrics rather than
theoretical assumptions. Never implies realized gains that did not occur.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


def compute_speedup_bounds(
    *,
    total_wall_ms: float,
    pricing_compute_ms: float,
    orchestration_ms: float,
    overhead_ms: float = 0.0,
    gross_savings_ms: float = 0.0,
    net_savings_ms: float = 0.0,
    total_pricings: int = 0,
    exact_hit_rate: float = 0.0,
    similarity_hit_rate: float = 0.0,
) -> Dict[str, Any]:
    """Compute Amdahl and Gustafson speedup bounds from measured results."""
    if total_wall_ms <= 0:
        return {"status": "insufficient_data", "reason": "total_wall_ms <= 0"}

    pricing_fraction = pricing_compute_ms / total_wall_ms
    orchestration_fraction = orchestration_ms / total_wall_ms
    overhead_fraction = overhead_ms / total_wall_ms
    removable_fraction = min(pricing_fraction, 1.0)
    non_removable_fraction = 1.0 - removable_fraction

    amdahl_levels = [0.25, 0.50, 0.75, 0.90, 0.95, 1.00]
    amdahl_bounds = {}
    for savings_level in amdahl_levels:
        effective_removable = removable_fraction * savings_level
        remaining = 1.0 - effective_removable
        speedup = 1.0 / max(remaining, 1e-10)
        amdahl_bounds[f"savings_{int(savings_level * 100)}pct"] = {
            "gross_savings_fraction": round(savings_level, 4),
            "effective_removable": round(effective_removable, 6),
            "theoretical_speedup": round(speedup, 4),
        }

    realized_savings_fraction = gross_savings_ms / max(pricing_compute_ms, 1e-10)
    realized_remaining = 1.0 - min(removable_fraction * realized_savings_fraction, removable_fraction)
    realized_gross_speedup = 1.0 / max(realized_remaining, 1e-10)

    net_remaining = 1.0 - min(
        removable_fraction * realized_savings_fraction - overhead_fraction,
        removable_fraction,
    )
    net_remaining = max(net_remaining, non_removable_fraction)
    realized_net_speedup = 1.0 / max(net_remaining, 1e-10)

    gustafson_scaled = {}
    for scale_factor in [2, 4, 8, 16]:
        scaled_pricing = pricing_compute_ms * scale_factor
        scaled_total = orchestration_ms + scaled_pricing + overhead_ms
        scaled_removable = scaled_pricing / max(scaled_total, 1e-10)
        scaled_speedup = 1.0 + scaled_removable * (scale_factor - 1) * realized_savings_fraction
        gustafson_scaled[f"scale_{scale_factor}x"] = {
            "scaled_removable_fraction": round(scaled_removable, 6),
            "gustafson_speedup": round(scaled_speedup, 4),
            "interpretation": "scaled_estimate_not_realized",
        }

    weak_reuse = exact_hit_rate + similarity_hit_rate < 0.10
    honesty = (
        "Current run has insufficient reuse for meaningful speedup claims. "
        "Bounds shown are theoretical given measured decomposition."
        if weak_reuse
        else "Reuse was observed; bounds reflect measured savings."
    )

    return {
        "measured_decomposition": {
            "total_wall_ms": round(total_wall_ms, 4),
            "pricing_compute_ms": round(pricing_compute_ms, 4),
            "orchestration_ms": round(orchestration_ms, 4),
            "overhead_ms": round(overhead_ms, 4),
            "pricing_fraction": round(pricing_fraction, 6),
            "orchestration_fraction": round(orchestration_fraction, 6),
            "removable_fraction": round(removable_fraction, 6),
            "non_removable_fraction": round(non_removable_fraction, 6),
        },
        "amdahl_fixed_size_bounds": amdahl_bounds,
        "realized_speedup": {
            "gross_savings_ms": round(gross_savings_ms, 4),
            "net_savings_ms": round(net_savings_ms, 4),
            "realized_savings_fraction": round(realized_savings_fraction, 6),
            "realized_gross_speedup": round(realized_gross_speedup, 4),
            "realized_net_speedup": round(realized_net_speedup, 4),
        },
        "gustafson_scaled_estimates": gustafson_scaled,
        "run_context": {
            "total_pricings": total_pricings,
            "exact_hit_rate": round(exact_hit_rate, 6),
            "similarity_hit_rate": round(similarity_hit_rate, 6),
            "weak_reuse_flag": weak_reuse,
        },
        "honesty_note": honesty,
    }


def write_speedup_bounds(
    bounds: Dict[str, Any],
    output_dir: Path,
) -> Dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "speedup_bounds.json"
    json_path.write_text(json.dumps(bounds, indent=2))

    lines = [
        "# Speedup Bounds Analysis",
        "",
        f"**Honesty note:** {bounds.get('honesty_note', '')}",
        "",
        "## Measured Decomposition",
        "",
    ]
    decomp = bounds.get("measured_decomposition", {})
    for k, v in decomp.items():
        lines.append(f"- {k}: {v}")

    lines.extend(["", "## Amdahl Fixed-Size Bounds", ""])
    lines.append("| Savings Level | Theoretical Speedup |")
    lines.append("|---------------|---------------------|")
    for level, data in bounds.get("amdahl_fixed_size_bounds", {}).items():
        lines.append(f"| {level} | {data['theoretical_speedup']:.4f}x |")

    realized = bounds.get("realized_speedup", {})
    lines.extend([
        "",
        "## Realized Speedup",
        "",
        f"- Gross speedup: {realized.get('realized_gross_speedup', 0):.4f}x",
        f"- Net speedup (after overhead): {realized.get('realized_net_speedup', 0):.4f}x",
        f"- Gross savings: {realized.get('gross_savings_ms', 0):.2f} ms",
        f"- Net savings: {realized.get('net_savings_ms', 0):.2f} ms",
        "",
    ])

    md_path = output_dir / "speedup_bounds.md"
    md_path.write_text("\n".join(lines))

    return {"json": str(json_path), "md": str(md_path)}
