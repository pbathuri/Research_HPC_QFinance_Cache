# SLM Readiness: Feature and Label Export Schema

## Purpose

This document describes how the research outputs can feed future SLM (Small Language Model) training pipelines for domain-aware decision support in quantitative finance workflows.

## Target SLM Capabilities

The SLM is intended for:
- **Workload classification** - predict workload family from parameters
- **Cacheability prediction** - predict whether a request is reusable
- **Reuse-policy recommendation** - suggest optimal policy tier
- **Failure explanation** - explain why a cache miss occurred
- **Regime-conditioned reasoning** - adjust recommendations by market regime
- **HPC scheduling suggestion** - recommend resource allocation

## Export Schema

### slm_training_examples.jsonl

One JSON object per line. Each record contains:

| Field | Type | Description |
|-------|------|-------------|
| `workload_id` | string | Unique request identifier |
| `workload_family` | string | Family (e.g., `exact_repeat_pricing`) |
| `workload_regime` | string | Market regime tag |
| `engine_name` | string | Engine used for pricing |
| `reuse_candidate_type` | string | `exact`, `similarity`, or `none` |
| `exact_match_flag` | bool | Whether exact cache hit occurred |
| `similarity_score` | float | Similarity score if applicable |
| `locality_score` | float | Temporal locality score |
| `reuse_distance` | float | Events since last same-key access |
| `working_set_size` | int | Current working set size |
| `policy_decision` | string | Decision outcome |
| `policy_tier` | string | Policy tier applied |
| `ground_truth_cacheability_label` | string | Ground-truth label |
| `error_if_reused` | float | Pricing error from reuse |
| `latency_saved_ms` | float | Time saved by reuse |
| `utility_score` | float | Net utility of the decision |
| `failure_reason` | string | Failure taxonomy code |
| `epistemic_status` | string | Observation quality |
| `data_source_status` | string | `synthetic` or `production` |
| `regime_tags` | string | Market regime tags |
| `portfolio_overlap_score` | float | Portfolio overlap metric |
| `event_overlap_score` | float | Event window overlap |
| `S0, K, sigma, T, r, num_paths` | float/int | Option parameters |
| `pricing_compute_time_ms` | float | Actual compute time |
| `parameter_hash` | string | Parameter fingerprint |
| `feature_hash` | string | Feature vector fingerprint |
| `cluster_id` | string | Cluster assignment |
| `run_label` | string | Run provenance label |
| `run_seed` | int | Deterministic seed |
| `execution_host` | string | Machine identifier |
| `backend_name` | string | Backend used |

### reuse_decision_dataset.csv

Same schema as JSONL, in CSV format for tabular ML pipelines.

### workload_family_dataset.csv

Per-family aggregates:

| Field | Description |
|-------|-------------|
| `workload_family` | Family identifier |
| `count` | Number of requests |
| `exact_hit_rate` | Exact cache hit rate |
| `similarity_hit_rate` | Similarity hit rate |
| `mean_utility` | Average utility score |
| `mean_latency_saved_ms` | Average latency savings |
| `unique_fraction` | Fraction of unique first-access items |

### cacheability_labels.csv

Focused label dataset for classification tasks:

| Field | Description |
|-------|-------------|
| `workload_id` | Request identifier |
| `workload_family` | Family |
| `ground_truth_cacheability_label` | Ground-truth label |
| `failure_reason` | Why not cached |
| `cache_hit` | Observed hit |
| `similarity_hit` | Observed similarity hit |
| `epistemic_status` | Observation quality |

## Quality Constraints

1. **Labels arise from disciplined logic**, not ML convenience
2. **Failure reasons are structured**, not free text
3. **Epistemic status is always present** - distinguishes observed from derived
4. **Synthetic data is labeled as such** via `data_source_status`
5. **Provenance links every record** to its run via `run_label` and `run_seed`

## SLM Training Patterns

### Supervised Classification
- Input: parameter features + regime + portfolio overlap
- Target: `ground_truth_cacheability_label`

### Decision Prediction
- Input: request features + cache state summary
- Target: `policy_decision` + `utility_score`

### Failure Explanation
- Input: request features + `failure_reason`
- Target: natural language explanation of why cache missed

### Regime-Conditioned Reasoning
- Input: regime_tags + parameter features
- Target: expected reuse mode + recommended policy tier

## Commands

```bash
# Export SLM datasets from a completed study
python3 run_repeated_workload_study.py --lane both --scale-label standard --seed 42

# Datasets will be in: outputs/repeated_workload_phase/slm_datasets/
# - slm_training_examples.jsonl
# - reuse_decision_dataset.csv
# - workload_family_dataset.csv
# - cacheability_labels.csv
# - slm_export_manifest.json
```
