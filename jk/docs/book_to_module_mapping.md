# Books and papers → modules (working map)

This is a **lab-maintained** index: tie major readings to code you can run or extend. Replace placeholder titles with your uploaded bibliography entries via ``research_memory.register_document_anchor``.

| Theme | Typical readings (placeholders) | Primary modules |
|-------|----------------------------------|-----------------|
| Stochastic calculus & options | Björk, Shreve, Hull (options) | `analytic_pricing.py`, `market_models.py`, `pricing.py` |
| Risk & extremes | McNeil–Frey–Embrechts | `risk_metrics.py`, `historical_risk.py`, `portfolio.py` |
| Empirical asset pricing / factors | Cochrane, FF documentation | `universe_analysis.py`, `historical_returns.py`; future `wrds_placeholder.py` |
| Market microstructure / TAQ | Hasbrouck, O’Hara, venue docs | `taq_kdb_adapter.py`, `event_book.py`, `data_sources.py` |
| Fourier / COS methods | Fang & Oosterlee | `fourier_placeholder.py` |
| Quantum Monte Carlo / QAE surveys | Montanaro et al. | `quantum_mapping.py`, `quantum_workflow.py` |
| NISQ workflows / caching | Circuit reuse literature | `circuit_cache.py`, `circuit_similarity.py`, `cache_policy.py` |
| Data engineering at scale | Vendor schema guides, WRDS manuals | `data_ingestion.py`, `data_registry.py`; future WRDS layer |

## How to extend

1. Add a row to this table when a new paper anchors a feature.
2. Call ``register_document_anchor`` from a notebook or one-off script with ``linked_module_refs`` pointing at filenames above.
3. Keep ``docs/research_to_code_mapping.md`` synchronized for **idea → symbol** lookups.
