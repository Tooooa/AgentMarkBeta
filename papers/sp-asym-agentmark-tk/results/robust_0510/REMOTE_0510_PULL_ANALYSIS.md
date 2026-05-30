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

## Stage 3.3 Semantic Rewrite Reruns

There are two useful but different 3.3 rerun directories.

### Full-Steps R1 Keep-Packets

Source directory:

`stage3_semantic_rewrite_full_steps_lmh_r1_keep_packets`

Scope:

- Dataset: all
- Records selected: 480
- Step rows: 10350
- Task rows: 2601
- Failures: 0
- Strengths: light, medium, heavy
- Top-k: 3, 5, 10
- Rerank repeats: 1
- Keep packets: true

Weighted top-10 strict/rank diagnostics:

| Dataset | Strength | Traj. | Strict recovery | Top-1 match | Top-10 overlap | Kendall tau | Packets |
|---|---|---:|---:|---:|---:|---:|---:|
| ALFWorld | light | 106 | 0.000 | 0.158 | 0.638 | 0.248 | 1.877 |
| ALFWorld | medium | 106 | 0.000 | 0.165 | 0.640 | 0.253 | 2.057 |
| ALFWorld | heavy | 106 | 0.000 | 0.163 | 0.637 | 0.247 | 1.868 |
| ToolBench | light | 183 | 0.000 | 0.360 | 0.637 | 0.216 | 1.454 |
| ToolBench | medium | 183 | 0.000 | 0.389 | 0.637 | 0.215 | 1.454 |
| ToolBench | heavy | 183 | 0.000 | 0.399 | 0.637 | 0.245 | 1.596 |

Pooled top-10 recovery in this run is 0.0 for ALFWorld and ToolBench. This run
is useful for rank-stability diagnostics and packet inspection, but it is weak
evidence for recovery because the pooled payload recovery does not succeed.

### ToolBench LMH R3 Pooled W300

Source directory:

`stage3_semantic_rewrite_toolbench_lmh_r3_pooled_w300`

Scope:

- Dataset: ToolBench
- Records selected: 360
- Step rows: 3231
- Task rows: 1647
- Failures: 0
- Strengths: light, medium, heavy
- Top-k: 3, 5, 10
- Rerank repeats: 3

Weighted top-10 strict/rank diagnostics:

| Dataset | Strength | Traj. | Strict recovery | Top-1 match | Top-10 overlap | Kendall tau | Packets |
|---|---|---:|---:|---:|---:|---:|---:|
| ToolBench | light | 183 | 0.011 | 0.395 | 0.595 | 0.189 | 2.016 |
| ToolBench | medium | 183 | 0.011 | 0.382 | 0.595 | 0.203 | 2.038 |
| ToolBench | heavy | 183 | 0.011 | 0.414 | 0.596 | 0.221 | 1.962 |

Top-10 pooled recovery:

| Dataset | Strength | Pool | Runs | Pooled recovery | Packets | Conflicts |
|---|---|---|---:|---:|---:|---:|
| ToolBench | light | all splits | 1 | 1.000 | 45.0 | 14.0 |
| ToolBench | medium | all splits | 1 | 1.000 | 45.0 | 13.0 |
| ToolBench | heavy | all splits | 1 | 1.000 | 45.0 | 14.0 |

Writing implication:

- Use the ToolBench LMH R3 pooled W300 run for the positive 3.3 semantic-rewrite
  recovery claim.
- Use the full-steps R1 keep-packets run as a caveat/rank-stability diagnostic,
  especially if discussing ALFWorld. Do not claim ALFWorld semantic-rewrite
  recovery from the current 3.3 artifacts.

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
4. For 3.3 semantic rewrite, use the ToolBench LMH R3 pooled W300 run for the
   positive pooled recovery claim and explicitly state that ALFWorld rewrite
   recovery is not established by the current artifacts.

