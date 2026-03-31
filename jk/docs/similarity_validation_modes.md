# Similarity Validation Modes and Tolerance Profiles

## Purpose

When a cache hit is returned (exact or approximate), the system can optionally recompute the result to verify correctness. This is essential for scientific rigor — we cannot claim approximate reuse is safe without control evidence.

## Validation Modes

| Mode | Behavior |
|------|----------|
| `off` | No validation. Use only when overhead must be minimized. |
| `sampled` (default) | Validate a random fraction of hits. Rate configurable. |
| `always` | Validate every cache hit. Maximum rigor, highest overhead. |
| `family_conditioned` | Different sampling rates per workload family. |
| `regime_conditioned` | Different sampling rates per market regime. |

Legacy aliases: `probabilistic` → `sampled`, `deterministic` → `always`.

## Tolerance Profiles

Each tolerance profile defines the maximum acceptable relative error:

| Profile | Threshold | Use Case |
|---------|-----------|----------|
| `strict` | 1% | Exact-repeat pricing, regulatory contexts |
| `moderate` | 5% | Near-repeat, portfolio cluster, scenario ladders |
| `exploratory` | 10% | Stress testing, parameter shock grids |

### Family Defaults

Each workload family has a default tolerance profile:
- `exact_repeat_pricing` → strict
- `near_repeat_pricing` → moderate
- `parameter_shock_grid` → exploratory
- `stress_churn_pricing` → exploratory
- All others → moderate

These can be overridden via `per_family_tolerance` in `ValidationConfig`.

## Configuration

```python
from qhpc_cache.similarity_validation import ValidationConfig

config = ValidationConfig(
    mode="family_conditioned",
    validation_rate=0.25,
    tolerance_profile="moderate",
    per_family_overrides={"parameter_shock_grid": 1.0},  # always validate grid
    per_family_tolerance={"exact_repeat_pricing": "strict"},
)
```

## Validation Summary Fields

The validation summary includes:
- `pass_count`, `fail_count`, `tolerance_pass_rate`
- `exact_reuse_validated`, `similarity_reuse_validated`
- `false_accept_count`: similarity hits that failed tolerance
- `by_family`: per-family breakdown
- `config`: full configuration used

## Interpreting Results

- **100% pass rate on exact reuse**: Expected. Exact reuse with same seed should produce identical results.
- **High pass rate on similarity reuse**: Good evidence that approximate reuse is safe under the tested tolerance.
- **false_accept_count > 0**: Indicates the similarity threshold or tolerance profile may be too permissive.
- **0 validations**: Either mode was "off" or no cache hits occurred.
