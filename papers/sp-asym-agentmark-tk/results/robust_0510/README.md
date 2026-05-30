# Robustness and Evidence Data Notes

This directory documents the robustness/evidence artifacts used while revising
`paper.tex`. The canonical source tables currently live outside the anonymous
paper package under:

`/Users/local/AgentMarkBeta/鲁棒实验_实验/remote_data/extracted/output-0510`

## Main Source Tables

- `stage3_robustness_pooled_rerun/stage_c_3_1_rank_noise_pooled_summary.csv`
  - Ranking-noise pooled recovery.
  - Caveat: the local index records repeats=1 for this run.
- `stage3_robustness_3_2_fixed_r10/stage_c_3_2_erasure_channel_pooled_summary.csv`
  - Fixed erasure/channel-degradation run with repeats=10.
  - Use this instead of the older buggy 3.2 output.
- `stage3_toolbench_5level_r3_subsample_w200/stage_c_3_3_semantic_rewrite_summary.csv`
  - ToolBench-only semantic rewrite rank-stability summary.
- `stage3_toolbench_5level_r3_subsample_w200/stage_c_3_3_semantic_rewrite_pooled_subsample_summary.csv`
  - ToolBench-only pooled subsample recovery under rewrite strengths.
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
- Stage 3.3 currently covers ToolBench only.
- Live L5 cross-model Top-k rerank/decode is not included in the local paper
  package yet; keep it as deployment calibration or pending evidence until its
  artifacts are available.
- OASIS is not included.

