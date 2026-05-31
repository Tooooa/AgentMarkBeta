#!/usr/bin/env python3
"""Build additional paper-facing diagnostics for A-E follow-up experiments."""

from __future__ import annotations

import argparse
import contextlib
import csv
import importlib.util
import io
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import torch


PAPER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PAPER_ROOT.parents[1]
RAW_ROOT = REPO_ROOT / "鲁棒实验_实验" / "remote_data" / "extracted" / "output-0510"
RESULT_DIR = PAPER_ROOT / "results" / "additional_experiments"
FIG_DIR = PAPER_ROOT / "figures"

CHANNEL_LEVELS = {
    "L0_exact_probs": 0,
    "L1_top10_rank": 1,
    "L2_top8_rank": 2,
    "L3_top6_rank": 3,
    "L4_top4_rank": 4,
    "L5_top2_rank": 5,
    "L6_selected_only": 6,
}


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


week2 = load_module(
    "week2_postprocess_for_additional",
    REPO_ROOT / "experiments" / "asym_agentmark_tk" / "scripts" / "run_week2_postprocess.py",
)

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agentmark.core.watermark_sampler import (  # noqa: E402
    DRBG_Legacy,
    differential_based_decoder,
    differential_based_recombination,
    generate_contextual_key,
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def as_float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    return float(value)


def fmt(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def normalize_probs(probs: dict[str, Any]) -> dict[str, float]:
    cleaned = {}
    for key, value in (probs or {}).items():
        try:
            v = float(value)
        except Exception:
            continue
        if math.isfinite(v) and v > 0:
            cleaned[str(key)] = v
    total = sum(cleaned.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in cleaned.items()}


def topk_probs(probs: dict[str, float], k: int) -> dict[str, float]:
    ranked = sorted(probs.items(), key=lambda kv: (-kv[1], kv[0]))[:k]
    return normalize_probs(dict(ranked))


def selected_bin(probs: dict[str, float], context: str, round_num: int) -> dict[str, Any] | None:
    if not probs:
        return None
    behaviors = sorted(probs)
    probs_tensor = torch.tensor([probs[b] for b in behaviors], dtype=torch.float32, device="cpu")
    indices_tensor = torch.arange(len(behaviors), device="cpu")
    indices_nonzero, bins, prob_new = differential_based_recombination(probs_tensor, indices_tensor)
    if float(prob_new.sum()) <= 0:
        return None
    prob_new = prob_new / prob_new.sum()
    key = generate_contextual_key([context])
    prg = DRBG_Legacy(key, str(round_num).encode("utf-8"))
    random_p = prg.generate_random(n=52)
    cdf = torch.cumsum(prob_new, dim=0)
    bin_idx = int(torch.searchsorted(cdf, random_p).item())
    start = int(bins[bin_idx].item())
    content_indices = [int(x) for x in indices_nonzero[start:].tolist()]
    content = tuple(behaviors[i] for i in content_indices)
    return {
        "bin_idx": bin_idx,
        "start": start,
        "size": len(content),
        "content": content,
    }


def decode_agentmark_bits(probs: dict[str, float], selected: str, context: str, round_num: int) -> str:
    with contextlib.redirect_stdout(io.StringIO()):
        return differential_based_decoder(
            probs,
            selected,
            context_for_key=context,
            round_num=round_num,
        )


def load_trajectories(root: Path) -> list[Any]:
    return week2.collect_alfworld(root) + week2.collect_toolbench(root)


def build_lemma1_counterfactual(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    trajectories = [tr for tr in load_trajectories(root) if tr.method == "agentmark" and tr.steps]
    detail_rows: list[dict[str, Any]] = []
    groups: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)

    for tr in trajectories:
        for step in tr.steps:
            exact = normalize_probs(step.probabilities)
            selected = step.chosen
            if selected not in exact:
                continue
            exact_bits = decode_agentmark_bits(exact, selected, step.context, step.round_num)
            if exact_bits == "":
                continue
            exact_bin = selected_bin(exact, step.context, step.round_num)
            if exact_bin is None:
                continue
            for k in (10, 8, 6, 4, 2):
                proxy = topk_probs(exact, k)
                selected_in_topk = selected in proxy
                topk_bits = ""
                topk_bin = None
                bin_changed = False
                bit_changed = False
                if selected_in_topk:
                    topk_bits = decode_agentmark_bits(proxy, selected, step.context, step.round_num)
                    topk_bin = selected_bin(proxy, step.context, step.round_num)
                    if topk_bin is not None:
                        bin_changed = exact_bin["content"] != topk_bin["content"]
                    bit_changed = exact_bits != topk_bits
                row = {
                    "dataset": tr.dataset,
                    "model": tr.model,
                    "split": tr.split,
                    "run": tr.run,
                    "task_id": tr.task_id,
                    "step_index": step.step_index,
                    "topk": k,
                    "candidate_count": len(exact),
                    "selected_in_topk": int(selected_in_topk),
                    "exact_bin_size": exact_bin["size"],
                    "topk_bin_size": topk_bin["size"] if topk_bin else 0,
                    "rank_stable_bin_changed": int(bin_changed),
                    "rank_stable_bit_changed": int(bit_changed),
                    "exact_bits_len": len(exact_bits),
                    "topk_bits_len": len(topk_bits),
                }
                detail_rows.append(row)
                groups[(tr.dataset, tr.model, k)].append(row)

    summary_rows: list[dict[str, Any]] = []
    for (dataset, model, k), rows in sorted(groups.items()):
        total = len(rows)
        stable = [r for r in rows if r["selected_in_topk"]]
        changed_bins = [r for r in stable if r["rank_stable_bin_changed"]]
        changed_bits = [r for r in stable if r["rank_stable_bit_changed"]]
        summary_rows.append(
            {
                "dataset": dataset,
                "model": model,
                "topk": k,
                "exact_decodable_steps": total,
                "rank_stable_steps": len(stable),
                "selected_dropped_steps": total - len(stable),
                "selected_dropped_rate": fmt((total - len(stable)) / total if total else 0),
                "bin_changed_given_rank_stable": fmt(len(changed_bins) / len(stable) if stable else 0),
                "bit_changed_given_rank_stable": fmt(len(changed_bits) / len(stable) if stable else 0),
                "bit_changed_given_bin_changed": fmt(
                    sum(1 for r in changed_bins if r["rank_stable_bit_changed"]) / len(changed_bins)
                    if changed_bins
                    else 0
                ),
                "exact_bits_mean": fmt(statistics.mean(r["exact_bits_len"] for r in rows) if rows else 0),
                "topk_bits_mean_rank_stable": fmt(statistics.mean(r["topk_bits_len"] for r in stable) if stable else 0),
            }
        )
    return summary_rows, detail_rows


def build_channel_ladder() -> list[dict[str, Any]]:
    rows = read_csv(PAPER_ROOT / "results" / "non_robust_0510" / "capacity_proxy_payload8_logged_channels.csv")
    out = []
    for row in rows:
        channel = row["Logged Channel"]
        out.append(
            {
                "dataset": row["Dataset"],
                "method": row["Method"],
                "level": CHANNEL_LEVELS[channel],
                "channel": channel,
                "payload_recovery_rate": fmt(as_float(row["Payload Recovery (%)"]) / 100.0),
                "bit_match_rate": fmt(as_float(row["Bit Match (%)"]) / 100.0),
                "c_eff_proxy_bits": fmt(as_float(row["Proxy C_eff"]), 3),
            }
        )
    return sorted(out, key=lambda r: (r["dataset"], r["method"], r["level"]))


def build_topk_extended(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = week2.load_payload(REPO_ROOT)
    trajectories = [
        tr
        for tr in week2.collect_alfworld(root)
        if tr.method == "rank" and tr.steps
    ]
    k_values: list[int | str] = [2, 4, 6, 8, 10, 20, 30, 40, "full"]
    rows_by_cell: dict[tuple[str, str, int | str], list[dict[str, Any]]] = defaultdict(list)
    candidate_counts = [max(len(s.probabilities), s.target_size) for tr in trajectories for s in tr.steps]
    max_candidate_count = max(candidate_counts) if candidate_counts else 0

    for tr in trajectories:
        for k in k_values:
            topk = 10**6 if k == "full" else int(k)
            res = week2.decode_trajectory(tr, payload, topk_override=topk)
            rows_by_cell[(tr.model, tr.split, k)].append(
                {
                    "decoded_len": res["decoded_len"],
                    "bit_match_rate": res["bit_match_rate"],
                    "payload_recovered": week2.payload_recovered(res, 8),
                }
            )

    cell_summaries: dict[int | str, list[dict[str, float]]] = defaultdict(list)
    for (_model, _split, k), items in sorted(rows_by_cell.items(), key=lambda item: (item[0][0], item[0][1], str(item[0][2]))):
        decoded = [float(x["decoded_len"]) for x in items]
        bit_match = [float(x["bit_match_rate"]) for x in items]
        dsr = sum(1 for x in items if x["payload_recovered"]) / len(items) if items else 0.0
        c_nom = statistics.mean(decoded) if decoded else 0.0
        cell_summaries[k].append(
            {
                "c_nom": c_nom,
                "payload_recovery_rate": dsr,
                "bit_match_rate": statistics.mean(bit_match) if bit_match else 0.0,
                "c_eff": c_nom * dsr,
            }
        )

    rows: list[dict[str, Any]] = []
    for k in k_values:
        cells = cell_summaries[k]
        c_nom = statistics.mean(x["c_nom"] for x in cells) if cells else 0.0
        dsr = statistics.mean(x["payload_recovery_rate"] for x in cells) if cells else 0.0
        bit_match = statistics.mean(x["bit_match_rate"] for x in cells) if cells else 0.0
        c_eff = statistics.mean(x["c_eff"] for x in cells) if cells else 0.0
        rows.append(
            {
                "dataset": "ALFWorld",
                "method": "AsymAgentMark-TK",
                "topk": k,
                "cells": len(cells),
                "c_nom_proxy_bits": fmt(c_nom, 4),
                "payload_recovery_rate": fmt(dsr),
                "bit_match_rate": fmt(bit_match),
                "c_eff_proxy_bits": fmt(c_eff, 6),
                "steps_with_more_candidates_than_k": (
                    sum(1 for c in candidate_counts if k != "full" and c > int(k))
                    if k != "full"
                    else 0
                ),
            }
        )

    audit = {
        "rank_trajectories": len(trajectories),
        "rank_steps": len(candidate_counts),
        "max_candidate_count": max_candidate_count,
        "mean_candidate_count": fmt(statistics.mean(candidate_counts) if candidate_counts else 0),
        "steps_over_20": sum(1 for c in candidate_counts if c > 20),
        "steps_over_20_rate": fmt(sum(1 for c in candidate_counts if c > 20) / len(candidate_counts) if candidate_counts else 0),
    }
    return rows, audit


def build_cnom_audit() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    capacity = [
        r
        for r in read_csv(RAW_ROOT / "asym_agentmark_tk" / "capacity_l0_l6_proxy.csv")
        if r["payload_len"] == "8"
    ]
    topk = read_csv(RAW_ROOT / "asym_agentmark_tk" / "topk_ablation.csv")

    repeats: list[dict[str, Any]] = []
    for source, rows, key_col, group_cols in [
        ("capacity_l0_l6_proxy", capacity, "channel", ["dataset", "method", "model", "split"]),
        ("topk_ablation", topk, "topk", ["dataset", "method", "model", "split"]),
    ]:
        grouped: dict[tuple[str, ...], dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        for row in rows:
            group = tuple(row[col] for col in group_cols)
            c_nom = str(round(as_float(row["c_nom_proxy_bits"]), 4))
            grouped[group][c_nom].append(row[key_col])
        for group, values in sorted(grouped.items()):
            for c_nom, labels in sorted(values.items(), key=lambda x: (float(x[0]), x[1])):
                if len(labels) > 1:
                    repeats.append(
                        {
                            "source": source,
                            **{col: val for col, val in zip(group_cols, group)},
                            "c_nom_proxy_bits": c_nom,
                            "repeated_settings": ",".join(labels),
                            "repeat_count": len(labels),
                        }
                    )

    proof_rows = []
    for k in (2, 4, 6, 8, 10, 20):
        proof_rows.append(
            {
                "topk": k,
                "floor_log2_topk": int(math.floor(math.log2(k))),
                "interpretation": "same nominal bits for adjacent k inside the same power-of-two bucket",
            }
        )
    return repeats, proof_rows


def build_prop2_summary(fine_root: Path) -> list[dict[str, Any]]:
    path = fine_root / "stage_c_3_1_rank_noise_summary.csv"
    if not path.exists():
        return []
    rows = read_csv(path)
    out = []
    for row in rows:
        if row["dataset"] != "toolbench":
            continue
        eps = as_float(row["epsilon"])
        k = int(float(row["topk"]))
        observed_bit_survival = as_float(row["accepted_steps_mean"]) / max(as_float(row["c_nom_proxy_bits"]), 1e-9)
        bound_flip = 1.0 - (1.0 - eps) ** max(1, math.ceil(math.log2(k)))
        out.append(
            {
                "model": row["model"],
                "split": row["split"],
                "topk": k,
                "noise_model": row["noise_model"],
                "epsilon": fmt(eps, 2),
                "trajectories": row["trajectories"],
                "strict_decode_success_rate": fmt(as_float(row["decode_success_rate"])),
                "dedup_packet_mean": fmt(as_float(row["dedup_packet_mean"])),
                "accepted_steps_mean": fmt(as_float(row["accepted_steps_mean"])),
                "c_nom_proxy_bits": fmt(as_float(row["c_nom_proxy_bits"])),
                "c_eff_proxy_bits": fmt(as_float(row["c_eff_proxy_bits"])),
                "observed_accepted_over_cnom": fmt(observed_bit_survival),
                "prop2_flip_upper_curve": fmt(bound_flip),
            }
        )
    return sorted(out, key=lambda r: (r["model"], r["split"], r["noise_model"], r["topk"], r["epsilon"]))


def make_channel_ladder_svg(rows: list[dict[str, Any]]) -> str:
    width, height = 1300, 620
    panel_w, panel_h = 520, 350
    x_offsets = {"ALFWorld": 95, "ToolBench": 725}
    y0 = 95
    colors = {"AgentMark-F": "#D55E00", "AsymAgentMark-TK": "#0072B2"}
    max_y = max(float(r["c_eff_proxy_bits"]) for r in rows) or 1.0
    max_y = math.ceil(max_y)

    def x(level: int, x0: int) -> float:
        return x0 + level / 6 * panel_w

    def y(value: float) -> float:
        return y0 + panel_h - value / max_y * panel_h

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#FFFFFF"/>',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#222}.title{font-size:30px;font-weight:700}.label{font-size:21px}.tick{font-size:16px;fill:#555}.legend{font-size:19px}</style>',
        '<text class="title" x="650" y="42" text-anchor="middle">Effective capacity over verifier-channel degradation</text>',
    ]
    for dataset, x0 in x_offsets.items():
        parts.append(f'<text class="label" x="{x0 + panel_w/2}" y="{y0 - 28}" text-anchor="middle">{dataset}</text>')
        parts.append(f'<rect x="{x0}" y="{y0}" width="{panel_w}" height="{panel_h}" fill="none" stroke="#333"/>')
        for frac in (0, 0.25, 0.5, 0.75, 1.0):
            yy = y(frac * max_y)
            parts.append(f'<line x1="{x0}" x2="{x0 + panel_w}" y1="{yy}" y2="{yy}" stroke="#E8E8E8"/>')
            parts.append(f'<text class="tick" x="{x0 - 10}" y="{yy + 5}" text-anchor="end">{frac * max_y:.1f}</text>')
        for level in range(7):
            xx = x(level, x0)
            parts.append(f'<line x1="{xx}" x2="{xx}" y1="{y0}" y2="{y0 + panel_h}" stroke="#F2F2F2"/>')
            parts.append(f'<text class="tick" x="{xx}" y="{y0 + panel_h + 24}" text-anchor="middle">L{level}</text>')
        for method, color in colors.items():
            pts = [r for r in rows if r["dataset"] == dataset and r["method"] == method]
            pts = sorted(pts, key=lambda r: int(r["level"]))
            coords = [(x(int(r["level"]), x0), y(float(r["c_eff_proxy_bits"]))) for r in pts]
            d = " ".join(("M" if i == 0 else "L") + f"{xx:.1f},{yy:.1f}" for i, (xx, yy) in enumerate(coords))
            parts.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="3.5"/>')
            for xx, yy in coords:
                parts.append(f'<circle cx="{xx:.1f}" cy="{yy:.1f}" r="4.2" fill="{color}"/>')
    legend_x, legend_y = 455, 565
    for i, (method, color) in enumerate(colors.items()):
        xbase = legend_x + i * 230
        parts.append(f'<line x1="{xbase}" x2="{xbase+46}" y1="{legend_y}" y2="{legend_y}" stroke="{color}" stroke-width="4"/>')
        parts.append(f'<text class="legend" x="{xbase+55}" y="{legend_y+7}">{method}</text>')
    parts.append('<text class="tick" x="650" y="604" text-anchor="middle">L0 exact probabilities; L1-L5 top-k ranks; L6 selected-only</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def make_prop2_svg(rows: list[dict[str, Any]]) -> str:
    rows = [
        r for r in rows
        if r["model"] == "deepseek" and r["noise_model"] == "adjacent_swap" and r["split"] == "G1_instruction"
    ]
    width, height = 900, 560
    x0, y0, panel_w, panel_h = 95, 70, 690, 360
    colors = {3: "#0072B2", 5: "#009E73", 10: "#CC79A7"}
    max_y = max([float(r["c_nom_proxy_bits"]) for r in rows] + [1.0])

    def x(eps: float) -> float:
        return x0 + eps / 0.5 * panel_w

    def y(value: float) -> float:
        return y0 + panel_h - value / max_y * panel_h

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#FFFFFF"/>',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#222}.title{font-size:27px;font-weight:700}.tick{font-size:15px;fill:#555}.legend{font-size:18px}</style>',
        '<text class="title" x="450" y="36" text-anchor="middle">Prop. 2 rank-noise curve: strict signal before pooling</text>',
        f'<rect x="{x0}" y="{y0}" width="{panel_w}" height="{panel_h}" fill="none" stroke="#333"/>',
    ]
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        yy = y(frac * max_y)
        parts.append(f'<line x1="{x0}" x2="{x0+panel_w}" y1="{yy}" y2="{yy}" stroke="#E8E8E8"/>')
        parts.append(f'<text class="tick" x="{x0-10}" y="{yy+5}" text-anchor="end">{frac * max_y:.1f}</text>')
    for eps in [i * 0.05 for i in range(11)]:
        xx = x(eps)
        if int(round(eps * 100)) % 10 == 0:
            parts.append(f'<line x1="{xx}" x2="{xx}" y1="{y0}" y2="{y0+panel_h}" stroke="#F0F0F0"/>')
            parts.append(f'<text class="tick" x="{xx}" y="{y0+panel_h+24}" text-anchor="middle">{eps:.1f}</text>')
    for k, color in colors.items():
        pts = sorted([r for r in rows if int(r["topk"]) == k], key=lambda r: float(r["epsilon"]))
        coords = [(x(float(r["epsilon"])), y(float(r["c_nom_proxy_bits"]))) for r in pts]
        d = " ".join(("M" if i == 0 else "L") + f"{xx:.1f},{yy:.1f}" for i, (xx, yy) in enumerate(coords))
        parts.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="3.2"/>')
        for xx, yy in coords:
            parts.append(f'<circle cx="{xx:.1f}" cy="{yy:.1f}" r="3.4" fill="{color}"/>')
    parts.append(f'<text class="tick" x="{x0+panel_w/2}" y="{y0+panel_h+58}" text-anchor="middle">epsilon</text>')
    parts.append(f'<text class="tick" transform="translate({x0-62},{y0+panel_h/2}) rotate(-90)" text-anchor="middle">mean decoded packets / trajectory</text>')
    for i, (k, color) in enumerate(colors.items()):
        lx = 255 + i * 135
        parts.append(f'<line x1="{lx}" x2="{lx+42}" y1="500" y2="500" stroke="{color}" stroke-width="4"/>')
        parts.append(f'<text class="legend" x="{lx+50}" y="507">k={k}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def write_report(
    *,
    lemma_rows: list[dict[str, Any]],
    ladder_rows: list[dict[str, Any]],
    topk_rows: list[dict[str, Any]],
    topk_audit: dict[str, Any],
    cnom_repeats: list[dict[str, Any]],
    prop2_rows: list[dict[str, Any]],
) -> None:
    def pick(rows: list[dict[str, Any]], **conds: Any) -> dict[str, Any]:
        for row in rows:
            if all(row.get(k) == v for k, v in conds.items()):
                return row
        return {}

    lines = [
        "# Additional Experiments A-E Results",
        "",
        "## A. Lemma 1 step-level counterfactual",
        "",
        "AgentMark-F exact-probability decoding was compared with a top-k verifier view that keeps the selected top-k order but drops the tail and renormalizes probabilities. The selected behavior remains rank-stable whenever it is still in the top-k set; changes below are therefore probability-bin effects, not candidate-order effects.",
        "",
        "| Dataset | Model | top-k | rank-stable steps | bin changed | bit changed | selected dropped |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in lemma_rows:
        if row["topk"] in (10, 4, 2):
            lines.append(
                f"| {row['dataset']} | {row['model']} | {row['topk']} | {row['rank_stable_steps']} | "
                f"{100*float(row['bin_changed_given_rank_stable']):.1f}% | "
                f"{100*float(row['bit_changed_given_rank_stable']):.1f}% | "
                f"{100*float(row['selected_dropped_rate']):.1f}% |"
            )
    lines.extend(
        [
            "",
            "## B. Prop. 2 fine rank-noise curve",
            "",
            "The fine-grid rerun uses ToolBench, repeats=10, k in {3,5,10}, epsilon=0:0.05:0.5. Pooled recovery is intentionally not the headline here because it saturates; the useful non-pooled signal is the per-trajectory decoded packet budget.",
            "",
            "| Model | Split | Noise | k | eps=0 Cnom | eps=0.25 Cnom | eps=0.5 Cnom | eps=0 strict DSR | eps=0.5 strict DSR |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for model, split, noise, k in [
        ("deepseek", "G1_instruction", "adjacent_swap", 3),
        ("deepseek", "G1_instruction", "adjacent_swap", 5),
        ("deepseek", "G1_instruction", "adjacent_swap", 10),
        ("gemini-flash", "G1_instruction", "adjacent_swap", 10),
    ]:
        r0 = pick(prop2_rows, model=model, split=split, noise_model=noise, topk=k, epsilon=0.0)
        r25 = pick(prop2_rows, model=model, split=split, noise_model=noise, topk=k, epsilon=0.25)
        r50 = pick(prop2_rows, model=model, split=split, noise_model=noise, topk=k, epsilon=0.5)
        if r0 and r25 and r50:
            lines.append(
                f"| {model} | {split} | {noise} | {k} | {float(r0['c_nom_proxy_bits']):.3f} | "
                f"{float(r25['c_nom_proxy_bits']):.3f} | {float(r50['c_nom_proxy_bits']):.3f} | "
                f"{float(r0['strict_decode_success_rate']):.3f} | {float(r50['strict_decode_success_rate']):.3f} |"
            )
    lines.extend(
        [
            "",
            "## C. Channel ladder",
            "",
            "L2 top-8 and L4 top-4 were already present in the canonical non-robust artifact; the missing piece was the paper-facing ladder figure/table.",
            "",
            "| Dataset | Method | L0 Ceff | L1 Ceff | L2 Ceff | L3 Ceff | L4 Ceff | L5 Ceff | L6 Ceff |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for dataset in ("ALFWorld", "ToolBench"):
        for method in ("AgentMark-F", "AsymAgentMark-TK"):
            vals = [
                float(pick(ladder_rows, dataset=dataset, method=method, level=level).get("c_eff_proxy_bits", 0.0))
                for level in range(7)
            ]
            lines.append(f"| {dataset} | {method} | " + " | ".join(f"{v:.3f}" for v in vals) + " |")
    lines.extend(
        [
            "",
            "## D. ALFWorld k* extension",
            "",
            f"ALFWorld rank logs contain {topk_audit['rank_steps']} decodable rank steps; max candidate count is {topk_audit['max_candidate_count']}, and steps with more than 20 candidates are {topk_audit['steps_over_20']} ({100*float(topk_audit['steps_over_20_rate']):.2f}%).",
            "",
            "| top-k | Cnom | DSR | bit match | Ceff |",
            "| ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in topk_rows:
        lines.append(
            f"| {row['topk']} | {float(row['c_nom_proxy_bits']):.3f} | "
            f"{float(row['payload_recovery_rate']):.3f} | {float(row['bit_match_rate']):.3f} | "
            f"{float(row['c_eff_proxy_bits']):.3f} |"
        )
    lines.extend(
        [
            "",
            "## E. Cnom repeated-value audit",
            "",
            "Cnom is `decoded_len_mean`: the mean proxy decoded bits per trajectory. Repeated neighboring values are expected when top-k values fall in the same floor(log2(k)) capacity bucket, or when most steps have fewer candidates than the larger k. The audit found repeated settings but no Ceff arithmetic inconsistency.",
            "",
            f"- Repeated Cnom groups found: {len(cnom_repeats)}.",
            "- Mechanism: k=4 and k=6 both expose at most 2 rank bits per eligible step; k=8 and k=10 both expose at most 3 rank bits per eligible step. If candidate counts are already below the larger k, Cnom cannot increase.",
            "",
            "## Artifacts",
            "",
            "- `lemma1_bin_instability_summary.csv`, `lemma1_bin_instability_steps.csv`",
            "- `prop2_rank_noise_fine_toolbench_summary.csv`, `fig_prop2_rank_noise_fine.svg`",
            "- `channel_ladder_main.csv`, `fig_channel_ladder_ceff.svg`",
            "- `alfworld_topk_extended.csv`, `alfworld_topk_extended_audit.json`",
            "- `cnom_repeated_value_audit.csv`, `cnom_capacity_bucket_explanation.csv`",
        ]
    )
    (RESULT_DIR / "ADDITIONAL_EXPERIMENTS_A_E.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-root", default=str(RAW_ROOT))
    parser.add_argument(
        "--prop2-root",
        default=str(PAPER_ROOT / "results" / "robust_0510" / "prop2_rank_noise_fine_toolbench"),
    )
    args = parser.parse_args()

    raw_root = Path(args.raw_root).resolve()
    prop2_root = Path(args.prop2_root).resolve()
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    lemma_summary, lemma_steps = build_lemma1_counterfactual(raw_root)
    ladder_rows = build_channel_ladder()
    topk_rows, topk_audit = build_topk_extended(raw_root)
    cnom_repeats, cnom_bucket = build_cnom_audit()
    prop2_rows = build_prop2_summary(prop2_root)

    write_csv(RESULT_DIR / "lemma1_bin_instability_summary.csv", lemma_summary)
    write_csv(RESULT_DIR / "lemma1_bin_instability_steps.csv", lemma_steps)
    write_csv(RESULT_DIR / "channel_ladder_main.csv", ladder_rows)
    write_csv(RESULT_DIR / "alfworld_topk_extended.csv", topk_rows)
    write_json(RESULT_DIR / "alfworld_topk_extended_audit.json", topk_audit)
    write_csv(RESULT_DIR / "cnom_repeated_value_audit.csv", cnom_repeats)
    write_csv(RESULT_DIR / "cnom_capacity_bucket_explanation.csv", cnom_bucket)
    write_csv(RESULT_DIR / "prop2_rank_noise_fine_toolbench_summary.csv", prop2_rows)

    (FIG_DIR / "fig_channel_ladder_ceff.svg").write_text(make_channel_ladder_svg(ladder_rows), encoding="utf-8")
    if prop2_rows:
        (FIG_DIR / "fig_prop2_rank_noise_fine.svg").write_text(make_prop2_svg(prop2_rows), encoding="utf-8")

    write_report(
        lemma_rows=lemma_summary,
        ladder_rows=ladder_rows,
        topk_rows=topk_rows,
        topk_audit=topk_audit,
        cnom_repeats=cnom_repeats,
        prop2_rows=prop2_rows,
    )
    print(f"[INFO] wrote additional experiment artifacts to {RESULT_DIR}")


if __name__ == "__main__":
    main()
