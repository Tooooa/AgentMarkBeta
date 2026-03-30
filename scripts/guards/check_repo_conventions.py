#!/usr/bin/env python3
"""Repository convention checks.

Checks:
- AGENTS.md <= 150 lines
- ARCHITECTURE.md <= 300 lines
- docs nesting depth <= 3 levels from docs/
- docs filenames use kebab-case (with allowed exceptions)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"

ALLOWED_FILE_EXCEPTIONS = {
    "OBSERVABILITY.md",
    "QUALITY_SCORE.md",
}

KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\.(md|txt)$")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8", errors="ignore").splitlines())


def main() -> int:
    errors: list[str] = []

    agents = ROOT / "AGENTS.md"
    arch = ROOT / "ARCHITECTURE.md"

    if not agents.exists():
        errors.append("AGENTS.md missing | fix: create AGENTS.md at repository root")
    else:
        c = line_count(agents)
        if c > 150:
            errors.append(f"AGENTS.md exceeds 150 lines ({c}) | fix: move details into docs/* and keep AGENTS as a map")

    if not arch.exists():
        errors.append("ARCHITECTURE.md missing | fix: create ARCHITECTURE.md at repository root")
    else:
        c = line_count(arch)
        if c > 300:
            errors.append(f"ARCHITECTURE.md exceeds 300 lines ({c}) | fix: split details into docs/ and keep architecture concise")

    if DOCS.exists():
        for p in DOCS.rglob("*"):
            if p.is_dir():
                depth = len(p.relative_to(DOCS).parts)
                if depth > 3:
                    errors.append(
                        f"{rel(p)} exceeds max docs depth 3 | fix: flatten directory hierarchy"
                    )
            if p.is_file() and p.suffix.lower() in {".md", ".txt"}:
                if p.name in ALLOWED_FILE_EXCEPTIONS:
                    continue
                if p.name == "index.md":
                    continue
                if not KEBAB_RE.match(p.name):
                    errors.append(
                        f"{rel(p)} is not kebab-case | fix: rename file to kebab-case (lowercase-with-hyphens)"
                    )

    generated = DOCS / "generated"
    if generated.exists():
        for f in generated.rglob("*.md"):
            text = f.read_text(encoding="utf-8", errors="ignore")
            if "自动生成，勿手动编辑" not in text:
                errors.append(
                    f"{rel(f)} missing generated marker | fix: add '自动生成，勿手动编辑' at top of file"
                )

    if errors:
        print("[CONVENTION_GUARD] violations found:")
        for e in sorted(set(errors)):
            print(f"- {e}")
        return 1

    print("[CONVENTION_GUARD] OK: repository conventions are satisfied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
