"""Literature expansion agent: local-first paper indexing, hypothesis tracking, idea generation.

Operates without external APIs by default.  If arXiv search is enabled via
``QHPC_ARXIV_SEARCH_ENABLED=true``, performs metadata-only queries.
All outputs are structured JSON/Markdown under ``outputs/research/``.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _research_output_dir() -> Path:
    return Path(os.environ.get("QHPC_OUTPUT_ROOT", "outputs")) / "research"


# ── Data models ──────────────────────────────────────────────────────

@dataclass
class PaperEntry:
    paper_id: str
    title: str
    authors: List[str] = field(default_factory=list)
    year: int = 0
    source: str = "local"
    arxiv_id: str = ""
    doi: str = ""
    local_path: str = ""
    tags: List[str] = field(default_factory=list)
    linked_modules: List[str] = field(default_factory=list)
    notes: str = ""
    added_at: str = ""

    def __post_init__(self) -> None:
        if not self.added_at:
            self.added_at = _utc_now_iso()


@dataclass
class Hypothesis:
    hypothesis_id: str
    statement: str
    source_paper_ids: List[str] = field(default_factory=list)
    target_modules: List[str] = field(default_factory=list)
    experiment_ideas: List[str] = field(default_factory=list)
    status: str = "proposed"
    added_at: str = ""

    def __post_init__(self) -> None:
        if not self.added_at:
            self.added_at = _utc_now_iso()


@dataclass
class ResearchQueue:
    """Ordered reading / experiment queue with priorities."""
    items: List[Dict[str, Any]] = field(default_factory=list)

    def add(self, *, item_type: str, item_id: str, priority: int = 5, reason: str = "") -> None:
        self.items.append({
            "item_type": item_type,
            "item_id": item_id,
            "priority": priority,
            "reason": reason,
            "added_at": _utc_now_iso(),
            "completed": False,
        })

    def pending(self) -> List[Dict[str, Any]]:
        return sorted(
            [i for i in self.items if not i["completed"]],
            key=lambda x: x["priority"],
        )


# ── Core paper index ─────────────────────────────────────────────────

_PAPER_INDEX: List[PaperEntry] = []
_HYPOTHESIS_MAP: List[Hypothesis] = []
_RESEARCH_QUEUE = ResearchQueue()


def register_paper(entry: PaperEntry) -> None:
    _PAPER_INDEX.append(entry)


def register_hypothesis(hyp: Hypothesis) -> None:
    _HYPOTHESIS_MAP.append(hyp)


def get_paper_index() -> List[PaperEntry]:
    return list(_PAPER_INDEX)


def get_hypothesis_map() -> List[Hypothesis]:
    return list(_HYPOTHESIS_MAP)


def get_research_queue() -> ResearchQueue:
    return _RESEARCH_QUEUE


# ── Seed the index with the project's core references ────────────────

def seed_core_references() -> None:
    """Populate the index with the project's primary textbook/paper corpus."""
    _core = [
        PaperEntry("tulchinsky2019", "Finding Alphas", ["I. Tulchinsky et al."], 2019,
                    tags=["alpha", "features"], linked_modules=["alpha_features", "alpha_evaluation"]),
        PaperEntry("ruppert2015", "Statistics and Data Analysis for Financial Engineering", ["D. Ruppert", "D. Matteson"], 2015,
                    tags=["statistics", "risk"], linked_modules=["risk_metrics", "historical_returns"]),
        PaperEntry("chan2013", "Algorithmic Trading", ["E. Chan"], 2013,
                    tags=["trading", "backtesting"], linked_modules=["experiment_runner"]),
        PaperEntry("jansen2020", "Machine Learning for Algorithmic Trading", ["S. Jansen"], 2020,
                    tags=["ml", "alpha", "features"], linked_modules=["alpha_features", "cache_policy"]),
        PaperEntry("depaula2022", "Quantum Machine Learning with Python", ["U. Deopaula-Liddy"], 2022,
                    tags=["quantum", "ml"], linked_modules=["quantum_mapping", "quantum_workflow"]),
        PaperEntry("lopez2018", "Advances in Financial Machine Learning", ["M. Lopez de Prado"], 2018,
                    tags=["ml", "microstructure", "labeling"], linked_modules=["alpha_features", "event_book"]),
        PaperEntry("tsay2010", "Analysis of Financial Time Series", ["R. Tsay"], 2010,
                    tags=["time-series", "volatility", "risk"], linked_modules=["historical_returns", "historical_risk"]),
        PaperEntry("frigo1999", "Cache-Oblivious Algorithms", ["M. Frigo et al."], 1999,
                    tags=["cache", "algorithms", "hpc"], linked_modules=["cache_store", "cache_metrics", "circuit_cache"]),
        PaperEntry("glasserman2003", "Monte Carlo Methods in Financial Engineering", ["P. Glasserman"], 2003,
                    tags=["monte-carlo", "pricing", "variance-reduction"], linked_modules=["pricing", "variance_reduction"]),
        PaperEntry("stamatopoulos2020", "Option Pricing using Quantum Computers", ["N. Stamatopoulos et al."], 2020,
                    tags=["quantum", "pricing", "qae"], linked_modules=["quantum_mapping", "quantum_workflow"]),
    ]
    for entry in _core:
        if not any(p.paper_id == entry.paper_id for p in _PAPER_INDEX):
            register_paper(entry)


