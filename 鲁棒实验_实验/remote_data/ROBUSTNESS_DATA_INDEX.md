# AgentMark 鲁棒性实验数据索引

生成时间：2026-05-30

本文件用于给后续写论文的 agent 提供数据入口、表格口径和可直接引用的实验结论草稿。所有路径均相对于：

`/Users/local/AgentMarkBeta/鲁棒实验_实验/remote_data/extracted/output-0510`

## 1. 数据包来源与完整性

本地压缩包：

`/Users/local/AgentMarkBeta/鲁棒实验_实验/remote_data/agentmark_robustness_data_20260530.tgz`

3.2 修复版补充包：

`/Users/local/AgentMarkBeta/鲁棒实验_实验/remote_data/stage3_robustness_3_2_fixed_r10_20260530.tgz`

解压目录：

`/Users/local/AgentMarkBeta/鲁棒实验_实验/remote_data/extracted`

远端来源：

`/root/autodl-tmp/output-0510`

随包保留的官方脚本与核心实现：

- `/Users/local/AgentMarkBeta/鲁棒实验_实验/remote_data/extracted/AgentMarkcg/AgentMarkBeta/experiments/asym_agentmark_tk/scripts/run_robustness_stage3.py`
- `/Users/local/AgentMarkBeta/鲁棒实验_实验/remote_data/extracted/AgentMarkcg/AgentMarkBeta/experiments/asym_agentmark_tk/scripts/run_semantic_rewrite_stage3_smoke.py`
- `/Users/local/AgentMarkBeta/鲁棒实验_实验/remote_data/extracted/AgentMarkcg/AgentMarkBeta/agentmark/core/rlnc_codec.py`
- `/Users/local/AgentMarkBeta/鲁棒实验_实验/remote_data/extracted/AgentMarkcg/AgentMarkBeta/agentmark/core/watermark_sampler.py`

已解压原始轨迹规模：

| 数据集 | 方法目录 | 文件数 | 说明 |
| --- | --- | ---: | --- |
| ALFWorld | `alfworld/{clean,agentmark,rank}` | 4932 | 3 methods × 2 models × 3 runs × 274 tasks |
| ToolBench | `toolbench/{clean,agentmark,rank}` | 2160 | 3 methods × 2 models × 3 runs × 120 tasks |

`stage3_robustness_pooled_rerun/README.md` 记录的 stage3 覆盖范围：

- Watermark records: 4728
- Clean records: 2364
- Repeats: 1
- FPR trials per trajectory/config: 1000

3.2 旧版结果存在 `agentmark` baseline 配置错误：`differential_based_decoder` 被错误地喂入 Top-k proxy/degraded probabilities，导致 AgentMark-F 几乎失败。旧 3.2 文件已在本地归档到：

`/Users/local/AgentMarkBeta/鲁棒实验_实验/remote_data/archive/20260530_3_2_buggy_local/stage3_robustness_pooled_rerun_3_2_files`

3.2 修复版已重跑：

- output dir: `stage3_robustness_3_2_fixed_r10`
- Repeats: 10
- script fix: `agentmark` 直接使用完整概率分布调用 `differential_based_decoder`; 只有 `rank` 使用 channel degradation / Top-k proxy.

重要限制：3.1 的扰动 repeat 仍只有 1。3.2 已补为 repeats=10。

## 2. 最重要的口径区分

后续写作必须区分两类成功率：

| 口径 | 对应文件 | 含义 | 写作建议 |
| --- | --- | --- | --- |
| Strict per-trajectory | `*_summary.csv`, `*_by_task.csv` | 单条 trajectory 独立恢复完整 payload | 作为困难设置或附录；数值普遍低 |
| Pooled evidence | `*_pooled.csv`, `*_pooled_summary.csv` | 同一条件下多条 trajectory 的 packets 合并后再 RLNC decode | 可作为主结果，但必须明确是 corpus-level / pooled detection |

核心写法建议：

> AgentMark-TK is robust under pooled-evidence detection, while exact single-trajectory payload recovery is limited by the small number of usable watermark packets per trajectory.

