# Robustness and Evidence Data Notes

This directory documents the robustness/evidence artifacts used while revising
`paper.tex`. The canonical source tables currently live outside the anonymous
paper package under:

`/Users/local/AgentMarkBeta/鲁棒实验_实验/remote_data/extracted/output-0510`

The May 30 remote pull also mirrors the latest server reruns under:

`/Users/local/AgentMarkBeta/鲁棒实验_实验/remote_data/output-0510`

See `REMOTE_0510_PULL_ANALYSIS.md` for the current analysis of the pulled
Stage 3.1 repeats=10, Stage 3.3 semantic rewrite, and L5 cross-model rerank
artifacts.

## Main Source Tables

- `stage3_robustness_alfworld_3_1_r10/stage_c_3_1_rank_noise_pooled_summary.csv`
  and `stage3_robustness_toolbench360_3_1_r10/stage_c_3_1_rank_noise_pooled_summary.csv`
  - Ranking-noise pooled recovery with repeats=10.
- `stage3_robustness_3_2_fixed_r10/stage_c_3_2_erasure_channel_pooled_summary.csv`
  - Fixed erasure/channel-degradation run with repeats=10.
  - Use this instead of the older buggy 3.2 output.
- `stage3_semantic_rewrite_toolbench_lmh_r3_pooled_w300/stage_c_3_3_semantic_rewrite_summary.csv`
  - ToolBench-only semantic rewrite rank-stability summary from the r3 rerun.
- `stage3_semantic_rewrite_toolbench_lmh_r3_pooled_w300/stage_c_3_3_semantic_rewrite_pooled_summary.csv`
  - ToolBench-only pooled recovery under light/medium/heavy rewrite strengths.
- `stage3_semantic_rewrite_full_steps_lmh_r1_keep_packets/`
  - Full-step r1 keep-packets run for diagnostics; do not use it as a positive
    pooled recovery claim.
- `capacity_l5_cross_model_rerank/` and `capacity_l5_cross_model_rerank_toolbench_packets/`
  - Real cross-model Top-k rerank/decode artifacts.
- `capacity_l5_cross_model_rerank_toolbench_pool_curve/`
  - ToolBench L5 pooled audit-window curve.
- `stage3_robustness_pooled_rerun/stage_c_3_4_false_positive_summary.csv`
  - Clean-trace random-payload false-positive trials.
- `evidence_strength/stage_d_4_1_confidence_summary.csv`
  - One-sided binomial evidence curves.
- `evidence_strength/stage_d_4_2_thresholds_summary.csv`
  - Minimum evidence thresholds.

## Writing Rules

- Strict single-trajectory recovery and pooled evidence must not be mixed.
- Pooled recovery may be described as corpus-level or audit-window evidence,
  not per-task attribution.
- Stage 3.3 positive pooled recovery currently covers ToolBench only; ALFWorld
  rewrite recovery is not established by the pulled artifacts.
- Live L5 cross-model Top-k rerank/decode is now mirrored locally. Treat it as
  mixed evidence: ToolBench pooled recovery is strong, while ALFWorld remains a
  hard rank-reconstruction boundary.
- OASIS is not included.
