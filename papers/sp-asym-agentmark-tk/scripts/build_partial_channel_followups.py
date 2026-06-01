#!/usr/bin/env python3
"""Build follow-up diagnostics for partial-channel paper revision.

Artifacts:
- rank-only pooled recovery contrast for AgentMark-F vs AsymAgentMark-TK.
- unordered-set keyed-partition simulation showing a second invariant instance.
- local targeted rank-perturbation stress test for AsymAgentMark-TK.

The script is offline-only and reads the local 0510 mirror.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import hmac
import io
import json
import math
import random
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import torch


PAPER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PAPER_ROOT.parents[1]
DEFAULT_INPUT_ROOT = REPO_ROOT / "实验数据" / "remote_data" / "extracted" / "output-0510"
RESULT_DIR = PAPER_ROOT / "results" / "followup_partial_channel"
FIG_DIR = PAPER_ROOT / "figures"
DEFAULT_PAYLOAD = "11001101"
POOL_SIZES = (1, 2, 3, 5, 8, 10, 15, 20, 30, 50, 80, 100)
POOL_REPEATS = 200
TOPK = 10
ALFWORLD_SPLITS = {"ID", "OOD"}

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agentmark.core.rlnc_codec import DeterministicRLNC  # noqa: E402
from agentmark.core.watermark_sampler import (  # noqa: E402
    DRBG,
    Dist,
    BinEncStep,
    differential_based_decoder,
    rank_based_decoder,
)


def load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
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


def fmt(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def load_default_payload() -> str:
    path = REPO_ROOT / "agentmark" / "data" / "bit_stream.txt"
    if path.exists():
        bits = "".join(ch for ch in path.read_text(encoding="utf-8") if ch in {"0", "1"})
        if bits:
            return bits
    return DEFAULT_PAYLOAD


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


def topk_linear_rank_surrogate(probs: dict[str, float], topk: int) -> dict[str, float]:
    ranked = sorted(probs.items(), key=lambda kv: (-kv[1], kv[0]))[:topk]
    if not ranked:
        return {}
    weights = {action: float(len(ranked) - i) for i, (action, _) in enumerate(ranked)}
    total = sum(weights.values())
    return {k: v / total for k, v in weights.items()}


def probs_from_order(order: list[str]) -> dict[str, float]:
    if not order:
        return {}
    weights = {action: float(len(order) - i) for i, action in enumerate(order)}
    total = sum(weights.values())
    return {k: v / total for k, v in weights.items()}


def method_from_path(path: Path) -> str:
    parts = set(path.parts)
    if "agentmark" in parts:
        return "agentmark"
    if "rank" in parts:
        return "rank"
    return "unknown"


def model_from_path(path: Path) -> str:
    for part in path.parts:
        if part in {"deepseek", "gemini-flash"}:
            return part
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
        if part in ALFWORLD_SPLITS:
            return part
    return "unknown"


def task_from_path(path: Path) -> str:
    for part in path.parts:
        if part.startswith("task_"):
            return part.replace("task_", "")
    return path.parent.name


def resolve_alfworld_meta(report: dict[str, Any], default_payload: str) -> tuple[str, Any]:
    cfg = report.get("metadata", {}).get("config", {}) if isinstance(report.get("metadata"), dict) else {}
    watermark_cfg = cfg.get("watermark_config", {}) if isinstance(cfg.get("watermark_config"), dict) else {}
    experiment_cfg = cfg.get("experiment_config", {}) if isinstance(cfg.get("experiment_config"), dict) else {}
    payload_len = int(watermark_cfg.get("payload_bit_length") or len(default_payload) or 8)
    payload = (default_payload[:payload_len] or DEFAULT_PAYLOAD)[:payload_len]
    stream_key = watermark_cfg.get("rlnc_stream_key")
    if stream_key is None:
        stream_key = experiment_cfg.get("random_seed")
    if stream_key is None:
        stream_key = run_from_path(Path(str(report.get("source", "")))) or 2025
    return payload, stream_key


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


def round_num(entry: dict[str, Any]) -> int:
    if entry.get("round_num") is not None:
        return int(entry.get("round_num") or 0)
    return max(int(entry.get("step_num", 1) or 1) - 1, 0)


def get_trace(report: dict[str, Any]) -> list[dict[str, Any]]:
    items = report.get("watermarked_results") or []
    if items and isinstance(items[0], dict):
        item = items[0]
        trace = (item.get("watermark_stats") or {}).get("detection_trace") or item.get("watermark_trace") or []
        return [x for x in trace if isinstance(x, dict)]
    return []


def dedup_packets(packets: Iterable[tuple[int, int]]) -> tuple[list[tuple[int, int]], int]:
    by_index: dict[int, int] = {}
    conflicts: set[int] = set()
    for idx, val in packets:
        if idx in by_index and by_index[idx] != val:
            conflicts.add(idx)
        else:
            by_index.setdefault(idx, val)
    for idx in conflicts:
        by_index.pop(idx, None)
    return sorted(by_index.items()), len(conflicts)


def decode_step(entry: dict[str, Any], view: str, topk: int, attack_budget: int = 0) -> str:
    probs = normalize_probs(entry.get("probabilities") or entry.get("effective_probs") or entry.get("raw_probs") or {})
    chosen = str(entry.get("action") or entry.get("chosen") or "")
    context = entry.get("context_for_key")
    rnum = round_num(entry)
    if not probs or not chosen:
        return ""

    with contextlib.redirect_stdout(io.StringIO()):
        if view == "agentmark_exact":
            return differential_based_decoder(probs, chosen, context_for_key=context, round_num=rnum)
        if view == "agentmark_rank_only_linear_top10":
            surrogate = topk_linear_rank_surrogate(probs, topk)
            if chosen not in surrogate:
                return ""
            return differential_based_decoder(surrogate, chosen, context_for_key=context, round_num=rnum)
        if view == "rank_top10":
            return rank_based_decoder(probs, chosen, context_for_key=context, round_num=rnum, topk=topk)
        if view == "rank_top10_targeted_swap":
            return targeted_rank_swap_decode(entry, topk=topk, budget=attack_budget)
    raise ValueError(f"unknown view: {view}")


def targeted_rank_swap_decode(entry: dict[str, Any], *, topk: int, budget: int) -> str:
    probs = normalize_probs(entry.get("probabilities") or entry.get("effective_probs") or entry.get("raw_probs") or {})
    chosen = str(entry.get("action") or entry.get("chosen") or "")
    context = entry.get("context_for_key")
    rnum = round_num(entry)
    order = [a for a, _ in sorted(probs.items(), key=lambda kv: (-kv[1], kv[0]))[:topk]]
    if chosen not in order:
        return ""
    clean = rank_based_decoder(probs, chosen, context_for_key=context, round_num=rnum, topk=topk)
    if budget <= 0 or not clean:
        return clean

    start = order.index(chosen)
    candidates: list[tuple[int, str]] = []
    for target in range(max(0, start - budget), min(len(order), start + budget + 1)):
        if target == start:
            continue
        perturbed = list(order)
        item = perturbed.pop(start)
        perturbed.insert(target, item)
        decoded = rank_based_decoder(
            probs_from_order(perturbed),
            chosen,
            context_for_key=context,
            round_num=rnum,
            topk=topk,
        )
        distance = sum(1 for a, b in zip(clean, decoded) if a != b) + abs(len(clean) - len(decoded))
        candidates.append((distance, decoded))
    if not candidates:
        return clean
    candidates.sort(key=lambda x: (x[0], len(x[1])), reverse=True)
    return candidates[0][1]


def recover_trace(trace: list[dict[str, Any]], view: str, payload: str, stream_key: Any, *, topk: int, attack_budget: int = 0) -> dict[str, Any]:
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
            bits = decode_step(entry, view, topk, attack_budget=attack_budget)
        except Exception:
            bits = ""
            counters["decode_exception_steps"] += 1
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

    dedup, conflicts = dedup_packets(packets)
    codec = DeterministicRLNC(payload, stream_key=stream_key)
    recovered = codec.decode([idx for idx, _ in dedup], [val for _, val in dedup]) if dedup else None
    if recovered == payload:
        reason = ""
    elif len(dedup) < len(payload):
        reason = "insufficient_packets"
    elif recovered is None:
        reason = "rank_deficient"
    else:
        reason = "payload_mismatch"
    return {
        "packet_count": len(packets),
        "dedup_packet_count": len(dedup),
        "conflicts": conflicts,
        "accepted_steps": counters["accepted_steps"],
        "len_mismatch_steps": counters["len_mismatch_steps"],
        "decode_exception_steps": counters["decode_exception_steps"],
        "recovered_payload": recovered or "",
        "decode_ok": recovered == payload,
        "failure_reason": reason,
        "dedup_packets": dedup,
    }


def collect_alfworld_decodes(
    input_root: Path,
    default_payload: str,
    *,
    attack_budget: int = 0,
    models: set[str] | None = None,
    splits: set[str] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    view_specs = {
        "agentmark": ("AgentMark-F exact probabilities", "agentmark_exact"),
        "agentmark_rank_only": ("AgentMark-F rank-only linear top-10 surrogate", "agentmark_rank_only_linear_top10"),
        "rank": ("AsymAgentMark-TK top-10 rank", "rank_top10"),
    }
    attack_specs = {}
    if attack_budget > 0:
        attack_specs["rank_targeted_swap"] = (f"AsymAgentMark-TK targeted rank swap b={attack_budget}", "rank_top10_targeted_swap")

    for method, specs in (("agentmark", view_specs), ("rank", {**{"rank": view_specs["rank"]}, **attack_specs})):
        for path in sorted((input_root / "alfworld" / method).glob("**/evaluation_report.json")):
            model = model_from_path(path)
            split = split_from_path(path)
            if models is not None and model not in models:
                continue
            if splits is not None and split not in splits:
                continue
            report = load_json(path)
            if not isinstance(report, dict):
                continue
            trace = get_trace(report)
            if not trace:
                continue
            payload, stream_key = resolve_alfworld_meta(report, default_payload)
            base = {
                "dataset": "alfworld",
                "method": method,
                "model": model,
                "split": split,
                "run": run_from_path(path),
                "task_id": task_from_path(path),
                "payload": payload,
                "payload_len": len(payload),
                "stream_key": stream_key,
                "source": str(path),
            }
            for view, (label, decode_view) in specs.items():
                res = recover_trace(
                    trace,
                    decode_view,
                    payload,
                    stream_key,
                    topk=TOPK,
                    attack_budget=attack_budget,
                )
                row = {**base, "view": view, "view_label": label}
                for key, value in res.items():
                    if key != "dedup_packets":
                        row[key] = value
                row["dedup_packets"] = res["dedup_packets"]
                rows.append(row)
    return rows


def pool_decode(rows: list[dict[str, Any]], payload: str, stream_key: Any) -> dict[str, Any]:
    packets: list[tuple[int, int]] = []
    for row in rows:
        packets.extend(row["dedup_packets"])
    dedup, conflicts = dedup_packets(packets)
    codec = DeterministicRLNC(payload, stream_key=stream_key)
    recovered = codec.decode([idx for idx, _ in dedup], [val for _, val in dedup]) if dedup else None
    return {
        "pooled_decode_success": recovered == payload,
        "pooled_dedup_packets": len(dedup),
        "pooled_conflicts": conflicts,
        "pooled_recovered_payload": recovered or "",
    }


def build_pool_curve(decoded_rows: list[dict[str, Any]], *, sample_repeats: int = POOL_REPEATS) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sample_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    groups: dict[tuple[str, str, str, int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in decoded_rows:
        groups[(row["view"], row["model"], row["split"], int(row["run"]), str(row["stream_key"]))].append(row)

    for key, items in sorted(groups.items()):
        view, model, split, run, stream_key = key
        payload = str(items[0]["payload"])
        rng = random.Random(int(hashlib.sha256("|".join(map(str, key)).encode()).hexdigest()[:16], 16))
        for pool_size in POOL_SIZES:
            if pool_size > len(items):
                continue
            repeats = 1 if pool_size == len(items) else sample_repeats
            for rep in range(repeats):
                picked = list(items) if pool_size == len(items) else rng.sample(items, pool_size)
                res = pool_decode(picked, payload, stream_key)
                sample_rows.append(
                    {
                        "view": view,
                        "view_label": items[0]["view_label"],
                        "model": model,
                        "split": split,
                        "run": run,
                        "pool_size": pool_size,
                        "repeat": rep,
                        "available_trajectories": len(items),
                        **res,
                    }
                )

    summary_groups: dict[tuple[str, str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in sample_rows:
        summary_groups[(row["view"], row["model"], row["split"], int(row["pool_size"]))].append(row)
    for key, items in sorted(summary_groups.items()):
        view, model, split, pool_size = key
        success = [1.0 if r["pooled_decode_success"] else 0.0 for r in items]
        dedup = [float(r["pooled_dedup_packets"]) for r in items]
        conflicts = [float(r["pooled_conflicts"]) for r in items]
        summary_rows.append(
            {
                "view": view,
                "view_label": items[0]["view_label"],
                "model": model,
                "split": split,
                "pool_size": pool_size,
                "sample_repeats": len(items),
                "success_mean": fmt(statistics.mean(success)),
                "success_std": fmt(statistics.stdev(success) if len(success) > 1 else 0.0),
                "dedup_packet_mean": fmt(statistics.mean(dedup)),
                "conflicts_mean": fmt(statistics.mean(conflicts)),
            }
        )
    return sample_rows, summary_rows


def keyed_order(actions: list[str], context: str, key: bytes) -> list[str]:
    def digest(action: str) -> str:
        msg = f"{context}\0{action}".encode("utf-8")
        return hmac.new(key, msg, hashlib.sha256).hexdigest()

    return sorted(actions, key=lambda a: (digest(a), a))


def unordered_set_enc_step(message: str, probs_by_action: dict[str, float], context: str, key: bytes) -> tuple[str, int, list[str]]:
    order = keyed_order(list(probs_by_action), context, key)
    probs = torch.tensor([probs_by_action[a] for a in order], dtype=torch.float32)
    indices = torch.arange(len(order))
    dist = Dist(probs, indices)
    msg_idx = 0
    rt_sync = math.ceil(math.log2(len(dist)))
    prg = DRBG(key, b"set-partition" + context.encode("utf-8"))
    while len(dist) > 1:
        even_mass = dist.probs[::2].sum()
        odd_mass = dist.probs[1::2].sum()
        dist_bin = Dist(torch.tensor([even_mass, odd_mass], dtype=torch.float32))
        if msg_idx >= len(message):
            break
        rt = prg.generate_random(n=52)
        rt_sync -= 1
        group, n_bits = BinEncStep(message[msg_idx], dist_bin, rt)
        msg_idx += n_bits
        if group.item() == 0:
            dist = Dist(dist.probs[::2], dist.indices[::2])
        else:
            dist = Dist(dist.probs[1::2], dist.indices[1::2])
    for _ in range(rt_sync):
        prg.generate_random(n=52)
    selected = order[int(dist.indices[0].item())]
    return selected, msg_idx, order


def unordered_set_dec_step(selected: str, unordered_actions: list[str], context: str, key: bytes) -> str:
    order = keyed_order(unordered_actions, context, key)
    try:
        rank = order.index(selected)
    except ValueError:
        return ""
    rt_sync = math.ceil(math.log2(len(order)))
    prg = DRBG(key, b"set-partition" + context.encode("utf-8"))
    rts = [prg.generate_random(n=52) for _ in range(rt_sync)]
    decoded = ""
    level = 0
    while rank != 0:
        if rank % 2 == 1:
            decoded += "1" if rts[level] < 0.5 else "0"
        rank //= 2
        level += 1
    return decoded


def jsd(p: dict[str, float], q: dict[str, float]) -> float:
    keys = set(p) | set(q)
    m = {k: 0.5 * (p.get(k, 0.0) + q.get(k, 0.0)) for k in keys}

    def kl(a: dict[str, float], b: dict[str, float]) -> float:
        return sum(a.get(k, 0.0) * math.log2(a.get(k, 0.0) / b[k]) for k in keys if a.get(k, 0.0) > 0 and b[k] > 0)

    return 0.5 * kl(p, m) + 0.5 * kl(q, m)


def simulate_unordered_set_instance(trials: int = 20000) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rng = random.Random(20260601)
    key = b"unordered-set-demo-key"
    actions = [f"a{i}" for i in range(8)]
    # This is a deliberately minimal positive instance. With equal group masses,
    # the keyed unordered-set order can use the same binary embedding primitive
    # while the verifier reconstructs only from set membership and the key.
    base_probs = {action: 1.0 / len(actions) for action in actions}
    payload = "11001101" * 64
    rows: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    bit_cursor = 0
    bit_errors = 0
    len_mismatches = 0
    decoded_bits = 0
    shuffle_failures = 0
    for t in range(trials):
        context = f"ctx-{t}"
        selected, consumed, order = unordered_set_enc_step(payload[bit_cursor:], base_probs, context, key)
        shuffled = list(actions)
        rng.shuffle(shuffled)
        decoded = unordered_set_dec_step(selected, shuffled, context, key)
        expected = payload[bit_cursor : bit_cursor + consumed]
        if len(decoded) != consumed:
            len_mismatches += 1
        bit_errors += sum(1 for a, b in zip(decoded, expected) if a != b) + abs(len(decoded) - len(expected))
        decoded_bits += consumed
        if unordered_set_dec_step(selected, list(reversed(order)), context, key) != decoded:
            shuffle_failures += 1
        counts[selected] += 1
        bit_cursor += consumed
        if bit_cursor > len(payload) - 16:
            bit_cursor = 0
        rows.append(
            {
                "trial": t,
                "selected": selected,
                "consumed_bits": consumed,
                "decoded_bits": decoded,
                "expected_bits": expected,
                "decode_ok": decoded == expected,
                "keyed_order": " ".join(order),
            }
        )
    empirical = {a: counts[a] / trials for a in actions}
    summary = {
        "invariant": "unordered_set_keyed_partition",
        "trials": trials,
        "actions": len(actions),
        "decoded_bits": decoded_bits,
        "decode_success_rate": fmt(sum(1 for r in rows if r["decode_ok"]) / len(rows)),
        "bit_error_rate": fmt(bit_errors / max(1, decoded_bits)),
        "length_mismatches": len_mismatches,
        "shuffle_invariance_failures": shuffle_failures,
        "mean_bits_per_step": fmt(decoded_bits / trials),
        "selection_jsd_vs_source": fmt(jsd(base_probs, empirical)),
        "source_probs": base_probs,
        "empirical_probs": {k: fmt(v) for k, v in empirical.items()},
        "interpretation": "Minimal positive instance on a balanced pseudo distribution: the verifier reconstructs a keyed canonical order from the unordered top-k set; no probability rank is used.",
    }
    return rows, summary


def make_line_svg(rows: list[dict[str, Any]], out_path: Path, *, title: str, model: str = "deepseek", split: str = "ID") -> None:
    selected = [r for r in rows if r.get("model") == model and r.get("split") == split]
    if not selected:
        return
    width, height = 980, 560
    ml, mr, mt, mb = 82, 34, 62, 72
    plot_w, plot_h = width - ml - mr, height - mt - mb
    xvals = sorted({int(r["pool_size"]) for r in selected})
    xmax = max(xvals)

    colors = {
        "agentmark": "#555555",
        "agentmark_rank_only": "#D55E00",
        "rank": "#0072B2",
        "rank_targeted_swap": "#CC79A7",
    }
    labels = {
        "agentmark": "AgentMark-F exact",
        "agentmark_rank_only": "AgentMark-F rank-only",
        "rank": "AsymAgentMark-TK",
        "rank_targeted_swap": "AsymAgentMark-TK targeted swap",
    }

    def sx(x: float) -> float:
        return ml + (x / xmax) * plot_w

    def sy(y: float) -> float:
        return mt + (1.0 - y) * plot_h

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>text{font-family:Arial,Helvetica,sans-serif;fill:#222}.title{font-size:24px;font-weight:700}.axis{font-size:14px}.tick{font-size:12px;fill:#555}.legend{font-size:14px}.grid{stroke:#ddd;stroke-width:1}.line{fill:none;stroke-width:3}.dot{stroke:white;stroke-width:1.5}</style>",
        f'<text class="title" x="{width/2}" y="34" text-anchor="middle">{title}</text>',
        f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt + plot_h}" stroke="#222"/>',
        f'<line x1="{ml}" y1="{mt + plot_h}" x2="{ml + plot_w}" y2="{mt + plot_h}" stroke="#222"/>',
    ]
    for y in (0.0, 0.25, 0.5, 0.75, 1.0):
        yy = sy(y)
        parts.append(f'<line class="grid" x1="{ml}" y1="{yy:.1f}" x2="{ml + plot_w}" y2="{yy:.1f}"/>')
        parts.append(f'<text class="tick" x="{ml - 12}" y="{yy + 4:.1f}" text-anchor="end">{y:.2f}</text>')
    for x in (1, 10, 20, 50, 100):
        if x <= xmax:
            xx = sx(x)
            parts.append(f'<text class="tick" x="{xx:.1f}" y="{mt + plot_h + 24}" text-anchor="middle">{x}</text>')
    parts.append(f'<text class="axis" x="{width/2}" y="{height - 20}" text-anchor="middle">pooled trajectories per audit window</text>')
    parts.append(f'<text class="axis" x="22" y="{height/2}" transform="rotate(-90 22 {height/2})" text-anchor="middle">payload recovery rate</text>')

    by_view: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in selected:
        by_view[str(row["view"])].append(row)
    legend_y = mt + 8
    for i, view in enumerate(["agentmark", "agentmark_rank_only", "rank", "rank_targeted_swap"]):
        items = sorted(by_view.get(view, []), key=lambda r: int(r["pool_size"]))
        if not items:
            continue
        points = [(sx(int(r["pool_size"])), sy(float(r["success_mean"]))) for r in items]
        path = " ".join(("M" if j == 0 else "L") + f"{x:.1f},{y:.1f}" for j, (x, y) in enumerate(points))
        parts.append(f'<path class="line" d="{path}" stroke="{colors.get(view, "#333")}"/>')
        for x, y in points:
            parts.append(f'<circle class="dot" cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{colors.get(view, "#333")}"/>')
        ly = legend_y + i * 22
        parts.append(f'<line x1="{width - 285}" y1="{ly}" x2="{width - 248}" y2="{ly}" stroke="{colors.get(view, "#333")}" stroke-width="3"/>')
        parts.append(f'<text class="legend" x="{width - 240}" y="{ly + 5}">{labels.get(view, view)}</text>')
    parts.append(f'<text class="tick" x="{ml}" y="{height - 44}">Dataset: ALFWorld, model={model}, split={split}, top-k={TOPK}</text>')
    parts.append("</svg>")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def write_summary_md(path: Path, pool_summary: list[dict[str, Any]], unordered_summary: dict[str, Any], attack_summary: list[dict[str, Any]]) -> None:
    def pick(view: str, pool: int, model: str = "deepseek", split: str = "ID") -> str:
        for r in pool_summary:
            if r["view"] == view and int(r["pool_size"]) == pool and r["model"] == model and r["split"] == split:
                return f"{float(r['success_mean']):.3f}"
        return "n/a"

    lines = [
        "# Partial-Channel Follow-up Diagnostics",
        "",
        "## Rank-only pooled contrast",
        "",
        "ALFWorld/DeepSeek/ID top-10 pooled recovery:",
        "",
        "| Method/view | Pool 1 | Pool 10 | Pool 20 | Pool 50 | Pool 100 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
        f"| AgentMark-F exact probabilities | {pick('agentmark', 1)} | {pick('agentmark', 10)} | {pick('agentmark', 20)} | {pick('agentmark', 50)} | {pick('agentmark', 100)} |",
        f"| AgentMark-F rank-only linear top-10 surrogate | {pick('agentmark_rank_only', 1)} | {pick('agentmark_rank_only', 10)} | {pick('agentmark_rank_only', 20)} | {pick('agentmark_rank_only', 50)} | {pick('agentmark_rank_only', 100)} |",
        f"| AsymAgentMark-TK top-10 rank | {pick('rank', 1)} | {pick('rank', 10)} | {pick('rank', 20)} | {pick('rank', 50)} | {pick('rank', 100)} |",
        "",
        "The AgentMark-F rank-only row is a forced verifier surrogate: it keeps only the top-10 rank order and assigns monotone linear pseudo-probabilities before running the differential decoder. This is not a supported AgentMark-F verification channel; it is an intentionally favorable rank-only proxy to test whether pooling rescues the baseline.",
        "",
        "## Unordered-set keyed partition",
        "",
        f"- Trials: {unordered_summary['trials']}",
        f"- Decode success: {unordered_summary['decode_success_rate']}",
        f"- Bit error rate: {unordered_summary['bit_error_rate']}",
        f"- Mean bits per step: {unordered_summary['mean_bits_per_step']}",
        f"- Selection JSD vs source distribution: {unordered_summary['selection_jsd_vs_source']}",
        f"- Shuffle invariance failures: {unordered_summary['shuffle_invariance_failures']}",
        "",
        "This confirms a second partial-channel invariant on pseudo data: the verifier reconstructs a keyed canonical order from the unordered top-k set, not from probability rank.",
        "",
        "## Targeted rank perturbation",
        "",
        "The local targeted swap diagnostic is a verifier-channel stress test, not the main threat model. It perturbs the reconstructed rank order after execution and measures how much pooled recovery degrades.",
        "",
    ]
    if attack_summary:
        lines.extend(
            [
                "| View | Pool 10 | Pool 20 | Pool 50 |",
                "| --- | ---: | ---: | ---: |",
                f"| Clean top-10 rank | {pick('rank', 10)} | {pick('rank', 20)} | {pick('rank', 50)} |",
                f"| Targeted swap budget 1 | {pick('rank_targeted_swap', 10)} | {pick('rank_targeted_swap', 20)} | {pick('rank_targeted_swap', 50)} |",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=RESULT_DIR)
    parser.add_argument("--fig-dir", type=Path, default=FIG_DIR)
    parser.add_argument("--pool-repeats", type=int, default=50)
    parser.add_argument("--unordered-trials", type=int, default=20000)
    parser.add_argument("--attack-budget", type=int, default=1)
    parser.add_argument("--models", default="deepseek", help="Comma-separated ALFWorld models to process, or 'all'.")
    parser.add_argument("--splits", default="ID", help="Comma-separated ALFWorld splits to process, or 'all'.")
    args = parser.parse_args()

    payload = load_default_payload()
    models = None if args.models == "all" else {x.strip() for x in args.models.split(",") if x.strip()}
    splits = None if args.splits == "all" else {x.strip() for x in args.splits.split(",") if x.strip()}
    decoded_rows = collect_alfworld_decodes(
        args.input_root,
        payload,
        attack_budget=args.attack_budget,
        models=models,
        splits=splits,
    )
    decoded_light = [{k: v for k, v in row.items() if k != "dedup_packets"} for row in decoded_rows]
    write_csv(args.output_dir / "rank_only_pooled_by_task.csv", decoded_light)
    pool_samples, pool_summary = build_pool_curve(decoded_rows, sample_repeats=args.pool_repeats)
    write_csv(args.output_dir / "rank_only_pooled_curve_samples.csv", pool_samples)
    write_csv(args.output_dir / "rank_only_pooled_curve_summary.csv", pool_summary)

    unordered_rows, unordered_summary = simulate_unordered_set_instance(args.unordered_trials)
    write_csv(args.output_dir / "unordered_set_keyed_partition_trials.csv", unordered_rows[:1000])
    write_json(args.output_dir / "unordered_set_keyed_partition_summary.json", unordered_summary)

    attack_summary = [r for r in pool_summary if r["view"] in {"rank", "rank_targeted_swap"}]
    make_line_svg(
        [r for r in pool_summary if r["view"] in {"agentmark", "agentmark_rank_only", "rank"}],
        args.fig_dir / "fig_rank_only_pooled_contrast.svg",
        title="Rank-only pooled recovery contrast",
    )
    make_line_svg(
        attack_summary,
        args.fig_dir / "fig_targeted_rank_perturbation.svg",
        title="Targeted rank-perturbation stress test",
    )
    write_summary_md(args.output_dir / "README.md", pool_summary, unordered_summary, attack_summary)

    print(f"Wrote {len(decoded_rows)} per-task decode rows")
    print(f"Wrote {len(pool_summary)} pooled summary rows")
    print(f"Unordered-set decode success: {unordered_summary['decode_success_rate']}")
    print(f"Results: {args.output_dir}")


if __name__ == "__main__":
    main()