def seed_core_hypotheses() -> None:
    """Populate hypothesis map with the project's active research directions."""
    _hyps = [
        Hypothesis("H1", "Similarity-based caching reduces redundant MC paths for near-identical option parameters",
                    source_paper_ids=["frigo1999", "glasserman2003"],
                    target_modules=["cache_store", "circuit_similarity", "cache_metrics"],
                    experiment_ideas=["Vary strike by 0.1% and measure cache similarity hit rate"]),
        Hypothesis("H2", "Circuit-aware cache keys enable quantum/classical workload reuse across problem families",
                    source_paper_ids=["stamatopoulos2020", "frigo1999"],
                    target_modules=["circuit_cache", "quantum_mapping"],
                    experiment_ideas=["Map pricing tasks to circuits, compute key similarity"]),
        Hypothesis("H3", "Antithetic variates combined with caching yield super-linear efficiency gains",
                    source_paper_ids=["glasserman2003"],
                    target_modules=["variance_reduction", "cache_store", "experiment_runner"],
                    experiment_ideas=["Compare cache hit rate with and without antithetic pairs"]),
        Hypothesis("H4", "Microstructure event windows exhibit higher cache stress than broad daily workloads",
                    source_paper_ids=["lopez2018", "frigo1999"],
                    target_modules=["event_book", "cache_metrics", "taq_kdb_adapter"],
                    experiment_ideas=["Run cache experiments on event-window vs daily data slices"]),
    ]
    for h in _hyps:
        if not any(x.hypothesis_id == h.hypothesis_id for x in _HYPOTHESIS_MAP):
            register_hypothesis(h)


# ── arXiv search (optional, metadata-only) ───────────────────────────

def arxiv_search_enabled() -> bool:
    return os.environ.get("QHPC_ARXIV_SEARCH_ENABLED", "true").strip().lower() == "true"


