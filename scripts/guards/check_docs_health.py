#!/usr/bin/env python3
"""Docs health guard.

Checks:
- each docs subdirectory has index.md
- index.md registers files in the same directory
- markdown links are valid relative links
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def list_md_files(directory: Path) -> list[Path]:
    return sorted([p for p in directory.iterdir() if p.is_file() and p.suffix.lower() == ".md"])


def check_index_presence(errors: list[str]) -> None:
    for d in [p for p in DOCS.rglob("*") if p.is_dir()]:
        if d == DOCS:
            continue
        idx = d / "index.md"
        if not idx.exists():
            errors.append(
                f"{rel(d)}: missing index.md | fix: create index.md using docs/index template"
            )


def check_index_registration(errors: list[str]) -> None:
    for d in [p for p in DOCS.rglob("*") if p.is_dir()]:
        idx = d / "index.md"
        if not idx.exists():
            continue
        content = idx.read_text(encoding="utf-8", errors="ignore")
        for f in list_md_files(d):
            if f.name == "index.md":
                continue
            if f.name not in content:
                errors.append(
                    f"{rel(idx)}: file not registered -> {f.name} | fix: add {f.name} to the document table"
                )


def check_links(errors: list[str]) -> None:
    for md in DOCS.rglob("*.md"):
        text = md.read_text(encoding="utf-8", errors="ignore")
        for m in LINK_RE.finditer(text):
            target = m.group(1).strip()
            if not target or target.startswith("http://") or target.startswith("https://") or target.startswith("mailto:"):
                continue
            target = target.split("#", 1)[0]
            if not target:
                continue
            resolved = (md.parent / target).resolve()
            if not resolved.exists():
                errors.append(
                    f"{rel(md)}: dead relative link -> {target} | fix: update link path or create target file"
                )


def main() -> int:
    if not DOCS.exists():
        print("[DOCS_GUARD] docs directory does not exist.")
        return 1

    errors: list[str] = []
    check_index_presence(errors)
    check_index_registration(errors)
    check_links(errors)

    if errors:
        print("[DOCS_GUARD] violations found:")
        for e in sorted(set(errors)):
            print(f"- {e}")
        return 1

    print("[DOCS_GUARD] OK: docs structure and links are healthy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
