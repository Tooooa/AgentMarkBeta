"""Run A0 vanilla ToolBench experiments (6 splits x 20 tasks x 3 rounds).

This launcher keeps the ToolBench run in baseline mode (no watermark) and writes
outputs with ALFWorld-aligned fields (trajectory/prompt/llm usage/time/action sequence).
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


DEFAULT_SPLITS = [
    "G1_instruction",
    "G1_category",
    "G1_tool",
    "G2_category",
    "G2_instruction",
    "G3_instruction",
]

DEFAULT_ROUNDS = [
    ("r1", 42),
    ("r2", 12345),
    ("r3", 2024),
]


def run_cmd(cmd, cwd: Path) -> None:
    print("[CMD]", " ".join(cmd))
    res = subprocess.run(cmd, cwd=str(cwd))
    if res.returncode != 0:
        raise SystemExit(f"Command failed with code {res.returncode}: {' '.join(cmd)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run A0 vanilla ToolBench experiments")
    parser.add_argument(
        "--config",
        type=str,
        default="experiments/toolbench/configs/a0_vanilla_toolbench.json",
        help="Base ToolBench config JSON",
    )
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="Model name (e.g., deepseek-chat, gemini-2.0-flash)",
    )
    parser.add_argument(
        "--base_url",
        type=str,
        required=True,
        help="OpenAI-compatible base URL",
    )
    parser.add_argument(
        "--api_key",
        type=str,
        required=True,
        help="API key for the model provider",
    )
    parser.add_argument(
        "--task_limit",
        type=int,
        default=20,
        help="Tasks per split (default: 20)",
    )
    parser.add_argument(
        "--run_root",
        type=str,
        default="output/a0_vanilla_toolbench",
        help="Output root directory",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[3]
    script_path = project_root / "experiments" / "toolbench" / "scripts" / "run_experiment.py"
    config_path = project_root / args.config

    run_root = project_root / args.run_root / args.model.replace("/", "_")
    run_root.mkdir(parents=True, exist_ok=True)

    os.environ["A0_TOOLBENCH_MODEL"] = args.model
    os.environ["A0_TOOLBENCH_BASE_URL"] = args.base_url
    os.environ["A0_TOOLBENCH_API_KEY"] = args.api_key
    os.environ["A0_TOOLBENCH_TASK_LIMIT"] = str(args.task_limit)

    for round_name, seed in DEFAULT_ROUNDS:
        run_name = run_root / round_name
        for split in DEFAULT_SPLITS:
            cmd = [
                sys.executable,
                "-u",
                str(script_path),
                "--config",
                str(config_path),
                "--split",
                split,
                "--seed",
                str(seed),
                "--run_name",
                str(run_name),
                "--no_watermark",
            ]
            run_cmd(cmd, cwd=project_root)

    print(f"[INFO] A0 vanilla ToolBench run finished. Output root: {run_root}")


if __name__ == "__main__":
    main()
