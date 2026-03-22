"""JSON-backed dataset registry and checkpoint tracking (resumable pipeline)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from qhpc_cache.data_models import DatasetRegistryEntry

REGISTRY_VERSION = 1

UnionPath = str | Path

CHECKPOINT_NAMES = (
    "environment_verified",
    "registry_initialized",
    "broad_universe_partial_complete",
    "broad_universe_complete",
    "reference_data_complete",
    "event_book_partial_complete",
    "event_book_complete",
    "rates_layer_complete",
    "analytics_ready",
    "critical_cache_window_built",
    "pixel_trace_exported",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def default_registry_paths(data_root: UnionPath | None = None) -> Dict[str, Path]:
    if data_root is None:
        data_root = os.environ.get("QHPC_DATA_ROOT", "data/qhpc_data")
    root = Path(str(data_root))
    reg = root / "registry"
    return {
        "root": root,
        "registry_dir": reg,
        "registry_file": reg / "dataset_registry.json",
        "checkpoints_file": reg / "checkpoints.json",
    }


def initialize_dataset_registry(
    data_root: UnionPath,
    *,
    force_reset: bool = False,
) -> Path:
    """Create registry directory and empty JSON files; idempotent unless ``force_reset``."""
    paths = default_registry_paths(data_root)
    paths["registry_dir"].mkdir(parents=True, exist_ok=True)
    reg_file = paths["registry_file"]
    ck_file = paths["checkpoints_file"]
    if force_reset or not reg_file.exists():
        payload = {"version": REGISTRY_VERSION, "entries": [], "updated_at_utc": _utc_now_iso()}
        reg_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if force_reset or not ck_file.exists():
        ck = {name: {"status": "pending", "updated_at_utc": ""} for name in CHECKPOINT_NAMES}
        ck_file.write_text(json.dumps({"checkpoints": ck, "updated_at_utc": _utc_now_iso()}, indent=2), encoding="utf-8")
    else:
        doc = json.loads(ck_file.read_text(encoding="utf-8"))
        ck = doc.get("checkpoints", {})
        changed = False
        for name in CHECKPOINT_NAMES:
            if name not in ck:
                ck[name] = {"status": "pending", "updated_at_utc": ""}
                changed = True
        if changed:
            doc["checkpoints"] = ck
            doc["updated_at_utc"] = _utc_now_iso()
            ck_file.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return reg_file


def _load_registry_document(registry_file: Path) -> Dict[str, Any]:
    if not registry_file.exists():
        return {"version": REGISTRY_VERSION, "entries": [], "updated_at_utc": _utc_now_iso()}
    return json.loads(registry_file.read_text(encoding="utf-8"))


def _write_registry_document(registry_file: Path, doc: Dict[str, Any]) -> None:
    doc["updated_at_utc"] = _utc_now_iso()
    registry_file.parent.mkdir(parents=True, exist_ok=True)
    registry_file.write_text(json.dumps(doc, indent=2), encoding="utf-8")


def register_dataset(
    data_root: UnionPath,
    entry: DatasetRegistryEntry,
) -> None:
    """Append or replace a registry row keyed by ``registry_key``."""
    paths = default_registry_paths(data_root)
    reg_file = paths["registry_file"]
    doc = _load_registry_document(reg_file)
    entries: List[Dict[str, Any]] = doc.get("entries", [])
    filtered = [row for row in entries if row.get("registry_key") != entry.registry_key]
    filtered.append(entry.to_dict())
    doc["entries"] = filtered
    _write_registry_document(reg_file, doc)


def register_event_window(
    data_root: UnionPath,
    entry: DatasetRegistryEntry,
) -> None:
    """Alias for ``register_dataset`` with event-kind semantics."""
    register_dataset(data_root, entry)


def register_rates_dataset(
    data_root: UnionPath,
    entry: DatasetRegistryEntry,
) -> None:
    """Alias for ``register_dataset`` with rates-kind semantics."""
    register_dataset(data_root, entry)


def load_dataset_registry(data_root: UnionPath) -> List[DatasetRegistryEntry]:
    paths = default_registry_paths(data_root)
    doc = _load_registry_document(paths["registry_file"])
    return [DatasetRegistryEntry.from_dict(row) for row in doc.get("entries", [])]


def set_checkpoint(
    data_root: UnionPath,
    checkpoint_label: str,
    *,
    status: str = "complete",
) -> None:
    """Update one checkpoint entry (must be in ``CHECKPOINT_NAMES``)."""
    if checkpoint_label not in CHECKPOINT_NAMES:
        raise ValueError(f"Unknown checkpoint: {checkpoint_label}")
    paths = default_registry_paths(data_root)
    ck_file = paths["checkpoints_file"]
    if not ck_file.exists():
        initialize_dataset_registry(data_root)
    doc = json.loads(ck_file.read_text(encoding="utf-8"))
    checkpoints = doc.get("checkpoints", {})
    checkpoints[checkpoint_label] = {"status": status, "updated_at_utc": _utc_now_iso()}
    doc["checkpoints"] = checkpoints
    doc["updated_at_utc"] = _utc_now_iso()
    ck_file.write_text(json.dumps(doc, indent=2), encoding="utf-8")


def load_checkpoints(data_root: UnionPath) -> Dict[str, Dict[str, str]]:
    paths = default_registry_paths(data_root)
    ck_file = paths["checkpoints_file"]
    if not ck_file.exists():
        return {}
    doc = json.loads(ck_file.read_text(encoding="utf-8"))
    return doc.get("checkpoints", {})


def summarize_registry(data_root: UnionPath) -> Dict[str, Any]:
    entries = load_dataset_registry(data_root)
    total_bytes = sum(entry.realized_disk_usage_bytes for entry in entries)
    by_kind: Dict[str, int] = {}
    for entry in entries:
        by_kind[entry.dataset_kind] = by_kind.get(entry.dataset_kind, 0) + 1
    return {
        "entry_count": len(entries),
        "total_realized_disk_usage_bytes": total_bytes,
        "by_dataset_kind": by_kind,
        "checkpoints": load_checkpoints(data_root),
    }


def is_checkpoint_complete(data_root: UnionPath, checkpoint_label: str) -> bool:
    checkpoints = load_checkpoints(data_root)
    row = checkpoints.get(checkpoint_label, {})
    return row.get("status") == "complete"
