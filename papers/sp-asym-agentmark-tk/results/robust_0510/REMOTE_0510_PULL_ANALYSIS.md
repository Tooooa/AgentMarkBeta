# Remote 0510 Pull Analysis

This note records the May 30, 2026 pull from the remote experiment server and
summarizes the experiment artifacts that are relevant to the paper revision.

## Local Mirror

Remote root:

`/root/autodl-tmp/output-0510`

Local mirror root:

`/Users/local/AgentMarkBeta/鲁棒实验_实验/remote_data/output-0510`

Synced directories:

- `stage3_robustness_alfworld_3_1_r10`
- `stage3_robustness_toolbench360_3_1_r10`
- `stage3_robustness_3_2_fixed_r10`
- `stage3_semantic_rewrite_full_steps_lmh_r1_keep_packets`
- `stage3_semantic_rewrite_toolbench_lmh_r3_pooled_w300`
- `capacity_l5_cross_model_rerank`
- `capacity_l5_cross_model_rerank_toolbench_packets`
- `capacity_l5_cross_model_rerank_toolbench_pool_curve`

The local mirror is raw experiment data and is not part of the anonymous paper
bundle. The paper should cite compact source tables and the artifact paths
below, not the whole mirrored directory.

## Stage 3.1 Ranking Noise, Repeats 10

Source tables:

- `stage3_robustness_alfworld_3_1_r10/stage_c_3_1_rank_noise_pooled_summary.csv`
- `stage3_robustness_toolbench360_3_1_r10/stage_c_3_1_rank_noise_pooled_summary.csv`

Scope:

- ALFWorld watermark records: 3288
- ToolBench watermark records: 1440
- Repeats: 10
- Top-k: 3, 5, 10
- Noise rates: 0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5

Top-10 adjacent-swap pooled recovery:

| Dataset | Model | Pool | eps=0.0 | eps=0.1 | eps=0.3 | eps=0.5 |
|---|---|---:|---:|---:|---:|---:|
| ALFWorld | DeepSeek | ID | 1.000 | 1.000 | 1.000 | 1.000 |
| ALFWorld | DeepSeek | OOD | 1.000 | 1.000 | 1.000 | 0.833 |
| ALFWorld | Gemini Flash | ID | 1.000 | 1.000 | 1.000 | 0.867 |
| ALFWorld | Gemini Flash | OOD | 1.000 | 1.000 | 1.000 | 0.767 |
| ToolBench | DeepSeek | all splits | 1.000 | 1.000 | 1.000 | 1.000 |
| ToolBench | Gemini Flash | all splits | 1.000 | 1.000 | 0.900 | 1.000 |

Writing implication:

- Replace the old repeats=1 ranking-noise discussion with this repeats=10
  result.
- The safest claim is: top-10 pooled evidence is stable through moderate rank
  noise; high noise degrades ALFWorld OOD/Gemini and should be reported as a
  boundary rather than hidden.

## Stage 3.2 Fixed Erasure, Repeats 10

Source table:

- `stage3_robustness_3_2_fixed_r10/stage_c_3_2_erasure_channel_pooled_summary.csv`

This is the fixed 3.2 rerun that should remain the canonical source for erasure
claims. It was mirrored locally together with the new data so that the whole
Stage 3 robustness package can be analyzed from one local root.

## Stage 3.3 ToolBench Matched Top-k Rerun

The latest 3.3 rerun supersedes the older semantic-rewrite table for the main
paper claim.

Source directory:

`toolbench_rank_topk_matched`

Scope:

- Dataset: ToolBench
- Model: DeepSeek v3.2
- Splits: G1_instruction, G1_category, G1_tool, G2_category,
  G2_instruction, G3_instruction
- Top-k: 3, 5, 10
- Runs/seeds: 1, 2, 3
- Task limit: 20 per split
- Jobs completed/succeeded: 1080/1080
- Failures: 0

Strict single-trajectory recovery remains packet-limited:

| $k$ | Traj. | Strict recovery | Mean dedup packets | Mean accepted steps |
|---:|---:|---:|---:|---:|
| 3 | 360 | 0.000 | 0.631 | 0.631 |
| 5 | 360 | 0.008 | 1.061 | 0.878 |
| 10 | 360 | 0.028 | 1.625 | 1.189 |

All-split pooled recovery by individual run:

| $k$ | Run 1 | Run 2 | Run 3 | Per-run success | Dedup packets by run |
|---:|---:|---:|---:|---:|---|
| 3 | 1.000 | 0.000 | 0.000 | 1/3 | 17 / 6 / 6 |
| 5 | 1.000 | 0.000 | 1.000 | 2/3 | 12 / 7 / 12 |
| 10 | 1.000 | 1.000 | 1.000 | 3/3 | 13 / 14 / 15 |

Pooling all splits and all runs succeeds for every tested top-k with no packet
conflicts:

