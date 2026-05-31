# Robustness and Evidence Data Notes

This directory documents the robustness/evidence artifacts used while revising
`paper.tex`. The canonical source tables currently live outside the anonymous
paper package under:

`/Users/local/AgentMarkBeta/鲁棒实验_实验/remote_data/extracted/output-0510`

The May 30 remote pull also mirrors the latest server reruns under:

`/Users/local/AgentMarkBeta/鲁棒实验_实验/remote_data/output-0510`

See `REMOTE_0510_PULL_ANALYSIS.md` for the original remote-pull analysis and
the compact CSVs in this directory for the paper-ready top-k calibration data.

## Main Source Tables

- `stage3_robustness_alfworld_3_1_r10/stage_c_3_1_rank_noise_pooled_summary.csv`
  and `stage3_robustness_toolbench360_3_1_r10/stage_c_3_1_rank_noise_pooled_summary.csv`
  - Ranking-noise pooled recovery with repeats=10.
- `stage3_robustness_3_2_fixed_r10/stage_c_3_2_erasure_channel_pooled_summary.csv`
  - Fixed erasure/channel-degradation run with repeats=10.
  - Use this instead of the older buggy 3.2 output.
- `toolbench_rank_topk_matched/postprocess/summary_global.csv`
  - ToolBench matched-top-k strict single-trajectory recovery summary.
- `toolbench_rank_topk_matched/postprocess/pooled_by_run.csv`
  - ToolBench matched-top-k all-split pooled recovery by seed.
- `toolbench_rank_topk_matched/pool_curve/pool_curve_summary.csv`
  - ToolBench matched-top-k sampled audit-window curve.
- `toolbench_rank_topk_matched_top2_top4_deepseek/` and
  `toolbench_rank_topk_matched_top2_top4_gemini/`
  - Additional same-model ToolBench top2/top4 calibration runs.
- `stage3_semantic_rewrite_toolbench_lmh_r3_pooled_w300/`
  - Older ToolBench semantic-rewrite rerun retained for diagnostics, but no
    longer used for the main 3.3 paper table.
- `l5_toolbench_rank_topk_matched_clean_w100/`
  - Real cross-model top3/top5/top10 matched rerank/decode artifacts.
- `l5_toolbench_rank_top2_top4_matched_clean_w100/`
  - Real cross-model top2/top4 matched rerank/decode artifacts.
- `toolbench_same_model_rank_depth.csv`
  - Paper-ready same-model top2/top3/top4/top5/top10 calibration summary.
- `l5_rank_depth_calibration.csv` and `l5_rank_depth_pool_curve.csv`
  - Paper-ready L5 rank-depth calibration table and sampled pool curve.
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
- Stage 3.3 positive pooled recovery currently covers ToolBench matched-top-k
  only; ALFWorld matched-top-k or rewrite recovery is not established by the
  pulled artifacts.
- Live L5 cross-model Top-k rerank/decode is now mirrored locally. Treat it as
  calibrated evidence: ToolBench has direction-specific positive operating
  points, while top2 is packet-limited and top4/top10 expose conflict
  accumulation.
- OASIS is not included.
