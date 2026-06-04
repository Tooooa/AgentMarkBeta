#!/usr/bin/env python3
"""Build compact paper views for semantic rewrite and evidence diagnostics."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

PAPER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PAPER_ROOT.parents[1]
RESULT_DIR = PAPER_ROOT / "results" / "robust_0510"
NON_ROBUST_DIR = PAPER_ROOT / "results" / "non_robust_0510"
FIG_DIR = PAPER_ROOT / "figures"

SEMANTIC_ROOTS = [
    REPO_ROOT / "实验数据" / "remote_data" / "output-0510" / "stage3_semantic_rewrite_toolbench_lmh_r3_pooled_w300",
    REPO_ROOT
    / "实验数据"
    / "remote_data"
    / "extracted"
    / "output-0510"
    / "stage3_semantic_rewrite_toolbench_lmh_r3_pooled_w300",
]
EVIDENCE_ROOTS = [
    REPO_ROOT / "output-0510" / "evidence_strength",
    REPO_ROOT / "实验数据" / "remote_data" / "extracted" / "output-0510" / "evidence_strength",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def fmt(x: float, digits: int = 3) -> str:
    return f"{x:.{digits}f}"


def semantic_root() -> Path:
    for root in SEMANTIC_ROOTS:
        if root.exists():
            return root
    raise FileNotFoundError("semantic rewrite artifact not found")


def evidence_root() -> Path:
    for root in EVIDENCE_ROOTS:
        if root.exists():
            return root
    raise FileNotFoundError("evidence strength artifact not found")


def weighted(rows: list[dict[str, str]], field: str, weight: str) -> float:
    total = sum(int(r[weight]) for r in rows)
    return sum(float(r[field]) * int(r[weight]) for r in rows) / max(total, 1)


def build_semantic_main() -> list[dict[str, object]]:
    root = semantic_root()
    summary = read_csv(root / "stage_c_3_3_semantic_rewrite_summary.csv")
    pooled = read_csv(root / "stage_c_3_3_semantic_rewrite_pooled_summary.csv")

    pooled_by_key = {
        (r["rewrite_strength"], int(r["topk"])): r
        for r in pooled
        if r.get("pool_split") == "ALL_SPLITS"
    }

    rows: list[dict[str, object]] = []
    for strength in ["light", "medium", "heavy"]:
        items = [
            r
            for r in summary
            if r["dataset"] == "toolbench"
            and r["method"] == "rank"
            and r["model"] == "deepseek"
            and r["rewrite_strength"] == strength
            and int(r["topk"]) == 10
        ]
        pool = pooled_by_key[(strength, 10)]
        rows.append(
            {
                "rewrite_strength": strength,
                "topk": 10,
                "steps": sum(int(r["steps"]) for r in items),
                "trajectories": sum(int(r["trajectories"]) for r in items),
                "rouge_l": fmt(weighted(items, "mean_rouge_l", "steps")),
                "token_jaccard": fmt(weighted(items, "mean_token_jaccard", "steps")),
                "rank_keep": fmt(weighted(items, "rank_keep_rate", "steps")),
                "top1_match": fmt(weighted(items, "top1_match_rate", "steps")),
                "topk_overlap": fmt(weighted(items, "topk_overlap_mean", "steps")),
                "kendall_tau": fmt(weighted(items, "kendall_tau_mean", "steps")),
                "strict_dsr": fmt(weighted(items, "decode_success_rate", "trajectories")),
                "pooled_dsr": fmt(float(pool["pooled_decode_success_rate_mean"])),
                "pooled_packets": fmt(float(pool["pooled_dedup_packet_mean"])),
                "pooled_conflicts": fmt(float(pool["pooled_conflicts_mean"])),
            }
        )
    return rows


def build_evidence_curve() -> list[dict[str, object]]:
    rows = read_csv(evidence_root() / "stage_d_4_1_confidence_summary.csv")
    out: list[dict[str, object]] = []
    configs = [
        ("agentmark", "L0_exact_probs", "AgentMark-F exact"),
        ("rank", "top10", "AsymMark-R top-10"),
    ]
    for dataset in ["alfworld", "toolbench"]:
        for method, config, label in configs:
            by_n: dict[int, list[dict[str, str]]] = defaultdict(list)
            for row in rows:
                if row["dataset"] == dataset and row["method"] == method and row["config"] == config:
                    by_n[int(row["N"])].append(row)
            for n in sorted(by_n):
                items = by_n[n]
                runs = sum(int(r["runs"]) for r in items)
                out.append(
                    {
                        "dataset": dataset,
                        "method": method,
                        "config": config,
                        "label": label,
                        "N": n,
                        "runs": runs,
                        "match_rate": fmt(sum(float(r["match_rate_mean"]) * int(r["runs"]) for r in items) / runs),
                        "mean_log10_p": fmt(
                            sum(float(r["log10_p_value_mean"]) * int(r["runs"]) for r in items) / runs
                        ),
                    }
                )
    return out


def main() -> None:
    semantic_rows = build_semantic_main()
    evidence_rows = build_evidence_curve()
    write_csv(
        RESULT_DIR / "semantic_rewrite_main_summary.csv",
        semantic_rows,
        [
            "rewrite_strength",
            "topk",
            "steps",
            "trajectories",
            "rouge_l",
            "token_jaccard",
            "rank_keep",
            "top1_match",
            "topk_overlap",
            "kendall_tau",
            "strict_dsr",
            "pooled_dsr",
            "pooled_packets",
            "pooled_conflicts",
        ],
    )
    write_csv(
        NON_ROBUST_DIR / "evidence_confidence_main_curve.csv",
        evidence_rows,
        ["dataset", "method", "config", "label", "N", "runs", "match_rate", "mean_log10_p"],
    )


if __name__ == "__main__":
    main()
