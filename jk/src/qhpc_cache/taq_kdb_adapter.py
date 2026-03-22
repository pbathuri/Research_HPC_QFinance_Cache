"""kdb+/q bridge for local ``kdb-taq`` workflow: inspection, discovery, extraction hooks.

This module treats **q** as an optional **extraction backend**. Downstream analytics stay in
Python (pandas); outputs are CSV/Parquet under ``qhpc_cache`` storage conventions.

Configuration (environment):

- ``QHPC_KDB_TAQ_REPO`` — root of the local kdb-taq checkout (default: ``~/desktop/kdb-taq`` with
  case variants tried on macOS).
- ``QHPC_KDB_EXTRACTION_COMMAND`` — optional shell command template. Must include ``{spec_file}``
  and may include ``{repo}``. Example: ``q {repo}/scripts/qhpc_export.q -spec {spec_file}``
- ``QHPC_KDB_Q_BINARY`` — override path to ``q`` executable (default: ``q`` on ``PATH``).

The kdb-taq repo is **not** vendored; users maintain extraction scripts there and point the
command template at them.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from qhpc_cache.data_models import EventWindowRequest
from qhpc_cache.data_sources import NyseTaqFileProvider

DEFAULT_KDB_TAQ_PATHS = (
    "/Users/prady/Desktop/kdb-taq",
    "/Users/prady/desktop/kdb-taq",
    "/Users/prady/Desktop/kdb-taq",
)


def default_kdb_taq_repo() -> Path:
    """Resolve repo path: env override, then first existing default candidate, else env path or first default."""
    env = os.environ.get("QHPC_KDB_TAQ_REPO", "").strip()
    if env:
        return Path(env).expanduser()
    for candidate in DEFAULT_KDB_TAQ_PATHS:
        path = Path(candidate)
        if path.is_dir():
            return path
    return Path(DEFAULT_KDB_TAQ_PATHS[0]).expanduser()


def q_binary_path() -> str:
    return os.environ.get("QHPC_KDB_Q_BINARY", "q").strip() or "q"


def q_available() -> Tuple[bool, str]:
    """Return whether ``q`` (or override) is invocable."""
    binary = q_binary_path()
    resolved = shutil.which(binary)
    if resolved:
        return True, resolved
    return False, binary


def inspect_kdb_taq_repo(repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """Summarize repository layout: existence, top-level names, q scripts, README snippet."""
    root = Path(repo_root) if repo_root is not None else default_kdb_taq_repo()
    result: Dict[str, Any] = {
        "repo_root": str(root),
        "exists": root.is_dir(),
        "top_level": [],
        "q_file_count": 0,
        "sample_q_files": [],
        "readme_excerpt": "",
        "q_available": q_available()[0],
        "q_resolution": q_available()[1],
    }
    if not root.is_dir():
        return result
    try:
        children = sorted(entry.name for entry in root.iterdir())
        result["top_level"] = children[:80]
    except OSError:
        result["top_level"] = []
    q_files: List[Path] = []
    q_file_count = 0
    try:
        for path in root.rglob("*.q"):
            q_file_count += 1
            if len(q_files) < 40:
                q_files.append(path)
            if q_file_count >= 100000:
                break
    except OSError:
        pass
    result["q_file_count"] = q_file_count
    result["sample_q_files"] = [str(path.relative_to(root)) for path in q_files[:25]]
    readme = root / "README.md"
    if not readme.is_file():
        readme = root / "readme.md"
    if readme.is_file():
        try:
            text = readme.read_text(encoding="utf-8", errors="replace")[:2000]
            result["readme_excerpt"] = text
        except OSError:
            result["readme_excerpt"] = ""
    return result


def discover_local_taq_datasets(repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """Find q scripts and flat-file style TAQ-ish paths under the kdb-taq tree."""
    root = Path(repo_root) if repo_root is not None else default_kdb_taq_repo()
    out: Dict[str, Any] = {
        "repo_root": str(root),
        "candidate_q_scripts": [],
        "flat_data_candidates": [],
    }
    if not root.is_dir():
        return out
    keywords = ("taq", "trade", "quote", "nyse", "nbbo", "extract", "load", "qhpc")
    try:
        for path in root.rglob("*.q"):
            lower = str(path).lower()
            if any(keyword in lower for keyword in keywords):
                rel = str(path.relative_to(root))
                if rel not in out["candidate_q_scripts"]:
                    out["candidate_q_scripts"].append(rel)
    except OSError:
        pass
    out["candidate_q_scripts"] = sorted(out["candidate_q_scripts"])[:60]
    extensions = (".csv", ".txt", ".bin", ".gz", ".parquet")
    try:
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in extensions:
                rel = str(path.relative_to(root))
                if any(keyword in rel.lower() for keyword in ("taq", "trade", "quote", "nyse")):
                    out["flat_data_candidates"].append(rel)
                    if len(out["flat_data_candidates"]) >= 40:
                        break
    except OSError:
        pass
    return out


def _pick_extraction_script(repo_root: Path) -> Optional[Path]:
    """Prefer explicit env, then known names under repo."""
    env_script = os.environ.get("QHPC_KDB_EXTRACTION_SCRIPT", "").strip()
    if env_script:
        candidate = Path(env_script).expanduser()
        if candidate.is_file():
            return candidate
        inner = repo_root / env_script
        if inner.is_file():
            return inner
    for name in (
        "scripts/qhpc_export_window.q",
        "scripts/qhpc_export.q",
        "qhpc_export_window.q",
        "lib/qhpc_export.q",
    ):
        path = repo_root / name
        if path.is_file():
            return path
    return None


@dataclass
class QExtractionResult:
    ok: bool
    message: str
    output_csv: Optional[Path]
    stdout: str
    stderr: str


def run_q_event_window_extraction(
    request: EventWindowRequest,
    *,
    repo_root: Optional[Path] = None,
    output_csv: Optional[Path] = None,
    timeout_seconds: float = 600.0,
) -> QExtractionResult:
    """Run kdb/q extraction: command template or ``q script.q spec.json``.

    Writes a JSON spec file; q script is responsible for reading it and emitting CSV to
    ``output_csv`` (or path inside spec).
    """
    root = Path(repo_root) if repo_root is not None else default_kdb_taq_repo()
    ok_q, q_path = q_available()
    if not ok_q:
        return QExtractionResult(False, f"q not found on PATH ({q_path})", None, "", "")

    if output_csv is None:
        output_csv = Path(tempfile.mkdtemp(prefix="qhpc_kdb_")) / f"{request.event_identifier}_out.csv"

    spec = {
        "event_identifier": request.event_identifier,
        "event_label": request.event_label,
        "start_timestamp": request.start_timestamp.isoformat(),
        "end_timestamp": request.end_timestamp.isoformat(),
        "symbols": list(request.symbols),
        "output_csv": str(output_csv),
        "repo_root": str(root),
        "notes": request.notes,
    }

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        delete=False,
        encoding="utf-8",
    ) as tmp:
        json.dump(spec, tmp, indent=2)
        spec_file = Path(tmp.name)

    env = os.environ.copy()
    env.setdefault("QHPC_SPEC_FILE", str(spec_file))
    env.setdefault("QHPC_OUTPUT_CSV", str(output_csv))

    command_template = os.environ.get("QHPC_KDB_EXTRACTION_COMMAND", "").strip()
    try:
        if command_template:
            cmd = command_template.format(spec_file=str(spec_file), repo=str(root))
            proc = subprocess.run(
                cmd,
                shell=True,
                cwd=str(root),
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        else:
            script = _pick_extraction_script(root)
            if script is None:
                return QExtractionResult(
                    False,
                    "No QHPC_KDB_EXTRACTION_COMMAND and no qhpc_export*.q under repo; set command or add script.",
                    None,
                    "",
                    "",
                )
            proc = subprocess.run(
                [q_path, str(script), str(spec_file)],
                cwd=str(root),
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        if proc.returncode != 0:
            return QExtractionResult(
                False,
                f"q exit {proc.returncode}",
                None,
                proc.stdout[-4000:] if proc.stdout else "",
                proc.stderr[-4000:] if proc.stderr else "",
            )
        if not output_csv.is_file():
            return QExtractionResult(
                False,
                f"q succeeded but output missing: {output_csv}",
                None,
                proc.stdout[-2000:] if proc.stdout else "",
                proc.stderr[-2000:] if proc.stderr else "",
            )
        return QExtractionResult(True, "ok", output_csv, proc.stdout or "", proc.stderr or "")
    except subprocess.TimeoutExpired:
        return QExtractionResult(False, "q subprocess timeout", None, "", "timeout")
    except Exception as exc:
        return QExtractionResult(False, str(exc), None, "", "")
    finally:
        try:
            spec_file.unlink(missing_ok=True)
        except OSError:
            pass


def load_extracted_event_window(csv_path: Path) -> "Any":
    """Load CSV written by q into a pandas DataFrame."""
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("pandas required; pip install -e '.[data-pipeline]'") from exc
    return pd.read_csv(csv_path)


def validate_extracted_event_window(
    frame: Any,
    request: EventWindowRequest,
) -> Tuple[bool, str]:
    """Reuse TAQ column/time validation from ``NyseTaqFileProvider``."""
    provider = NyseTaqFileProvider()
    return provider.validate_taq_window(frame, request)


def kdb_backend_ready(repo_root: Optional[Path] = None) -> Tuple[bool, str]:
    """True if repo exists, q works, and either command template or default script exists."""
    root = Path(repo_root) if repo_root is not None else default_kdb_taq_repo()
    if not root.is_dir():
        return False, f"kdb-taq repo not found: {root}"
    ok_q, _ = q_available()
    if not ok_q:
        return False, "q executable not available"
    if os.environ.get("QHPC_KDB_EXTRACTION_COMMAND", "").strip():
        return True, "QHPC_KDB_EXTRACTION_COMMAND set"
    script = _pick_extraction_script(root)
    if script:
        return True, f"using script {script.relative_to(root)}"
    return False, "set QHPC_KDB_EXTRACTION_COMMAND or add scripts/qhpc_export_window.q"
