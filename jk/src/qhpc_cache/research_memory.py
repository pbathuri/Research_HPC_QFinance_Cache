"""Lightweight research memory: ties uploaded reading lists to modules (no vector DB)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from qhpc_cache.knowledge_cache import (
    CriticalConcept,
    export_critical_window_json_serializable,
    get_critical_cache_window,
    summarize_knowledge_cache,
)


@dataclass
class DocumentAnchor:
    """User- or lab-supplied pointer to an external document (path/DOI/title only)."""

    anchor_id: str
    title_or_path: str
    kind: str
    linked_module_refs: Tuple[str, ...] = field(default_factory=tuple)
    notes: str = ""
    added_at_utc: str = ""

    def __post_init__(self) -> None:
        if not self.added_at_utc:
            self.added_at_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# Runtime list; not persisted automatically (undergraduate simplicity).
_USER_ANCHORS: List[DocumentAnchor] = []


@dataclass
class DataSourceAnchor:
    """Maps an institutional or vendor dataset to modules (WRDS, Databento, kdb, etc.)."""

    anchor_id: str
    source_kind: str
    description: str
    module_refs: Tuple[str, ...] = field(default_factory=tuple)
    registry_key_hint: str = ""
    notes: str = ""
    added_at_utc: str = ""

    def __post_init__(self) -> None:
        if not self.added_at_utc:
            self.added_at_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat()


_DATA_SOURCE_ANCHORS: List[DataSourceAnchor] = []


def register_data_source_anchor(
    *,
    anchor_id: str,
    source_kind: str,
    description: str,
    module_refs: Optional[List[str]] = None,
    registry_key_hint: str = "",
    notes: str = "",
) -> DataSourceAnchor:
    """Record WRDS/Databento/kdb/TAQ alignment for the local reference layer."""
    a = DataSourceAnchor(
        anchor_id=anchor_id,
        source_kind=source_kind,
        description=description,
        module_refs=tuple(module_refs or ()),
        registry_key_hint=registry_key_hint,
        notes=notes,
    )
    _DATA_SOURCE_ANCHORS.append(a)
    return a


def list_data_source_anchors() -> List[DataSourceAnchor]:
    return list(_DATA_SOURCE_ANCHORS)


def seed_default_data_source_anchors() -> None:
    """Idempotent seed for fresh sessions (call from pipeline if desired)."""
    if _DATA_SOURCE_ANCHORS:
        return
    register_data_source_anchor(
        anchor_id="ds_databento_daily",
        source_kind="databento",
        description="Broad US equity/ETF daily OHLCV (EQUS.MINI or configured schema)",
        module_refs=["data_ingestion.py", "data_sources.py"],
        registry_key_hint="databento_daily_universe",
    )
    register_data_source_anchor(
        anchor_id="ds_kdb_taq",
        source_kind="kdb_taq",
        description="Local NYSE TAQ extraction via kdb-taq repo",
        module_refs=["taq_kdb_adapter.py", "event_book.py"],
        registry_key_hint="taq_event_windows",
    )
    register_data_source_anchor(
        anchor_id="ds_wrds_crsp_treasury",
        source_kind="wrds",
        description="CRSP Treasury / inflation context via WRDS SQL",
        module_refs=["wrds_provider.py", "wrds_registry.py", "rates_data.py"],
        registry_key_hint="wrds_crsp_treasury_context",
    )


def register_document_anchor(
    *,
    anchor_id: str,
    title_or_path: str,
    kind: str = "paper",
    linked_module_refs: Optional[List[str]] = None,
    notes: str = "",
) -> DocumentAnchor:
    """Record a document the research group associates with specific modules."""
    anchor = DocumentAnchor(
        anchor_id=anchor_id,
        title_or_path=title_or_path,
        kind=kind,
        linked_module_refs=tuple(linked_module_refs or ()),
        notes=notes,
    )
    _USER_ANCHORS.append(anchor)
    return anchor


def list_document_anchors() -> List[DocumentAnchor]:
    return list(_USER_ANCHORS)


def critical_window_with_modules() -> Dict[str, Any]:
    """Bundle concepts + high-level module map for reporting."""
    seed_default_data_source_anchors()
    return {
        "critical_concepts": export_critical_window_json_serializable(),
        "summary": summarize_knowledge_cache(),
        "registered_anchors": [
            {
                "anchor_id": anchor.anchor_id,
                "title_or_path": anchor.title_or_path,
                "kind": anchor.kind,
                "linked_module_refs": list(anchor.linked_module_refs),
                "notes": anchor.notes,
                "added_at_utc": anchor.added_at_utc,
            }
            for anchor in _USER_ANCHORS
        ],
        "data_source_anchors": [
            {
                "anchor_id": a.anchor_id,
                "source_kind": a.source_kind,
                "description": a.description,
                "module_refs": list(a.module_refs),
                "registry_key_hint": a.registry_key_hint,
                "notes": a.notes,
                "added_at_utc": a.added_at_utc,
            }
            for a in _DATA_SOURCE_ANCHORS
        ],
    }


def align_concept_to_modules(concept_id: str) -> Optional[CriticalConcept]:
    for concept in get_critical_cache_window():
        if concept.concept_id == concept_id:
            return concept
    return None
