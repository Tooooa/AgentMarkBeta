#!/usr/bin/env python3
"""Build ToolBench rank-depth calibration artifacts for the paper."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


PAPER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PAPER_ROOT.parents[1]
REMOTE_ROOT = REPO_ROOT / "鲁棒实验_实验" / "remote_data" / "output-0510"
RESULT_DIR = PAPER_ROOT / "results" / "robust_0510"
FIG_DIR = PAPER_ROOT / "figures"

TOPK_ROOT = REMOTE_ROOT / "l5_toolbench_rank_topk_matched_clean_w100"
TOP24_ROOT = REMOTE_ROOT / "l5_toolbench_rank_top2_top4_matched_clean_w100"

SAME_MODEL_ROOTS = {
    "deepseek": [
        REMOTE_ROOT / "toolbench_rank_topk_matched",
        REMOTE_ROOT / "toolbench_rank_topk_matched_top2_top4_deepseek",
    ],
    "gemini-flash": [
        REMOTE_ROOT / "toolbench_rank_topk_matched_gemini",
        REMOTE_ROOT / "toolbench_rank_topk_matched_top2_top4_gemini",
    ],
}

K_VALUES = [2, 3, 4, 5, 10]
LABELS = {
    "deepseek->gemini-flash": "DeepSeek -> Gemini",
    "gemini-flash->deepseek": "Gemini -> DeepSeek",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def as_float(value: str | None) -> float:
    if value in (None, ""):
        return 0.0
    return float(value)


def as_int(value: str | None) -> int:
    if value in (None, ""):
        return 0
    return int(float(value))


def fmt(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}"


def build_same_model() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for model, roots in SAME_MODEL_ROOTS.items():
        by_k: dict[int, dict[str, object]] = {}
        for root in roots:
            post = root / "postprocess"
            summary_path = post / "summary_global.csv"
            pooled_path = post / "pooled.csv"
            curve_path = root / "pool_curve" / "pool_curve_summary.csv"
            if not summary_path.exists():
                continue

            for r in read_csv(summary_path):
                k = as_int(r.get("topk") or r.get("rank_topk"))
                by_k.setdefault(k, {})
                by_k[k].update(
                    {
                        "model": model,
                        "topk": k,
                        "trajectories": as_int(r.get("trajectories")),
                        "strict_success": fmt(as_float(r.get("decode_success_rate"))),
                        "dedup_packets_per_traj": fmt(as_float(r.get("dedup_packet_mean"))),
                        "accepted_steps_per_traj": fmt(as_float(r.get("accepted_steps_mean"))),
                    }
                )

            if pooled_path.exists():
                for r in read_csv(pooled_path):
                    k = as_int(r.get("topk") or r.get("rank_topk"))
                    by_k.setdefault(k, {"model": model, "topk": k})
                    by_k[k].update(
                        {
                            "all_pooled_success": fmt(as_float(r.get("pooled_decode_success_rate"))),
                            "all_pooled_dedup": as_int(r.get("pooled_dedup_packet_count")),
                            "all_pooled_conflicts": as_int(r.get("pooled_conflicts")),
                            "all_pooled_reason": r.get("pooled_failure_reason", ""),
                        }
                    )

            if curve_path.exists():
                for r in read_csv(curve_path):
                    k = as_int(r.get("topk") or r.get("rank_topk"))
                    pool_size = as_int(r.get("pool_size"))
                    if pool_size not in (10, 20, 50, 100):
                        continue
                    by_k.setdefault(k, {"model": model, "topk": k})
                    by_k[k][f"pool{pool_size}_success"] = fmt(
                        as_float(r.get("pooled_decode_success_rate_mean"))
                    )

        for k in K_VALUES:
            if k in by_k:
                rows.append(by_k[k])
    return rows


def weighted_summary(root: Path) -> dict[tuple[str, int], dict[str, object]]:
    grouped: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    for r in read_csv(root / "l5_cross_model_summary.csv"):
        direction = f"{r['embed_model']}->{r['verifier_model']}"
        grouped[(direction, as_int(r["topk"]))].append(r)

    out: dict[tuple[str, int], dict[str, object]] = {}
    for key, items in grouped.items():
        steps = sum(as_int(r["steps"]) for r in items)
        traj = sum(as_int(r["trajectories"]) for r in items)

        def step_avg(col: str) -> float:
            return sum(as_float(r[col]) * as_int(r["steps"]) for r in items) / max(1, steps)

        def traj_avg(col: str) -> float:
            return sum(as_float(r[col]) * as_int(r["trajectories"]) for r in items) / max(1, traj)

        out[key] = {
            "direction": key[0],
            "direction_label": LABELS.get(key[0], key[0]),
            "topk": key[1],
            "trajectories": traj,
            "steps": steps,
            "top1_match": fmt(step_avg("top1_match_rate")),
            "topk_overlap": fmt(step_avg("topk_overlap_mean")),
            "kendall_tau": fmt(step_avg("kendall_tau_mean")),
            "rank_displacement": fmt(step_avg("rank_displacement_mean")),
            "dedup_packets_per_traj": fmt(traj_avg("dedup_packet_mean")),
            "accepted_steps_per_traj": fmt(traj_avg("accepted_steps_mean")),
        }
    return out


def build_l5() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    summary: dict[tuple[str, int], dict[str, object]] = {}
    curve_rows: list[dict[str, object]] = []

    for root in (TOPK_ROOT, TOP24_ROOT):
        summary.update(weighted_summary(root))

        for r in read_csv(root / "l5_cross_model_pooled.csv"):
            direction = f"{r['embed_model']}->{r['verifier_model']}"
            k = as_int(r["topk"])
            summary.setdefault((direction, k), {"direction": direction, "topk": k})
            summary[(direction, k)].update(
                {
                    "all_pooled_success": fmt(as_float(r["pooled_decode_success_rate"])),
                    "all_pooled_dedup": as_int(r["pooled_dedup_packet_count"]),
                    "all_pooled_conflicts": as_int(r["pooled_conflicts"]),
                    "all_pooled_reason": r["pooled_failure_reason"],
                    "all_pooled_recovered_payload": r["pooled_recovered_payload"],
                }
            )

        for r in read_csv(root / "pool_slices" / "pool_curve_summary.csv"):
            direction = f"{r['embed_model']}->{r['verifier_model']}"
            row = {
                "direction": direction,
                "direction_label": LABELS.get(direction, direction),
                "topk": as_int(r["topk"]),
                "pool_size": as_int(r["pool_size"]),
                "success_mean": fmt(as_float(r["pooled_decode_success_rate_mean"])),
                "dedup_mean": fmt(as_float(r["pooled_dedup_packet_mean"])),
                "conflicts_mean": fmt(as_float(r["pooled_conflicts_mean"])),
            }
            curve_rows.append(row)

    curve_by_key: dict[tuple[str, int], list[dict[str, object]]] = defaultdict(list)
    for row in curve_rows:
        curve_by_key[(str(row["direction"]), int(row["topk"]))].append(row)

    out_rows: list[dict[str, object]] = []
    for key in sorted(summary, key=lambda x: (x[0], x[1])):
        best = max(curve_by_key[key], key=lambda r: float(r["success_mean"]))
        summary[key].update(
            {
                "best_pool_size": best["pool_size"],
                "best_pool_success": best["success_mean"],
                "best_pool_dedup": best["dedup_mean"],
                "best_pool_conflicts": best["conflicts_mean"],
            }
        )
        out_rows.append(summary[key])
    return out_rows, sorted(curve_rows, key=lambda r: (str(r["direction"]), int(r["topk"]), int(r["pool_size"])))


def make_svg(curve_rows: list[dict[str, object]]) -> str:
    width, height = 1500, 900
    margin_l, margin_r = 90, 30
    margin_t, margin_b = 90, 75
    panel_w, panel_h = 650, 285
    gap_x, gap_y = 90, 110
    colors = {2: "#7A7A7A", 3: "#0072B2", 4: "#D55E00", 5: "#009E73", 10: "#CC79A7"}
    dash = {2: "5 5", 3: "", 4: "8 4", 5: "", 10: "2 4"}

    grouped: dict[tuple[str, int], list[dict[str, object]]] = defaultdict(list)
    for row in curve_rows:
        grouped[(str(row["direction"]), int(row["topk"]))].append(row)

    def esc(s: object) -> str:
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def tx(x: float, x0: float, xmax: float = 125.0) -> float:
        return x0 + x / xmax * panel_w

    def ty(y: float, y0: float, ymax: float) -> float:
        return y0 + panel_h - y / ymax * panel_h

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#222}.title{font-size:30px;font-weight:700}.label{font-size:22px}.tick{font-size:17px;fill:#555}.legend{font-size:19px}.small{font-size:17px}</style>',
        '<text class="title" x="750" y="42" text-anchor="middle">ToolBench L5 rank-depth calibration</text>',
    ]

    panels = [
        ("deepseek->gemini-flash", "Pooled recovery", 0, 1.0),
        ("gemini-flash->deepseek", "Pooled recovery", 1, 1.0),
        ("deepseek->gemini-flash", "Mean conflicts", 2, 24.0),
        ("gemini-flash->deepseek", "Mean conflicts", 3, 24.0),
    ]

    for direction, y_label, idx, ymax in panels:
        col = idx % 2
        row = idx // 2
        x0 = margin_l + col * (panel_w + gap_x)
        y0 = margin_t + row * (panel_h + gap_y)
        parts.append(f'<text class="label" x="{x0 + panel_w / 2}" y="{y0 - 28}" text-anchor="middle">{esc(LABELS[direction])}</text>')
        parts.append(f'<rect x="{x0}" y="{y0}" width="{panel_w}" height="{panel_h}" fill="none" stroke="#333" stroke-width="1.4"/>')
        for frac in ([0, 0.25, 0.5, 0.75, 1.0] if ymax == 1.0 else [0, 0.25, 0.5, 0.75, 1.0]):
            yv = frac * ymax
            y = ty(yv, y0, ymax)
            parts.append(f'<line x1="{x0}" x2="{x0 + panel_w}" y1="{y}" y2="{y}" stroke="#E5E5E5"/>')
            parts.append(f'<text class="tick" x="{x0 - 12}" y="{y + 6}" text-anchor="end">{yv:.2g}</text>')
        for xv in [0, 25, 50, 75, 100, 125]:
            x = tx(xv, x0)
            parts.append(f'<line x1="{x}" x2="{x}" y1="{y0}" y2="{y0 + panel_h}" stroke="#F0F0F0"/>')
            parts.append(f'<text class="tick" x="{x}" y="{y0 + panel_h + 26}" text-anchor="middle">{xv}</text>')
        parts.append(f'<text class="small" x="{x0 + panel_w/2}" y="{y0 + panel_h + 56}" text-anchor="middle">pooled trajectories</text>')
        parts.append(f'<text class="small" transform="translate({x0 - 65},{y0 + panel_h/2}) rotate(-90)" text-anchor="middle">{esc(y_label)}</text>')

        for k in K_VALUES:
            pts = grouped.get((direction, k), [])
            if not pts:
                continue
            pts = sorted(pts, key=lambda r: int(r["pool_size"]))
            metric = "success_mean" if row == 0 else "conflicts_mean"
            coords = [(tx(float(r["pool_size"]), x0), ty(float(r[metric]), y0, ymax)) for r in pts if float(r["pool_size"]) <= 125]
            if not coords:
                continue
            d = " ".join(("M" if i == 0 else "L") + f"{x:.1f},{y:.1f}" for i, (x, y) in enumerate(coords))
            dash_attr = f' stroke-dasharray="{dash[k]}"' if dash[k] else ""
            parts.append(f'<path d="{d}" fill="none" stroke="{colors[k]}" stroke-width="3.2"{dash_attr}/>')
            for x, y in coords:
                parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.4" fill="{colors[k]}"/>')

    # Legend
    legend_x, legend_y = 475, 850
    for idx, k in enumerate(K_VALUES):
        x = legend_x + idx * 120
        dash_attr = f' stroke-dasharray="{dash[k]}"' if dash[k] else ""
        parts.append(f'<line x1="{x}" x2="{x+42}" y1="{legend_y}" y2="{legend_y}" stroke="{colors[k]}" stroke-width="4"{dash_attr}/>')
        parts.append(f'<text class="legend" x="{x+50}" y="{legend_y+7}">k={k}</text>')

    parts.append('<text class="small" x="750" y="885" text-anchor="middle">top2 is packet-limited; top4/top10 accumulate conflicts; top3 and top5 are direction-specific calibrated operating points.</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def main() -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    same_model = build_same_model()
    l5_summary, l5_curve = build_l5()

    write_csv(
        RESULT_DIR / "toolbench_same_model_rank_depth.csv",
        same_model,
        [
            "model",
            "topk",
            "trajectories",
            "strict_success",
            "dedup_packets_per_traj",
            "accepted_steps_per_traj",
            "all_pooled_success",
            "all_pooled_dedup",
            "all_pooled_conflicts",
            "all_pooled_reason",
            "pool10_success",
            "pool20_success",
            "pool50_success",
            "pool100_success",
        ],
    )
    write_csv(
        RESULT_DIR / "l5_rank_depth_calibration.csv",
        l5_summary,
        [
            "direction",
            "direction_label",
            "topk",
            "trajectories",
            "steps",
            "top1_match",
            "topk_overlap",
            "kendall_tau",
            "rank_displacement",
            "dedup_packets_per_traj",
            "accepted_steps_per_traj",
            "all_pooled_success",
            "all_pooled_dedup",
            "all_pooled_conflicts",
            "all_pooled_reason",
            "all_pooled_recovered_payload",
            "best_pool_size",
            "best_pool_success",
            "best_pool_dedup",
            "best_pool_conflicts",
        ],
    )
    write_csv(
        RESULT_DIR / "l5_rank_depth_pool_curve.csv",
        l5_curve,
        ["direction", "direction_label", "topk", "pool_size", "success_mean", "dedup_mean", "conflicts_mean"],
    )
    (FIG_DIR / "fig_l5_rank_depth_calibration.svg").write_text(make_svg(l5_curve))


if __name__ == "__main__":
    main()
