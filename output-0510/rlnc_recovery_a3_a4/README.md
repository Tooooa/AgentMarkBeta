# A3/A4 RLNC Recovery for output-0510

- Input root: `/root/autodl-tmp/output-0510`
- Output dir: `/root/autodl-tmp/output-0510/rlnc_recovery_a3_a4`
- Task rows: 4728
- Decoded OK: 1901
- Methods: `{"agentmark": 2364, "rank": 2364}`
- OK by method: `{"agentmark": 1314, "rank": 587}`
- Meta sources: `{"report_metadata": 3288, "rlnc_meta": 1440}`
- Recovery unit: single trajectory. No packets are merged across tasks.

## Recovery Rates

| Dataset | Method | Tasks | OK | Rate |
|---|---|---:|---:|---:|
| ALFWorld | agentmark | 1644 | 1245 | 75.73% |
| ALFWorld | rank | 1644 | 573 | 34.85% |
| ToolBench | agentmark | 720 | 69 | 9.58% |
| ToolBench | rank | 720 | 14 | 1.94% |

## Files

- `rlnc_recovery_by_task.csv/json`: per-task packet and payload recovery.
- `rlnc_recovery_by_cell.csv/json`: dataset x method x model x split x run recovery rates.
- `rlnc_recovery_mean_std.csv/json`: mean/std across runs.

## Notes

- A3 `agentmark` uses `differential_based_decoder`; A4 `rank` uses `rank_based_decoder`.
- ALFWorld reconstructs packet indices from task-local trace order when explicit bit indices are absent.
- ToolBench uses explicit `bit_index_before/after`; when no metadata is found it tries payload `11001101` and stream key `2025` with `meta_source=fallback`.
- Steps with decoded length mismatching the embedded length are excluded and counted as `len_mismatch_steps`.
- `decode_ok=True` means `DeterministicRLNC.decode(received_indices, received_bits)` recovered exactly the expected payload `11001101`.
