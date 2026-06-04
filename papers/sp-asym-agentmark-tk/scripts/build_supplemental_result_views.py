#!/usr/bin/env python3
"""Build compact paper views for semantic rewrite and evidence diagnostics."""

from __future__ import annotations

import csv
import contextlib
import io
import json
import math
import random
import statistics
import sys
from collections import Counter
from collections import defaultdict
from pathlib import Path

import numpy as np

PAPER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PAPER_ROOT.parents[1]
RESULT_DIR = PAPER_ROOT / "results" / "robust_0510"
NON_ROBUST_DIR = PAPER_ROOT / "results" / "non_robust_0510"
FIG_DIR = PAPER_ROOT / "figures"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agentmark.core.parser_utils import extract_and_normalize_probabilities  # noqa: E402
from agentmark.core.rlnc_codec import DeterministicRLNC  # noqa: E402
from agentmark.core.watermark_sampler import rank_based_decoder  # noqa: E402

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


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def fmt(x: float, digits: int = 3) -> str:
    return f"{x:.{digits}f}"


def stable_seed(*items: object) -> int:
    text = "|".join(str(item) for item in items)
    import hashlib

    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)


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


def normalize_probs(raw: dict[str, object], actions: list[str]) -> dict[str, float]:
    vals: dict[str, float] = {}
    for action in actions:
        try:
            vals[action] = max(0.0, float(raw.get(action, 0.0)))
        except Exception:
            vals[action] = 0.0
    total = sum(vals.values())
    if total <= 0 and actions:
        return {action: 1.0 / len(actions) for action in actions}
    return {action: value / total for action, value in vals.items()}


def entry_probs(entry: dict[str, object]) -> dict[str, float]:
    raw = entry.get("probabilities") or entry.get("effective_probs") or entry.get("raw_probs") or {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, float] = {}
    for key, value in raw.items():
        try:
            v = float(value)
        except Exception:
            continue
        if math.isfinite(v):
            out[str(key)] = max(0.0, v)
    return out


def entry_chosen(entry: dict[str, object]) -> str:
    return str(entry.get("action") or entry.get("chosen") or entry.get("selected_action") or "")


def round_num_for_toolbench(entry: dict[str, object]) -> int:
    return int(entry.get("task_idx", 0) or 0) + int(entry.get("round", 0) or 0)


def step_id_for_entry(entry: dict[str, object]) -> int:
    for key in ("step_num", "round"):
        if entry.get(key) is not None:
            try:
                return int(entry.get(key))
            except Exception:
                pass
    return -1


def expected_embed_len(entry: dict[str, object]) -> int:
    if entry.get("bit_index_before") is not None and entry.get("bit_index_after") is not None:
        try:
            return max(0, int(entry["bit_index_after"]) - int(entry["bit_index_before"]))
        except Exception:
            pass
    try:
        return max(0, int(entry.get("bits_embedded") or 0))
    except Exception:
        return 0


