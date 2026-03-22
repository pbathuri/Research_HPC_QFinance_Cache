#!/usr/bin/env python3
"""Invoke the Codex CLI non-interactively for planning, review prep, or audits.

Requires `codex` on PATH. Does not import qhpc_cache. Defaults:
- working directory: repository root (parent of ``tools/``)
- ``codex exec`` with ``--sandbox read-only`` unless overridden

Example::

    python3 tools/codex_dev/invoke_codex.py \\
        --prompt "List modules under src/qhpc_cache and one-sentence roles."

Exit code is Codex's exit code (non-zero on failure or agent error).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prompt",
        default="",
        help="Instruction string passed to codex exec (use --prompt-file for long text).",
    )
    parser.add_argument(
        "--prompt-file",
        type=Path,
        default=None,
        help="Read prompt from this UTF-8 file (stdin to codex if '-' ).",
    )
    parser.add_argument(
        "--sandbox",
        default="read-only",
        choices=["read-only", "workspace-write", "danger-full-access"],
        help="Codex sandbox policy (default: read-only).",
    )
    parser.add_argument(
        "--cd",
        type=Path,
        default=None,
        help="Working directory for Codex (default: jk/ repo root).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the command instead of running it.",
    )
    args = parser.parse_args()

    codex_bin = shutil.which("codex")
    if codex_bin is None:
        print("codex not found on PATH; install or add to PATH.", file=sys.stderr)
        return 127

    workdir = args.cd if args.cd is not None else _repo_root()
    cmd: list[str] = [
        codex_bin,
        "exec",
        "-C",
        str(workdir),
        "--sandbox",
        args.sandbox,
    ]

    if args.prompt_file is not None:
        cmd.append("-")
        prompt_data = args.prompt_file.read_text(encoding="utf-8")
        stdin_data = prompt_data.encode("utf-8")
    else:
        stdin_data = None
        cmd.append(args.prompt if args.prompt else "Briefly describe this Python package layout.")

    if args.dry_run:
        print("Would run:", " ".join(cmd))
        if stdin_data is not None:
            print("(with stdin from prompt file)")
        return 0

    proc = subprocess.run(
        cmd,
        input=stdin_data,
        cwd=str(workdir),
        check=False,
    )
    return int(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
