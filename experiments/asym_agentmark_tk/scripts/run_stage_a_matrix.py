#!/usr/bin/env python3
"""Stage A launcher for AsymAgentMark-TK trajectory generation.

This launcher creates temporary JSON configs under the requested output root and
invokes the existing ALFWorld/ToolBench runners. API keys are read from
environment variables and never written into the generated configs.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ALF_SCRIPT = PROJECT_ROOT / "experiments/alfworld/scripts/run_experiment.py"
TB_SCRIPT = PROJECT_ROOT / "experiments/toolbench/scripts/run_experiment.py"
OUT_ROOT = PROJECT_ROOT / "output/asym_agentmark_tk/stage_a"

METHODS = {
    "vanilla": {"watermark": False, "alf_vanilla": True, "alf_method": "differential", "tb_strategy": None},
    "clean": {"watermark": False, "alf_vanilla": False, "alf_method": "differential", "tb_strategy": None},
    "rg": {"watermark": True, "alf_vanilla": False, "alf_method": "green_red", "tb_strategy": "red_green"},
    "agentmark_f": {"watermark": True, "alf_vanilla": False, "alf_method": "differential", "tb_strategy": "differential"},
    "asym_tk": {"watermark": True, "alf_vanilla": False, "alf_method": "rank", "tb_strategy": "rank"},
}

MODELS = {
    "deepseek": {
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com",
        "api_env": "DEEPSEEK_API_KEY",
    },
    "gemini": {
        "model": "gemini-2.0-flash",
        "base_url": "https://aihubmix.com/v1",
        "api_env": "GEMINI_API_KEY",
    },
}

SPLITS = {
    "alfworld": ["id", "ood"],
    "toolbench": [
        "G1_instruction",
        "G1_category",
        "G1_tool",
        "G2_category",
        "G2_instruction",
        "G3_instruction",
    ],
}


def require_env(name: str) -> None:
    if not os.environ.get(name):
        raise RuntimeError(f"Missing required environment variable: {name}")


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def alf_config(method: str, model_key: str, split: str, run: int, output_dir: Path) -> Path:
    method_cfg = METHODS[method]
    model_cfg = MODELS[model_key]
    cfg = {
        "api_key": f"${{{model_cfg['api_env']}}}",
        "base_url": model_cfg["base_url"],
        "model": model_cfg["model"],
        "alfworld_config": {
            "config_path": "experiments/alfworld/configs/base_config.yaml",
            "eval_split": "valid_seen" if split == "id" else "valid_unseen",
            "train_eval": "eval_in_distribution" if split == "id" else "eval_out_of_distribution",
            "num_tasks": 1,
            "max_steps_per_task": 30,
            "context_window_size": 3,
            "use_vanilla_mode": method_cfg["alf_vanilla"],
            "sampling_strategy": "weighted",
            "sampling_temperature": 1.0,
        },
        "watermark_config": {
            "payload_bit_length": 8,
            "ecc_method": "rlnc",
            "rlnc_stream_key": run,
            "rlnc_bits_per_step": 5,
            "rlnc_min_stream_length": 8192,
            "method": method_cfg["alf_method"],
            "green_red_config": {"gamma": 0.5, "delta": 2.0},
            "embedding_strategy": "cyclic",
        },
        "experiment_config": {
            "random_seed": 2025 + run,
            "save_failed_trajectories": True,
            "output_dir": str(output_dir),
            "log_level": "INFO",
            "bit_stream_path": "agentmark/data/bit_stream.txt",
            "num_rounds": 1,
            "resample_tasks_each_round": False,
            "auto_decode": method_cfg["watermark"],
            "save_step_prompts": True,
            "decoder_task_index": None,
        },
        "prompt_config": {
            "use_few_shot": True,
            "few_shot_count": 2,
            "include_reasoning": False,
        },
        "role_config": {
            "name": "AI Assistant",
            "system_prompt": "You are an AI assistant helping to complete household tasks.",
        },
    }
    path = output_dir / "configs" / f"alfworld_{method}_{model_key}_{split}_r{run}.json"
    write_json(path, cfg)
    return path


def tb_config(method: str, model_key: str, split: str, run: int, output_dir: Path) -> Path:
    method_cfg = METHODS[method]
    model_cfg = MODELS[model_key]
    mode = "watermark" if method_cfg["watermark"] else "baseline"
    cfg = {
        "common_config": {
            "data_root": "experiments/toolbench/data/data",
            "toolenv_root": "experiments/toolbench/data/data/toolenv/tools",
            "cache_root": "experiments/toolbench/data/fake_response_cache",
            "use_local_model": False,
            "api_key": f"${{{model_cfg['api_env']}}}",
            "base_url": model_cfg["base_url"],
            "model": model_cfg["model"],
            "split": split,
            "task_limit": 20,
            "filter_failed_reference": False,
            "max_steps": 10,
            "verbose": True,
            "seed": 2025 + run,
            "shuffle": False,
            "temperature": 0.7,
        },
        "baseline_specific": {
            "mode": "baseline",
            "run_name": str(output_dir / "toolbench" / method / model_key / f"run_{run}"),
        },
        "watermark_specific": {
            "mode": "watermark",
            "run_name": str(output_dir / "toolbench" / method / model_key / f"run_{run}"),
            "sampling_strategy": method_cfg["tb_strategy"] or "differential",
            "bit_stream_path": "agentmark/data/bit_stream.txt",
            "watermark_config": {
                "sampling_strategy": method_cfg["tb_strategy"] or "differential",
                "embedding_strategy": "cyclic",
                "payload_bit_length": 8,
                "use_rlnc": True,
            },
        },
    }
    path = output_dir / "configs" / f"toolbench_{method}_{model_key}_{split}_r{run}.json"
    write_json(path, cfg)
    return path


def run_cmd(cmd: list[str], log_path: Path) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as f:
        proc = subprocess.run(cmd, cwd=PROJECT_ROOT, stdout=f, stderr=subprocess.STDOUT)
    return proc.returncode


def alf_task_ids(split: str, smoke: bool) -> list[int]:
    if smoke:
        return [0]
    return list(range(140 if split == "id" else 134))


def tb_task_indices(smoke: bool) -> list[int]:
    return [0] if smoke else list(range(20))


def build_jobs(args: argparse.Namespace) -> list[tuple[list[str], Path]]:
    jobs: list[tuple[list[str], Path]] = []
    out_root = Path(args.output_root).resolve()
    for method in args.methods:
        method_cfg = METHODS[method]
        for model_key in args.models:
            if not args.dry_run:
                require_env(MODELS[model_key]["api_env"])
            for run in args.runs:
                if "alfworld" in args.datasets:
                    for split in SPLITS["alfworld"]:
                        cfg = alf_config(method, model_key, split, run, out_root)
                        for task_id in alf_task_ids(split, args.smoke):
                            split_out = out_root / "alfworld" / method / model_key / f"run_{run}" / split / f"task_{task_id}"
                            cmd = [
                                sys.executable,
                                str(ALF_SCRIPT),
                                "--config",
                                str(cfg),
                                "--eval-split",
                                split,
                                "--task-ids-list",
                                str(task_id),
                                "--num-rounds",
                                "1",
                                "--output-dir",
                                str(split_out),
                                "--random-seed",
                                str(2025 + run),
                            ]
                            if method_cfg["watermark"]:
                                cmd.append("--skip-baseline")
                            else:
                                cmd.append("--skip-watermarked")
                            jobs.append((cmd, split_out / "run.log"))
                if "toolbench" in args.datasets:
                    for split in SPLITS["toolbench"]:
                        cfg = tb_config(method, model_key, split, run, out_root)
                        for task_index in tb_task_indices(args.smoke):
                            log_path = out_root / "logs" / "toolbench" / method / model_key / f"run_{run}" / f"{split}_{task_index}.log"
                            cmd = [
                                sys.executable,
                                str(TB_SCRIPT),
                                "--config",
                                str(cfg),
                                "--split",
                                split,
                                "--seed",
                                str(2025 + run),
                                "--task_index",
                                str(task_index),
                            ]
                            if method_cfg["watermark"]:
                                cmd.extend(["--sampling_strategy", method_cfg["tb_strategy"] or "differential"])
                            else:
                                cmd.append("--no_watermark")
                            jobs.append((cmd, log_path))
    return jobs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--datasets", nargs="+", default=["alfworld", "toolbench"], choices=["alfworld", "toolbench"])
    parser.add_argument("--methods", nargs="+", default=list(METHODS), choices=list(METHODS))
    parser.add_argument("--models", nargs="+", default=list(MODELS), choices=list(MODELS))
    parser.add_argument("--runs", nargs="+", type=int, default=[1, 2, 3])
    parser.add_argument("--output-root", default=str(OUT_ROOT))
    parser.add_argument("--max-workers", type=int, default=50)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    jobs = build_jobs(args)
    print(f"[INFO] prepared {len(jobs)} jobs")
    if args.dry_run:
        for cmd, log_path in jobs[:20]:
            print("[DRY]", " ".join(cmd), ">", log_path)
        if len(jobs) > 20:
            print(f"[DRY] ... {len(jobs) - 20} more jobs")
        return

    failed: list[Path] = []
    with ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        futures = {pool.submit(run_cmd, cmd, log): log for cmd, log in jobs}
        for idx, fut in enumerate(as_completed(futures), start=1):
            log = futures[fut]
            rc = fut.result()
            if rc != 0:
                failed.append(log)
            if idx % 20 == 0 or idx == len(jobs):
                print(f"[INFO] progress {idx}/{len(jobs)} failed={len(failed)}")
    if failed:
        print("[WARN] failed logs:")
        for log in failed[:50]:
            print(log)
        sys.exit(1)
    print("[INFO] all jobs completed")


if __name__ == "__main__":
    main()
