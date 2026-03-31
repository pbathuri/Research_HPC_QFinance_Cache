# Net Utility and Decision Overhead Accounting

## Motivation

Cache-guided systems have overhead. On weak-reuse workloads, the overhead of lookup, similarity search, policy decisions, and validation can easily exceed the compute saved. This module measures that honestly.

## Per-Request Overhead Decomposition

For each request, the system computes:

| Field | Description |
|-------|-------------|
| `lookup_overhead_ms` | Time spent on cache lookup |
| `similarity_search_overhead_ms` | Time for similarity candidate search |
| `decision_overhead_ms` | Total decision time (lookup + similarity search) |
| `validation_overhead_ms` | Recomputation cost for validation |
| `total_overhead_ms` | All overhead combined |
| `gross_runtime_saved_ms` | Compute time avoided by cache hit |
| `net_runtime_saved_ms` | Gross saved minus overhead |
| `reuse_harm_penalty_ms` | Penalty for harmful reuse |
| `net_utility_ms` | Final net utility (gross - overhead - harm) |
| `net_utility_label` | "beneficial" / "neutral" / "harmful" |

## Aggregation Levels

Overhead accounting is aggregated at:
- **Per-request**: Individual decision accounting
- **Per-family**: Which workload families benefit from caching
- **Per-run**: Overall system utility
- **Cross-run**: Stability of findings across runs

## Interpreting Results

### Positive net utility
The cache system saved more time than it cost. This is meaningful evidence.

### Negative net utility
The overhead exceeded savings. This is an honest and important finding — it means the workload does not benefit from caching at this granularity.

### Mixed results by family
Expected outcome. Some families (exact repeat, hotset) should show positive utility. Others (stress churn, cold-start heavy) may show neutral or negative.

## Connection to Speedup Bounds

The net utility feeds into the Amdahl/Gustafson analysis. When net utility is negative, the realized speedup is below 1.0, honestly indicating slowdown rather than speedup.

## SLM Export

Overhead fields are included in SLM training records:
- `decision_overhead_ms`
- `gross_runtime_saved_ms`
- `net_runtime_saved_ms`
- `net_utility_label`

This enables training classifiers for "should we use the cache for this request type?"