| $k$ | Traj. | Pooled recovery | Packets | Dedup packets | Conflicts | Stream keys |
|---:|---:|---:|---:|---:|---:|---:|
| 3 | 360 | 1.000 | 227 | 29 | 0 | 3 |
| 5 | 360 | 1.000 | 382 | 31 | 0 | 3 |
| 10 | 360 | 1.000 | 585 | 42 | 0 | 3 |

Sampled all-level audit-window curve:

| $k$ | Pool 10 | Pool 15 | Pool 20 | Pool 30 |
|---:|---:|---:|---:|---:|
| 3 | 0.590 | 0.905 | 0.985 | 1.000 |
| 5 | 0.860 | 0.965 | 0.990 | 1.000 |
| 10 | 0.950 | 0.995 | 1.000 | 1.000 |

Writing implication:

- Use this matched-top-k run for the main 3.3 ToolBench table.
- The honest interpretation is not "single ToolBench task attribution is now
  solved." It is: after matching the embedder and verifier top-k, ToolBench is
  still packet-limited at the task level, but pooled audit-window recovery is
  reliable, especially at k=10.
- The older `stage3_semantic_rewrite_*` directories are retained as diagnostic
  artifacts, but they should not drive the main 3.3 paper claim.

## L5 Real Cross-Model Top-k Rerank/Decode

Source directories:

- `capacity_l5_cross_model_rerank`
- `capacity_l5_cross_model_rerank_toolbench_packets`
- `capacity_l5_cross_model_rerank_toolbench_pool_curve`

This is real cross-model verifier rerank through model APIs, not an offline
proxy. The verifier model rescored each eligible candidate set before top-k
rank decoding.

Full L5 top-10 weighted diagnostics:

| Dataset | Embedder | Verifier | Traj. | Strict recovery | Top-1 match | Top-10 overlap | Kendall tau | Packets |
|---|---|---|---:|---:|---:|---:|---:|---:|
| ALFWorld | DeepSeek | Gemini Flash | 754 | 0.000 | 0.216 | 0.596 | 0.463 | 1.553 |
| ALFWorld | Gemini Flash | DeepSeek | 805 | 0.001 | 0.195 | 0.633 | 0.459 | 2.631 |
| ToolBench | DeepSeek | Gemini Flash | 183 | 0.044 | 0.836 | 0.640 | 0.869 | 3.082 |
| ToolBench | Gemini Flash | DeepSeek | 182 | 0.006 | 0.750 | 0.593 | 0.752 | 1.901 |

Full L5 top-10 pooled recovery:

| Dataset | Embedder | Verifier | Pool | Pooled recovery | Packets |
|---|---|---|---|---:|---:|
| ALFWorld | DeepSeek | Gemini Flash | ID | 0.000 | 0.0 |
| ALFWorld | DeepSeek | Gemini Flash | OOD | 0.000 | 0.0 |
| ALFWorld | Gemini Flash | DeepSeek | ID | 0.667 | 27.3 |
| ALFWorld | Gemini Flash | DeepSeek | OOD | 0.000 | 31.3 |
| ToolBench | DeepSeek | Gemini Flash | all splits | 1.000 | 44.0 |
| ToolBench | Gemini Flash | DeepSeek | all splits | 1.000 | 33.0 |

ToolBench L5 top-10 pool curve:

| Embedder | Verifier | Pool size 1 | 5 | 10 | 20 | 30 | 50 | 100 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| DeepSeek | Gemini Flash | 0.035 | 0.625 | 0.935 | 0.990 | 1.000 | 1.000 | 1.000 |
| Gemini Flash | DeepSeek | 0.005 | 0.255 | 0.705 | 0.945 | 0.990 | 1.000 | 1.000 |

Writing implication:

- L5 is now available and can replace the previous "pending" threat statement.
- The result should be framed as mixed but useful:
  - ToolBench is strong cross-model evidence when pooled over modest audit
    windows.
  - ALFWorld exposes a harder cross-model rank-reconstruction boundary.
- Strict single-trajectory recovery remains low, consistent with the packet
  scarcity argument.

## Recommended Paper Updates

1. Update the artifact mapping appendix to include the new local mirror and the
   exact L5/3.1/3.3 source directories.
2. Replace the Stage 3.1 table with repeats=10 values or state that the table is
   from repeats=10.
3. Add a short L5 paragraph/table:
   - ToolBench pooled cross-model top-10 reaches 1.0 in both directions.
   - ToolBench pool curve reaches 0.935/0.705 at pool size 10 and 0.990/0.945 at
     pool size 20.
   - ALFWorld strict and pooled recovery remain weak except Gemini-to-DeepSeek
     ID pooled recovery.
4. For 3.3, use the new `toolbench_rank_topk_matched` matched-top-k rerun for
   the positive ToolBench pooled recovery claim. Keep the semantic-rewrite
   directories as diagnostics only unless a separate rewrite claim is needed.