不要把 pooled success 写成普通 per-task success。

## 3. 3.1 Ranking Noise

主数据源：

| 文件 | 行数 | 粒度 | 推荐用途 |
| --- | ---: | --- | --- |
| `stage3_robustness_pooled_rerun/stage_c_3_1_rank_noise_pooled_summary.csv` | 672 | dataset/method/model/split/topk/noise/epsilon across 3 runs | 主表、主图 |
| `stage3_robustness_pooled_rerun/stage_c_3_1_rank_noise_pooled.csv` | 2016 | 每个 run 的 pooled decode | 画误差线或复查 run-level 异常 |
| `stage3_robustness_pooled_rerun/stage_c_3_1_rank_noise_summary.csv` | 672 | strict per-trajectory summary | 附录或 caveat |
| `stage3_robustness_pooled_rerun/stage_c_3_1_rank_noise_by_task.csv` | 99288 | 单 task × 扰动条件 | Debug 和做更细粒度分析 |

字段重点：

- `dataset`, `model`, `split`, `topk`, `noise_model`, `epsilon`
- `pooled_decode_success_rate_mean/std`
- `pooled_dedup_packet_mean/std`
- strict 表里的 `decode_success_rate`, `dedup_packet_mean`

可用实验条件：

- dataset: `alfworld`, `toolbench`
- method: `rank`
- model: `deepseek`, `gemini-flash`
- topk: 3, 5, 10
- noise_model: `adjacent_swap`, `kendall_tau`
- epsilon: 0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5

DeepSeek + topk=10 + adjacent_swap 代表性 pooled 结果：

| dataset | split | eps=0.0 | eps=0.1 | eps=0.3 | eps=0.5 | 解释 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| ALFWorld | ID | 1.000 | 1.000 | 1.000 | 1.000 | 强鲁棒 |
| ALFWorld | OOD | 1.000 | 1.000 | 1.000 | 0.667 | 高扰动下略降 |
| ToolBench | G1_category | 0.667 | 0.667 | 0.333 | 0.000 | 对噪声敏感 |
| ToolBench | G2_category | 0.333 | 0.333 | 0.333 | 0.000 | 对噪声敏感 |
| ToolBench | G3_instruction | 0.667 | 0.667 | 0.667 | 0.333 | 中等鲁棒 |

推荐论文结论：

> Rank-based watermarking tolerates moderate ranking noise on ALFWorld under pooled detection. ToolBench is harder: pooled recovery degrades under high perturbation, likely because fewer reliable packets survive per split.

注意：strict per-trajectory 成功率远低于 pooled，原因是单条轨迹的可用 packets 数量不足。

## 4. 3.2 Step Erasure / Channel Degradation

主数据源：

| 文件 | 行数 | 粒度 | 推荐用途 |
| --- | ---: | --- | --- |
| `stage3_robustness_3_2_fixed_r10/stage_c_3_2_erasure_channel_pooled_summary.csv` | 252 | dataset/method/model/pool_split/topk/erasure across 3 runs × 10 repeats | 主表、方法对比图 |
| `stage3_robustness_3_2_fixed_r10/stage_c_3_2_erasure_channel_pooled.csv` | 5880 | 每个 run/repeat 的 pooled decode | 画误差线或复查 run-level 异常 |
| `stage3_robustness_3_2_fixed_r10/stage_c_3_2_erasure_channel_summary.csv` | 672 | strict per-trajectory summary | 附录或 caveat |
| `stage3_robustness_3_2_fixed_r10/stage_c_3_2_erasure_channel_by_task.csv` | 992880 | 单 task × erasure × repeat 条件 | Debug 和细粒度分析 |

字段重点：

- `dataset`, `method`, `model`, `pool_split`, `topk`, `erasure_rate`
- `pooled_decode_success_rate_mean/std`
- `pooled_dedup_packet_mean/std`
- strict 表里的 `split`, `decode_success_rate`, `accepted_steps_mean`

可用实验条件：

- dataset: `alfworld`, `toolbench`
- method: `agentmark`, `rank`
- model: `deepseek`, `gemini-flash`
- topk: 3, 5, 10
- erasure_rate: 0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9

