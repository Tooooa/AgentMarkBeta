#!/usr/bin/env python3
"""Run Evidence Significance experiments for AsymAgentMark-TK.

This is an offline-only post-processing script for experiment axis 4 in the
0510 design doc. It reads existing A3/A4 watermarked trajectories, decodes the
logged watermark bits, compares them with the expected RLNC stream for the
payload, and computes exact one-sided binomial p-values.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agentmark.core.rlnc_codec import DeterministicRLNC
from agentmark.core.watermark_sampler import differential_based_decoder, rank_based_decoder


DEFAULT_INPUT_ROOT = Path("/root/autodl-tmp/output-0510")
DEFAULT_OUTPUT_DIR = DEFAULT_INPUT_ROOT / "evidence_strength"
DEFAULT_PAYLOAD = "11001101"
DEFAULT_STREAM_KEY = 2025
N_VALUES = (5, 10, 20, 30, 50, 80, 100, 150, 200)
TOPK_VALUES: tuple[int | None, ...] = (None, 10, 5, 3, 2)
PAYLOAD_LENGTHS = (8, 16, 32, 64)
ALPHAS = (0.05, 0.01, 0.001)
NOISE_RATES = (0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5)
ERASURE_RATES = (0.0, 0.1, 0.2, 0.3, 0.5, 0.7)
TOOLBENCH_SPLITS = {
    "G1_category",
    "G1_instruction",
    "G1_tool",
    "G2_category",
    "G2_instruction",
    "G3_instruction",
}


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
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_default_payload() -> str:
    path = PROJECT_ROOT / "agentmark/data/bit_stream.txt"
    if path.exists():
        bits = "".join(ch for ch in path.read_text(encoding="utf-8") if ch in {"0", "1"})
        if bits:
            return bits
    return DEFAULT_PAYLOAD


def method_from_path(path: Path) -> str:
    parts = set(path.parts)
    if "agentmark" in parts:
        return "agentmark"
    if "rank" in parts:
        return "rank"
    return "unknown"


def model_from_path(path: Path) -> str:
    for part in path.parts:
        if part in {"deepseek", "gemini-flash", "gemini"}:
            return "gemini-flash" if part == "gemini" else part
    return "unknown"


def run_from_path(path: Path) -> int:
    for part in path.parts:
        if part.startswith("run_"):
            try:
                return int(part.split("_", 1)[1])
            except ValueError:
                return 0
    return 0


def split_from_path(path: Path) -> str:
    for part in path.parts:
        if part in {"ID", "OOD"} or part in TOOLBENCH_SPLITS:
            return part
    return "unknown"


def task_from_path(path: Path, dataset: str) -> str:
    if dataset == "alfworld":
        for part in path.parts:
            if part.startswith("task_"):
                return part.replace("task_", "")
    return path.stem


def normalize_meta_payload(meta: dict[str, Any], default_payload: str) -> tuple[str, Any, str]:
    payload = meta.get("payload") or meta.get("payload_bits") or default_payload[:8]
    payload = "".join(ch for ch in str(payload) if ch in {"0", "1"}) or default_payload[:8]
    stream_key = meta.get("stream_key", DEFAULT_STREAM_KEY)
    return payload, stream_key, "rlnc_meta"


def build_toolbench_manifest(input_root: Path) -> dict[tuple[str, str, int, str, str], dict[str, Any]]:
    rows = load_json(input_root / "manifests/toolbench_clean_records.json")
    out: dict[tuple[str, str, int, str, str], dict[str, Any]] = {}
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            key = (
                str(row.get("method")),
                str(row.get("model")),
                int(row.get("run")),
                str(row.get("split")),
                str(row.get("task_file")),
            )
        except Exception:
            continue
        out[key] = row
    return out


def resolve_toolbench_meta(
    path: Path,
    manifest: dict[tuple[str, str, int, str, str], dict[str, Any]],
    default_payload: str,
) -> tuple[str, Any, str, str]:
    key = (method_from_path(path), model_from_path(path), run_from_path(path), split_from_path(path), path.name)
    candidates: list[Path] = []
    row = manifest.get(key)
    if row:
        for field in ("original_path", "source_pred_root"):
            value = row.get(field)
            if value:
                p = Path(str(value))
                candidates.append(p)
                candidates.extend(p.parents)
    candidates.extend(path.parents)

    seen: set[Path] = set()
    for base in candidates:
        if base in seen:
            continue
        seen.add(base)
        meta_path = base if base.name == "rlnc_meta.json" else base / "rlnc_meta.json"
        if meta_path.exists():
            meta = load_json(meta_path)
            if isinstance(meta, dict):
                payload, stream_key, source = normalize_meta_payload(meta, default_payload)
                return payload, stream_key, source, str(meta_path)
    return default_payload[:8], DEFAULT_STREAM_KEY, "fallback", ""


def resolve_alfworld_meta(report: dict[str, Any], default_payload: str) -> tuple[str, Any, str, str]:
    cfg = report.get("metadata", {}).get("config", {}) if isinstance(report.get("metadata"), dict) else {}
    watermark_cfg = cfg.get("watermark_config", {}) if isinstance(cfg.get("watermark_config"), dict) else {}
    experiment_cfg = cfg.get("experiment_config", {}) if isinstance(cfg.get("experiment_config"), dict) else {}
    payload_len = int(watermark_cfg.get("payload_bit_length") or 8)
    payload = default_payload[:payload_len] or DEFAULT_PAYLOAD
    stream_key = watermark_cfg.get("rlnc_stream_key")
    if stream_key is None:
        stream_key = experiment_cfg.get("random_seed")
    if stream_key is None:
        stream_key = DEFAULT_STREAM_KEY
    return payload, stream_key, "report_metadata", ""


def expected_embed_len(entry: dict[str, Any]) -> int:
    if entry.get("bit_index_before") is not None and entry.get("bit_index_after") is not None:
        try:
            return max(0, int(entry["bit_index_after"]) - int(entry["bit_index_before"]))
        except Exception:
            pass
    try:
        return max(0, int(entry.get("bits_embedded") or 0))
    except Exception:
        return 0


def decode_entry(entry: dict[str, Any], method: str, dataset: str, topk: int | None) -> str:
    probs = entry.get("probabilities") or entry.get("effective_probs") or entry.get("raw_probs") or {}
    chosen = entry.get("action") or entry.get("chosen")
    context = entry.get("context_for_key")
    if dataset == "toolbench":
        round_num = int(entry.get("task_idx", 0) or 0) + int(entry.get("round", 0) or 0)
    else:
        round_num = entry.get("round_num")
        if round_num is None:
            round_num = max(int(entry.get("step_num", 1) or 1) - 1, 0)
    if method == "rank":
        return rank_based_decoder(probs, chosen, context_for_key=context, round_num=int(round_num), topk=topk)
    return differential_based_decoder(probs, chosen, context_for_key=context, round_num=int(round_num))


def topk_label(method: str, topk: int | None) -> str:
    if method == "agentmark":
        return "L0_exact_probs"
    return "full_rank" if topk is None else f"top{topk}"


def binom_sf(k: int, n: int, p: float = 0.5) -> float:
    if n <= 0:
        return 1.0
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    if p != 0.5:
        return sum(math.comb(n, i) * (p**i) * ((1 - p) ** (n - i)) for i in range(k, n + 1))
    return math.ldexp(sum(math.comb(n, i) for i in range(k, n + 1)), -n)


def p_value_from_matches(matches: list[int], n: int) -> tuple[int, int, float]:
    observed = matches[:n]
    s_obs = sum(observed)
    return len(observed), s_obs, binom_sf(s_obs, len(observed), 0.5) if observed else 1.0


def stable_seed(*items: Any) -> int:
    text = "|".join(str(item) for item in items)
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)


def collect_observations_from_trace(
    *,
    trace: list[dict[str, Any]],
    dataset: str,
    method: str,
    model: str,
    split: str,
    run: int,
    task_id: str,
    source: str,
    payload: str,
    stream_key: Any,
    topk: int | None,
) -> tuple[list[dict[str, Any]], Counter[str]]:
    rows: list[dict[str, Any]] = []
    counters: Counter[str] = Counter()
    cursor = 0
    codec = DeterministicRLNC(payload, stream_key=stream_key)
    config = topk_label(method, topk)

    for entry in trace:
        if not isinstance(entry, dict):
            continue
        embed_len = expected_embed_len(entry)
        has_explicit_index = entry.get("bit_index_before") is not None and entry.get("bit_index_after") is not None
        if embed_len <= 0:
            counters["no_bits_steps"] += 1
            continue
        start = int(entry["bit_index_before"]) if has_explicit_index else cursor
        expected = codec.get_stream(start, embed_len)
        try:
            decoded = decode_entry(entry, method, dataset, topk)
        except Exception:
            counters["decode_exception_steps"] += 1
            decoded = ""
        if len(decoded) != embed_len:
            counters["len_mismatch_steps"] += 1
            if not has_explicit_index:
                cursor += embed_len
            continue
        bit_matches = [1 if a == b else 0 for a, b in zip(decoded, expected)]
        rows.append(
            {
                "dataset": dataset,
                "method": method,
                "model": model,
                "split": split,
                "run": run,
                "task_id": task_id,
                "config": config,
                "topk": "full" if topk is None else topk,
                "source": source,
                "step_start_index": start,
                "bits_in_step": embed_len,
                "decoded_bits": decoded,
                "expected_bits": expected,
                "step_match": int(all(bit_matches)),
                "bit_matches": "".join(str(x) for x in bit_matches),
            }
        )
        counters["accepted_steps"] += 1
        if not has_explicit_index:
            cursor += embed_len
    return rows, counters


def collect_observations(input_root: Path, default_payload: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []

    for method in ("agentmark", "rank"):
        for path in sorted((input_root / "alfworld" / method).glob("**/evaluation_report.json")):
            report = load_json(path)
            if not isinstance(report, dict):
                continue
            items = report.get("watermarked_results") or []
            if not items or not isinstance(items[0], dict):
                continue
            payload, stream_key, meta_source, meta_path = resolve_alfworld_meta(report, default_payload)
            trace = (items[0].get("watermark_stats") or {}).get("detection_trace") or items[0].get("watermark_trace") or []
            model = model_from_path(path)
            split = split_from_path(path)
            run = run_from_path(path)
            task_id = task_from_path(path, "alfworld")
            topks = (None,) if method == "agentmark" else TOPK_VALUES
            for topk in topks:
                obs, counts = collect_observations_from_trace(
                    trace=trace,
                    dataset="alfworld",
                    method=method,
                    model=model,
                    split=split,
                    run=run,
                    task_id=task_id,
                    source=str(path),
                    payload=payload,
                    stream_key=stream_key,
                    topk=topk,
                )
                rows.extend(obs)
                audit.append(
                    {
                        "dataset": "alfworld",
                        "method": method,
                        "model": model,
                        "split": split,
                        "run": run,
                        "task_id": task_id,
                        "config": topk_label(method, topk),
                        "payload_len": len(payload),
                        "stream_key": stream_key,
                        "meta_source": meta_source,
                        "meta_path": meta_path,
                        **counts,
                    }
                )

    manifest = build_toolbench_manifest(input_root)
    for method in ("agentmark", "rank"):
        for path in sorted((input_root / "toolbench" / method).glob("**/*.json")):
            if path.name == "rlnc_meta.json" or path.parent.name not in TOOLBENCH_SPLITS:
                continue
            data = load_json(path)
            if not isinstance(data, dict):
                continue
            trace = data.get("watermark_trace") or []
            if not isinstance(trace, list):
                continue
            payload, stream_key, meta_source, meta_path = resolve_toolbench_meta(path, manifest, default_payload)
            model = model_from_path(path)
            split = split_from_path(path)
            run = run_from_path(path)
            task_id = task_from_path(path, "toolbench")
            topks = (None,) if method == "agentmark" else TOPK_VALUES
            for topk in topks:
                obs, counts = collect_observations_from_trace(
                    trace=trace,
                    dataset="toolbench",
                    method=method,
                    model=model,
                    split=split,
                    run=run,
                    task_id=task_id,
                    source=str(path),
                    payload=payload,
                    stream_key=stream_key,
                    topk=topk,
                )
                rows.extend(obs)
                audit.append(
                    {
                        "dataset": "toolbench",
                        "method": method,
                        "model": model,
                        "split": split,
                        "run": run,
                        "task_id": task_id,
                        "config": topk_label(method, topk),
                        "payload_len": len(payload),
                        "stream_key": stream_key,
                        "meta_source": meta_source,
                        "meta_path": meta_path,
                        **counts,
                    }
                )
    return rows, audit


def group_step_matches(rows: list[dict[str, Any]]) -> dict[tuple[Any, ...], list[int]]:
    groups: dict[tuple[Any, ...], list[tuple[str, int]]] = defaultdict(list)
    for row in rows:
        key = (row["dataset"], row["method"], row["model"], row["split"], row["run"], row["config"])
        order = f"{row['task_id']}|{int(row['step_start_index']):08d}|{row['source']}"
        groups[key].append((order, int(row["step_match"])))
    return {key: [match for _, match in sorted(items)] for key, items in groups.items()}


def summarize_confidence(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    per_run = []
    groups = group_step_matches(rows)
    for key, matches in sorted(groups.items()):
        dataset, method, model, split, run, config = key
        for n in N_VALUES:
            observed_n, s_obs, p_value = p_value_from_matches(matches, n)
            per_run.append(
                {
                    "dataset": dataset,
                    "method": method,
                    "model": model,
                    "split": split,
                    "run": run,
                    "config": config,
                    "N": n,
                    "observed_N": observed_n,
                    "matches": s_obs,
                    "match_rate": s_obs / observed_n if observed_n else 0.0,
                    "p_value": p_value,
                    "log10_p_value": math.log10(max(p_value, 1e-300)),
                    "truncated": observed_n < n,
                }
            )

    agg_groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in per_run:
        agg_groups[(row["dataset"], row["method"], row["model"], row["split"], row["config"], row["N"])].append(row)

    aggregate = []
    for key, items in sorted(agg_groups.items()):
        dataset, method, model, split, config, n = key
        logps = [float(x["log10_p_value"]) for x in items]
        rates = [float(x["match_rate"]) for x in items]
        observed = [int(x["observed_N"]) for x in items]
        aggregate.append(
            {
                "dataset": dataset,
                "method": method,
                "model": model,
                "split": split,
                "config": config,
                "N": n,
                "runs": len(items),
                "observed_N_min": min(observed),
                "observed_N_mean": statistics.mean(observed),
                "match_rate_mean": statistics.mean(rates),
                "match_rate_std": statistics.stdev(rates) if len(rates) > 1 else 0.0,
                "log10_p_value_mean": statistics.mean(logps),
                "log10_p_value_std": statistics.stdev(logps) if len(logps) > 1 else 0.0,
                "p_value_geomean": 10 ** statistics.mean(logps),
            }
        )
    return per_run, aggregate


def summarize_thresholds(confidence_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    per_run = []
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in confidence_rows:
        grouped[(row["dataset"], row["method"], row["model"], row["split"], row["run"], row["config"])].append(row)
    for key, items in sorted(grouped.items()):
        dataset, method, model, split, run, config = key
        ordered = sorted(items, key=lambda x: int(x["N"]))
        for alpha in ALPHAS:
            hit = next((row for row in ordered if float(row["p_value"]) < alpha and not row["truncated"]), None)
            per_run.append(
                {
                    "dataset": dataset,
                    "method": method,
                    "model": model,
                    "split": split,
                    "run": run,
                    "config": config,
                    "payload_len": 8,
                    "alpha": alpha,
                    "N_min": hit["N"] if hit else "",
                    "attained": hit is not None,
                    "p_value_at_N_min": hit["p_value"] if hit else "",
                }
            )

    # The requested L dimension is reported analytically from the binomial model:
    # require at least L confidently matching coded packets, then apply the same
    # alpha threshold on the first available N grid.
    for row in list(per_run):
        if row["payload_len"] != 8 or not row["attained"]:
            continue
        for length in PAYLOAD_LENGTHS:
            if length == 8:
                continue
            scaled = int(math.ceil(int(row["N_min"]) * length / 8))
            grid_hit = next((n for n in N_VALUES if n >= scaled), "")
            new_row = dict(row)
            new_row["payload_len"] = length
            new_row["N_min"] = grid_hit
            new_row["attained"] = grid_hit != ""
            new_row["p_value_at_N_min"] = ""
            per_run.append(new_row)

    agg_groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in per_run:
        agg_groups[(row["dataset"], row["method"], row["model"], row["split"], row["config"], row["payload_len"], row["alpha"])].append(row)
    aggregate = []
    for key, items in sorted(agg_groups.items()):
        dataset, method, model, split, config, payload_len, alpha = key
        attained = [row for row in items if row["attained"] and row["N_min"] != ""]
        n_values = [int(row["N_min"]) for row in attained]
        aggregate.append(
            {
                "dataset": dataset,
                "method": method,
                "model": model,
                "split": split,
                "config": config,
                "payload_len": payload_len,
                "alpha": alpha,
                "runs": len(items),
                "attained_runs": len(attained),
                "N_min_mean": statistics.mean(n_values) if n_values else "",
                "N_min_std": statistics.stdev(n_values) if len(n_values) > 1 else 0.0 if n_values else "",
                "N_min_median": statistics.median(n_values) if n_values else "",
            }
        )
    return per_run, aggregate


def perturb_matches(matches: list[int], *, noise_rate: float, erasure_rate: float, seed: int) -> list[int]:
    rng = random.Random(seed)
    out = []
    for match in matches:
        if erasure_rate and rng.random() < erasure_rate:
            continue
        value = match
        if noise_rate and rng.random() < noise_rate:
            value = 1 - value
        out.append(value)
    return out


def summarize_compensation(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups = group_step_matches(rows)
    out = []
    for key, matches in sorted(groups.items()):
        dataset, method, model, split, run, config = key
        if method != "rank":
            continue
        base_hits: dict[float, int | None] = {}
        for alpha in (0.01,):
            base_hits[alpha] = next((n for n in N_VALUES if p_value_from_matches(matches, n)[2] < alpha and len(matches) >= n), None)
        for noise in NOISE_RATES:
            for erasure in ERASURE_RATES:
                for alpha, base_n in base_hits.items():
                    attack_n = None
                    attack_observed = 0
                    for raw_n in N_VALUES:
                        if len(matches) < raw_n:
                            continue
                        perturbed = perturb_matches(
                            matches[:raw_n],
                            noise_rate=noise,
                            erasure_rate=erasure,
                            seed=stable_seed(dataset, method, model, split, run, config, noise, erasure, raw_n),
                        )
                        observed_n, s_obs, p_value = p_value_from_matches(perturbed, len(perturbed))
                        if observed_n > 0 and p_value < alpha:
                            attack_n = raw_n
                            attack_observed = observed_n
                            break
                    out.append(
                        {
                            "dataset": dataset,
                            "method": method,
                            "model": model,
                            "split": split,
                            "run": run,
                            "config": config,
                            "alpha": alpha,
                            "noise_rate": noise,
                            "erasure_rate": erasure,
                            "N_clean": base_n or "",
                            "N_attack": attack_n or "",
                            "compensation_ratio": (attack_n / base_n) if attack_n and base_n else "",
                            "observed_after_attack": attack_observed,
                        }
                    )
    return out


def aggregate_compensation(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[
            (
                row["dataset"],
                row["method"],
                row["model"],
                row["split"],
                row["config"],
                row["alpha"],
                row["noise_rate"],
                row["erasure_rate"],
            )
        ].append(row)
    out = []
    for key, items in sorted(groups.items()):
        dataset, method, model, split, config, alpha, noise, erasure = key
        ratios = [float(row["compensation_ratio"]) for row in items if row["compensation_ratio"] != ""]
        attack_ns = [int(row["N_attack"]) for row in items if row["N_attack"] != ""]
        clean_ns = [int(row["N_clean"]) for row in items if row["N_clean"] != ""]
        out.append(
            {
                "dataset": dataset,
                "method": method,
                "model": model,
                "split": split,
                "config": config,
                "alpha": alpha,
                "noise_rate": noise,
                "erasure_rate": erasure,
                "runs": len(items),
                "attained_runs": len(ratios),
                "N_clean_mean": statistics.mean(clean_ns) if clean_ns else "",
                "N_attack_mean": statistics.mean(attack_ns) if attack_ns else "",
                "compensation_ratio_mean": statistics.mean(ratios) if ratios else "",
                "compensation_ratio_std": statistics.stdev(ratios) if len(ratios) > 1 else 0.0 if ratios else "",
            }
        )
    return out


def try_write_plots(output_dir: Path, confidence_agg: list[dict[str, Any]], threshold_agg: list[dict[str, Any]]) -> list[str]:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return []
    paths: list[str] = []
    plot_dir = output_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    for dataset in sorted({row["dataset"] for row in confidence_agg}):
        subset = [row for row in confidence_agg if row["dataset"] == dataset and row["split"] in {"ID", "G1_instruction"}]
        if not subset:
            continue
        plt.figure(figsize=(10, 6))
        for label in sorted({(row["method"], row["model"], row["split"], row["config"]) for row in subset}):
            method, model, split, config = label
            rows = sorted(
                [row for row in subset if (row["method"], row["model"], row["split"], row["config"]) == label],
                key=lambda x: int(x["N"]),
            )
            if not rows:
                continue
            plt.plot([row["N"] for row in rows], [row["log10_p_value_mean"] for row in rows], marker="o", label=f"{method}/{model}/{split}/{config}")
        for alpha in ALPHAS:
            plt.axhline(math.log10(alpha), linestyle="--", linewidth=1, color="gray")
        plt.xlabel("Observed steps N")
        plt.ylabel("mean log10(p-value)")
        plt.title(f"Evidence confidence curve ({dataset})")
        plt.legend(fontsize=7)
        plt.tight_layout()
        path = plot_dir / f"stage_d_4_1_confidence_{dataset}.png"
        plt.savefig(path, dpi=180)
        plt.close()
        paths.append(str(path))

    heat_rows = [row for row in threshold_agg if row["alpha"] == 0.01 and row["method"] == "rank" and row["payload_len"] == 8]
    if heat_rows:
        labels = sorted({(row["dataset"], row["model"], row["split"]) for row in heat_rows})
        for dataset, model, split in labels[:4]:
            rows = [row for row in heat_rows if (row["dataset"], row["model"], row["split"]) == (dataset, model, split)]
            configs = [cfg for cfg in ("full_rank", "top10", "top5", "top3", "top2") if any(row["config"] == cfg for row in rows)]
            vals = []
            for cfg in configs:
                row = next((x for x in rows if x["config"] == cfg), None)
                vals.append(float(row["N_min_mean"]) if row and row["N_min_mean"] != "" else math.nan)
            plt.figure(figsize=(7, 3))
            plt.bar(configs, vals)
            plt.ylabel("N_min mean (alpha=0.01)")
            plt.title(f"Minimum evidence threshold ({dataset}/{model}/{split})")
            plt.tight_layout()
            path = plot_dir / f"stage_d_4_2_threshold_{dataset}_{model}_{split}.png"
            plt.savefig(path, dpi=180)
            plt.close()
            paths.append(str(path))
    return paths


def write_readme(output_dir: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Evidence Strength Experiment",
        "",
        f"- Input root: `{summary['input_root']}`",
        f"- Output dir: `{summary['output_dir']}`",
        f"- Step observations: {summary['step_observations']}",
        f"- Audit rows: {summary['audit_rows']}",
        "",
        "## Completed",
        "",
        "- 4.1 解码置信度曲线：exact one-sided binomial test, H0 match probability = 0.5.",
        "- 4.2 最小证据阈值：alpha in {0.05, 0.01, 0.001}; payload lengths {8, 16, 32, 64}.",
        "- 4.3 鲁棒性补偿分析：基于 4.1 match 序列注入 erasure/noise 后重新求 N_attack / N_clean.",
        "",
        "## Artifacts",
        "",
    ]
    for name, path in summary["artifacts"].items():
        lines.append(f"- `{name}`: `{path}`")
    if summary.get("plots"):
        lines.extend(["", "## Plots", ""])
        for path in summary["plots"]:
            lines.append(f"- `{path}`")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- `agentmark` uses differential decoding at L0 exact probabilities.",
            "- `rank` reports full-rank plus top-k decoder views for k = 10, 5, 3, 2.",
            "- Step-level evidence counts one accepted embedding step as one Bernoulli trial; a step matches only when all decoded bits for that step match the expected RLNC coded bits.",
        ]
    )
    (output_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", default=str(DEFAULT_INPUT_ROOT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    input_root = Path(args.input_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    default_payload = load_default_payload()
    observations, audit = collect_observations(input_root, default_payload)
    confidence_run, confidence_agg = summarize_confidence(observations)
    threshold_run, threshold_agg = summarize_thresholds(confidence_run)
    compensation = summarize_compensation(observations)
    compensation_agg = aggregate_compensation(compensation)

    artifacts = {
        "observations_json": str(output_dir / "evidence_step_observations.json"),
        "observations_csv": str(output_dir / "evidence_step_observations.csv"),
        "audit_json": str(output_dir / "evidence_decode_audit.json"),
        "audit_csv": str(output_dir / "evidence_decode_audit.csv"),
        "stage_d_4_1_per_run_json": str(output_dir / "stage_d_4_1_confidence_per_run.json"),
        "stage_d_4_1_per_run_csv": str(output_dir / "stage_d_4_1_confidence_per_run.csv"),
        "stage_d_4_1_summary_json": str(output_dir / "stage_d_4_1_confidence_summary.json"),
        "stage_d_4_1_summary_csv": str(output_dir / "stage_d_4_1_confidence_summary.csv"),
        "stage_d_4_2_per_run_json": str(output_dir / "stage_d_4_2_thresholds_per_run.json"),
        "stage_d_4_2_per_run_csv": str(output_dir / "stage_d_4_2_thresholds_per_run.csv"),
        "stage_d_4_2_summary_json": str(output_dir / "stage_d_4_2_thresholds_summary.json"),
        "stage_d_4_2_summary_csv": str(output_dir / "stage_d_4_2_thresholds_summary.csv"),
        "stage_d_4_3_compensation_json": str(output_dir / "stage_d_4_3_compensation.json"),
        "stage_d_4_3_compensation_csv": str(output_dir / "stage_d_4_3_compensation.csv"),
        "stage_d_4_3_compensation_summary_json": str(output_dir / "stage_d_4_3_compensation_summary.json"),
        "stage_d_4_3_compensation_summary_csv": str(output_dir / "stage_d_4_3_compensation_summary.csv"),
    }
    write_json(Path(artifacts["observations_json"]), observations)
    write_csv(Path(artifacts["observations_csv"]), observations)
    write_json(Path(artifacts["audit_json"]), audit)
    write_csv(Path(artifacts["audit_csv"]), audit)
    write_json(Path(artifacts["stage_d_4_1_per_run_json"]), confidence_run)
    write_csv(Path(artifacts["stage_d_4_1_per_run_csv"]), confidence_run)
    write_json(Path(artifacts["stage_d_4_1_summary_json"]), confidence_agg)
    write_csv(Path(artifacts["stage_d_4_1_summary_csv"]), confidence_agg)
    write_json(Path(artifacts["stage_d_4_2_per_run_json"]), threshold_run)
    write_csv(Path(artifacts["stage_d_4_2_per_run_csv"]), threshold_run)
    write_json(Path(artifacts["stage_d_4_2_summary_json"]), threshold_agg)
    write_csv(Path(artifacts["stage_d_4_2_summary_csv"]), threshold_agg)
    write_json(Path(artifacts["stage_d_4_3_compensation_json"]), compensation)
    write_csv(Path(artifacts["stage_d_4_3_compensation_csv"]), compensation)
    write_json(Path(artifacts["stage_d_4_3_compensation_summary_json"]), compensation_agg)
    write_csv(Path(artifacts["stage_d_4_3_compensation_summary_csv"]), compensation_agg)

    plots = try_write_plots(output_dir, confidence_agg, threshold_agg)
    summary = {
        "input_root": str(input_root),
        "output_dir": str(output_dir),
        "step_observations": len(observations),
        "audit_rows": len(audit),
        "artifacts": artifacts,
        "plots": plots,
    }
    write_json(output_dir / "evidence_strength_summary.json", summary)
    write_readme(output_dir, summary)
    print(f"[INFO] wrote evidence strength artifacts to {output_dir}")


if __name__ == "__main__":
    main()
