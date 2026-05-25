#!/usr/bin/env python3
"""Build final capacity and perception artifacts for AsymAgentMark-TK.

This entrypoint is offline-only. It reads the canonical 2026-05-10 trajectory
tree and existing A3/A4 RLNC recovery tables, then writes paper-facing
JSON/CSV/Markdown summaries without invoking any model APIs.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
DEFAULT_INPUT_ROOT = Path("/root/autodl-tmp/output-0510")
DEFAULT_OUTPUT_DIR = DEFAULT_INPUT_ROOT / "asym_agentmark_tk"
DEFAULT_PAYLOAD_LENS = (8, 16, 32, 64)
DEFAULT_TOPK = (2, 4, 6, 8, 10, 20)
EXPECTED_ALFWORLD = 8220
EXPECTED_TOOLBENCH = 3600
EXPECTED_WATERMARK = 4728


def load_week2_module() -> Any:
    module_path = SCRIPT_DIR / "run_week2_postprocess.py"
    spec = importlib.util.spec_from_file_location("run_week2_postprocess", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


week2 = load_week2_module()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any, *, overwrite: bool) -> None:
    ensure_writable(path, overwrite)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], *, overwrite: bool) -> None:
    ensure_writable(path, overwrite)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_text(path: Path, text: str, *, overwrite: bool) -> None:
    ensure_writable(path, overwrite)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def ensure_writable(path: Path, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} already exists; pass --overwrite to replace it")


def parse_ints(values: list[str]) -> tuple[int, ...]:
    parsed = tuple(int(v) for v in values)
    if not parsed or any(v <= 0 for v in parsed):
        raise argparse.ArgumentTypeError("values must be positive integers")
    return parsed


def validate_input_root(input_root: Path) -> dict[str, Any]:
    gap_path = input_root / "audit/gap_manifest.json"
    if not gap_path.exists():
        raise FileNotFoundError(f"Missing audit gap manifest: {gap_path}")
    gaps = load_json(gap_path)
    alf_gaps = gaps.get("alfworld", [])
    tb_gaps = gaps.get("toolbench", [])
    if alf_gaps or tb_gaps:
        raise RuntimeError(f"Input root is not complete: alfworld={len(alf_gaps)}, toolbench={len(tb_gaps)}")
    return gaps


def add_runs(rows: list[dict[str, Any]], runs: int = 3) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        item = dict(row)
        if "runs" not in item and "complete_runs" not in item:
            item["runs"] = runs
        out.append(item)
    return out


def add_effective_capacity(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        item = dict(row)
        c_nom = float(item.get("decoded_len_mean", 0.0))
        success = float(item.get("payload_recovery_rate", 0.0))
        item["c_nom_proxy_bits"] = round(c_nom, 6)
        item["c_eff_proxy_bits"] = round(c_nom * success, 6)
        out.append(item)
    return out


def normalize_utility_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        item = dict(row)
        if "mean_success_rate" in item:
            item["mean_success_rate_pct"] = item.pop("mean_success_rate")
        if "std_success_rate" in item:
            item["std_success_rate_pct"] = item.pop("std_success_rate")
        out.append(item)
    return out


def load_rlnc_exact_rows(input_root: Path) -> list[dict[str, Any]]:
    path = input_root / "rlnc_recovery_a3_a4/rlnc_recovery_mean_std.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing exact RLNC recovery table: {path}")
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out = []
    for row in rows:
        item = dict(row)
        item["payload_len"] = 8
        item["decode_success_rate_mean"] = item.pop("recovery_rate_mean")
        item["decode_success_rate_std"] = item.pop("recovery_rate_std")
        item["strict_payload_match"] = True
        out.append(item)
    return out


def summarize_counts(trajectories: list[Any], watermark_trajectories: list[Any]) -> dict[str, Any]:
    dataset_counts = Counter(tr.dataset for tr in trajectories)
    method_counts = Counter((tr.dataset, tr.method) for tr in trajectories)
    return {
        "trajectory_count": len(trajectories),
        "alfworld_count": dataset_counts.get("alfworld", 0),
        "toolbench_count": dataset_counts.get("toolbench", 0),
        "watermark_decode_capable_count": len(watermark_trajectories),
        "method_counts": {"|".join(key): value for key, value in sorted(method_counts.items())},
    }


def validate_counts(counts: dict[str, Any]) -> None:
    expected = {
        "alfworld_count": EXPECTED_ALFWORLD,
        "toolbench_count": EXPECTED_TOOLBENCH,
        "watermark_decode_capable_count": EXPECTED_WATERMARK,
    }
    mismatches = {
        key: {"expected": value, "actual": counts.get(key)}
        for key, value in expected.items()
        if counts.get(key) != value
    }
    if mismatches:
        raise RuntimeError(f"Unexpected trajectory counts: {json.dumps(mismatches, ensure_ascii=False)}")


def validate_rows(name: str, rows: list[dict[str, Any]], required: set[str]) -> None:
    if not rows:
        raise RuntimeError(f"{name} produced no rows")
    for idx, row in enumerate(rows):
        missing = required - set(row)
        if missing:
            raise RuntimeError(f"{name} row {idx} missing columns: {sorted(missing)}")
        for key in ("dataset", "method", "model", "split"):
            if key in row and row[key] in ("", None):
                raise RuntimeError(f"{name} row {idx} has empty {key}")


def validate_capacity_math(rows: list[dict[str, Any]]) -> None:
    for idx, row in enumerate(rows):
        c_nom = float(row["c_nom_proxy_bits"])
        success = float(row["payload_recovery_rate"])
        c_eff = float(row["c_eff_proxy_bits"])
        if not math.isclose(c_eff, round(c_nom * success, 6), abs_tol=1e-6):
            raise RuntimeError(f"capacity C_eff mismatch at row {idx}")


def markdown_table(rows: list[dict[str, Any]], columns: list[str], *, limit: int | None = None) -> str:
    visible = rows if limit is None else rows[:limit]
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in visible:
        lines.append("| " + " | ".join(str(row.get(col, "")) for col in columns) + " |")
    if limit is not None and len(rows) > limit:
        lines.append(f"\nShowing {limit} of {len(rows)} rows. See CSV/JSON for the full table.")
    return "\n".join(lines) + "\n"


def write_artifact_set(
    output_dir: Path,
    stem: str,
    rows: list[dict[str, Any]],
    md_title: str,
    md_columns: list[str],
    *,
    overwrite: bool,
) -> dict[str, str]:
    json_path = output_dir / f"{stem}.json"
    csv_path = output_dir / f"{stem}.csv"
    md_path = output_dir / f"{stem}.md"
    write_json(json_path, rows, overwrite=overwrite)
    write_csv(csv_path, rows, overwrite=overwrite)
    md = f"# {md_title}\n\n" + markdown_table(rows, md_columns, limit=80)
    write_text(md_path, md, overwrite=overwrite)
    return {"json": str(json_path), "csv": str(csv_path), "md": str(md_path)}


def write_readme(output_dir: Path, input_root: Path, summary: dict[str, Any], artifacts: dict[str, dict[str, str]], *, overwrite: bool) -> None:
    lines = [
        "# AsymAgentMark-TK Capacity and Perception Artifacts",
        "",
        f"- Input root: `{input_root}`",
        f"- Output dir: `{output_dir}`",
        "- Scope: ALFWorld + ToolBench only; OASIS is not included in this delivery.",
        "- API usage: none. This is an offline postprocess over canonical 0510 trajectories.",
        "",
        "## Completeness",
        "",
        f"- ALFWorld task records: {summary['counts']['alfworld_count']}",
        f"- ToolBench task records: {summary['counts']['toolbench_count']}",
        f"- A3/A4 watermark decode-capable trajectories: {summary['counts']['watermark_decode_capable_count']}",
        "- `audit/gap_manifest.json` has empty ALFWorld and ToolBench gaps.",
        "",
        "## Capacity Metrics",
        "",
        "- `capacity_l0_l6_proxy.*` is a bit-level offline channel proxy for L0-L6 and Top-k trend analysis.",
        "- `topk_ablation.*` is the AsymAgentMark-TK/rank-only Top-k ablation.",
        "- `capacity_rlnc_exact_recovery.*` is the strict A3/A4 RLNC bit-exact payload recovery table and must not be mixed with proxy capacity claims.",
        "- Proxy `C_eff` is reported as `c_eff_proxy_bits = c_nom_proxy_bits * payload_recovery_rate`, where `c_nom_proxy_bits` is the mean decoded proxy bits per trajectory available from logged metadata.",
        "",
        "## Files",
        "",
    ]
    for name, paths in artifacts.items():
        lines.append(f"- `{name}`: `{paths['csv']}`")
    lines.extend(
        [
            "",
            "## Reproduce",
            "",
            "```bash",
            "cd /root/autodl-tmp/AgentMarkcg/AgentMarkBeta",
            "python experiments/asym_agentmark_tk/scripts/run_capacity_perception.py --overwrite",
            "```",
        ]
    )
    write_text(output_dir / "README.md", "\n".join(lines) + "\n", overwrite=overwrite)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", default=str(DEFAULT_INPUT_ROOT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--payload-lens", nargs="+", default=[str(v) for v in DEFAULT_PAYLOAD_LENS])
    parser.add_argument("--topk", nargs="+", default=[str(v) for v in DEFAULT_TOPK])
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    input_root = Path(args.input_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    payload_lens = parse_ints(args.payload_lens)
    topk_values = parse_ints(args.topk)

    validate_input_root(input_root)
    output_dir.mkdir(parents=True, exist_ok=True)

    week2.PAYLOAD_LENGTHS = payload_lens
    week2.TOPK_VALUES = topk_values

    payload = week2.load_payload(PROJECT_ROOT)
    trajectories = week2.collect_alfworld(input_root) + week2.collect_toolbench(input_root)
    watermark_trajectories = [tr for tr in trajectories if tr.method in {"agentmark", "rank"} and tr.steps]
    counts = summarize_counts(trajectories, watermark_trajectories)
    validate_counts(counts)

    capacity_rows = add_runs(add_effective_capacity(week2.summarize_capacity(watermark_trajectories, payload)))
    topk_rows = add_runs(add_effective_capacity(week2.summarize_topk(watermark_trajectories, payload)))
    utility_rows = normalize_utility_rows(week2.load_utility_summary(input_root))
    jsd_rows = add_runs(week2.summarize_jsd(trajectories))
    rlnc_rows = load_rlnc_exact_rows(input_root)

    validate_rows("capacity_l0_l6_proxy", capacity_rows, {"dataset", "method", "model", "split", "channel", "payload_len", "payload_recovery_rate", "c_eff_proxy_bits"})
    validate_rows("topk_ablation", topk_rows, {"dataset", "method", "model", "split", "topk", "payload_recovery_rate", "c_eff_proxy_bits"})
    validate_rows("utility_retention", utility_rows, {"dataset", "method", "model", "mean_success_rate_pct", "mean_steps"})
    validate_rows("behavior_jsd", jsd_rows, {"dataset", "method", "model", "split", "baseline", "jsd"})
    validate_rows("capacity_rlnc_exact_recovery", rlnc_rows, {"dataset", "method", "model", "split", "runs", "decode_success_rate_mean"})
    validate_capacity_math(capacity_rows)
    validate_capacity_math(topk_rows)

    artifacts = {
        "capacity_l0_l6_proxy": write_artifact_set(
            output_dir,
            "capacity_l0_l6_proxy",
            capacity_rows,
            "Capacity 1.1 L0-L6 Offline Proxy",
            ["dataset", "method", "model", "split", "channel", "payload_len", "runs", "payload_recovery_rate", "c_nom_proxy_bits", "c_eff_proxy_bits"],
            overwrite=args.overwrite,
        ),
        "capacity_rlnc_exact_recovery": write_artifact_set(
            output_dir,
            "capacity_rlnc_exact_recovery",
            rlnc_rows,
            "Capacity 1.1 Strict RLNC Payload Recovery",
            ["dataset", "method", "model", "split", "runs", "payload_len", "decode_success_rate_mean", "decode_success_rate_std", "dedup_packet_mean"],
            overwrite=args.overwrite,
        ),
        "topk_ablation": write_artifact_set(
            output_dir,
            "topk_ablation",
            topk_rows,
            "Capacity 1.2 Top-k Ablation",
            ["dataset", "method", "model", "split", "topk", "runs", "payload_recovery_rate", "c_nom_proxy_bits", "c_eff_proxy_bits"],
            overwrite=args.overwrite,
        ),
        "utility_retention": write_artifact_set(
            output_dir,
            "utility_retention",
            utility_rows,
            "Perception 2.1 Utility Retention",
            ["dataset", "method", "model", "split", "complete_runs", "mean_success_rate_pct", "std_success_rate_pct", "mean_steps", "std_steps"],
            overwrite=args.overwrite,
        ),
        "behavior_jsd": write_artifact_set(
            output_dir,
            "behavior_jsd",
            jsd_rows,
            "Perception 2.2 Behavior Distribution JSD",
            ["dataset", "method", "model", "split", "baseline", "runs", "jsd", "actions"],
            overwrite=args.overwrite,
        ),
    }

    summary = {
        "input_root": str(input_root),
        "output_dir": str(output_dir),
        "payload_lens": payload_lens,
        "topk": topk_values,
        "counts": counts,
        "artifacts": artifacts,
        "assumptions": [
            "ALFWorld and ToolBench only; OASIS is excluded.",
            "No LLM/API calls are made.",
            "Proxy capacity and exact RLNC payload recovery are reported separately.",
        ],
    }
    write_json(output_dir / "summary.json", summary, overwrite=args.overwrite)
    write_readme(output_dir, input_root, summary, artifacts, overwrite=args.overwrite)
    print(f"[INFO] wrote capacity/perception artifacts to {output_dir}")


if __name__ == "__main__":
    main()
