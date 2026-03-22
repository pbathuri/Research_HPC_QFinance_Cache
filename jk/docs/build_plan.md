# Build plan — implementation order

Execution order used for the upgrade (aligned with the user’s phases). The baseline
described here is **implemented**; day-to-day validation is `run_demo.py` + `tests/`.

1. **Phase 0 — Audit & docs**  
   `current_state_audit.md`, `research_to_code_mapping.md`, `build_plan.md`, `local_resource_audit.md`, `dependency_decisions.md`.

2. **Phase 1 — Classical core**  
   `market_models.py`, `payoffs.py`, `analytic_pricing.py`, refactor `pricing.py` (`MonteCarloPricingResult`), `risk_metrics.py`, `portfolio.py`.

3. **Phase 2 — Variance reduction & Fourier**  
   `variance_reduction.py`, upgrade `fourier_placeholder.py` (characteristic function, COS / quadrature-based COS coefficients, BS reference).

4. **Phase 3 — Quantum mapping**  
   `quantum_mapping.py`, `quantum_workflow.py`.

5. **Phase 4 — Circuit cache & similarity**  
   `circuit_cache.py`, `circuit_similarity.py`.

6. **Phase 5 — Cache policies**  
   `cache_policy_features.py`, refactor `cache_policy.py` (`BaseCachePolicy`, `HeuristicCachePolicy`, `LogisticCachePolicy`, `AIAssistedCachePolicy`).

7. **Phase 6 — Experiments**  
   `experiment_configs.py`, `research_scenarios.py`, `reporting.py`, extend `experiment_runner.py`.

8. **Phase 7 — Demos & tests**  
   `run_demo.py`, new/updated `tests/*`.

9. **Phase 8 — README & research docs**  
   `README.md`, `architecture_overview.md`, `research_questions.md`, `future_extensions.md`.

10. **Optional**  
    Minimal `tools/research_agent/` if time permits (no core imports).

## Principles

- Extend existing modules where they already own a concern; add new files when responsibility is new.
- Keep **core** free of LangChain, agents, Lean, and AutoResearchClaw imports.
- Prefer **explicit names** and **short functions** over clever abstractions.
