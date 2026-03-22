"""Structured concept cache (not RAG): short anchors for books, papers, and code alignment."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class CriticalConcept:
    """One row in the critical cache window."""

    concept_id: str
    domain: str
    summary: str
    module_refs: Tuple[str, ...] = field(default_factory=tuple)
    reading_hints: Tuple[str, ...] = field(default_factory=tuple)
    pitfalls: Tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "concept_id": self.concept_id,
            "domain": self.domain,
            "summary": self.summary,
            "module_refs": list(self.module_refs),
            "reading_hints": list(self.reading_hints),
            "pitfalls": list(self.pitfalls),
        }


def _t(*items: str) -> Tuple[str, ...]:
    return tuple(items)


BUILT_IN_CRITICAL_CONCEPTS: Tuple[CriticalConcept, ...] = (
    CriticalConcept(
        "mds_001",
        "market_data_sourcing",
        "Vendor data has schema and calendar conventions; align timestamps (UTC) and symbology before panels.",
        _t("data_sources.py", "data_ingestion.py", "taq_kdb_adapter.py"),
        _t("Databento schema docs", "NYSE TAQ reference"),
        _t("Mixing adjusted/unadjusted splits inference"),
    ),
    CriticalConcept(
        "fe_001",
        "feature_engineering",
        "Returns and volatility features should be defined consistently (log vs simple; annualization factor).",
        _t("historical_returns.py", "universe_analysis.py"),
        _t("Time-series cross-validation literature"),
        _t("Look-ahead in rolling windows"),
    ),
    CriticalConcept(
        "alpha_001",
        "alpha_research",
        "Hypothesis → signal → backtest discipline; separate research code from production-grade paths.",
        _t("experiment_runner.py", "experiment_configs.py"),
        _t("Factor research surveys"),
        _t("Data mining without economic prior"),
    ),
    CriticalConcept(
        "robust_001",
        "overfitting_robustness",
        "Stability across subsamples and stress windows matters more than in-sample fit for research claims.",
        _t("event_book.py", "historical_risk.py"),
        _t("Harvey et al. multiple testing context"),
        _t("Single peak backtest selection"),
    ),
    CriticalConcept(
        "var_001",
        "var_cvar",
        "Sample quantile VaR/CVaR here are teaching tools—not regulatory internal models.",
        _t("risk_metrics.py", "historical_risk.py", "portfolio.py"),
        _t("McNeil/Frey/Embrechts extremes"),
        _t("Confusing return vs P&L sign conventions"),
    ),
    CriticalConcept(
        "vol_001",
        "volatility_time_series",
        "Realized vs implied; clustering; use rolling estimators with clear window semantics.",
        _t("historical_returns.py", "market_models.py"),
        _t("Andersen et al. realized volatility"),
        _t("Annualization without sqrt-of-time justification"),
    ),
    CriticalConcept(
        "bs_001",
        "black_scholes_continuous_time",
        "Black–Scholes is a benchmark: assumptions (lognormal, constant vol) rarely hold literally.",
        _t("analytic_pricing.py", "pricing.py"),
        _t("Björk / Shreve continuous-time finance"),
        _t("Using BS delta as hedge ratio without transaction costs model"),
    ),
    CriticalConcept(
        "cos_001",
        "cos_fourier_bridge",
        "COS links characteristic function to prices; good for validation vs MC and BS.",
        _t("fourier_placeholder.py"),
        _t("Fang & Oosterlee COS method"),
        _t("Truncation domain truncation error in COS"),
    ),
    CriticalConcept(
        "qf_001",
        "quantum_finance_mapping",
        "Map classical expectation problems to quantum estimation framing without speedup claims.",
        _t("quantum_mapping.py", "quantum_workflow.py"),
        _t("QMCI survey papers"),
        _t("Confusing sampling error with circuit shot noise models"),
    ),
    CriticalConcept(
        "qmci_001",
        "qmci_qae_concepts",
        "QAE targets amplitude of a prepared state; cost models need depth, width, error budgets.",
        _t("quantum_mapping.py"),
        _t("Montanaro AE surveys"),
        _t("Ignoring loading problem cost"),
    ),
    CriticalConcept(
        "cc_001",
        "circuit_caching",
        "Exact keys for reuse; metadata for policy decisions and audit trails.",
        _t("circuit_cache.py"),
        _t("NISQ workflow papers"),
        _t("Treating similar circuits as identical without tolerance"),
    ),
    CriticalConcept(
        "sim_001",
        "similarity_caching",
        "Explainable similarity supports human-in-the-loop reuse policies.",
        _t("circuit_similarity.py", "cache_policy_features.py", "cache_policy.py"),
        _t("ML for systems caching"),
        _t("Black-box similarity without feature provenance"),
    ),
    CriticalConcept(
        "hybrid_001",
        "hybrid_quantum_hpc",
        "Hybrid stacks batch classical prep/post with quantum kernels; schedulers and data locality dominate.",
        _t("docs/future_extensions.md", "data_registry.py"),
        _t("HPC + quantum roadmaps"),
        _t("Ignoring classical I/O bottleneck in speedup claims"),
    ),
)


def get_critical_cache_window() -> List[CriticalConcept]:
    """Return the canonical in-repo concept window."""
    return list(BUILT_IN_CRITICAL_CONCEPTS)


def get_concepts_by_domain(domain: str) -> List[CriticalConcept]:
    domain_lower = domain.lower()
    return [concept for concept in BUILT_IN_CRITICAL_CONCEPTS if concept.domain == domain_lower]


def summarize_knowledge_cache() -> Dict[str, Any]:
    domains: Dict[str, int] = {}
    for concept in BUILT_IN_CRITICAL_CONCEPTS:
        domains[concept.domain] = domains.get(concept.domain, 0) + 1
    return {
        "concept_count": len(BUILT_IN_CRITICAL_CONCEPTS),
        "domains": domains,
    }


def export_critical_window_json_serializable() -> List[Dict[str, Any]]:
    return [concept.to_dict() for concept in BUILT_IN_CRITICAL_CONCEPTS]


@dataclass(frozen=True)
class ResearchReference:
    """Lightweight citation anchor for books/papers (not a full bibliography)."""

    reference_id: str
    title: str
    kind: str = "book_or_paper"
    module_refs: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ResearchConceptNote:
    """Short note tying a concept id to reading or lab discussion."""

    concept_id: str
    note_text: str
    source_hint: str = ""


@dataclass(frozen=True)
class CriticalCacheWindow:
    """Versioned bundle of in-repo critical concepts."""

    version: str
    concepts: Tuple[CriticalConcept, ...]


def build_default_research_reference_set() -> Tuple[ResearchReference, ...]:
    """Seed references aligned to module map (expand with your own uploads)."""
    return (
        ResearchReference(
            "ref_market_data",
            "Market data vendor schemas and symbology",
            "topic",
            _t("data_sources.py", "data_ingestion.py"),
        ),
        ResearchReference(
            "ref_risk",
            "Quantitative risk and extremes",
            "topic",
            _t("historical_risk.py", "risk_metrics.py"),
        ),
        ResearchReference(
            "ref_quantum_mapping",
            "Quantum algorithms for Monte Carlo / QAE (conceptual)",
            "topic",
            _t("quantum_mapping.py", "quantum_workflow.py"),
        ),
    )


def build_concept_note_library() -> Tuple[ResearchConceptNote, ...]:
    """Starter notes; replace with lab-specific reading list."""
    return tuple(
        ResearchConceptNote(c.concept_id, c.summary[:120] + "...", "")
        for c in BUILT_IN_CRITICAL_CONCEPTS
    )


def build_critical_cache_window() -> CriticalCacheWindow:
    """Canonical critical window object."""
    return CriticalCacheWindow(version="1.0", concepts=BUILT_IN_CRITICAL_CONCEPTS)


def export_critical_cache_window(window: CriticalCacheWindow) -> List[Dict[str, Any]]:
    """JSON-serializable export of a ``CriticalCacheWindow``."""
    return [c.to_dict() for c in window.concepts]


def search_critical_cache_window(
    query: str,
    *,
    concepts: Optional[List[CriticalConcept]] = None,
) -> List[CriticalConcept]:
    """Case-insensitive substring match on domain, summary, or concept_id."""
    pool = concepts if concepts is not None else get_critical_cache_window()
    query_lower = query.lower()
    out: List[CriticalConcept] = []
    for concept in pool:
        if query_lower in concept.concept_id.lower():
            out.append(concept)
        elif query_lower in concept.domain.lower():
            out.append(concept)
        elif query_lower in concept.summary.lower():
            out.append(concept)
    return out
