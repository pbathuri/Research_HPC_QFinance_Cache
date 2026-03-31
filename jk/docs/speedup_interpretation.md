# Speedup Bounds Interpretation

## Principle

This system computes speedup bounds from **measured** run data, not theoretical assumptions. It never implies realized performance gains that did not occur.

## Amdahl's Law (Fixed-Size)

For a fixed workload, the maximum speedup from caching is bounded by:

```
Speedup = 1 / (1 - f_removable * savings_fraction)
```

Where:
- `f_removable` = fraction of total runtime that is pricing compute (measured)
- `savings_fraction` = fraction of removable compute actually saved by caching

The system computes bounds at 25%, 50%, 75%, 90%, 95%, and 100% savings levels.

## Gustafson's Law (Scaled Workload)

For larger workloads, the system estimates:

```
Speedup = 1 + f_removable_scaled * (scale_factor - 1) * savings_fraction
```

This projects how speedup would scale if the workload were 2x, 4x, 8x, or 16x larger. These are explicitly marked as **scaled estimates, not realized results**.

## Realized Speedup

The system also computes:
- **Gross speedup**: Based on measured savings before overhead
- **Net speedup**: After subtracting decision overhead and validation cost

If net speedup < 1.0, the system honestly reports that caching was a net cost.

## Weak Reuse Flag

When `exact_hit_rate + similarity_hit_rate < 10%`, the system sets `weak_reuse_flag: true` and adds an honesty note stating that speedup claims are not meaningful for this run.

## Interpreting Full-Pipeline Results

The recent BigRed full-pipeline run showed:
- ~548 pricings, no realized reuse
- Speedup effectively 1.0x (no benefit)
- This is correctly reported as weak reuse

This is not a failure — it means the full pipeline workload is too unique for caching to help. The repeated-workload path with structured families is where reuse evidence is generated.

## Interpreting Repeated-Workload Results

Repeated-workload studies with families like `exact_repeat_pricing` and `hotset_coldset_mixed` should show:
- Higher pricing fraction (most runtime is compute)
- Positive gross savings
- Positive or near-zero net savings depending on overhead
- Amdahl bounds that are meaningful because removable fraction is large

## Output Files

- `research/speedup_bounds.json` — Full analysis with decomposition and bounds
- `research/speedup_bounds.md` — Human-readable summary table