def resolve_local_source(source: str) -> Path:
    p = Path(source)
    candidates = [
        p,
        Path(str(p).replace("/root/autodl-tmp/output-0510", str(REPO_ROOT / "实验数据" / "remote_data" / "extracted" / "output-0510"))),
        Path(str(p).replace("/root/autodl-tmp/output-0510", str(REPO_ROOT / "实验数据" / "remote_data" / "output-0510"))),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(source)


def raw_actions_for_entry(entry: dict[str, object], actions: list[str]) -> list[str]:
    raw = entry.get("raw_probs")
    out: list[str] = []
    seen: set[str] = set()
    if isinstance(raw, dict):
        for action in raw:
            text = str(action)
            if text not in seen:
                seen.add(text)
                out.append(text)
    for action in actions:
        if action not in seen:
            seen.add(action)
            out.append(action)
    return out


def mean_rerank_probs(raw_response: str, actions: list[str]) -> dict[str, float]:
    try:
        payload = json.loads(raw_response)
    except Exception:
        payload = [raw_response]
    if not isinstance(payload, list):
        payload = [payload]
    rows: list[dict[str, float]] = []
    for item in payload:
        text = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
        rows.append(extract_and_normalize_probabilities(text, actions))
    if not rows:
        return normalize_probs({}, actions)
    totals = {action: 0.0 for action in actions}
    for row in rows:
        normalized = normalize_probs(row, actions)
        for action in actions:
            totals[action] += normalized[action]
    return normalize_probs({action: value / len(rows) for action, value in totals.items()}, actions)


def build_rewritten_trace(report: dict[str, object], step_probs: dict[int, dict[str, float]]) -> list[dict[str, object]]:
    trace = report.get("watermark_trace") or []
    out: list[dict[str, object]] = []
    if not isinstance(trace, list):
        return out
    for entry in trace:
        if not isinstance(entry, dict):
            continue
        item = dict(entry)
        step_num = step_id_for_entry(item)
        if step_num in step_probs:
            if item.get("effective_probs") is not None:
                item["effective_probs"] = step_probs[step_num]
                item["raw_probs"] = step_probs[step_num]
            else:
                item["probabilities"] = step_probs[step_num]
        out.append(item)
    return out


def majority_packets(packets: list[tuple[int, int]]) -> tuple[list[tuple[int, int]], int, int]:
    votes: dict[int, Counter[int]] = defaultdict(Counter)
    for idx, val in packets:
        votes[int(idx)][int(val)] += 1
    resolved: list[tuple[int, int]] = []
    conflicted = 0
    tied = 0
    for idx, counter in votes.items():
        zeros = counter.get(0, 0)
        ones = counter.get(1, 0)
        if zeros and ones:
            conflicted += 1
        if zeros == ones:
            tied += 1
            continue
        resolved.append((idx, 1 if ones > zeros else 0))
    return sorted(resolved), conflicted, tied


def majority_keyed_packets(packets: list[tuple[object, int, int]]) -> tuple[list[tuple[object, int, int]], int, int]:
    votes: dict[tuple[str, int], Counter[int]] = defaultdict(Counter)
    original_keys: dict[tuple[str, int], object] = {}
    for stream_key, idx, val in packets:
        key = (str(stream_key), int(idx))
        original_keys.setdefault(key, stream_key)
        votes[key][int(val)] += 1
    resolved: list[tuple[object, int, int]] = []
    conflicted = 0
    tied = 0
    for key, counter in votes.items():
        zeros = counter.get(0, 0)
        ones = counter.get(1, 0)
        if zeros and ones:
            conflicted += 1
        if zeros == ones:
            tied += 1
            continue
        _, idx = key
        resolved.append((original_keys[key], idx, 1 if ones > zeros else 0))
    return sorted(resolved, key=lambda item: (str(item[0]), item[1])), conflicted, tied


def recover_from_packets(packets: list[tuple[int, int]], payload: str, stream_key: object) -> dict[str, object]:
    dedup, conflicts, tied = majority_packets(packets)
    codec = DeterministicRLNC(payload, stream_key=stream_key)
    recovered = codec.decode([idx for idx, _ in dedup], [bit for _, bit in dedup]) if dedup else None
    return {
        "decode_ok": recovered == payload,
        "dedup_packet_count": len(dedup),
        "conflicts": conflicts,
        "tied_packet_indices": tied,
        "recovered_payload": recovered or "",
    }


def recover_from_keyed_packets(packets: list[tuple[object, int, int]], payload: str) -> dict[str, object]:
    dedup, conflicts, tied = majority_keyed_packets(packets)
    recovered = None
    if len(dedup) >= len(payload):
        matrix = []
        vector = []
        for stream_key, idx, val in dedup:
            codec = DeterministicRLNC(payload, stream_key=stream_key)
            matrix.append(codec._generate_coeffs(idx))
            vector.append(int(val))
        solver = DeterministicRLNC(payload, stream_key=2025)
        recovered = solver._solve_gf2(np.array(matrix, dtype=int), np.array(vector, dtype=int))
    return {
        "decode_ok": recovered == payload,
        "dedup_packet_count": len(dedup),
        "conflicts": conflicts,
        "tied_packet_indices": tied,
        "recovered_payload": recovered or "",
    }


def recover_trace_packets(trace: list[dict[str, object]], payload: str, stream_key: object, topk: int) -> dict[str, object]:
    packets: list[tuple[int, int]] = []
    cursor = 0
    counters: Counter[str] = Counter()
    for entry in trace:
        embed_len = expected_embed_len(entry)
        has_explicit_index = entry.get("bit_index_before") is not None and entry.get("bit_index_after") is not None
        if embed_len <= 0:
            counters["no_bits_steps"] += 1
            continue
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                bits = rank_based_decoder(
                    entry_probs(entry),
                    entry_chosen(entry),
                    context_for_key=entry.get("context_for_key"),
                    round_num=round_num_for_toolbench(entry),
                    topk=topk,
                )
        except Exception:
            counters["decode_exception_steps"] += 1
            if not has_explicit_index:
                cursor += embed_len
            continue
        if len(bits) != embed_len:
            counters["len_mismatch_steps"] += 1
            if not has_explicit_index:
                cursor += embed_len
            continue
        start = int(entry["bit_index_before"]) if has_explicit_index else cursor
        for off, bit in enumerate(bits):
            packets.append((start + off, int(bit)))
        counters["accepted_steps"] += 1
        if not has_explicit_index:
            cursor += embed_len
    recovered = recover_from_packets(packets, payload, stream_key)
    return {
        **recovered,
        "packet_count": len(packets),
        "accepted_steps": counters["accepted_steps"],
        "_packets": packets,
        "_keyed_packets": [(stream_key, idx, val) for idx, val in packets],
    }


def build_semantic_task_packets(topk: int = 10) -> list[dict[str, object]]:
    root = semantic_root()
    steps = [
        row
        for row in read_csv(root / "stage_c_3_3_semantic_rewrite_steps.csv")
        if row["dataset"] == "toolbench"
        and row["method"] == "rank"
        and row["model"] == "deepseek"
        and int(row["topk"]) == topk
    ]
    by_task = {
        (row["source"], row["rewrite_strength"], int(row["topk"])): row
        for row in read_csv(root / "stage_c_3_3_semantic_rewrite_by_task.csv")
        if row["dataset"] == "toolbench"
        and row["method"] == "rank"
        and row["model"] == "deepseek"
        and int(row["topk"]) == topk
    }
    step_groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in steps:
        step_groups[(row["source"], row["rewrite_strength"])].append(row)

    rows: list[dict[str, object]] = []
    report_cache: dict[str, dict[str, object]] = {}
    for (source, strength), items in sorted(step_groups.items()):
        meta = by_task.get((source, strength, topk))
        if not meta:
            continue
        if source not in report_cache:
            report_cache[source] = read_json(resolve_local_source(source))  # type: ignore[assignment]
        report = report_cache[source]
        original_trace = report.get("watermark_trace") or []
        entry_by_step = {
            step_id_for_entry(entry): entry
            for entry in original_trace
            if isinstance(entry, dict) and step_id_for_entry(entry) >= 0
        }
        step_probs: dict[int, dict[str, float]] = {}
        for item in items:
            step_num = int(item["step_num"])
            entry = entry_by_step.get(step_num)
            if not isinstance(entry, dict):
                continue
            actions = list(entry_probs(entry).keys())
            raw_actions = raw_actions_for_entry(entry, actions)
            step_probs[step_num] = mean_rerank_probs(item["rerank_raw_response"], raw_actions)
        rewritten_trace = build_rewritten_trace(report, step_probs)
        recovered = recover_trace_packets(rewritten_trace, str(meta["payload"]), meta["stream_key"], topk)
        rows.append(
            {
                "dataset": meta["dataset"],
                "method": meta["method"],
                "model": meta["model"],
                "pool_split": meta["pool_split"],
                "pool_run": meta["pool_run"],
                "rewrite_strength": strength,
                "topk": topk,
                "source": source,
                "task_id": meta["task_id"],
                "payload": meta["payload"],
                "stream_key": meta["stream_key"],
                **recovered,
            }
        )
    return rows


def pooled_result(items: list[dict[str, object]]) -> dict[str, object]:
    payloads = sorted({str(row["payload"]) for row in items})
    stream_keys = sorted({str(row["stream_key"]) for row in items})
    packets: list[tuple[int, int]] = []
    keyed_packets: list[tuple[object, int, int]] = []
    for row in items:
        packets.extend(row.get("_packets") or [])  # type: ignore[arg-type]
        keyed_packets.extend(row.get("_keyed_packets") or [])  # type: ignore[arg-type]
    if len(payloads) == 1 and len(stream_keys) == 1:
        res = recover_from_packets(packets, payloads[0], items[0]["stream_key"])
    elif len(payloads) == 1:
        res = recover_from_keyed_packets(keyed_packets, payloads[0])
    else:
        res = {"decode_ok": False, "dedup_packet_count": 0, "conflicts": 0, "tied_packet_indices": 0}
    return {
        "pooled_decode_success_rate": 1.0 if res["decode_ok"] else 0.0,
        "pooled_dedup_packet_count": res["dedup_packet_count"],
        "pooled_conflicts": res["conflicts"],
        "pooled_tied_packet_indices": res["tied_packet_indices"],
    }


def build_semantic_pool_curve() -> list[dict[str, object]]:
    task_rows = build_semantic_task_packets(topk=10)
    pool_sizes = [5, 10, 20, 30, 50, 75, 100, 150, 183]
    repeats = 50
    out: list[dict[str, object]] = []
    groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in task_rows:
        groups[str(row["rewrite_strength"])].append(row)
    for strength in ["light", "medium", "heavy"]:
        items = sorted(groups[strength], key=lambda row: (str(row["source"]), str(row["task_id"])))
        available = len(items)
        for pool_size in pool_sizes:
            if pool_size > available:
                continue
            sampled = []
            for repeat in range(1 if pool_size == available else repeats):
                rng = random.Random(stable_seed("semantic_pool", strength, pool_size, repeat))
                sample = list(items) if pool_size == available else rng.sample(items, pool_size)
                sampled.append(pooled_result(sample))
            success = [float(row["pooled_decode_success_rate"]) for row in sampled]
            packets = [float(row["pooled_dedup_packet_count"]) for row in sampled]
            conflicts = [float(row["pooled_conflicts"]) for row in sampled]
            out.append(
                {
                    "rewrite_strength": strength,
                    "topk": 10,
                    "pool_size": pool_size,
                    "sample_repeats": len(sampled),
                    "available_trajectories": available,
                    "pooled_dsr_mean": fmt(statistics.mean(success)),
                    "pooled_dsr_std": fmt(statistics.stdev(success) if len(success) > 1 else 0.0),
                    "dedup_packets_mean": fmt(statistics.mean(packets)),
                    "conflicts_mean": fmt(statistics.mean(conflicts)),
                }
            )
    return out


def make_semantic_pool_svg(rows: list[dict[str, object]]) -> str:
    width, height = 760, 440
    margin_l, margin_r, margin_t, margin_b = 78, 24, 44, 58
    plot_w = width - margin_l - margin_r
    plot_h = height - margin_t - margin_b
    colors = {"light": "#0072B2", "medium": "#D55E00", "heavy": "#009E73"}
    dash = {"light": "", "medium": "7 4", "heavy": "2 4"}
    labels = {"light": "Light", "medium": "Medium", "heavy": "Heavy"}

    def tx(x: float) -> float:
        return margin_l + x / 183.0 * plot_w

    def ty(y: float) -> float:
        return margin_t + (1.0 - y) * plot_h

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#222}.tick{font-size:17px;fill:#555}.label{font-size:18px}.legend{font-size:18px}</style>',
        f'<rect x="{margin_l}" y="{margin_t}" width="{plot_w}" height="{plot_h}" fill="none" stroke="#333" stroke-width="1.3"/>',
    ]
    for yv in [0, 0.25, 0.5, 0.75, 1.0]:
        y = ty(yv)
        parts.append(f'<line x1="{margin_l}" x2="{margin_l + plot_w}" y1="{y}" y2="{y}" stroke="#E7E7E7"/>')
        parts.append(f'<text class="tick" x="{margin_l - 10}" y="{y + 6}" text-anchor="end">{yv:.2g}</text>')
    for xv in [0, 25, 50, 75, 100, 150, 183]:
        x = tx(xv)
        parts.append(f'<line x1="{x}" x2="{x}" y1="{margin_t}" y2="{margin_t + plot_h}" stroke="#F1F1F1"/>')
        parts.append(f'<text class="tick" x="{x}" y="{margin_t + plot_h + 26}" text-anchor="middle">{xv}</text>')
    parts.append(f'<text class="label" x="{margin_l + plot_w / 2}" y="{height - 16}" text-anchor="middle">pooled trajectories</text>')
    parts.append(f'<text class="label" transform="translate(22,{margin_t + plot_h / 2}) rotate(-90)" text-anchor="middle">payload recovery</text>')
    for strength in ["light", "medium", "heavy"]:
        pts = [
            (float(row["pool_size"]), float(row["pooled_dsr_mean"]))
            for row in rows
            if row["rewrite_strength"] == strength
        ]
        pts = sorted(pts)
        coords = [(tx(x), ty(y)) for x, y in pts]
        d = " ".join(("M" if i == 0 else "L") + f"{x:.1f},{y:.1f}" for i, (x, y) in enumerate(coords))
        dash_attr = f' stroke-dasharray="{dash[strength]}"' if dash[strength] else ""
        parts.append(f'<path d="{d}" fill="none" stroke="{colors[strength]}" stroke-width="3.2"{dash_attr}/>')
        for x, y in coords:
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{colors[strength]}"/>')
    legend_x, legend_y = 230, 22
    for idx, strength in enumerate(["light", "medium", "heavy"]):
        x = legend_x + idx * 125
        dash_attr = f' stroke-dasharray="{dash[strength]}"' if dash[strength] else ""
        parts.append(f'<line x1="{x}" x2="{x + 38}" y1="{legend_y}" y2="{legend_y}" stroke="{colors[strength]}" stroke-width="4"{dash_attr}/>')
        parts.append(f'<text class="legend" x="{x + 48}" y="{legend_y + 6}">{labels[strength]}</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


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
    semantic_curve_rows = build_semantic_pool_curve()
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
        RESULT_DIR / "semantic_rewrite_pool_curve.csv",
        semantic_curve_rows,
        [
            "rewrite_strength",
            "topk",
            "pool_size",
            "sample_repeats",
            "available_trajectories",
            "pooled_dsr_mean",
            "pooled_dsr_std",
            "dedup_packets_mean",
            "conflicts_mean",
        ],
    )
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    (FIG_DIR / "fig_semantic_rewrite_pool_curve.svg").write_text(
        make_semantic_pool_svg(semantic_curve_rows),
        encoding="utf-8",
    )
    write_csv(
        NON_ROBUST_DIR / "evidence_confidence_main_curve.csv",
        evidence_rows,
        ["dataset", "method", "config", "label", "N", "runs", "match_rate", "mean_log10_p"],
    )


if __name__ == "__main__":
    main()
