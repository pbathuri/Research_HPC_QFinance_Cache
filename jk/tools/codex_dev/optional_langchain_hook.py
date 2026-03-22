"""Optional LangChain hook that shells out to Codex (no core package dependency).

Install optional dependencies first::

    pip install -e ".[ai-workflow]"

If ``langchain_core`` is missing, imports from this module still work for
``codex_available`` / ``run_codex_exec``; only ``make_optional_codex_runnable``
returns non-None when LangChain is installed.

**Use case**: glue Codex into a larger research DAG (e.g. LangGraph) while
keeping ``qhpc_cache`` free of framework imports.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional


def codex_available() -> bool:
    return shutil.which("codex") is not None


def run_codex_exec(
    prompt: str,
    *,
    repo_root: Optional[Path] = None,
    sandbox: str = "read-only",
) -> int:
    """Run ``codex exec``; return process exit code. Does not raise on failure."""
    codex_bin = shutil.which("codex")
    if codex_bin is None:
        return 127
    root = repo_root or Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [
            codex_bin,
            "exec",
            "-C",
            str(root),
            "--sandbox",
            sandbox,
            prompt,
        ],
        cwd=str(root),
        check=False,
    )
    return int(proc.returncode)


def make_optional_codex_runnable(
    *,
    repo_root: Optional[Path] = None,
    sandbox: str = "read-only",
) -> Optional[Any]:
    """Return a LangChain Runnable if ``langchain_core`` is installed; else None.

    The runnable accepts a string prompt and returns the string prompt unchanged
    after Codex runs (Codex output is on stdout; capture can be added later).
    For a full integration, wrap subprocess with stdout capture or use Codex MCP.
    """
    try:
        from langchain_core.runnables import RunnableLambda
    except ImportError:
        return None

    root = repo_root or Path(__file__).resolve().parents[2]

    def _step(prompt: str) -> str:
        if not codex_available():
            raise RuntimeError("codex not on PATH")
        codex_bin = shutil.which("codex")
        assert codex_bin is not None
        proc = subprocess.run(
            [
                codex_bin,
                "exec",
                "-C",
                str(root),
                "--sandbox",
                sandbox,
                prompt,
            ],
            cwd=str(root),
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"codex exec exited with {proc.returncode}: {proc.stderr[:500]!r}"
            )
        return proc.stdout or ""

    return RunnableLambda(_step)