DeepSeek + topk=10 代表性 pooled 结果（修复版 r10）：

| dataset | method | pool_split | erasure=0.0 | erasure=0.5 | erasure=0.9 | 解释 |
| --- | --- | --- | ---: | ---: | ---: | --- |
| ALFWorld | agentmark | ID | 1.000 | 1.000 | 1.000 | 修复后 baseline 正常 |
| ALFWorld | agentmark | OOD | 1.000 | 1.000 | 1.000 | 修复后 baseline 正常 |
| ALFWorld | rank | ID | 1.000 | 1.000 | 1.000 | 极强 |
| ALFWorld | rank | OOD | 1.000 | 1.000 | 1.000 | 极强 |
| ToolBench | agentmark | ALL_SPLITS | 1.000 | 1.000 | 1.000 | 全 split 池化后可恢复 |
| ToolBench | rank | ALL_SPLITS | 1.000 | 1.000 | 1.000 | 全 split 池化后可恢复 |

DeepSeek + topk=10 strict per-trajectory erasure=0 参考：

| dataset | method | split | trajectories | strict decode success | dedup packets |
| --- | --- | --- | ---: | ---: | ---: |
| ALFWorld | agentmark | ID | 4200 | 0.667 | 19.56 |
| ALFWorld | agentmark | OOD | 4020 | 0.721 | 21.90 |
| ALFWorld | rank | ID | 4200 | 0.219 | 6.59 |
| ALFWorld | rank | OOD | 4020 | 0.234 | 7.15 |
| ToolBench | agentmark | G1_category | 600 | 0.033 | 1.18 |
| ToolBench | agentmark | G2_category | 600 | 0.200 | 3.93 |
| ToolBench | agentmark | G3_instruction | 600 | 0.183 | 3.10 |
| ToolBench | rank | G1_category | 600 | 0.050 | 1.17 |
| ToolBench | rank | G2_category | 600 | 0.033 | 2.10 |
| ToolBench | rank | G3_instruction | 600 | 0.033 | 1.58 |

推荐论文结论：

> After fixing the AgentMark-F decoder configuration, both AgentMark-F and AsymAgentMark-TK recover robustly under pooled erasure-channel detection. Strict single-trajectory recovery remains much lower, especially on ToolBench, because individual trajectories contain few usable packets.

风险点：

- 旧版 3.2 不可引用；它只作为 bug 诊断记录。
- ToolBench pooled summary 现在以 `ALL_SPLITS` 为主要池化口径；单 split 的 strict recovery 仍很低。
- 3.2 的 pooled 结论是 corpus-level/pool-level detection，不是单条 trajectory 的 payload 恢复率。

## 5. 3.3 Semantic Rewrite

优先使用 5-level 版本：

`stage3_toolbench_5level_r3_subsample_w200`

备用版本：

`stage3_semantic_rewrite_toolbench_lmh_r3_pooled_w300`

优先使用 5-level 的原因：

- 包含 `original`, `minimal`, `light`, `medium`, `heavy`
- 可以把 rewrite 后的效果和 original rerank baseline 对齐比较
- 包含 pooled subsample 表，能展示 pool size 增大后的恢复曲线

主数据源：

| 文件 | 行数 | 粒度 | 推荐用途 |
| --- | ---: | --- | --- |
| `stage3_toolbench_5level_r3_subsample_w200/stage_c_3_3_semantic_rewrite_summary.csv` | 90 | split/rewrite_strength/topk summary | 主表：语义改写对 rank stability 的影响 |
| `stage3_toolbench_5level_r3_subsample_w200/stage_c_3_3_semantic_rewrite_pooled_subsample_summary.csv` | 150 | rewrite_strength/topk/pool_size | 主图：pool size vs decode success |
| `stage3_toolbench_5level_r3_subsample_w200/stage_c_3_3_semantic_rewrite_steps.csv` | 5385 | step-level rerank details | 分析 rank_keep/top1/overlap |
| `stage3_toolbench_5level_r3_subsample_w200/stage_c_3_3_semantic_rewrite_by_task.csv` | 2745 | task-level decode | 附录或 debug |
| `stage3_toolbench_5level_r3_subsample_w200/stage_c_3_3_semantic_rewrite_pooled_summary.csv` | 15 | all-splits pooled | 只能作为上界或 sanity check |

