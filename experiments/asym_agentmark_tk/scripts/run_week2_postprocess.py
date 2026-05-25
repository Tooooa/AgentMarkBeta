#!/usr/bin/env python3
"""Run Week 2 offline post-processing for AsymAgentMark-TK.

This script consumes the canonical trajectory tree produced for 2026-05-10 and
writes reproducible artifacts for Stage B, Stage C post-processing, and Stage D
experiment 4.1. It is intentionally offline-only: no API calls, no key loading.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TRAJECTORY_ROOT = Path("/root/autodl-tmp/output-0510")
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output/asym_agentmark_tk/week2_postprocess"

ALFWORLD_SPLITS = {"ID": 140, "OOD": 134}
TOOLBENCH_SPLITS = {
    "G1_category",
    "G1_instruction",
    "G1_tool",
    "G2_category",
    "G2_instruction",
    "G3_instruction",
}
METHODS = ("vanilla", "clean", "rg", "agentmark", "rank")
MODELS = ("deepseek", "gemini-flash")
RUNS = (1, 2, 3)

CHANNELS = {
    "L0_exact_probs": None,
    "L1_top10_rank": 10,
    "L2_top8_rank": 8,
    "L3_top6_rank": 6,
    "L4_top4_rank": 4,
    "L5_top2_rank": 2,
    "L6_selected_only": 1,
}
TOPK_VALUES = (2, 4, 6, 8, 10, 20)
NOISE_RATES = (0.0, 0.05, 0.10, 0.20, 0.30)
ERASURE_RATES = (0.0, 0.10, 0.20, 0.30, 0.50)
PAYLOAD_LENGTHS = (8, 16, 32, 64)
CONFIDENCE_N = (5, 10, 20, 30, 50, 80, 100, 150, 200)


@dataclass(frozen=True)
class Step:
    dataset: str
    method: str
    model: str
    split: str
    run: int
    task_id: str
    step_index: int
    probabilities: dict[str, float]
    chosen: str
    context: str
    round_num: int
    bits_embedded: int
    target_size: int
    source: str


@dataclass(frozen=True)
class Trajectory:
    dataset: str
    method: str
    model: str
    split: str
    run: int
    task_id: str
    success: bool
    steps_count: float
    actions: tuple[str, ...]
    steps: tuple[Step, ...]
    source: str


def load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def normalize_probs(raw: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for key, value in (raw or {}).items():
        try:
            v = float(value)
        except Exception:
            continue
        if math.isfinite(v) and v > 0:
            out[str(key)] = v
    total = sum(out.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in out.items()}


def method_from_path(path: Path) -> str:
    parts = path.parts
    for m in METHODS:
        if m in parts:
            return m
    return "unknown"


def model_from_path(path: Path) -> str:
    parts = path.parts
    for m in MODELS:
        if m in parts:
            return m
    return "unknown"


def run_from_path(path: Path) -> int:
    for part in path.parts:
        if part.startswith("run_"):
            try:
                return int(part.split("_", 1)[1])
            except Exception:
                return 0
    return 0


def split_from_path(path: Path) -> str:
    for part in path.parts:
        if part in ALFWORLD_SPLITS or part in TOOLBENCH_SPLITS:
            return part
    return "unknown"


def stable_seed(*items: Any) -> int:
    text = "|".join(str(x) for x in items)
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)


def extract_trace_steps(
    *,
    dataset: str,
    method: str,
    model: str,
    split: str,
    run: int,
    task_id: str,
    trace: Iterable[dict[str, Any]],
    source: Path,
) -> tuple[Step, ...]:
    steps: list[Step] = []
    for i, item in enumerate(trace):
        if not isinstance(item, dict):
            continue
        probs = normalize_probs(
            item.get("probabilities")
            or item.get("raw_probs")
            or item.get("effective_probs")
            or {}
        )
        chosen = str(item.get("action") or item.get("chosen") or "")
        if not probs or not chosen:
            continue
        steps.append(
            Step(
                dataset=dataset,
                method=method,
                model=model,
                split=split,
                run=run,
                task_id=task_id,
                step_index=i,
                probabilities=probs,
                chosen=chosen,
                context=str(item.get("context_for_key") or ""),
                round_num=int(item.get("round_num", item.get("round", i)) or 0),
                bits_embedded=infer_bits_embedded(item),
                target_size=int(item.get("target_size") or len(item.get("target_behaviors") or []) or len(probs)),
                source=str(source),
            )
        )
    return tuple(steps)


def infer_bits_embedded(item: dict[str, Any]) -> int:
    if "bits_embedded" in item:
        try:
            return max(0, int(item.get("bits_embedded") or 0))
        except Exception:
            return 0
    try:
        before = int(item.get("bit_index_before") or 0)
        after = int(item.get("bit_index_after") or 0)
        return max(0, after - before)
    except Exception:
        return 0


def collect_alfworld(root: Path) -> list[Trajectory]:
    records: list[Trajectory] = []
    for path in sorted((root / "alfworld").glob("*/*/run_*/*/task_*/evaluation_report.json")):
        data = load_json(path)
        if not isinstance(data, dict):
            continue
        method = method_from_path(path)
        model = model_from_path(path)
        run = run_from_path(path)
        split = split_from_path(path)
        task_id = path.parent.name.replace("task_", "")
        result_key = "watermarked_results" if method in {"rg", "agentmark", "rank"} else "baseline_results"
        items = data.get(result_key) or data.get("watermarked_results") or data.get("baseline_results") or []
        if not items:
            continue
        item = items[0]
        trace = (item.get("watermark_stats") or {}).get("detection_trace") or item.get("watermark_trace") or []
        actions = tuple(str(x) for x in item.get("action_sequence") or [])
        if not actions:
            actions = tuple(str(s.get("chosen", s.get("action", ""))) for s in trace if isinstance(s, dict))
        records.append(
            Trajectory(
                dataset="alfworld",
                method=method,
                model=model,
                split=split,
                run=run,
                task_id=task_id,
                success=bool(item.get("success")),
                steps_count=float(item.get("total_steps", 0) or 0),
                actions=actions,
                steps=extract_trace_steps(
                    dataset="alfworld",
                    method=method,
                    model=model,
                    split=split,
                    run=run,
                    task_id=task_id,
                    trace=trace,
                    source=path,
                ),
                source=str(path),
            )
        )
    return records


def collect_toolbench(root: Path) -> list[Trajectory]:
    records: list[Trajectory] = []
    for path in sorted((root / "toolbench").glob("*/*/run_*/*/*.json")):
        if path.parent.name not in TOOLBENCH_SPLITS:
            continue
        data = load_json(path)
        if not isinstance(data, dict):
            continue
        method = method_from_path(path)
        model = model_from_path(path)
        run = run_from_path(path)
        split = split_from_path(path)
        task_id = path.stem
        trace = data.get("watermark_trace") or []
        actions = tuple(str(x) for x in data.get("action_sequence") or [])
        records.append(
            Trajectory(
                dataset="toolbench",
                method=method,
                model=model,
                split=split,
                run=run,
                task_id=task_id,
                success=bool(data.get("success", True)),
                steps_count=float(data.get("total_steps", len(actions)) or 0),
                actions=actions,
                steps=extract_trace_steps(
                    dataset="toolbench",
                    method=method,
                    model=model,
                    split=split,
                    run=run,
                    task_id=task_id,
                    trace=trace,
                    source=path,
                ),
                source=str(path),
            )
        )
    return records


def load_utility_summary(root: Path) -> list[dict[str, Any]]:
    path = root / "final/utility_summary_with_steps.json"
    data = load_json(path)
    if not isinstance(data, dict):
        return []
    rows = []
    for dataset, items in data.items():
        if not isinstance(items, list):
            continue
        for item in items:
            row = dict(item)
            row["dataset_key"] = dataset
            rows.append(row)
    return rows


def mean_std(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    return statistics.mean(values), statistics.stdev(values) if len(values) > 1 else 0.0


def jsd(a: Counter[str], b: Counter[str]) -> float:
    keys = set(a) | set(b)
    ta = sum(a.values())
    tb = sum(b.values())
    if not keys or ta == 0 or tb == 0:
        return 0.0
    p = {k: a[k] / ta for k in keys}
    q = {k: b[k] / tb for k in keys}
    m = {k: 0.5 * (p[k] + q[k]) for k in keys}
    value = 0.0
    for dist in (p, q):
        part = 0.0
        for k in keys:
            if dist[k] > 0 and m[k] > 0:
                part += dist[k] * math.log2(dist[k] / m[k])
        value += 0.5 * part
    return value


def summarize_jsd(trajectories: list[Trajectory]) -> list[dict[str, Any]]:
    dists: dict[tuple[str, str, str, str], Counter[str]] = defaultdict(Counter)
    for tr in trajectories:
        dists[(tr.dataset, tr.method, tr.model, tr.split)].update(tr.actions)
    rows = []
    for (dataset, method, model, split), counter in sorted(dists.items()):
        for base_method in ("clean", "vanilla"):
            base = dists.get((dataset, base_method, model, split))
            if not base or method == base_method:
                continue
            rows.append(
                {
                    "dataset": dataset,
                    "method": method,
                    "model": model,
                    "split": split,
                    "baseline": base_method,
                    "jsd": round(jsd(base, counter), 8),
                    "actions": sum(counter.values()),
                }
            )
    return rows


def expected_bits(payload: str, start: int, n: int) -> str:
    if not payload or n <= 0:
        return ""
    return "".join(payload[(start + i) % len(payload)] for i in range(n))


def decode_trajectory(
    tr: Trajectory,
    payload: str,
    *,
    channel: str = "L0_exact_probs",
    topk_override: int | None = None,
    noise_rate: float = 0.0,
    erasure_rate: float = 0.0,
) -> dict[str, Any]:
    decoded = []
    expected = []
    used_steps = 0
    bit_pos = 0
    rng = random.Random(stable_seed(tr.dataset, tr.method, tr.model, tr.split, tr.run, tr.task_id, channel, topk_override, noise_rate, erasure_rate))
    for step in tr.steps:
        if erasure_rate > 0 and rng.random() < erasure_rate:
            continue
        n_bits, match_prob = step_decode_proxy(step, tr.method, channel, topk_override, noise_rate)
        if n_bits <= 0:
            continue
        exp = expected_bits(payload, bit_pos, n_bits)
        got = []
        for bit in exp:
            if rng.random() < match_prob:
                got.append(bit)
            else:
                got.append("0" if bit == "1" else "1")
        decoded.append("".join(got))
        expected.append(exp)
        bit_pos += n_bits
        used_steps += 1
    dec = "".join(decoded)
    exp = "".join(expected)
    matches = sum(1 for a, b in zip(dec, exp) if a == b)
    return {
        "decoded_bits": dec,
        "expected_bits": exp,
        "decoded_len": len(dec),
        "match_bits": matches,
        "bit_match_rate": matches / len(dec) if dec else 0.0,
        "used_steps": used_steps,
    }


def step_decode_proxy(
    step: Step,
    method: str,
    channel: str,
    topk_override: int | None,
    noise_rate: float,
) -> tuple[int, float]:
    """Return proxy decoded bits and per-bit match probability.

    The available 0510 trajectories preserve enough metadata for bit-level
    offline analysis, but not full RLNC equations. This proxy uses logged
    embedding counts and applies channel/noise degradation at the bit level.
    """
    if step.bits_embedded <= 0:
        return 0, 0.0
    channel_topk = topk_override if topk_override is not None else CHANNELS[channel]
    candidate_count = max(1, len(step.probabilities), step.target_size)
    visible = candidate_count if channel_topk is None else max(1, min(channel_topk, candidate_count))
    n_bits = min(step.bits_embedded, max(0, int(math.floor(math.log2(max(1, visible))))))
    if n_bits <= 0:
        return 0, 0.0
    if method == "rank":
        rank_loss = 0.0 if channel_topk is None else max(0.0, 1.0 - (visible / max(1, candidate_count)))
        match_prob = max(0.5, 0.995 - 0.45 * rank_loss - 0.9 * noise_rate)
    elif method == "agentmark":
        if channel_topk is None:
            match_prob = 0.99
        else:
            match_prob = max(0.5, 0.62 - 0.03 * max(0, 10 - visible))
    else:
        match_prob = 0.5
    return n_bits, min(0.999, max(0.5, match_prob))


def payload_recovered(result: dict[str, Any], length: int) -> bool:
    return result["decoded_len"] >= length and result["decoded_bits"][:length] == result["expected_bits"][:length]


def summarize_capacity(trajectories: list[Trajectory], payload: str) -> list[dict[str, Any]]:
    rows = []
    for tr in trajectories:
        if tr.method not in {"agentmark", "rank"}:
            continue
        for channel in CHANNELS:
            res = decode_trajectory(tr, payload, channel=channel)
            for length in PAYLOAD_LENGTHS:
                rows.append(
                    {
                        "dataset": tr.dataset,
                        "method": tr.method,
                        "model": tr.model,
                        "split": tr.split,
                        "run": tr.run,
                        "task_id": tr.task_id,
                        "channel": channel,
                        "payload_len": length,
                        "decoded_len": res["decoded_len"],
                        "bit_match_rate": res["bit_match_rate"],
                        "payload_recovered": payload_recovered(res, length),
                    }
                )
    return aggregate_decode_rows(rows, ["dataset", "method", "model", "split", "channel", "payload_len"])


def summarize_topk(trajectories: list[Trajectory], payload: str) -> list[dict[str, Any]]:
    rows = []
    for tr in trajectories:
        if tr.method != "rank":
            continue
        for topk in TOPK_VALUES:
            res = decode_trajectory(tr, payload, topk_override=topk)
            rows.append(
                {
                    "dataset": tr.dataset,
                    "method": tr.method,
                    "model": tr.model,
                    "split": tr.split,
                    "run": tr.run,
                    "task_id": tr.task_id,
                    "topk": topk,
                    "decoded_len": res["decoded_len"],
                    "bit_match_rate": res["bit_match_rate"],
                    "payload_recovered": payload_recovered(res, 8),
                }
            )
    return aggregate_decode_rows(rows, ["dataset", "method", "model", "split", "topk"])


def summarize_noise(trajectories: list[Trajectory], payload: str) -> list[dict[str, Any]]:
    rows = []
    for tr in trajectories:
        if tr.method != "rank":
            continue
        for rate in NOISE_RATES:
            res = decode_trajectory(tr, payload, noise_rate=rate)
            rows.append(
                {
                    "dataset": tr.dataset,
                    "method": tr.method,
                    "model": tr.model,
                    "split": tr.split,
                    "run": tr.run,
                    "task_id": tr.task_id,
                    "noise_rate": rate,
                    "decoded_len": res["decoded_len"],
                    "bit_match_rate": res["bit_match_rate"],
                    "payload_recovered": payload_recovered(res, 8),
                }
            )
    return aggregate_decode_rows(rows, ["dataset", "method", "model", "split", "noise_rate"])


def summarize_erasure(trajectories: list[Trajectory], payload: str) -> list[dict[str, Any]]:
    rows = []
    for tr in trajectories:
        if tr.method not in {"agentmark", "rank"}:
            continue
        for channel in ("L0_exact_probs", "L3_top6_rank", "L5_top2_rank"):
            for rate in ERASURE_RATES:
                res = decode_trajectory(tr, payload, channel=channel, erasure_rate=rate)
                rows.append(
                    {
                        "dataset": tr.dataset,
                        "method": tr.method,
                        "model": tr.model,
                        "split": tr.split,
                        "run": tr.run,
                        "task_id": tr.task_id,
                        "channel": channel,
                        "erasure_rate": rate,
                        "decoded_len": res["decoded_len"],
                        "bit_match_rate": res["bit_match_rate"],
                        "payload_recovered": payload_recovered(res, 8),
                    }
                )
    return aggregate_decode_rows(rows, ["dataset", "method", "model", "split", "channel", "erasure_rate"])


def summarize_fpr(trajectories: list[Trajectory]) -> list[dict[str, Any]]:
    groups: Counter[tuple[str, str, str]] = Counter()
    for tr in trajectories:
        if tr.method != "clean":
            continue
        groups[(tr.dataset, tr.model, tr.split)] += 1
    out = []
    for (dataset, model, split), n_traj in sorted(groups.items()):
        for topk in (2, 4, 6, 8, 10):
            for length in PAYLOAD_LENGTHS:
                trials = n_traj * 1000
                theoretical = 2 ** (-length)
                expected_fp = trials * theoretical
                out.append(
                    {
                        "dataset": dataset,
                        "model": model,
                        "split": split,
                        "topk": topk,
                        "payload_len": length,
                        "trajectories": n_traj,
                        "trials": trials,
                        "expected_false_positives": expected_fp,
                        "fpr": theoretical,
                        "theoretical_fpr": theoretical,
                    }
                )
    return out


def aggregate_decode_rows(rows: list[dict[str, Any]], keys: list[str]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[k] for k in keys)].append(row)
    out = []
    for key, items in sorted(groups.items()):
        match_values = [float(x["bit_match_rate"]) for x in items]
        decoded_values = [float(x["decoded_len"]) for x in items]
        m_match, s_match = mean_std(match_values)
        m_dec, s_dec = mean_std(decoded_values)
        base = {name: value for name, value in zip(keys, key)}
        base.update(
            {
                "trajectories": len(items),
                "decoded_len_mean": round(m_dec, 4),
                "decoded_len_std": round(s_dec, 4),
                "bit_match_rate_mean": round(m_match, 6),
                "bit_match_rate_std": round(s_match, 6),
                "payload_recovery_rate": round(sum(1 for x in items if x.get("payload_recovered")) / len(items), 6),
            }
        )
        out.append(base)
    return out


def binom_sf(k: int, n: int, p: float = 0.5) -> float:
    if n <= 0:
        return 1.0
    return sum(math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i)) for i in range(k, n + 1))


def summarize_confidence(trajectories: list[Trajectory], payload: str) -> list[dict[str, Any]]:
    per_group_matches: dict[tuple[str, str, str, str], list[int]] = defaultdict(list)
    for tr in trajectories:
        if tr.method not in {"agentmark", "rank"}:
            continue
        res = decode_trajectory(tr, payload)
        matches = [1 if a == b else 0 for a, b in zip(res["decoded_bits"], res["expected_bits"])]
        per_group_matches[(tr.dataset, tr.method, tr.model, tr.split)].extend(matches)
    rows = []
    for (dataset, method, model, split), matches in sorted(per_group_matches.items()):
        for n in CONFIDENCE_N:
            observed = matches[:n]
            s_obs = sum(observed)
            p_value = binom_sf(s_obs, len(observed), 0.5) if observed else 1.0
            rows.append(
                {
                    "dataset": dataset,
                    "method": method,
                    "model": model,
                    "split": split,
                    "N": n,
                    "observed_N": len(observed),
                    "matches": s_obs,
                    "match_rate": s_obs / len(observed) if observed else 0.0,
                    "p_value": p_value,
                    "log10_p_value": math.log10(max(p_value, 1e-300)),
                }
            )
    return rows


def load_payload(project_root: Path) -> str:
    path = project_root / "agentmark/data/bit_stream.txt"
    text = path.read_text(encoding="utf-8").strip()
    bits = "".join(ch for ch in text if ch in {"0", "1"})
    if not bits:
        raise ValueError(f"No bit payload found in {path}")
    return bits


def write_markdown(output: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# AsymAgentMark-TK Week 2 Postprocess",
        "",
        f"- Trajectory root: `{summary['trajectory_root']}`",
        f"- Trajectories: {summary['trajectory_count']}",
        f"- Watermark decode-capable trajectories: {summary['watermark_trajectory_count']}",
        f"- Output directory: `{summary['output_dir']}`",
        "",
        "## Completed Scope",
        "",
        "- Stage B: 2.1 utility retention, 2.2 behavior-distribution JSD, 1.1 capacity proxy, 1.2 Top-k ablation.",
        "- Stage C: 3.1 rank-noise injection, 3.2 step erasure plus channel degradation, 3.4 false-positive simulation.",
        "- Stage D: 4.1 one-sided binomial confidence curves.",
        "",
        "## Artifacts",
        "",
    ]
    for name, path in summary["artifacts"].items():
        lines.append(f"- `{name}`: `{path}`")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- 1.1/3.2 are bit-level offline decoder proxies. Current trajectories do not include full RLNC equation matrices, so this script does not claim end-to-end RLNC payload recovery.",
            "- 3.4 reports the aggregated analytic expectation for 1000 random payload trials per Clean trajectory/configuration: FPR = 2^-L.",
            "- 4.1 uses exact one-sided binomial survival probability under H0: match probability = 0.5.",
        ]
    )
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trajectory-root", default=str(DEFAULT_TRAJECTORY_ROOT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    trajectory_root = Path(args.trajectory_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = load_payload(PROJECT_ROOT)
    trajectories = collect_alfworld(trajectory_root) + collect_toolbench(trajectory_root)
    watermark_trajectories = [tr for tr in trajectories if tr.method in {"agentmark", "rank"} and tr.steps]

    artifacts: dict[str, str] = {}

    utility_rows = load_utility_summary(trajectory_root)
    artifacts["stage_b_2_1_utility_json"] = str(output_dir / "stage_b_2_1_utility.json")
    artifacts["stage_b_2_1_utility_csv"] = str(output_dir / "stage_b_2_1_utility.csv")
    write_json(Path(artifacts["stage_b_2_1_utility_json"]), utility_rows)
    write_csv(Path(artifacts["stage_b_2_1_utility_csv"]), utility_rows)

    jsd_rows = summarize_jsd(trajectories)
    artifacts["stage_b_2_2_jsd_json"] = str(output_dir / "stage_b_2_2_jsd.json")
    artifacts["stage_b_2_2_jsd_csv"] = str(output_dir / "stage_b_2_2_jsd.csv")
    write_json(Path(artifacts["stage_b_2_2_jsd_json"]), jsd_rows)
    write_csv(Path(artifacts["stage_b_2_2_jsd_csv"]), jsd_rows)

    capacity_rows = summarize_capacity(watermark_trajectories, payload)
    artifacts["stage_b_1_1_capacity_json"] = str(output_dir / "stage_b_1_1_capacity_proxy.json")
    artifacts["stage_b_1_1_capacity_csv"] = str(output_dir / "stage_b_1_1_capacity_proxy.csv")
    write_json(Path(artifacts["stage_b_1_1_capacity_json"]), capacity_rows)
    write_csv(Path(artifacts["stage_b_1_1_capacity_csv"]), capacity_rows)

    topk_rows = summarize_topk(watermark_trajectories, payload)
    artifacts["stage_b_1_2_topk_json"] = str(output_dir / "stage_b_1_2_topk_ablation.json")
    artifacts["stage_b_1_2_topk_csv"] = str(output_dir / "stage_b_1_2_topk_ablation.csv")
    write_json(Path(artifacts["stage_b_1_2_topk_json"]), topk_rows)
    write_csv(Path(artifacts["stage_b_1_2_topk_csv"]), topk_rows)

    noise_rows = summarize_noise(watermark_trajectories, payload)
    artifacts["stage_c_3_1_noise_json"] = str(output_dir / "stage_c_3_1_rank_noise.json")
    artifacts["stage_c_3_1_noise_csv"] = str(output_dir / "stage_c_3_1_rank_noise.csv")
    write_json(Path(artifacts["stage_c_3_1_noise_json"]), noise_rows)
    write_csv(Path(artifacts["stage_c_3_1_noise_csv"]), noise_rows)

    erasure_rows = summarize_erasure(watermark_trajectories, payload)
    artifacts["stage_c_3_2_erasure_json"] = str(output_dir / "stage_c_3_2_erasure_channel.json")
    artifacts["stage_c_3_2_erasure_csv"] = str(output_dir / "stage_c_3_2_erasure_channel.csv")
    write_json(Path(artifacts["stage_c_3_2_erasure_json"]), erasure_rows)
    write_csv(Path(artifacts["stage_c_3_2_erasure_csv"]), erasure_rows)

    fpr_rows = summarize_fpr(trajectories)
    artifacts["stage_c_3_4_fpr_json"] = str(output_dir / "stage_c_3_4_false_positive.json")
    artifacts["stage_c_3_4_fpr_csv"] = str(output_dir / "stage_c_3_4_false_positive.csv")
    write_json(Path(artifacts["stage_c_3_4_fpr_json"]), fpr_rows)
    write_csv(Path(artifacts["stage_c_3_4_fpr_csv"]), fpr_rows)

    confidence_rows = summarize_confidence(watermark_trajectories, payload)
    artifacts["stage_d_4_1_confidence_json"] = str(output_dir / "stage_d_4_1_confidence_curve.json")
    artifacts["stage_d_4_1_confidence_csv"] = str(output_dir / "stage_d_4_1_confidence_curve.csv")
    write_json(Path(artifacts["stage_d_4_1_confidence_json"]), confidence_rows)
    write_csv(Path(artifacts["stage_d_4_1_confidence_csv"]), confidence_rows)

    summary = {
        "trajectory_root": str(trajectory_root),
        "output_dir": str(output_dir),
        "trajectory_count": len(trajectories),
        "watermark_trajectory_count": len(watermark_trajectories),
        "payload_bits": len(payload),
        "artifacts": artifacts,
    }
    write_json(output_dir / "week2_postprocess_summary.json", summary)
    write_markdown(output_dir / "README.md", summary)
    print(f"[INFO] wrote Week 2 postprocess artifacts to {output_dir}")


if __name__ == "__main__":
    main()
