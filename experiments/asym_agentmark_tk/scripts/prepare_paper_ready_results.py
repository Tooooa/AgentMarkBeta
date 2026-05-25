#!/usr/bin/env python3
"""Prepare paper-ready non-robustness result tables for AsymAgentMark-TK.

The script only reads already-generated offline artifacts under output-0510.
It intentionally excludes ongoing robustness experiments. The generated tables
are designed for direct use in the S&P-style paper draft and keep proxy capacity
separate from strict payload recovery.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
DEFAULT_INPUT_ROOT = PROJECT_ROOT / "output-0510"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "papers/sp-asym-agentmark-tk/results/non_robust_0510"

METHOD_LABELS = {
    "vanilla": "Vanilla",
    "clean": "Clean",
    "rg": "Red-Green",
    "agentmark": "AgentMark-F",
    "rank": "AsymAgentMark-TK",
}

DATASET_LABELS = {
    "alfworld": "ALFWorld",
    "ALFWorld": "ALFWorld",
    "toolbench": "ToolBench",
    "ToolBench": "ToolBench",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def fnum(value: Any, digits: int = 2) -> str:
    return f"{float(value):.{digits}f}"


def pct(value: Any, digits: int = 1) -> str:
    return f"{100.0 * float(value):.{digits}f}"


def mean(values: Iterable[float]) -> float:
    vals = list(values)
    if not vals:
        return float("nan")
    return statistics.fmean(vals)


def stdev(values: Iterable[float]) -> float:
    vals = list(values)
    if len(vals) < 2:
        return 0.0
    return statistics.stdev(vals)


def label_method(method: str) -> str:
    return METHOD_LABELS.get(method, method)


def label_dataset(dataset: str) -> str:
    return DATASET_LABELS.get(dataset, dataset)


def grouped(rows: Iterable[dict[str, Any]], keys: tuple[str, ...]) -> dict[tuple[Any, ...], list[dict[str, Any]]]:
    out: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        out[tuple(row[k] for k in keys)].append(row)
    return out


def markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(col, "")) for col in columns) + " |")
    return "\n".join(lines)


def latex_escape(text: Any) -> str:
    s = str(text)
    return (
        s.replace("\\", "\\textbackslash{}")
        .replace("&", "\\&")
        .replace("%", "\\%")
        .replace("_", "\\_")
        .replace("#", "\\#")
    )


def latex_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]], caption: str, label: str) -> str:
    colspec = "l" * len(columns)
    lines = [
        "\\begin{table}[t]",
        "\\centering",
        "\\small",
        f"\\caption{{{latex_escape(caption)}}}",
        f"\\label{{{label}}}",
        f"\\begin{{tabular}}{{{colspec}}}",
        "\\toprule",
        " & ".join(title for _, title in columns) + " \\\\",
        "\\midrule",
    ]
    for row in rows:
        lines.append(" & ".join(latex_escape(row.get(key, "")) for key, _ in columns) + " \\\\")
    lines.extend(["\\bottomrule", "\\end{tabular}", "\\end{table}", ""])
    return "\n".join(lines)


def build_utility_tables(input_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = read_csv(input_root / "asym_agentmark_tk/utility_retention.csv")
    detailed: list[dict[str, Any]] = []
    for row in rows:
        detailed.append(
            {
                "Dataset": label_dataset(row["dataset"]),
                "Method": label_method(row["method"]),
                "Model": row["model"],
                "Split": row["split"],
                "Runs": row["complete_runs"],
                "SR (%)": fnum(row["mean_success_rate_pct"], 2),
                "SR Std": fnum(row["std_success_rate_pct"], 2),
                "Steps": fnum(row["mean_steps"], 2),
                "Steps Std": fnum(row["std_steps"], 2),
            }
        )

    summary: list[dict[str, Any]] = []
    for (dataset, method), items in grouped(rows, ("dataset", "method")).items():
        sr = [float(x["mean_success_rate_pct"]) for x in items]
        steps = [float(x["mean_steps"]) for x in items]
        summary.append(
            {
                "Dataset": label_dataset(dataset),
                "Method": label_method(method),
                "Cells": len(items),
                "SR Mean (%)": fnum(mean(sr), 2),
                "SR Cell Std": fnum(stdev(sr), 2),
                "Steps Mean": fnum(mean(steps), 2),
            }
        )
    summary.sort(key=lambda r: (r["Dataset"], ["Vanilla", "Clean", "Red-Green", "AgentMark-F", "AsymAgentMark-TK"].index(r["Method"])))
    return summary, detailed


def build_jsd_table(input_root: Path) -> list[dict[str, Any]]:
    rows = [r for r in read_csv(input_root / "asym_agentmark_tk/behavior_jsd.csv") if r["baseline"] == "clean"]
    out: list[dict[str, Any]] = []
    for (dataset, method), items in grouped(rows, ("dataset", "method")).items():
        vals = [float(x["jsd"]) for x in items]
        out.append(
            {
                "Dataset": label_dataset(dataset),
                "Method": label_method(method),
                "Cells": len(items),
                "JSD vs Clean": fnum(mean(vals), 4),
                "JSD Cell Std": fnum(stdev(vals), 4),
            }
        )
    out.sort(key=lambda r: (r["Dataset"], r["Method"]))
    return out


def build_strict_recovery_table(input_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = read_csv(input_root / "rlnc_recovery_a3_a4/rlnc_recovery_mean_std.csv")
    detailed: list[dict[str, Any]] = []
    for row in rows:
        detailed.append(
            {
                "Dataset": label_dataset(row["dataset"]),
                "Method": label_method(row["method"]),
                "Model": row["model"],
                "Split": row["split"],
                "Runs": row["runs"],
                "Payload Recovery (%)": pct(row["recovery_rate_mean"], 2),
                "Recovery Std (%)": pct(row["recovery_rate_std"], 2),
                "Dedup Packets": fnum(row["dedup_packet_mean"], 2),
            }
        )

    summary: list[dict[str, Any]] = []
    for (dataset, method), items in grouped(rows, ("dataset", "method")).items():
        rates = [float(x["recovery_rate_mean"]) for x in items]
        packets = [float(x["dedup_packet_mean"]) for x in items]
        summary.append(
            {
                "Dataset": label_dataset(dataset),
                "Method": label_method(method),
                "Cells": len(items),
                "Payload Recovery (%)": pct(mean(rates), 2),
                "Recovery Cell Std (%)": pct(stdev(rates), 2),
                "Dedup Packets": fnum(mean(packets), 2),
            }
        )
    summary.sort(key=lambda r: (r["Dataset"], r["Method"]))
    return summary, detailed


def build_topk_table(input_root: Path) -> list[dict[str, Any]]:
    rows = read_csv(input_root / "asym_agentmark_tk/topk_ablation.csv")
    out: list[dict[str, Any]] = []
    for (dataset, topk), items in grouped(rows, ("dataset", "topk")).items():
        rates = [float(x["payload_recovery_rate"]) for x in items]
        c_eff = [float(x["c_eff_proxy_bits"]) for x in items]
        bit_match = [float(x["bit_match_rate_mean"]) for x in items]
        out.append(
            {
                "Dataset": label_dataset(dataset),
                "Top-k": topk,
                "Cells": len(items),
                "Payload Recovery (%)": pct(mean(rates), 2),
                "Bit Match (%)": pct(mean(bit_match), 2),
                "Proxy C_eff": fnum(mean(c_eff), 3),
            }
        )
    out.sort(key=lambda r: (r["Dataset"], int(r["Top-k"])))
    return out


def build_capacity_proxy_payload8(input_root: Path) -> list[dict[str, Any]]:
    rows = [
        r
        for r in read_csv(input_root / "asym_agentmark_tk/capacity_l0_l6_proxy.csv")
        if r["payload_len"] == "8"
    ]
    out: list[dict[str, Any]] = []
    for (dataset, method, channel), items in grouped(rows, ("dataset", "method", "channel")).items():
        rates = [float(x["payload_recovery_rate"]) for x in items]
        c_eff = [float(x["c_eff_proxy_bits"]) for x in items]
        bit_match = [float(x["bit_match_rate_mean"]) for x in items]
        out.append(
            {
                "Dataset": label_dataset(dataset),
                "Method": label_method(method),
                "Logged Channel": channel,
                "Cells": len(items),
                "Payload Recovery (%)": pct(mean(rates), 2),
                "Bit Match (%)": pct(mean(bit_match), 2),
                "Proxy C_eff": fnum(mean(c_eff), 3),
            }
        )
    out.sort(key=lambda r: (r["Dataset"], r["Method"], r["Logged Channel"]))
    return out


def build_evidence_tables(input_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    confidence = read_csv(input_root / "evidence_strength/stage_d_4_1_confidence_summary.csv")
    confidence_rows = [
        r
        for r in confidence
        if r["N"] == "50" and ((r["method"] == "agentmark" and r["config"] == "L0_exact_probs") or (r["method"] == "rank" and r["config"] == "top10"))
    ]
    confidence_out: list[dict[str, Any]] = []
    for (dataset, method, config), items in grouped(confidence_rows, ("dataset", "method", "config")).items():
        confidence_out.append(
            {
                "Dataset": label_dataset(dataset),
                "Method": label_method(method),
                "Config": config,
                "Cells": len(items),
                "Match Rate (%)": pct(mean(float(x["match_rate_mean"]) for x in items), 2),
                "Mean log10 p": fnum(mean(float(x["log10_p_value_mean"]) for x in items), 3),
            }
        )
    confidence_out.sort(key=lambda r: (r["Dataset"], r["Method"], r["Config"]))

    thresholds = read_csv(input_root / "evidence_strength/stage_d_4_2_thresholds_summary.csv")
    threshold_rows = [
        r
        for r in thresholds
        if r["payload_len"] == "32"
        and r["alpha"] == "0.01"
        and ((r["method"] == "agentmark" and r["config"] == "L0_exact_probs") or (r["method"] == "rank" and r["config"] in {"top10", "top5", "top3", "top2"}))
    ]
    threshold_out: list[dict[str, Any]] = []
    for (dataset, method, config), items in grouped(threshold_rows, ("dataset", "method", "config")).items():
        attained = sum(int(x["attained_runs"]) for x in items)
        runs = sum(int(x["runs"]) for x in items)
        valid_n = [float(x["N_min_mean"]) for x in items if x["N_min_mean"]]
        threshold_out.append(
            {
                "Dataset": label_dataset(dataset),
                "Method": label_method(method),
                "Config": config,
                "Payload": 32,
                "Alpha": "0.01",
                "Attained": f"{attained}/{runs}",
                "N_min": fnum(mean(valid_n), 1) if valid_n else "NA",
            }
        )
    threshold_out.sort(key=lambda r: (r["Dataset"], r["Method"], r["Config"]))
    return confidence_out, threshold_out


def write_readme(output_dir: Path, input_root: Path, tables: dict[str, list[dict[str, Any]]]) -> None:
    lines = [
        "# Paper-ready non-robustness results for output-0510",
        "",
        f"- Source root: `{input_root}`",
        "- Scope: ALFWorld and ToolBench; OASIS is not included in the 0510 artifact.",
        "- Excluded: ongoing robustness experiments 3.1 ranking noise, 3.2 erasure/degraded-channel payload recovery, 3.3 semantic rewriting, and 3.4 empirical FPR.",
        "- Included: trajectory completeness, utility, behavior JSD, strict RLNC payload recovery, top-k ablation, capacity proxy, and evidence strength.",
        "",
        "## Recommended paper usage",
        "",
        "- Use `utility_main.csv` and `utility_by_cell.csv` for the utility-retention table.",
        "- Use `strict_rlnc_recovery_main.csv` as the main bit-exact payload recovery result.",
        "- Use `topk_ablation_main.csv` for the Top-k ablation figure/table.",
        "- Use `evidence_confidence_n50.csv` and `evidence_threshold_payload32_alpha01.csv` for evidence-strength claims.",
        "- Treat `capacity_proxy_payload8_logged_channels.csv` as a logged offline proxy. The logged L5/L6 labels are not the original design's cross-model/noisy-rank channels.",
        "",
        "## Generated tables",
        "",
    ]
    for name, rows in tables.items():
        lines.append(f"- `{name}.csv`: {len(rows)} rows")
    lines.extend(
        [
            "",
            "## Quick view",
            "",
            "### Utility main",
            "",
            markdown_table(tables["utility_main"], list(tables["utility_main"][0].keys())),
            "",
            "### Strict RLNC recovery main",
            "",
            markdown_table(tables["strict_rlnc_recovery_main"], list(tables["strict_rlnc_recovery_main"][0].keys())),
            "",
            "### Top-k ablation main",
            "",
            markdown_table(tables["topk_ablation_main"], list(tables["topk_ablation_main"][0].keys())),
            "",
        ]
    )
    (output_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    input_root = args.input_root.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    utility_main, utility_by_cell = build_utility_tables(input_root)
    behavior_jsd_clean = build_jsd_table(input_root)
    strict_main, strict_by_cell = build_strict_recovery_table(input_root)
    topk_main = build_topk_table(input_root)
    capacity_proxy = build_capacity_proxy_payload8(input_root)
    evidence_conf, evidence_thresh = build_evidence_tables(input_root)

    tables = {
        "utility_main": utility_main,
        "utility_by_cell": utility_by_cell,
        "behavior_jsd_clean": behavior_jsd_clean,
        "strict_rlnc_recovery_main": strict_main,
        "strict_rlnc_recovery_by_cell": strict_by_cell,
        "topk_ablation_main": topk_main,
        "capacity_proxy_payload8_logged_channels": capacity_proxy,
        "evidence_confidence_n50": evidence_conf,
        "evidence_threshold_payload32_alpha01": evidence_thresh,
    }

    for name, rows in tables.items():
        write_csv(output_dir / f"{name}.csv", rows)

    latex = "\n".join(
        [
            latex_table(
                utility_main,
                [("Dataset", "Dataset"), ("Method", "Method"), ("SR Mean (%)", "SR (\\%)"), ("SR Cell Std", "Std"), ("Steps Mean", "Steps")],
                "Task utility on the canonical 0510 ALFWorld and ToolBench trajectories.",
                "tab:utility-0510",
            ),
            latex_table(
                strict_main,
                [("Dataset", "Dataset"), ("Method", "Method"), ("Payload Recovery (%)", "Recovery (\\%)"), ("Recovery Cell Std (%)", "Std"), ("Dedup Packets", "Packets")],
                "Strict single-trajectory RLNC payload recovery.",
                "tab:strict-rlnc-0510",
            ),
            latex_table(
                topk_main,
                [("Dataset", "Dataset"), ("Top-k", "$k$"), ("Payload Recovery (%)", "Recovery (\\%)"), ("Bit Match (%)", "Bit match (\\%)"), ("Proxy C_eff", "$C_{eff}$")],
                "Top-k ablation for AsymAgentMark-TK.",
                "tab:topk-0510",
            ),
            latex_table(
                evidence_conf,
                [("Dataset", "Dataset"), ("Method", "Method"), ("Config", "Config"), ("Match Rate (%)", "Match (\\%)"), ("Mean log10 p", "$\\log_{10} p$")],
                "Evidence strength at N=50 observed embedding steps.",
                "tab:evidence-n50-0510",
            ),
        ]
    )
    (output_dir / "paper_tables.tex").write_text(latex, encoding="utf-8")

    summary = {
        "source_root": str(input_root),
        "output_dir": str(output_dir),
        "tables": {name: len(rows) for name, rows in tables.items()},
        "robustness_excluded": [
            "3.1 ranking-noise decode-success curves",
            "3.2 erasure plus channel-degradation payload-recovery heatmaps",
            "3.3 semantic rewriting",
            "3.4 empirical false-positive stress test",
        ],
        "capacity_proxy_caveat": "capacity_proxy_payload8_logged_channels uses logged offline channel labels; do not present logged L5/L6 as cross-model/noisy-rank evidence.",
    }
    write_json(output_dir / "summary.json", summary)
    write_readme(output_dir, input_root, tables)
    print(f"[INFO] wrote paper-ready non-robustness results to {output_dir}")


if __name__ == "__main__":
    main()