字段重点：

- semantic stability: `mean_rouge_l`, `mean_token_jaccard`
- rank stability: `rank_keep_rate`, `top1_match_rate`, `topk_overlap_mean`
- decoding: `decode_success_rate`, `pooled_decode_success_rate_mean/std`
- sampling: `pool_size`, `sample_repeats`, `available_trajectories`

运行设置：

- dataset: `toolbench`
- method: `rank`
- model: `deepseek`
- rewrite_strength: `original`, `minimal`, `light`, `medium`, `heavy`
- topk: 3, 5, 10
- API model: `deepseek-v3.2`
- failures: 0
- selected records: 360
- max steps per task: 3

G1_category + topk=10 strict summary：

| rewrite | Rouge-L | token Jaccard | rank keep | top1 match | strict decode |
| --- | ---: | ---: | ---: | ---: | ---: |
| original | 1.000 | 1.000 | 0.700 | 0.800 | 0.176 |
| minimal | 0.514 | 0.506 | 0.367 | 0.633 | 0.059 |
| light | 0.787 | 0.678 | 0.367 | 0.567 | 0.059 |
| medium | 0.313 | 0.283 | 0.300 | 0.567 | 0.059 |
| heavy | 0.278 | 0.254 | 0.367 | 0.533 | 0.118 |

topk=10 pooled subsample：

| rewrite | pool=30 | pool=100 | 解释 |
| --- | ---: | ---: | --- |
| original | 1.000 | 1.000 | rerank baseline 上界 |
| minimal | 0.750 | 0.990 | 轻微改写后靠池化恢复 |
| light | 0.600 | 0.970 | 需要更大 pool |
| medium | 0.530 | 0.820 | 改写较强时下降明显 |
| heavy | 0.670 | 0.980 | 非单调，可能与样本池和重写分布有关 |

推荐论文结论：

> Semantic rewrites substantially reduce local rank preservation, but pooled evidence recovers the watermark when enough trajectories are available. The original rerank baseline is not perfectly stable either, so rewritten results should be compared against the original condition rather than against an assumed 100% step-level preservation.

风险点：

- 当前 3.3 是 ToolBench-only，不覆盖 ALFWorld。
- 每个 task 最多 3 steps，strict per-task decode success 偏低。
- `heavy` pooled subsample 出现非单调，建议写趋势时强调 pool-size robustness，而不是逐强度严格单调。

## 6. 3.4 False Positive Rate

主数据源：

| 文件 | 行数 | 粒度 | 推荐用途 |
| --- | ---: | --- | --- |
| `stage3_robustness_pooled_rerun/stage_c_3_4_false_positive_summary.csv` | 240 | dataset/model/split/topk/payload_len | 主表、主图 |
| `stage3_robustness_pooled_rerun/stage_c_3_4_false_positive_by_task.csv` | 35460 | clean trajectory × random payload trials | 附录或 debug |

字段重点：

- `payload_len`, `trials`, `false_positive_count`
- `fpr_micro`
- `fpr_macro_mean/std`
- `theoretical_fpr`

可用实验条件：

- dataset: `alfworld`, `toolbench`
- model: `deepseek`, `gemini-flash`
- topk: 3, 5, 10
- payload_len: 4, 6, 8, 10, 12
- trials: 1000 per trajectory/config

DeepSeek + topk=10 代表性结果：