def search_arxiv_metadata(query: str, max_results: int = 10) -> List[Dict[str, str]]:
    """Lightweight arXiv API search returning title/id/summary.  Requires network."""
    if not arxiv_search_enabled():
        return []
    try:
        import urllib.request
        import xml.etree.ElementTree as ET

        url = f"http://export.arxiv.org/api/query?search_query=all:{urllib.request.quote(query)}&max_results={max_results}"
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = resp.read().decode("utf-8")
        root = ET.fromstring(data)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        results: List[Dict[str, str]] = []
        for entry in root.findall("atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            summary_el = entry.find("atom:summary", ns)
            id_el = entry.find("atom:id", ns)
            results.append({
                "title": (title_el.text or "").strip().replace("\n", " ") if title_el is not None else "",
                "arxiv_url": (id_el.text or "").strip() if id_el is not None else "",
                "summary": (summary_el.text or "").strip()[:300] if summary_el is not None else "",
            })
        return results
    except Exception:
        return []


# ── Export structured outputs ────────────────────────────────────────

def export_paper_index(output_dir: Optional[Path] = None) -> Path:
    out = (output_dir or _research_output_dir()) / "paper_index.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps([asdict(p) for p in _PAPER_INDEX], indent=2, default=str), encoding="utf-8")
    return out


def export_hypothesis_map(output_dir: Optional[Path] = None) -> Path:
    out = (output_dir or _research_output_dir()) / "hypothesis_map.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps([asdict(h) for h in _HYPOTHESIS_MAP], indent=2, default=str), encoding="utf-8")
    return out


def export_research_queue(output_dir: Optional[Path] = None) -> Path:
    out = (output_dir or _research_output_dir()) / "research_queue.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    pending = _RESEARCH_QUEUE.pending()
    lines = ["# Research Queue", "", f"Generated: {_utc_now_iso()}", ""]
    if not pending:
        lines.append("(empty)")
    for i, item in enumerate(pending, 1):
        lines.append(f"{i}. [{item['item_type']}] **{item['item_id']}** (priority {item['priority']})")
        if item.get("reason"):
            lines.append(f"   - {item['reason']}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def export_module_literature_links(output_dir: Optional[Path] = None) -> Path:
    """Markdown mapping: module -> papers."""
    out = (output_dir or _research_output_dir()) / "module_literature_links.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    mod_map: Dict[str, List[str]] = {}
    for p in _PAPER_INDEX:
        for mod in p.linked_modules:
            mod_map.setdefault(mod, []).append(f"{p.title} ({p.paper_id})")
    lines = ["# Module-to-Literature Links", "", f"Generated: {_utc_now_iso()}", ""]
    for mod in sorted(mod_map):
        lines.append(f"## {mod}")
        for ref in mod_map[mod]:
            lines.append(f"- {ref}")
        lines.append("")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def export_arxiv_watchlist(queries: Optional[List[str]] = None, output_dir: Optional[Path] = None) -> Path:
    """Run arXiv searches and save results (or empty if disabled)."""
    out = (output_dir or _research_output_dir()) / "arxiv_watchlist.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    if queries is None:
        queries = [
            "quantum monte carlo finance cache",
            "similarity caching computational finance",
            "cache-oblivious algorithms scientific computing",
        ]
    results: Dict[str, Any] = {"generated": _utc_now_iso(), "arxiv_enabled": arxiv_search_enabled(), "queries": {}}
    for q in queries:
        results["queries"][q] = search_arxiv_metadata(q, max_results=5)
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return out


def _detect_local_langchain() -> Optional[Path]:
    """Return path to local langchain repo if present (for doc/code reference)."""
    env_path = os.environ.get("QHPC_LANGCHAIN_LOCAL_PATH", "")
    candidates = [Path(env_path)] if env_path else []
    candidates.append(Path.home() / "Desktop" / "langchain")
    for p in candidates:
        if p.is_dir() and (p / "libs").is_dir():
            return p
    return None


LANGCHAIN_LOCAL_PATH: Optional[Path] = _detect_local_langchain()


def run_literature_expansion(output_dir: Optional[Path] = None) -> Dict[str, str]:
    """Seed references, export all structured outputs, return path map."""
    seed_core_references()
    seed_core_hypotheses()

    if LANGCHAIN_LOCAL_PATH is not None:
        register_paper(PaperEntry(
            paper_id="langchain_local",
            title="LangChain / LangGraph (local source)",
            source="local_repo",
            local_path=str(LANGCHAIN_LOCAL_PATH),
            tags=["orchestration", "langgraph", "agents", "langchain"],
            linked_modules=["orchestrator", "literature_agent"],
            notes=f"Local repo at {LANGCHAIN_LOCAL_PATH}; langgraph used as real execution engine",
        ))

    _RESEARCH_QUEUE.add(item_type="paper", item_id="frigo1999", priority=1,
                        reason="Core cache-oblivious theory for cache research layer")
    _RESEARCH_QUEUE.add(item_type="experiment", item_id="H1_similarity_sweep", priority=2,
                        reason="Validate similarity cache hypothesis with parametric sweep")
    _RESEARCH_QUEUE.add(item_type="paper", item_id="stamatopoulos2020", priority=3,
                        reason="Quantum option pricing circuits for mapping layer")
    paths = {
        "paper_index": str(export_paper_index(output_dir)),
        "hypothesis_map": str(export_hypothesis_map(output_dir)),
        "research_queue": str(export_research_queue(output_dir)),
        "module_literature_links": str(export_module_literature_links(output_dir)),
        "arxiv_watchlist": str(export_arxiv_watchlist(output_dir=output_dir)),
    }
    return paths
