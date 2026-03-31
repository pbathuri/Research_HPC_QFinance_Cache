"""Cross-run aggregation layer for combining local and BigRed evidence.

Ingests run manifests, research artifacts, and SLM exports from multiple
runs and produces aggregate research-grade summaries with seed stability,
per-family metrics, and claims support matrices.
"""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


def discover_runs(base_dirs: Sequence[Path]) -> List[Path]:
    """Find valid run directories containing a repeated_workload_manifest.json or run_manifest.json."""
    runs: List[Path] = []
    for base in base_dirs:
        p = Path(base)
        if not p.exists():
            continue
        for manifest_name in ("repeated_workload_manifest.json", "run_manifest.json"):
            if (p / manifest_name).exists():
                runs.append(p)
                break
        for child in sorted(p.iterdir()) if p.is_dir() else []:
            if child.is_dir():
                for manifest_name in ("repeated_workload_manifest.json", "run_manifest.json"):
                    if (child / manifest_name).exists():
                        runs.append(child)
                        break
    return runs


def _load_json_safe(path: Path) -> Dict[str, Any]:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {}


def aggregate_research_runs(
    run_dirs: Sequence[Path],
    output_dir: Path,
) -> Dict[str, Any]:
    """Combine evidence from multiple runs into aggregate summaries."""
    output_dir.mkdir(parents=True, exist_ok=True)

    run_records: List[Dict[str, Any]] = []
    family_data: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    claim_matrix: Dict[str, Dict[str, str]] = {}
    honesty_flags: List[Dict[str, Any]] = []
    slm_file_paths: List[str] = []
    local_runs: List[str] = []
    hpc_runs: List[str] = []

    for rd in run_dirs:
        rd = Path(rd)
        manifest = _load_json_safe(rd / "repeated_workload_manifest.json")
        is_rws = bool(manifest)
        if not manifest:
            manifest = _load_json_safe(rd / "run_manifest.json")
        if not manifest:
            continue

        if is_rws:
            run_label = str(manifest.get("scale_label", "")) + f"_seed{manifest.get('deterministic_seed', '')}"
        else:
            run_label = f"fp_{manifest.get('run_id', '')[:8]}"
        is_hpc = bool(manifest.get("budget_utilization", {}).get("execution_host", "")) or \
                 manifest.get("requested_backend", "").startswith("slurm")

        run_rec = {
            "run_dir": str(rd),
            "run_label": run_label,
            "seed": manifest.get("deterministic_seed", 0),
            "scale_label": manifest.get("scale_label", ""),
            "lane_selection": manifest.get("lane_selection", ""),
            "summary_rows_count": manifest.get("summary_rows_count", 0),
            "is_hpc": is_hpc,
        }

        cacheability = _load_json_safe(rd / "research" / "cacheability_summary.json")
        utility = _load_json_safe(rd / "research" / "utility_summary.json")
        hpc_util = _load_json_safe(rd / "research" / "hpc_utilization.json")
        expanded = _load_json_safe(rd / "research" / "expanded_metrics.json")
        validation = _load_json_safe(rd / "research" / "similarity_validation_summary.json")

        run_rec["exact_hit_rate"] = expanded.get("exact_hit_rate", 0.0)
        run_rec["similarity_hit_rate"] = expanded.get("similarity_hit_rate", 0.0)
        run_rec["useful_hit_rate"] = expanded.get("useful_hit_rate", 0.0)
        run_rec["harmful_hit_rate"] = expanded.get("harmful_hit_rate", 0.0)
        run_rec["total_utility"] = utility.get("total_utility", 0.0)
        run_rec["mean_utility"] = utility.get("mean_utility", 0.0)
        run_rec["validation_pass_rate"] = validation.get("tolerance_pass_rate", 0.0)
        run_rec["compute_fraction"] = hpc_util.get("compute_fraction", 0.0)
        run_rec["cache_recall_on_reusable"] = cacheability.get("cache_recall_on_reusable", 0.0)

        run_records.append(run_rec)

        if is_hpc:
            hpc_runs.append(run_label)
        else:
            local_runs.append(run_label)

        fam_metrics = expanded.get("by_family", {})
        for fam, fm in fam_metrics.items():
            family_data[fam].append({**fm, "run_label": run_label, "seed": manifest.get("deterministic_seed", 0)})

        claims = _load_json_safe(rd / "research" / "research_claims_manifest.json")
        for c in claims.get("claims", []):
            cid = c.get("claim_id", "")
            if cid not in claim_matrix:
                claim_matrix[cid] = {}
            claim_matrix[cid][run_label] = c.get("support_status", "not_tested")

        honesty = _load_json_safe(rd / "research" / "research_honesty_manifest.json")
        if honesty:
            honesty_flags.append({"run_label": run_label, **honesty.get("summary", {})})

        net_util = _load_json_safe(rd / "research" / "net_utility_summary.json")
        run_rec["total_overhead_ms"] = net_util.get("total_overhead_ms", 0.0)
        run_rec["total_net_saved_ms"] = net_util.get("total_net_saved_ms", 0.0)
        run_rec["net_utility_positive"] = net_util.get("net_utility_positive", False)
        run_rec["beneficial_rate"] = net_util.get("beneficial_rate", 0.0)
        run_rec["harmful_rate"] = net_util.get("harmful_rate", 0.0)

        speedup = _load_json_safe(rd / "research" / "speedup_bounds.json")
        run_rec["realized_net_speedup"] = speedup.get("realized_speedup", {}).get("realized_net_speedup", 1.0)
        run_rec["weak_reuse_flag"] = speedup.get("run_context", {}).get("weak_reuse_flag", True)

        contract = _load_json_safe(rd / "artifact_contract.json")
        run_rec["artifact_generated_count"] = contract.get("generated", 0)
        run_rec["artifact_skipped_count"] = contract.get("skipped", 0)

        slm_manifest = _load_json_safe(rd / "slm_datasets" / "slm_export_manifest.json")
        if slm_manifest:
            for k, v in slm_manifest.get("files", {}).items():
                slm_file_paths.append(v)

    per_family_agg = _aggregate_families(family_data)
    seed_stability = _compute_seed_stability(run_records)
    claim_safety = _compute_claim_safety(claim_matrix, run_records)
    overhead_agg = _aggregate_overhead(run_records)

    aggregate = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "run_count": len(run_records),
        "local_run_count": len(local_runs),
        "hpc_run_count": len(hpc_runs),
        "per_family": per_family_agg,
        "seed_stability": seed_stability,
        "claim_support_matrix": claim_matrix,
        "claim_safety": claim_safety,
        "overhead_aggregate": overhead_agg,
        "run_summaries": run_records,
        "slm_file_count": len(slm_file_paths),
    }

    json_path = output_dir / "aggregate_research_summary.json"
    json_path.write_text(json.dumps(aggregate, indent=2, default=str))

    _write_aggregate_md(aggregate, output_dir / "aggregate_research_summary.md")
    _write_family_csv(per_family_agg, output_dir / "per_family_metrics.csv")
    _write_claim_csv(claim_matrix, output_dir / "claim_support_matrix.csv")
    _write_slm_manifest(slm_file_paths, output_dir / "slm_dataset_manifest.json")
    _write_overhead_csv(run_records, output_dir / "per_run_overhead.csv")

    return aggregate