| dataset | split | L=4 | L=8 | L=12 | theory L=4/L=8/L=12 | 解释 |
| --- | --- | ---: | ---: | ---: | --- | --- |
| ALFWorld | ID | 0.04329 | 0.00137 | 0.00008 | 0.0625 / 0.00391 / 0.00024 | 随 L 指数下降 |
| ALFWorld | OOD | 0.04245 | 0.00132 | 0.00008 | 0.0625 / 0.00391 / 0.00024 | 随 L 指数下降 |
| ToolBench | G1_category | 0.00205 | 0.00000 | 0.00000 | 0.0625 / 0.00391 / 0.00024 | 低 FPR，但 packet 不足 |
| ToolBench | G2_category | 0.00000 | 0.00000 | 0.00000 | 0.0625 / 0.00391 / 0.00024 | 低 FPR，但 packet 不足 |
| ToolBench | G3_instruction | 0.00000 | 0.00000 | 0.00000 | 0.0625 / 0.00391 / 0.00024 | 低 FPR，但 packet 不足 |

推荐论文结论：

> Empirical false-positive rates decay with payload length and stay below the ideal random-match bound in real clean traces. The gap is partly because many clean trajectories do not contain enough decodable packets.

注意：ToolBench 的极低 FPR 不能单独作为强安全证据，因为它和 packet scarcity 有关。

## 7. 其它可复用数据源

原始 manifest：

- `manifests/alfworld_clean_records.csv`
- `manifests/alfworld_clean_records.json`
- `manifests/toolbench_clean_records.csv`
- `manifests/toolbench_clean_records.json`
- `manifests/clean_build_summary.json`

与论文主实验相关但不属于鲁棒性 stage3 的表：

| 目录 | 文件 | 用途 |
| --- | --- | --- |
| `asym_agentmark_tk` | `topk_ablation.csv` | top-k 消融 |
| `asym_agentmark_tk` | `capacity_rlnc_exact_recovery.csv` | 原始 capacity / RLNC 恢复 |
| `asym_agentmark_tk` | `utility_retention.csv` | utility retention |
| `asym_agentmark_tk` | `behavior_jsd.csv` | 行为分布偏移 |
| `rlnc_recovery_a3_a4` | `rlnc_recovery_by_cell.csv` | A3/A4 RLNC 恢复对比 |
| `rlnc_recovery_a3_a4` | `rlnc_recovery_mean_std.csv` | 恢复率均值方差 |

这些表适合写主论文的非鲁棒性实验，或用于解释为什么鲁棒性实验选择 rank/A4 作为主方法。

## 8. 建议给论文 agent 的任务分工

建议论文 agent 按如下方式使用数据：

1. 先读取本索引，确认 strict 与 pooled 口径。
2. 3.1 主图使用 `stage_c_3_1_rank_noise_pooled_summary.csv`，x 轴为 `epsilon`，y 轴为 `pooled_decode_success_rate_mean`，分 facet 展示 dataset/split/topk。
3. 3.2 主图使用 `stage3_robustness_3_2_fixed_r10/stage_c_3_2_erasure_channel_pooled_summary.csv`，x 轴为 `erasure_rate`，y 轴为 `pooled_decode_success_rate_mean`，用 method 对比 `agentmark` 和 `rank`。
4. 3.3 主图一使用 `stage_c_3_3_semantic_rewrite_summary.csv` 展示 rank stability；主图二使用 `stage_c_3_3_semantic_rewrite_pooled_subsample_summary.csv` 展示 pool size 对恢复率的影响。
5. 3.4 主图使用 `stage_c_3_4_false_positive_summary.csv`，x 轴为 `payload_len`，y 轴为 `fpr_micro`，同时画 `theoretical_fpr` 虚线。
6. 附录使用 `*_by_task.csv` 和 strict `*_summary.csv` 报告单轨迹恢复限制。

## 9. 目前需要补跑或人工复查的点

优先级从高到低：

1. 3.1 仍可考虑补 repeat/seed，当前 `Repeats: 1`。
2. 若论文需要完整覆盖，3.3 补 ALFWorld semantic rewrite 或增加每个 task 的 steps。
3. 3.4 写作时解释 empirical FPR 低于 theory 的原因：真实 clean trace 中 decodable packets 不足。

## 10. 一句话总论

当前数据足以支撑这样的鲁棒性结论：

> AsymAgentMark-TK is robust in corpus-level pooled detection under ranking noise, erasure, and semantic rewrite perturbations; exact single-trajectory decoding is much harder and mainly limited by packet scarcity. False positives remain low and decrease rapidly with payload length.
