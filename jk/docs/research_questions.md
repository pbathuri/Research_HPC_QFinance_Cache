# Research questions for the human researcher

Use these as prompts for experiments, literature review, and thesis direction.

## Caching and reuse

- When does **exact** cache reuse (same parameters / same compiled object) become worthwhile relative to recompilation cost?
- When is **similarity-based** reuse too risky for pricing or risk numbers? How would you quantify accuracy risk?
- How should **financial tolerance** (e.g. basis-point error budget) enter a cache decision rule?
- Under what book structures does a **heuristic** policy outperform a **learned** policy (or vice versa)?
- What **portfolio** structures create natural clusters for circuit or result reuse?

## Quantum mapping (pre-hardware)

- How should **QMCI-style** tasks be represented before real quantum execution exists, so that classical and quantum teams share one schema?
- Where is **amplitude estimation** the right abstraction vs plain sampling for a given payoff encoding?
- What **resource estimates** (depth, qubits, shots) are honest enough for proposals without implying realized speedup?

## Method choice

- When should **Fourier / COS** (or other semi-analytic methods) be preferred over **pure Monte Carlo** for validation or variance reduction?
- When is a **control variate** based on terminal spot inadequate, and what alternative controls (e.g. delta-based) belong in the next iteration?

## Risk

- How sensitive are **VaR/CVaR** estimates to scenario design when the book is options-only vs mixed cash and options?
- How would you stress-test the **similarity score** so that reuse policies fail safely?

## Acceptance criteria

- What is the right **acceptance criterion** for approximate reuse (e.g. maximum allowed price delta, maximum CVaR shift)?
- How do you log decisions so an undergraduate can **audit** why a cache hit was allowed?
