#!/usr/bin/env python3
"""Recover A3/A4 RLNC payloads from /root/autodl-tmp/output-0510.

The script is offline-only: it reads existing trajectories, decodes accepted
watermark packets, runs DeterministicRLNC recovery, and writes result tables
under the requested output directory.
"""

from __future__ import annotations

import argparse
import csv
import json
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
DEFAULT_OUTPUT_DIR = DEFAULT_INPUT_ROOT / "rlnc_recovery_a3_a4"
DEFAULT_PAYLOAD = "11001101"
DEFAULT_STREAM_KEY = 2025
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


def find_rlnc_meta_near(path: Path) -> Path | None:
    candidates = [path.parent / "rlnc_meta.json"]
    candidates.extend(parent / "rlnc_meta.json" for parent in path.parents)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def build_toolbench_manifest(input_root: Path) -> dict[tuple[str, str, int, str, str], dict[str, Any]]:
    manifest_path = input_root / "manifests/toolbench_clean_records.json"
    rows = load_json(manifest_path)
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


def resolve_toolbench_meta(path: Path, manifest: dict[tuple[str, str, int, str, str], dict[str, Any]], default_payload: str) -> tuple[str, Any, str, str]:
    method = method_from_path(path)
    model = model_from_path(path)
    run = run_from_path(path)
    split = split_from_path(path)
    key = (method, model, run, split, path.name)
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


def decode_entry(entry: dict[str, Any], method: str, dataset: str) -> str:
    probs = entry.get("probabilities") or entry.get("effective_probs") or {}
    chosen = entry.get("action") or entry.get("chosen")
    context = entry.get("context_for_key")
    if dataset == "toolbench":
        round_num = int(entry.get("task_idx", 0) or 0) + int(entry.get("round", 0) or 0)
    else:
        round_num = entry.get("round_num")
        if round_num is None:
            round_num = max(int(entry.get("step_num", 1) or 1) - 1, 0)
    if method == "rank":
        return rank_based_decoder(probs, chosen, context_for_key=context, round_num=int(round_num))
    return differential_based_decoder(probs, chosen, context_for_key=context, round_num=int(round_num))


def dedup_packets(packets: list[tuple[int, int]]) -> tuple[list[tuple[int, int]], int]:
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


def recover_from_trace(
    *,
    trace: list[dict[str, Any]],
    dataset: str,
    method: str,
    payload: str,
    stream_key: Any,
) -> dict[str, Any]:
    packets: list[tuple[int, int]] = []
    counters: Counter[str] = Counter()
    cursor = 0

    for entry in trace:
        if not isinstance(entry, dict):
            continue
        embed_len = expected_embed_len(entry)
        has_explicit_index = entry.get("bit_index_before") is not None and entry.get("bit_index_after") is not None
        if embed_len <= 0:
            counters["no_bits"] += 1
            continue
        try:
            bits = decode_entry(entry, method, dataset)
        except Exception:
            counters["decode_exception"] += 1
            if not has_explicit_index:
                cursor += embed_len
            continue
        if len(bits) != embed_len:
            counters["len_mismatch"] += 1
            if not has_explicit_index:
                cursor += embed_len
            continue
        if has_explicit_index:
            start = int(entry["bit_index_before"])
        else:
            start = cursor
        for off, bit in enumerate(bits):
            packets.append((start + off, int(bit)))
        counters["accepted_steps"] += 1
        if not has_explicit_index:
            cursor += embed_len

    dedup, conflict_count = dedup_packets(packets)
    encoder = DeterministicRLNC(payload, stream_key=stream_key)
    recovered = None
    if dedup:
        recovered = encoder.decode([idx for idx, _ in dedup], [bit for _, bit in dedup])
    decode_ok = recovered == payload
    if decode_ok:
        failure_reason = ""
    elif len(dedup) < len(payload):
        failure_reason = "insufficient_packets"
    elif recovered is None:
        failure_reason = "rank_deficient"
    else:
        failure_reason = "payload_mismatch"
    if not packets and counters["len_mismatch"]:
        failure_reason = "all_steps_len_mismatch"
    return {
        "packet_count": len(packets),
        "dedup_packet_count": len(dedup),
        "conflicts": conflict_count,
        "accepted_steps": counters["accepted_steps"],
        "no_bits_steps": counters["no_bits"],
        "len_mismatch_steps": counters["len_mismatch"],
        "decode_exception_steps": counters["decode_exception"],
        "recovered_payload": recovered or "",
        "decode_ok": decode_ok,
        "failure_reason": failure_reason,
    }


