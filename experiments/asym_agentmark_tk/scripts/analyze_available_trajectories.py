#!/usr/bin/env python3
"""Analyze available AsymAgentMark-TK trajectories.

The script is intentionally read-only for experiment outputs. It scans the
current repository output tree, normalizes ALFWorld and ToolBench records into a
common schema, and writes coverage plus utility/JSD summaries for the follow-up
experiments described in the AsymAgentMark-TK design document.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output/asym_agentmark_tk/analysis"

ALFWORLD_EXPECTED = {"id": 140, "ood": 134}
TOOLBENCH_SPLITS = {
    "G1_category",
    "G1_instruction",
    "G1_tool",
    "G2_category",
    "G2_instruction",
    "G3_instruction",
}


@dataclass(frozen=True)
class TrajectoryRecord:
    dataset: str
    method: str
    model: str
    split: str
    run: str
    task_id: str
    success: bool
    total_steps: int
    actions: tuple[str, ...]
    source: str
    bits_embedded: float = 0.0


def load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def infer_method(path: Path, record: dict[str, Any] | None = None) -> str:
    text = str(path).lower()
    if "vanilla" in text or "baseline" in text and record and not record.get("watermark_trace"):
        return "vanilla"
    if "clean" in text:
        return "clean"
    if "red_green" in text or "green_red" in text or "/rg" in text or "_rg" in text:
        return "rg"
    if "rank" in text or "asym" in text:
        return "asym_tk"
    if "agentmark" in text or "differential" in text or "watermark" in text:
        return "agentmark_f"
    if record and record.get("method") == "baseline":
        return "vanilla"
    if record and record.get("watermark_trace"):
        return "agentmark_f"
    return "unknown"


def infer_model(path: Path, metadata: dict[str, Any] | None = None) -> str:
    text = str(path).lower()
    if "gemini" in text:
        return "gemini-flash"
    if "deepseek" in text:
        return "deepseek"
    if metadata:
        cfg = metadata.get("config") if isinstance(metadata.get("config"), dict) else {}
        model = cfg.get("model") or metadata.get("model")
        if model:
            model_text = str(model).lower()
            if "gemini" in model_text:
                return "gemini-flash"
            if "deepseek" in model_text:
                return "deepseek"
    return "unknown"


def infer_alf_split(path: Path) -> str:
    parts = [p.lower() for p in path.parts]
    if "ood" in parts:
        return "ood"
    if "id" in parts:
        return "id"
    text = str(path).lower()
    if "valid_unseen" in text or "out_of_distribution" in text:
        return "ood"
    return "id"


def infer_run(path: Path) -> str:
    text = str(path)
    for pattern in (r"round[_-]?0?([1-9]\d*)", r"run[_-]?0?([1-9]\d*)", r"_r0?([1-9]\d*)"):
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return f"run_{int(match.group(1))}"
    return "run_unknown"


def action_sequence(record: dict[str, Any]) -> tuple[str, ...]:
    actions = record.get("action_sequence")
    if isinstance(actions, list):
        return tuple(str(a) for a in actions)
    trajectory = record.get("trajectory")
    if isinstance(trajectory, list):
        seq = []
        for step in trajectory:
            if isinstance(step, dict):
                action = step.get("selected_action")
                if action:
                    seq.append(str(action))
        return tuple(seq)
    return tuple()


def trace_bits(record: dict[str, Any]) -> float:
    total = 0.0
    for item in record.get("watermark_trace") or []:
        if not isinstance(item, dict):
            continue
        try:
            total += max(0.0, float(item.get("bit_index_after", 0)) - float(item.get("bit_index_before", 0)))
        except Exception:
            pass
    wm_stats = record.get("watermark_stats")
    if isinstance(wm_stats, dict):
        try:
            total = max(total, float(wm_stats.get("total_bits_embedded", 0) or 0))
        except Exception:
            pass
    return total


def collect_alfworld(output_root: Path) -> list[TrajectoryRecord]:
    records: list[TrajectoryRecord] = []
    for path in output_root.rglob("evaluation_report_*.json"):
        data = load_json(path)
        if not isinstance(data, dict):
            continue
        metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
        split = infer_alf_split(path)
        model = infer_model(path, metadata)
        run = infer_run(path)
        for key in ("baseline_results", "watermarked_results"):
            for item in data.get(key) or []:
                if not isinstance(item, dict):
                    continue
                method = infer_method(path, item)
                if key == "baseline_results" and method == "agentmark_f":
                    method = "vanilla"
                task_id = str(item.get("task_id", "unknown"))
                records.append(
                    TrajectoryRecord(
                        dataset="alfworld",
                        method=method,
                        model=model,
                        split=split,
                        run=run,
                        task_id=task_id,
                        success=bool(item.get("success")),
                        total_steps=int(item.get("total_steps", 0) or 0),
                        actions=action_sequence(item),
                        source=str(path),
                        bits_embedded=trace_bits(item),
                    )
                )
    return records


def collect_toolbench(output_root: Path) -> list[TrajectoryRecord]:
    records: list[TrajectoryRecord] = []
    for path in output_root.rglob("*.json"):
        if "toolbench" not in str(path).lower():
            continue
        if path.name in {"rlnc_meta.json", "decode_summary.json"}:
            continue
        if path.parent.name not in TOOLBENCH_SPLITS:
            continue
        data = load_json(path)
        if not isinstance(data, dict) or "trajectory" not in data:
            continue
        records.append(
            TrajectoryRecord(
                dataset="toolbench",
                method=infer_method(path, data),
                model=infer_model(path),
                split=path.parent.name,
                run=infer_run(path),
                task_id=path.stem,
                success=bool(data.get("success", True)),
                total_steps=int(data.get("total_steps", 0) or 0),
                actions=action_sequence(data),
                source=str(path),
                bits_embedded=trace_bits(data),
            )
        )
    return records


def mean_std(values: list[float]) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "std": 0.0}
    return {
        "mean": statistics.mean(values),
        "std": statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def tooleval_solve_rate(items: list[TrajectoryRecord]) -> tuple[float | None, str]:
    if not items:
        return None, "missing"
    first = Path(items[0].source)
    split = items[0].split
    method = "watermark" if items[0].method in {"asym_tk", "agentmark_f", "rg"} else "baseline"
    for parent in first.parents:
        if parent.name.startswith("run_"):
            candidates = [
                parent / "eval" / f"{split}_{method}.json",
                parent / "eval" / f"{split}_watermark.json",
                parent / "eval" / f"{split}_baseline.json",
            ]
            break
    else:
        candidates = []

    for path in candidates:
        data = load_json(path)
        if not isinstance(data, dict) or not data:
            continue
        runtimes: set[str] = set()
        for info in data.values():
            if isinstance(info, dict) and isinstance(info.get("is_solved"), dict):
                runtimes.update(str(k) for k in info["is_solved"].keys())
        if not runtimes:
            runtimes = {"0"}

        scores = []
        for runtime in sorted(runtimes):
            score = 0.0
            for info in data.values():
                solved = info.get("is_solved", {}) if isinstance(info, dict) else {}
                value = solved.get(runtime) if isinstance(solved, dict) else solved
                if value == "AnswerStatus.Solved":
                    score += 1.0
                elif value == "AnswerStatus.Unsure":
                    score += 0.5
            scores.append(score / len(data) * 100.0)
        return statistics.mean(scores), f"tooleval:{path.name}"
    return None, "generation_completion"


def jsd(counter_a: Counter[str], counter_b: Counter[str]) -> float:
    keys = set(counter_a) | set(counter_b)
    total_a = sum(counter_a.values())
    total_b = sum(counter_b.values())
    if total_a == 0 or total_b == 0:
        return 0.0

    def kl(p: dict[str, float], q: dict[str, float]) -> float:
        value = 0.0
        for key, pv in p.items():
            qv = q.get(key, 0.0)
            if pv > 0 and qv > 0:
                value += pv * math.log2(pv / qv)
        return value

    p = {k: counter_a[k] / total_a for k in keys}
    q = {k: counter_b[k] / total_b for k in keys}
    m = {k: 0.5 * (p[k] + q[k]) for k in keys}
    return 0.5 * kl(p, m) + 0.5 * kl(q, m)


def summarize(records: list[TrajectoryRecord]) -> dict[str, Any]:
    by_cell: dict[tuple[str, str, str, str, str], list[TrajectoryRecord]] = defaultdict(list)
    by_rollup: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)
    utility_rows = []

    for rec in records:
        by_cell[(rec.dataset, rec.method, rec.model, rec.split, rec.run)].append(rec)

    for key, items in sorted(by_cell.items()):
        dataset, method, model, split, run = key
        success_metric = "task_success"
        eval_rate = None
        if dataset == "toolbench":
            eval_rate, success_metric = tooleval_solve_rate(items)
        success_rate = (
            eval_rate
            if eval_rate is not None
            else sum(1 for item in items if item.success) / len(items) * 100.0
        )
        avg_steps = statistics.mean(item.total_steps for item in items) if items else 0.0
        total_steps = sum(item.total_steps for item in items)
        total_bits = sum(item.bits_embedded for item in items)
        bps = total_bits / total_steps if total_steps else 0.0
        bpt = total_bits / len(items) if items else 0.0
        utility_rows.append(
            {
                "dataset": dataset,
                "method": method,
                "model": model,
                "split": split,
                "run": run,
                "n": len(items),
                "success_rate": success_rate,
                "success_metric": success_metric,
                "avg_steps": avg_steps,
                "bps": bps,
                "bpt": bpt,
            }
        )
        by_rollup[(dataset, method, model, split)].append(success_rate)

    rollup_rows = []
    for key, values in sorted(by_rollup.items()):
        dataset, method, model, split = key
        stats = mean_std(values)
        rollup_rows.append(
            {
                "dataset": dataset,
                "method": method,
                "model": model,
                "split": split,
                "runs": len(values),
                "success_rate_mean": stats["mean"],
                "success_rate_std": stats["std"],
            }
        )

    jsd_rows = []
    clean_by_dataset_model_split: dict[tuple[str, str, str], Counter[str]] = {}
    dist_by_group: dict[tuple[str, str, str, str], Counter[str]] = defaultdict(Counter)
    for rec in records:
        group = (rec.dataset, rec.method, rec.model, rec.split)
        dist_by_group[group].update(rec.actions)
    for (dataset, method, model, split), counter in dist_by_group.items():
        if method == "clean":
            clean_by_dataset_model_split[(dataset, model, split)] = counter
    for (dataset, method, model, split), counter in sorted(dist_by_group.items()):
        base = clean_by_dataset_model_split.get((dataset, model, split))
        if base is None or method == "clean":
            continue
        jsd_rows.append(
            {
                "dataset": dataset,
                "method": method,
                "model": model,
                "split": split,
                "jsd_vs_clean": jsd(base, counter),
            }
        )

    return {
        "records": len(records),
        "utility_by_run": utility_rows,
        "utility_mean_std": rollup_rows,
        "jsd_vs_clean": jsd_rows,
    }


def coverage(records: Iterable[TrajectoryRecord]) -> dict[str, Any]:
    cells: dict[tuple[str, str, str, str, str], set[str]] = defaultdict(set)
    for rec in records:
        cells[(rec.dataset, rec.method, rec.model, rec.split, rec.run)].add(rec.task_id)
    rows = []
    for (dataset, method, model, split, run), task_ids in sorted(cells.items()):
        expected = None
        if dataset == "alfworld":
            expected = ALFWORLD_EXPECTED.get(split)
        elif dataset == "toolbench":
            expected = 20
        rows.append(
            {
                "dataset": dataset,
                "method": method,
                "model": model,
                "split": split,
                "run": run,
                "unique_tasks": len(task_ids),
                "expected_tasks": expected,
                "complete": expected is not None and len(task_ids) >= expected,
            }
        )
    return {"cells": rows}


def write_markdown(summary: dict[str, Any], cov: dict[str, Any], output: Path) -> None:
    lines = [
        "# AsymAgentMark-TK Available Trajectory Analysis",
        "",
        f"- Normalized trajectory records: {summary['records']}",
        "- Expected full matrix: 5 methods x 2 models x (ALFWorld ID/OOD + ToolBench 6 splits) x 3 runs.",
        "- This report only summarizes data currently present under `output/`; missing cells remain pending for Stage A generation.",
        "",
        "## Coverage",
        "",
            "| Dataset | Method | Model | Split | Run | Unique tasks | Expected | Complete |",
        "|---|---|---|---|---:|---:|---:|---|",
    ]
    for row in cov["cells"]:
        expected = "" if row["expected_tasks"] is None else str(row["expected_tasks"])
        lines.append(
            f"| {row['dataset']} | {row['method']} | {row['model']} | {row['split']} | "
            f"{row['run']} | {row['unique_tasks']} | {expected} | {row['complete']} |"
        )

    lines.extend(
        [
            "",
            "## Utility Mean/Std",
            "",
            "| Dataset | Method | Model | Split | Runs | SR mean | SR std |",
            "|---|---|---|---|---:|---:|---:|",
        ]
    )
    for row in summary["utility_mean_std"]:
        lines.append(
            f"| {row['dataset']} | {row['method']} | {row['model']} | {row['split']} | "
            f"{row['runs']} | {row['success_rate_mean']:.2f} | {row['success_rate_std']:.2f} |"
        )

    lines.extend(
        [
            "",
            "## JSD vs Clean",
            "",
            "| Dataset | Method | Model | Split | JSD |",
            "|---|---|---|---|---:|",
        ]
    )
    if summary["jsd_vs_clean"]:
        for row in summary["jsd_vs_clean"]:
            lines.append(
                f"| {row['dataset']} | {row['method']} | {row['model']} | "
                f"{row['split']} | {row['jsd_vs_clean']:.6f} |"
            )
    else:
        lines.append("| PENDING | PENDING | PENDING | PENDING | PENDING |")

    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", default=str(PROJECT_ROOT / "output"))
    parser.add_argument("--analysis-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    output_root = Path(args.output_root).resolve()
    analysis_dir = Path(args.analysis_dir).resolve()
    analysis_dir.mkdir(parents=True, exist_ok=True)

    records = collect_alfworld(output_root) + collect_toolbench(output_root)
    summary = summarize(records)
    cov = coverage(records)

    (analysis_dir / "available_trajectory_summary.json").write_text(
        json.dumps(
            {
                "summary": summary,
                "coverage": cov,
                "records": [asdict(rec) for rec in records],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    write_markdown(summary, cov, analysis_dir / "available_trajectory_summary.md")
    print(f"[INFO] wrote {analysis_dir / 'available_trajectory_summary.md'}")


if __name__ == "__main__":
    main()
