#!/usr/bin/env python3
"""Post-process ToolBench rank runs.

This script intentionally starts after model generation:
1. convert per-query AgentMark predictions to StableToolBench eval format;
2. optionally run ToolEval pass-rate evaluation;
3. write a compact markdown summary across run_1..run_3.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SPLITS = [
    "G1_category",
    "G1_instruction",
    "G1_tool",
    "G2_category",
    "G2_instruction",
    "G3_instruction",
]
TASK_LABELS = {
    "G1_category": "A1 (G1_category)",
    "G1_instruction": "A2 (G1_instruction)",
    "G1_tool": "A3 (G1_tool)",
    "G2_category": "A4 (G2_category)",
    "G2_instruction": "A5 (G2_instruction)",
    "G3_instruction": "A6 (G3_instruction)",
}


def resolve_path(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else (PROJECT_ROOT / p).resolve()


def run(cmd: list[str], env: dict[str, str] | None = None) -> None:
    print("[CMD]", " ".join(cmd))
    subprocess.run(cmd, cwd=PROJECT_ROOT, env=env, check=True)


def mean_std(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    return statistics.mean(values), statistics.pstdev(values)


def fmt_mean(values: list[float], digits: int = 1) -> str:
    if not values:
        return "PENDING"
    m, s = mean_std(values)
    return f"{m:.{digits}f}+/-{s:.{digits}f}"


def prediction_metrics(exp_dir: Path, split: str) -> dict[str, float]:
    steps: list[float] = []
    total_bits = 0.0
    total_tasks = 0
    for path in sorted((exp_dir / split).glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        total_tasks += 1
        step_count = float(data.get("total_steps", 0) or 0)
        steps.append(step_count)
        trace = data.get("watermark_trace") or []
        for item in trace:
            if isinstance(item, dict):
                total_bits += float(item.get("bit_index_after", 0) - item.get("bit_index_before", 0))

    total_steps = sum(steps)
    return {
        "tasks": float(total_tasks),
        "steps": statistics.mean(steps) if steps else 0.0,
        "bps": (total_bits / total_steps) if total_steps else 0.0,
        "bpt": (total_bits / total_tasks) if total_tasks else 0.0,
    }


def eval_solve_rate(eval_file: Path) -> float | None:
    if not eval_file.exists():
        return None
    try:
        data: dict[str, Any] = json.loads(eval_file.read_text())
    except Exception:
        return None
    if not data:
        return 0.0

    runtimes: set[int] = set()
    for info in data.values():
        solved = info.get("is_solved", {})
        if isinstance(solved, dict):
            runtimes.update(int(k) for k in solved.keys())
    if not runtimes:
        runtimes = {0}

    scores: list[float] = []
    for runtime in sorted(runtimes):
        score = 0.0
        for info in data.values():
            solved = info.get("is_solved", {})
            value = solved.get(str(runtime)) if isinstance(solved, dict) else solved
            if value == "AnswerStatus.Solved":
                score += 1.0
            elif value == "AnswerStatus.Unsure":
                score += 0.5
        scores.append(score / len(data) * 100.0)
    return statistics.mean(scores)


def build_eval_env() -> dict[str, str]:
    env = os.environ.copy()
    pool = None
    if os.environ.get("API_POOL_FILE"):
        return env
    if os.environ.get("DASHSCOPE_API_KEY"):
        pool = [{
            "api_key": os.environ["DASHSCOPE_API_KEY"],
            "api_base": os.environ.get("OPENAI_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model": os.environ.get("EXP_MODEL") or os.environ.get("EVAL_MODEL") or "deepseek-v3.2",
        }]
    elif os.environ.get("DEEPSEEK_API_KEY"):
        pool = [{
            "api_key": os.environ["DEEPSEEK_API_KEY"],
            "api_base": os.environ.get("OPENAI_BASE_URL") or "https://api.deepseek.com/v1",
            "model": os.environ.get("EXP_MODEL") or os.environ.get("EVAL_MODEL") or "deepseek-v3.2",
        }]
    elif os.environ.get("OPENAI_API_KEY") and os.environ.get("EVAL_MODEL"):
        pool = [{
            "api_key": os.environ["OPENAI_API_KEY"],
            "api_base": os.environ.get("OPENAI_BASE_URL"),
            "model": os.environ["EVAL_MODEL"],
        }]
    if pool is None:
        raise RuntimeError(
            "No evaluator API configured. Set API_POOL_FILE, or DEEPSEEK_API_KEY, "
            "or OPENAI_API_KEY plus EVAL_MODEL."
        )
    tmp = tempfile.NamedTemporaryFile("w", suffix="_api_pool.json", delete=False)
    json.dump(pool, tmp)
    tmp.close()
    env["API_POOL_FILE"] = tmp.name
    return env


def convert_all(rank_root: Path, runs: list[int], method: str) -> None:
    script = PROJECT_ROOT / "experiments/toolbench/tools/stable_toolbench_eval/convert_to_answer_format.py"
    for run_id in runs:
        run_root = rank_root / f"run_{run_id}"
        exp_dir = run_root / f"exp_rank_toolbench_gemini_r{run_id}"
        for split in SPLITS:
            answer_dir = exp_dir / split
            if not answer_dir.exists():
                print(f"[WARN] missing {answer_dir}")
                continue
            output = run_root / "converted" / method / f"{split}.json"
            output.parent.mkdir(parents=True, exist_ok=True)
            run([
                sys.executable,
                str(script),
                "--answer_dir",
                str(answer_dir),
                "--method",
                method,
                "--output",
                str(output),
            ])


def eval_all(
    rank_root: Path,
    runs: list[int],
    method: str,
    test_ids: Path,
    evaluate_times: int,
    max_eval_threads: int,
) -> None:
    script = PROJECT_ROOT / "experiments/toolbench/tools/stable_toolbench_eval/eval_pass_rate.py"
    env = build_eval_env()
    for run_id in runs:
        run_root = rank_root / f"run_{run_id}"
        save_path = run_root / "eval"
        save_path.mkdir(parents=True, exist_ok=True)
        for split in SPLITS:
            converted = run_root / "converted" / method / f"{split}.json"
            if not converted.exists():
                print(f"[WARN] missing converted file {converted}")
                continue
            run([
                sys.executable,
                str(script),
                "--converted_answer_path",
                str(run_root / "converted"),
                "--save_path",
                str(save_path),
                "--reference_model",
                method,
                "--test_ids",
                str(test_ids),
                "--test_set",
                split,
                "--max_eval_threads",
                str(max_eval_threads),
                "--evaluate_times",
                str(evaluate_times),
                "--overwrite",
            ], env=env)


def write_summary(rank_root: Path, runs: list[int], method: str, title: str) -> Path:
    rows: list[str] = []
    split_sr: dict[str, list[float]] = {split: [] for split in SPLITS}
    split_steps: dict[str, list[float]] = {split: [] for split in SPLITS}
    split_bps: dict[str, list[float]] = {split: [] for split in SPLITS}
    split_bpt: dict[str, list[float]] = {split: [] for split in SPLITS}

    for split in SPLITS:
        for run_id in runs:
            run_root = rank_root / f"run_{run_id}"
            exp_dir = run_root / f"exp_rank_toolbench_gemini_r{run_id}"
            metrics = prediction_metrics(exp_dir, split)
            if metrics["tasks"]:
                split_steps[split].append(metrics["steps"])
                split_bps[split].append(metrics["bps"])
                split_bpt[split].append(metrics["bpt"])
            sr = eval_solve_rate(run_root / "eval" / f"{split}_{method}.json")
            if sr is not None:
                split_sr[split].append(sr)

        rows.append(
            "| ToolBench | {task} | {sr} | {steps} | {bps} | {bpt} | N/A | N/A |".format(
                task=TASK_LABELS[split],
                sr=fmt_mean(split_sr[split]),
                steps=fmt_mean(split_steps[split]),
                bps=fmt_mean(split_bps[split], 6),
                bpt=fmt_mean(split_bpt[split], 6),
            )
        )

    avg_sr = [statistics.mean(vals) for vals in split_sr.values() if vals]
    avg_steps = [statistics.mean(vals) for vals in split_steps.values() if vals]
    avg_bps = [statistics.mean(vals) for vals in split_bps.values() if vals]
    avg_bpt = [statistics.mean(vals) for vals in split_bpt.values() if vals]
    rows.append(
        "| ToolBench | Avg | {sr} | {steps} | {bps} | {bpt} | N/A | N/A |".format(
            sr=fmt_mean(avg_sr),
            steps=fmt_mean(avg_steps),
            bps=fmt_mean(avg_bps, 6),
            bpt=fmt_mean(avg_bpt, 6),
        )
    )

    decode_lines = []
    for run_id in runs:
        p = rank_root / f"run_{run_id}" / f"exp_rank_toolbench_gemini_r{run_id}" / "decode_summary.json"
        if not p.exists():
            continue
        try:
            d = json.loads(p.read_text())
        except Exception:
            continue
        decode_lines.append(
            f"- run_{run_id}: RLNC {d.get('rlnc_status', 'N/A')}, "
            f"accuracy {float(d.get('global_accuracy', 0.0)):.2f}%, "
            f"bits {d.get('total_bits_decoded', 0)}"
        )

    out_dir = rank_root / "实验结果汇总表格"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "实验结果汇总表格_rank.md"
    body = [
        f"# {title} ToolBench 实验结果汇总表格",
        "",
        "| Setting | Task | SR (%) | Steps | bps | bpt | ▲s/step | ▲Tok/step(%) |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
        *rows,
        "",
        "## Decode",
        *(decode_lines or ["- No decode_summary.json found."]),
        "",
        "Note: SR stays PENDING until ToolEval JSON files exist under run_*/eval/.",
    ]
    out_file.write_text("\n".join(body), encoding="utf-8")
    return out_file


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rank-root",
        default="output/toolbench/rank/gemini-flash",
        help="Directory containing run_1, run_2, run_3.",
    )
    parser.add_argument("--runs", nargs="+", type=int, default=[1, 2, 3])
    parser.add_argument("--method", default="watermark")
    parser.add_argument("--run-eval", action="store_true")
    parser.add_argument(
        "--test-ids",
        default="experiments/toolbench/data/data/test_query_ids",
    )
    parser.add_argument("--evaluate-times", type=int, default=1)
    parser.add_argument("--max-eval-threads", type=int, default=10)
    parser.add_argument("--title", default="Gemini Flash Rank")
    args = parser.parse_args()

    rank_root = resolve_path(args.rank_root)
    convert_all(rank_root, args.runs, args.method)
    if args.run_eval:
        eval_all(
            rank_root,
            args.runs,
            args.method,
            resolve_path(args.test_ids),
            args.evaluate_times,
            args.max_eval_threads,
        )
    summary = write_summary(rank_root, args.runs, args.method, args.title)
    print(f"[INFO] summary written to {summary}")


if __name__ == "__main__":
    main()
