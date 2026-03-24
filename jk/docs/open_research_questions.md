# Open research questions (living list)

This file tracks **unresolved** research decisions. It is intentionally incomplete—update as the lab converges.

Pairs with machine-readable entries in **`data/research/question_log.json`** (version-controlled). You may copy or append this file into a run-scoped `outputs/.../research/` folder for a given experiment; the repository does not require `outputs/` to be committed.

## Portfolio & workload

1. Which **portfolio workload families** should be benchmarked first for cache behavior (broad ETF vs. concentrated book vs. event-stress book)?
2. How should **event-window stress** be weighted vs. steady-state daily panels in cache policy evaluation?

## Feature space & condensation

3. What is the operational definition of **feature condensation success** (variance explained threshold, collision rate caps, interpretability constraints)?
4. Should condensation keys be **shared** across engines (single namespace) or **per model family**?

## Similarity & near-hit policy

5. What **similarity threshold** and **evidence standard** justify labeling a near-hit as “research-relevant” vs. noise?
6. Should **similarity hits** ever influence execution (approximate reuse), or remain observational only?

## Rates & institutional data

7. When **WRDS Treasury** and **local CRSP file** disagree on calendar alignment, which source dominates for this lab’s papers?
8. Which **WRDS tables** are contractually available for your subscription (confirm in Schema Finder)—candidate lists in `wrds_queries.py` may need edits.

## Quantum / HPC future

9. Which **quantum mapping objects** (problem descriptors, resource estimates) matter most for the first honest BigRed200 benchmark?
10. What classical baseline must be fixed before any hybrid speedup narrative?

## Validation & factors

11. Which **Fama-French / factor** overlays are required for validation of alpha features in this project?
12. How will **TAQ–CRSP link** quality be audited before scaling event windows?

---

*Do not treat unanswered items as defaults in code—log assumptions in commit messages or dataset `notes` fields.*
