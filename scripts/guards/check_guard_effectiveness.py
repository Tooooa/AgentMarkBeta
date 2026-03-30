#!/usr/bin/env python3
"""Guard effectiveness check.

This script intentionally injects a temporary architecture violation,
verifies check_architecture.py catches it with rule R1, then restores state.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARCH_GUARD = ROOT / "scripts" / "guards" / "check_architecture.py"
TMP_FILE = ROOT / "agentmark" / "core" / "_tmp_violation_for_guard.py"


def run_arch_guard() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ARCH_GUARD)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )


def main() -> int:
    baseline = run_arch_guard()
    if baseline.returncode != 0:
        print("[GUARD_EFFECTIVENESS] baseline architecture guard failed.")
        print(baseline.stdout)
        print(baseline.stderr)
        return 1

    try:
        TMP_FILE.write_text("import experiments.toolbench.scripts.run_pipeline\n", encoding="ascii")

        violated = run_arch_guard()
        combined = (violated.stdout or "") + "\n" + (violated.stderr or "")
        if violated.returncode == 0:
            print("[GUARD_EFFECTIVENESS] expected failure but architecture guard passed.")
            return 1
        if "R1 core layer must not depend on environments/dashboard/experiments" not in combined:
            print("[GUARD_EFFECTIVENESS] architecture guard failed for unexpected reason.")
            print(combined)
            return 1

    finally:
        if TMP_FILE.exists():
            TMP_FILE.unlink()

    restored = run_arch_guard()
    if restored.returncode != 0:
        print("[GUARD_EFFECTIVENESS] architecture guard did not recover after cleanup.")
        print(restored.stdout)
        print(restored.stderr)
        return 1

    print("[GUARD_EFFECTIVENESS] OK: violation was caught and guard recovered after cleanup.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