def recover_alfworld(input_root: Path, default_payload: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for method in ("agentmark", "rank"):
        for path in sorted((input_root / "alfworld" / method).glob("**/evaluation_report.json")):
            report = load_json(path)
            if not isinstance(report, dict):
                continue
            payload, stream_key, meta_source, meta_path = resolve_alfworld_meta(report, default_payload)
            item = None
            items = report.get("watermarked_results") or []
            if items and isinstance(items[0], dict):
                item = items[0]
            if item is None:
                continue
            trace = (item.get("watermark_stats") or {}).get("detection_trace") or item.get("watermark_trace") or []
            result = recover_from_trace(
                trace=trace,
                dataset="alfworld",
                method=method,
                payload=payload,
                stream_key=stream_key,
            )
            rows.append(
                {
                    "dataset": "alfworld",
                    "method": method,
                    "model": model_from_path(path),
                    "split": split_from_path(path),
                    "run": run_from_path(path),
                    "task_id": task_from_path(path, "alfworld"),
                    "source": str(path),
                    "payload": payload,
                    "payload_len": len(payload),
                    "stream_key": stream_key,
                    "meta_source": meta_source,
                    "meta_path": meta_path,
                    **result,
                }
            )
    return rows


def recover_toolbench(input_root: Path, default_payload: str) -> list[dict[str, Any]]:
    manifest = build_toolbench_manifest(input_root)
    rows: list[dict[str, Any]] = []
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
            result = recover_from_trace(
                trace=trace,
                dataset="toolbench",
                method=method,
                payload=payload,
                stream_key=stream_key,
            )
            rows.append(
                {
                    "dataset": "toolbench",
                    "method": method,
                    "model": model_from_path(path),
                    "split": split_from_path(path),
                    "run": run_from_path(path),
                    "task_id": task_from_path(path, "toolbench"),
                    "source": str(path),
                    "payload": payload,
                    "payload_len": len(payload),
                    "stream_key": stream_key,
                    "meta_source": meta_source,
                    "meta_path": meta_path,
                    **result,
                }
            )
    return rows


def aggregate_by_cell(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (row["dataset"], row["method"], row["model"], row["split"], row["run"])
        groups[key].append(row)
    out = []
    for (dataset, method, model, split, run), items in sorted(groups.items()):
        decode_values = [1 if row["decode_ok"] else 0 for row in items]
        packets = [int(row["dedup_packet_count"]) for row in items]
        conflicts = [int(row["conflicts"]) for row in items]
        meta_counts = Counter(str(row["meta_source"]) for row in items)
        failure_counts = Counter(str(row["failure_reason"] or "ok") for row in items)
        out.append(
            {
                "dataset": dataset,
                "method": method,
                "model": model,
                "split": split,
                "run": run,
                "tasks": len(items),
                "decode_ok_tasks": sum(decode_values),
                "recovery_rate": sum(decode_values) / len(items) if items else 0.0,
                "dedup_packet_mean": statistics.mean(packets) if packets else 0.0,
                "conflict_mean": statistics.mean(conflicts) if conflicts else 0.0,
                "meta_sources": json.dumps(dict(meta_counts), ensure_ascii=False, sort_keys=True),
                "failure_reasons": json.dumps(dict(failure_counts), ensure_ascii=False, sort_keys=True),
            }
        )
    return out


def aggregate_mean_std(cell_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in cell_rows:
        groups[(row["dataset"], row["method"], row["model"], row["split"])].append(row)
    out = []
    for (dataset, method, model, split), items in sorted(groups.items()):
        rates = [float(row["recovery_rate"]) for row in items]
        packets = [float(row["dedup_packet_mean"]) for row in items]
        out.append(
            {
                "dataset": dataset,
                "method": method,
                "model": model,
                "split": split,
                "runs": len(items),
                "recovery_rate_mean": statistics.mean(rates) if rates else 0.0,
                "recovery_rate_std": statistics.stdev(rates) if len(rates) > 1 else 0.0,
                "dedup_packet_mean": statistics.mean(packets) if packets else 0.0,
                "dedup_packet_std": statistics.stdev(packets) if len(packets) > 1 else 0.0,
            }
        )
    return out


def write_readme(output_dir: Path, input_root: Path, task_rows: list[dict[str, Any]], cell_rows: list[dict[str, Any]]) -> None:
    ok = sum(1 for row in task_rows if row["decode_ok"])
    by_method = Counter(row["method"] for row in task_rows)
    ok_by_method = Counter(row["method"] for row in task_rows if row["decode_ok"])
    meta_sources = Counter(str(row["meta_source"]) for row in task_rows)
    lines = [
        "# A3/A4 RLNC Recovery for output-0510",
        "",
        f"- Input root: `{input_root}`",
        f"- Output dir: `{output_dir}`",
        f"- Task rows: {len(task_rows)}",
        f"- Decoded OK: {ok}",
        f"- Methods: `{json.dumps(dict(by_method), ensure_ascii=False, sort_keys=True)}`",
        f"- OK by method: `{json.dumps(dict(ok_by_method), ensure_ascii=False, sort_keys=True)}`",
        f"- Meta sources: `{json.dumps(dict(meta_sources), ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Files",
        "",
        "- `rlnc_recovery_by_task.csv/json`: per-task packet and payload recovery.",
        "- `rlnc_recovery_by_cell.csv/json`: dataset x method x model x split x run recovery rates.",
        "- `rlnc_recovery_mean_std.csv/json`: mean/std across runs.",
        "",
        "## Notes",
        "",
        "- A3 `agentmark` uses `differential_based_decoder`; A4 `rank` uses `rank_based_decoder`.",
        "- ALFWorld reconstructs packet indices from task-local trace order when explicit bit indices are absent.",
        "- ToolBench uses explicit `bit_index_before/after`; when no metadata is found it tries payload `11001101` and stream key `2025` with `meta_source=fallback`.",
        "- Steps with decoded length mismatching the embedded length are excluded and counted as `len_mismatch_steps`.",
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
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
    task_rows = recover_alfworld(input_root, default_payload) + recover_toolbench(input_root, default_payload)
    cell_rows = aggregate_by_cell(task_rows)
    mean_std_rows = aggregate_mean_std(cell_rows)

    write_json(output_dir / "rlnc_recovery_by_task.json", task_rows)
    write_csv(output_dir / "rlnc_recovery_by_task.csv", task_rows)
    write_json(output_dir / "rlnc_recovery_by_cell.json", cell_rows)
    write_csv(output_dir / "rlnc_recovery_by_cell.csv", cell_rows)
    write_json(output_dir / "rlnc_recovery_mean_std.json", mean_std_rows)
    write_csv(output_dir / "rlnc_recovery_mean_std.csv", mean_std_rows)
    write_readme(output_dir, input_root, task_rows, cell_rows)

    print(f"[INFO] wrote {len(task_rows)} task rows to {output_dir}")


if __name__ == "__main__":
    main()
