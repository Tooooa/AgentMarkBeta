#!/usr/bin/env python3
"""Architecture dependency guard for AgentMark.

Checks import directions based on docs/design-docs/dependency-rules.md.
Returns non-zero if violations are found.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ISOLATED_PREFIXES = (
    "experiments/oasis_watermark/oasis/",
    "experiments/toolbench/MarkLLM/",
    "dashboard/.git_backup/",
)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def is_isolated(path: Path) -> bool:
    p = rel(path)
    return any(p.startswith(prefix) for prefix in ISOLATED_PREFIXES)


def py_files() -> list[Path]:
    files: list[Path] = []
    for p in ROOT.rglob("*.py"):
        rp = rel(p)
        if "/.git/" in rp or "/__pycache__/" in rp:
            continue
        if is_isolated(p):
            continue
        files.append(p)
    return files


def module_targets(node: ast.AST) -> list[tuple[str, int]]:
    targets: list[tuple[str, int]] = []
    line = getattr(node, "lineno", 0)
    if isinstance(node, ast.Import):
        for n in node.names:
            targets.append((n.name, line))
    elif isinstance(node, ast.ImportFrom):
        if node.module:
            targets.append((node.module, line))
    return targets


def classify(path: str) -> str:
    if path.startswith("agentmark/core/"):
        return "core"
    if path.startswith("agentmark/environments/"):
        return "environments"
    if path.startswith("agentmark/proxy/"):
        return "proxy"
    if path.startswith("agentmark/sdk/"):
        return "sdk"
    if path.startswith("dashboard/server/routers/"):
        return "routers"
    if path.startswith("dashboard/server/services/"):
        return "services"
    if path.startswith("dashboard/server/core/"):
        return "server_core"
    if path.startswith("dashboard/server/models/"):
        return "server_models"
    if path.startswith("dashboard/server/utils/"):
        return "server_utils"
    if path.startswith("experiments/"):
        return "experiments"
    return "other"


def violates(src_kind: str, import_target: str, src_path: str) -> tuple[bool, str]:
    # R1: core cannot import environments/dashboard/experiments
    if src_kind == "core" and (
        import_target.startswith("agentmark.environments")
        or import_target.startswith("dashboard")
        or import_target.startswith("experiments")
    ):
        return True, "R1 core layer must not depend on environments/dashboard/experiments"

    # R2: environments cannot import dashboard
    if src_kind == "environments" and import_target.startswith("dashboard"):
        return True, "R2 environments layer must not depend on dashboard"

    # R3: proxy cannot import experiments
    if src_kind == "proxy" and import_target.startswith("experiments"):
        return True, "R3 proxy layer must not depend on experiments"

    # R4: routers cannot import experiments directly
    if src_kind == "routers" and import_target.startswith("experiments"):
        return True, "R4 routers layer must not depend on experiments directly"

    # R6: agentmark must not import experiments
    if src_path.startswith("agentmark/") and import_target.startswith("experiments"):
        return True, "R6 agentmark must not depend on experiments"

    return False, ""


def main() -> int:
    violations: list[str] = []
    for file in py_files():
        src_path = rel(file)
        src_kind = classify(src_path)
        try:
            tree = ast.parse(file.read_text(encoding="utf-8"), filename=src_path)
        except Exception as exc:
            violations.append(
                f"{src_path}: parse_error | failed to parse file: {exc} | fix: ensure Python syntax is valid"
            )
            continue

        for node in ast.walk(tree):
            for target, line in module_targets(node):
                bad, rule = violates(src_kind, target, src_path)
                if bad:
                    violations.append(
                        f"{src_path}:{line}: {rule} | import={target} | fix: move shared logic to agentmark/sdk or dashboard/server/services and import that boundary"
                    )

    if violations:
        print("[ARCH_GUARD] violations found:")
        for v in sorted(set(violations)):
            print(f"- {v}")
        return 1

    print("[ARCH_GUARD] OK: no architecture dependency violations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
