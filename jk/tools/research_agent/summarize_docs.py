#!/usr/bin/env python3
"""Optional utility: list qhpc_cache docs with titles (stdlib only).

Not imported by the core package. Run from repo root:
  python3 tools/research_agent/summarize_docs.py
"""

from __future__ import annotations

from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    docs_dir = root / "docs"
    if not docs_dir.exists():
        print("No docs/ directory found.")
        return
    print(f"Documentation index under {docs_dir}:\n")
    for path in sorted(docs_dir.glob("*.md")):
        first_line = path.read_text(encoding="utf-8").splitlines()[0:1]
        title = first_line[0] if first_line else "(empty)"
        print(f"- {path.name}: {title}")


if __name__ == "__main__":
    main()