def _aggregate_families(
    family_data: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Dict[str, Any]]:
    agg = {}
    for fam, records in family_data.items():
        n = len(records)
        exact_rates = [float(r.get("exact_hit_rate", 0)) for r in records]
        sim_rates = [float(r.get("similarity_hit_rate", 0)) for r in records]
        useful_rates = [float(r.get("useful_hit_rate", 0)) for r in records]
        harmful_rates = [float(r.get("harmful_hit_rate", 0)) for r in records]
        rd_means = [float(r.get("mean_reuse_distance", 0)) for r in records]

        agg[fam] = {
            "run_count": n,
            "mean_exact_hit_rate": round(sum(exact_rates) / n, 6) if n else 0.0,
            "std_exact_hit_rate": round(_std(exact_rates), 6),
            "mean_similarity_hit_rate": round(sum(sim_rates) / n, 6) if n else 0.0,
            "mean_useful_hit_rate": round(sum(useful_rates) / n, 6) if n else 0.0,
            "mean_harmful_hit_rate": round(sum(harmful_rates) / n, 6) if n else 0.0,
            "mean_reuse_distance": round(sum(rd_means) / n, 4) if n else 0.0,
            "seeds": [r.get("seed", 0) for r in records],
        }
    return agg


def _compute_seed_stability(
    run_records: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    if len(run_records) < 2:
        return {"status": "insufficient_runs", "run_count": len(run_records)}

    metrics = ["exact_hit_rate", "similarity_hit_rate", "useful_hit_rate", "mean_utility"]
    stability = {}
    for m in metrics:
        values = [float(r.get(m, 0)) for r in run_records]
        stability[m] = {
            "mean": round(sum(values) / len(values), 6),
            "std": round(_std(values), 6),
            "min": round(min(values), 6),
            "max": round(max(values), 6),
            "cv": round(_std(values) / max(abs(sum(values) / len(values)), 1e-10), 6),
        }
    return stability


def _std(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(variance)


def _write_aggregate_md(aggregate: Dict[str, Any], path: Path) -> None:
    lines = [
        "# Aggregate Research Summary",
        "",
        f"Generated: {aggregate['generated_utc']}",
        f"Runs: {aggregate['run_count']} (local: {aggregate['local_run_count']}, HPC: {aggregate['hpc_run_count']})",
        "",
        "## Per-Family Metrics",
        "",
        "| Family | Runs | Exact HR | Sim HR | Useful HR | Harmful HR | Mean RD |",
        "|--------|------|----------|--------|-----------|------------|---------|",
    ]
    for fam, fm in aggregate.get("per_family", {}).items():
        lines.append(
            f"| {fam} | {fm['run_count']} | {fm['mean_exact_hit_rate']:.4f} | "
            f"{fm['mean_similarity_hit_rate']:.4f} | {fm['mean_useful_hit_rate']:.4f} | "
            f"{fm['mean_harmful_hit_rate']:.4f} | {fm['mean_reuse_distance']:.2f} |"
        )

    stability = aggregate.get("seed_stability", {})
    if stability and stability.get("status") != "insufficient_runs":
        lines.extend(["", "## Seed Stability", ""])
        lines.append("| Metric | Mean | Std | CV |")
        lines.append("|--------|------|-----|-----|")
        for m, vals in stability.items():
            if isinstance(vals, dict):
                lines.append(f"| {m} | {vals['mean']:.6f} | {vals['std']:.6f} | {vals['cv']:.4f} |")

    lines.append("")
    path.write_text("\n".join(lines))


def _write_family_csv(per_family: Dict[str, Dict[str, Any]], path: Path) -> None:
    fields = ["family", "run_count", "mean_exact_hit_rate", "std_exact_hit_rate",
              "mean_similarity_hit_rate", "mean_useful_hit_rate", "mean_harmful_hit_rate",
              "mean_reuse_distance"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for fam, fm in per_family.items():
            w.writerow({"family": fam, **{k: fm.get(k, 0) for k in fields if k != "family"}})


def _write_claim_csv(matrix: Dict[str, Dict[str, str]], path: Path) -> None:
    all_runs = sorted(set(r for statuses in matrix.values() for r in statuses))
    fields = ["claim_id"] + all_runs
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for cid, statuses in matrix.items():
            row = {"claim_id": cid}
            for r in all_runs:
                row[r] = statuses.get(r, "not_tested")
            w.writerow(row)


def _write_slm_manifest(paths: List[str], output_path: Path) -> None:
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "total_files": len(paths),
        "files": paths,
    }
    output_path.write_text(json.dumps(manifest, indent=2))


def _compute_claim_safety(
    claim_matrix: Dict[str, Dict[str, str]],
    run_records: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """Classify claims as safe/provisional based on cross-run support."""
    if not claim_matrix:
        return {"status": "no_claims"}

    n_runs = len(run_records)
    safe: List[str] = []
    provisional: List[str] = []
    unsupported: List[str] = []

    for cid, statuses in claim_matrix.items():
        supported_count = sum(1 for s in statuses.values() if s in ("supported", "conditionally_supported"))
        if supported_count >= max(2, n_runs * 0.5):
            safe.append(cid)
        elif supported_count >= 1:
            provisional.append(cid)
        else:
            unsupported.append(cid)

    return {
        "safe_to_claim": safe,
        "provisional": provisional,
        "not_yet_safe": unsupported,
        "total_claims": len(claim_matrix),
        "runs_analyzed": n_runs,
    }


def _aggregate_overhead(
    run_records: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """Aggregate overhead and net-utility across runs."""
    n = len(run_records)
    if n == 0:
        return {"status": "no_runs"}

    overhead_vals = [float(r.get("total_overhead_ms", 0)) for r in run_records]
    net_saved_vals = [float(r.get("total_net_saved_ms", 0)) for r in run_records]
    beneficial_rates = [float(r.get("beneficial_rate", 0)) for r in run_records]
    net_positive_count = sum(1 for r in run_records if r.get("net_utility_positive"))

    return {
        "run_count": n,
        "mean_total_overhead_ms": round(sum(overhead_vals) / n, 4),
        "mean_total_net_saved_ms": round(sum(net_saved_vals) / n, 4),
        "mean_beneficial_rate": round(sum(beneficial_rates) / n, 6),
        "net_positive_run_count": net_positive_count,
        "net_positive_run_fraction": round(net_positive_count / n, 4),
    }


def _write_overhead_csv(
    run_records: Sequence[Dict[str, Any]], path: Path
) -> None:
    fields = [
        "run_label", "seed", "scale_label", "is_hpc",
        "total_overhead_ms", "total_net_saved_ms",
        "net_utility_positive", "beneficial_rate", "harmful_rate",
        "realized_net_speedup", "weak_reuse_flag",
    ]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in run_records:
            w.writerow({k: r.get(k, "") for k in fields})
