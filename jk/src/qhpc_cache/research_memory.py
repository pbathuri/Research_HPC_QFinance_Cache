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
    }


def align_concept_to_modules(concept_id: str) -> Optional[CriticalConcept]:
    for concept in get_critical_cache_window():
        if concept.concept_id == concept_id:
            return concept
    return None
