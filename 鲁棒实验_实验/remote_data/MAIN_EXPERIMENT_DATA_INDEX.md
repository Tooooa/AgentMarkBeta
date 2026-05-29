# AsymAgentMark-TK 全实验数据索引

生成时间：2026-05-30

本文件对照原始实验设计：

`/Users/local/AgentMarkBeta/论文写作经验/AsymAgentMark-TK 实验设计细节 c654630d517d83f89777016f636a6457.md`

整理当前已拉到本地的数据表、可用程度和缺口。所有表路径均相对于：

`/Users/local/AgentMarkBeta/鲁棒实验_实验/remote_data/extracted/output-0510`

鲁棒性 3.x 的详细索引见：

`/Users/local/AgentMarkBeta/鲁棒实验_实验/remote_data/ROBUSTNESS_DATA_INDEX.md`

补充包：

`/Users/local/AgentMarkBeta/鲁棒实验_实验/remote_data/agentmark_extra_evidence_vanilla_rg_20260530.tgz`

## 0. 当前数据总体状态

`asym_agentmark_tk/README.md` 记录：

- Scope: ALFWorld + ToolBench only; OASIS not included.
- ALFWorld task records: 8220
- ToolBench task records: 3600
- A3/A4 watermark decode-capable trajectories: 4728
- offline postprocess, no API usage

`asym_agentmark_tk/summary.json` 记录的汇总规模：

| dataset | method | records |
| --- | --- | ---: |
| ALFWorld | vanilla / clean / rg / agentmark / rank | 各 1644 |
| ToolBench | vanilla / clean / rg / agentmark / rank | 各 720 |

第一批本地压缩包只包含以下原始轨迹目录：

| dataset | local raw methods | 文件数 |
| --- | --- | ---: |
| ALFWorld | `clean`, `agentmark`, `rank` | 4932 |
| ToolBench | `clean`, `agentmark`, `rank` | 2160 |

随后已从远端补拉 Vanilla/RG 原始目录：

| dataset | added raw methods | 文件数 |
| --- | --- | ---: |
| ALFWorld | `vanilla`, `rg` | 3288 |
| ToolBench | `vanilla`, `rg` | 1440 |

因此当前本地已具备 A0/A1/A2/A3/A4 的 ALFWorld + ToolBench 原始数据和汇总表。OASIS 仍无数据。

## 1. 实验覆盖矩阵

| 设计实验 | 当前数据源 | 可用程度 | 备注 |
| --- | --- | --- | --- |
| 1.1 有效容量 L0-L6 | `asym_agentmark_tk/capacity_l0_l6_proxy.csv`; `asym_agentmark_tk/capacity_rlnc_exact_recovery.csv`; `rlnc_recovery_a3_a4/*` | 部分可用 | 有 proxy capacity 和 strict RLNC；不是完整跨模型 L5 重推断 |
| 1.2 Top-k 消融 | `asym_agentmark_tk/topk_ablation.csv` | 可用 | rank 方法，topk=2/4/6/8/10/20 |
| 2.1 效用保持 | `asym_agentmark_tk/utility_retention.csv` | 可用 | 包含 vanilla/clean/rg/agentmark/rank 汇总 |
| 2.2 行为分布 JSD | `asym_agentmark_tk/behavior_jsd.csv` | 可用 | 包含相对 clean/vanilla 的 JSD |
| 3.1 排名噪声 | `stage3_robustness_pooled_rerun/stage_c_3_1_*` | 可用 | 详见鲁棒性索引；repeat=1 |
| 3.2 擦除+信道降级 | `stage3_robustness_pooled_rerun/stage_c_3_2_*` | 可用但需复查 baseline | agentmark baseline 异常偏弱 |
| 3.3 语义改写 | `stage3_toolbench_5level_r3_subsample_w200/*` | 可用但仅 ToolBench | DeepSeek rewrite/rerank，failures=0 |
| 3.4 假阳性 | `stage3_robustness_pooled_rerun/stage_c_3_4_*` | 可用 | clean traces, 1000 random payload trials |
| 4.1 解码置信度曲线 | `evidence_strength/stage_d_4_1_confidence_*` | 可用 | exact one-sided binomial test |
| 4.2 最小证据阈值 | `evidence_strength/stage_d_4_2_thresholds_*` | 可用 | alpha={0.05,0.01,0.001}; L={8,16,32,64} |
| 4.3 鲁棒性补偿分析 | `evidence_strength/stage_d_4_3_compensation*` | 可用 | noise × erasure 下的 N_attack/N_clean |
| OASIS | 无 | 缺失 | 原设计中为可选补充 |

## 2. 实验 1.1：有效容量对比

主数据源：

| 文件 | 行数 | 字段 | 推荐用途 |
| --- | ---: | --- | --- |
| `asym_agentmark_tk/capacity_l0_l6_proxy.csv` | 896 | `dataset`, `method`, `model`, `split`, `channel`, `payload_len`, `payload_recovery_rate`, `c_nom_proxy_bits`, `c_eff_proxy_bits` | 主图候选：L0-L6 proxy capacity |
| `asym_agentmark_tk/capacity_rlnc_exact_recovery.csv` | 32 | `dataset`, `method`, `model`, `split`, `decode_success_rate_mean/std`, `dedup_packet_mean` | strict payload recovery 对照 |
| `rlnc_recovery_a3_a4/rlnc_recovery_mean_std.csv` | 32 | `dataset`, `method`, `model`, `split`, `recovery_rate_mean/std` | 与 exact recovery 类似，按 run 均值 |
| `rlnc_recovery_a3_a4/rlnc_recovery_by_task.csv` | 4728 | task-level packet/decode fields | Debug 或补充分析 |

重要 caveat：

- `capacity_l0_l6_proxy.csv` 是 offline channel proxy，不等价于完整重推断的真实 L1-L6 解码。
- `capacity_rlnc_exact_recovery.csv` 是 strict single-trajectory exact payload recovery，不能和 proxy `C_eff` 混为一个指标。
- 原设计里的 L5 “跨模型推断”在当前汇总里没有明确作为真实 cross-model rerank 解码表出现。

可直接引用的 strict RLNC 代表性结果：

| dataset | method | model | split | decode success | dedup packets |
| --- | --- | --- | --- | ---: | ---: |
| ALFWorld | agentmark | deepseek | ID | 0.667 | 19.56 |
| ALFWorld | agentmark | deepseek | OOD | 0.721 | 21.90 |
| ALFWorld | rank | deepseek | ID | 0.233 | 7.15 |
| ALFWorld | rank | deepseek | OOD | 0.241 | 7.72 |
| ALFWorld | agentmark | gemini-flash | ID | 0.829 | 37.53 |
| ALFWorld | rank | gemini-flash | ID | 0.507 | 15.70 |
| ToolBench | agentmark | deepseek | all splits | 0.000-0.200 | 1.18-3.93 |
| ToolBench | rank | deepseek | all splits | 0.000-0.050 | 1.17-2.27 |

建议论文写法：

> We report proxy channel capacity and strict exact payload recovery separately. The proxy table characterizes the information available under degraded channel knowledge, while strict RLNC recovery evaluates whether a single trajectory can recover the exact payload.

## 3. 实验 1.2：Top-k 消融

主数据源：

`asym_agentmark_tk/topk_ablation.csv`

规模与字段：

- rows: 96
- method: `rank`
- topk: 2, 4, 6, 8, 10, 20
- metrics: `payload_recovery_rate`, `c_nom_proxy_bits`, `c_eff_proxy_bits`, `bit_match_rate_mean/std`

代表性结果：

| dataset | model | split | topk=2 C_eff | topk=10 C_eff | topk=20 C_eff | 解释 |
| --- | --- | --- | ---: | ---: | ---: | --- |
| ALFWorld | deepseek | ID | 0.014 | 0.385 | 1.935 | k 增大明显提升 |
| ALFWorld | deepseek | OOD | 0.050 | 0.357 | 2.552 | k=20 提升明显 |
| ALFWorld | gemini-flash | ID | 0.048 | 1.975 | 6.746 | Gemini 下 packet 更多 |
| ToolBench | deepseek | G1_category | 0.000 | 0.058 | 0.078 | ToolBench 整体容量低 |
| ToolBench | deepseek | G2_category | 0.000 | 0.148 | 0.148 | 边际收益有限 |

建议论文结论：

> Larger Top-k generally improves effective proxy capacity, with the clearest gains on ALFWorld. ToolBench remains packet-limited, so increasing k alone cannot fully compensate for short or sparse trajectories.

## 4. 实验 2.1：效用保持

主数据源：

`asym_agentmark_tk/utility_retention.csv`

规模与字段：

- rows: 30
- methods: `vanilla`, `clean`, `rg`, `agentmark`, `rank`
- metrics: `mean_success_rate_pct`, `std_success_rate_pct`, `mean_steps`, `std_steps`

ALFWorld 代表性结果：

| method | model | ID SR | OOD SR | ID steps | OOD steps |
| --- | --- | ---: | ---: | ---: | ---: |
| clean | deepseek | 88.57 | 89.55 | 14.64 | 14.19 |
| agentmark | deepseek | 87.38 | 89.80 | 14.70 | 15.21 |
| rank | deepseek | 87.14 | 87.31 | 14.33 | 14.85 |
| clean | gemini-flash | 72.62 | 69.40 | 17.34 | 18.76 |
| agentmark | gemini-flash | 72.14 | 68.41 | 18.05 | 18.36 |
| rank | gemini-flash | 70.95 | 68.91 | 18.47 | 17.94 |

ToolBench all_6_splits 代表性结果：

| method | model | SR | steps |
| --- | --- | ---: | ---: |
| clean | deepseek | 77.36 | 5.87 |
| agentmark | deepseek | 74.54 | 4.51 |
| rank | deepseek | 77.41 | 5.61 |
| clean | gemini-flash | 73.94 | 4.76 |
| agentmark | gemini-flash | 74.86 | 4.57 |
| rank | gemini-flash | 76.71 | 4.52 |

建议论文结论：

> Rank watermarking preserves task utility close to the clean pipeline on both ALFWorld and ToolBench. Differences between clean, AgentMark-F, and rank are generally within the variation induced by model and split.

注意：

- Vanilla 在 ALFWorld deepseek 上和 clean 差异很大，说明 Vanilla/Clean pipeline 不是完全等价控制组；写作时优先用 clean 作为 pipeline-matched upper bound。

## 5. 实验 2.2：行为分布 JSD

主数据源：

`asym_agentmark_tk/behavior_jsd.csv`

规模与字段：

- rows: 128
- metrics: `jsd`, `actions`, `runs`
- baseline: `clean` 或 `vanilla`

代表性观察：

- ALFWorld deepseek: `rank` vs `clean` 的 JSD 约 0.066-0.079，`agentmark` vs `clean` 约 0.061-0.077。
- ALFWorld gemini-flash: `rank`/`agentmark` vs `clean` 的 JSD 较高，尤其 OOD 约 0.22-0.23。
- ToolBench: 不同 split 波动较大，`rank` vs `clean` 在部分 split 可低至约 0.057-0.13，也有 split 到 0.19 左右。

建议论文结论：

> Rank watermarking does not introduce a larger behavioral distribution shift than the AgentMark-F baseline under the same clean-pipeline reference. Distributional shift is more model- and split-dependent than method-dependent.

风险点：

- ALFWorld deepseek 的 clean-vs-vanilla JSD 很高，说明 pipeline 差异本身很大。不可把 vanilla 当成唯一“自然行为”基线。
- 当前表没有 χ²/KS p-value，仅有 JSD。

## 6. 原始轨迹与 manifest

manifest 数据源：

| 文件 | 行数 | 用途 |
| --- | ---: | --- |
| `manifests/alfworld_clean_records.csv` | 8220 | ALFWorld 全方法清单，含 success/steps/source/path |
| `manifests/toolbench_clean_records.csv` | 3600 | ToolBench 全方法清单，含 split/task_file/source path |
| `manifests/clean_build_summary.json` | 1 | 构建审计与来源概览 |

本地 raw 目录：

- `alfworld/clean`
- `alfworld/agentmark`
- `alfworld/rank`
- `toolbench/clean`
- `toolbench/agentmark`
- `toolbench/rank`

补充包已拉取以下 raw 目录：

- `alfworld/vanilla`
- `alfworld/rg`
- `toolbench/vanilla`
- `toolbench/rg`

当前可以对 2.1/2.2 重算行为序列、动作分布或 task-level 指标。

## 7. 实验 4.x：证据强度

主数据目录：

`evidence_strength`

`evidence_strength/README.md` 记录：

- Step observations: 55475
- Audit rows: 14184
- 4.1: exact one-sided binomial test, H0 match probability = 0.5
- 4.2: alpha in {0.05, 0.01, 0.001}, payload lengths {8, 16, 32, 64}
- 4.3: 基于 4.1 match 序列注入 erasure/noise 后重新求 `N_attack / N_clean`

主数据源：

| 文件 | 行数 | 字段 | 推荐用途 |
| --- | ---: | --- | --- |
| `evidence_strength/evidence_step_observations.csv` | 55475 | `dataset`, `method`, `config`, `step_match`, `bit_matches` | step-level Bernoulli observations |
| `evidence_strength/evidence_decode_audit.csv` | 14184 | `accepted_steps`, `no_bits_steps`, `len_mismatch_steps` | 审计可用 step |
| `evidence_strength/stage_d_4_1_confidence_summary.csv` | 864 | `N`, `match_rate_mean`, `log10_p_value_mean`, `p_value_geomean` | 4.1 主表 |
| `evidence_strength/stage_d_4_1_confidence_per_run.csv` | 2592 | per-run confidence | 误差线/复查 |
| `evidence_strength/stage_d_4_2_thresholds_summary.csv` | 1116 | `payload_len`, `alpha`, `N_min_mean`, `attained_runs` | 4.2 主表 |
| `evidence_strength/stage_d_4_2_thresholds_per_run.csv` | 3183 | per-run thresholds | 误差线/复查 |
| `evidence_strength/stage_d_4_3_compensation_summary.csv` | 3360 | `noise_rate`, `erasure_rate`, `N_clean_mean`, `N_attack_mean`, `compensation_ratio_mean` | 4.3 主表 |
| `evidence_strength/stage_d_4_3_compensation.csv` | 10080 | per-run compensation | 误差线/复查 |

可用配置：

- dataset: `alfworld`, `toolbench`
- method: `agentmark`, `rank`
- config: `L0_exact_probs`, `full_rank`, `top10`, `top5`, `top3`, `top2`
- N: 5, 10, 20, 30, 50, 80, 100, 150, 200
- alpha: 0.05, 0.01, 0.001
- payload_len: 8, 16, 32, 64
- compensation noise_rate: 0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5
- compensation erasure_rate: 0.0, 0.1, 0.2, 0.3, 0.5, 0.7

DeepSeek + ALFWorld ID 代表性 4.1 结果：

| method/config | N=5 p-value | N=10 p-value | N=20 p-value | N=100 p-value | 解释 |
| --- | ---: | ---: | ---: | ---: | --- |
| agentmark/L0 | 3.12e-2 | 9.77e-4 | 9.54e-7 | 7.89e-31 | oracle 证据最快 |
| rank/top10 | 2.60e-1 | 1.85e-2 | 4.32e-5 | 4.10e-26 | N=20 已显著 |
| rank/top5 | 2.60e-1 | 1.85e-2 | 4.32e-5 | 3.71e-26 | 与 top10 接近 |
| rank/top3 | 1.03e-1 | 4.83e-3 | 7.26e-6 | 1.19e-25 | 此 cell 中 top3 更快 |

DeepSeek + ALFWorld ID, alpha=0.01 的 4.2 最小步数：

| method/config | L=8 N_min | L=16 N_min | attained runs |
| --- | ---: | ---: | --- |
| agentmark/L0 | 10 | 20 | 3/3 |
| rank/top10 | 20 | 50 | 3/3 |
| rank/top5 | 20 | 50 | 3/3 |
| rank/top3 | 16.67 | 40 | 3/3 |

DeepSeek + ALFWorld ID, rank top10, alpha=0.01 的 4.3 补偿：

| noise | erasure | N_clean | N_attack | ratio | attained |
| ---: | ---: | ---: | ---: | ---: | --- |
| 0.0 | 0.0 | 20 | 20 | 1.00 | 3/3 |
| 0.1 | 0.0 | 20 | 23.33 | 1.17 | 3/3 |
| 0.3 | 0.0 | 20 | 43.33 | 2.17 | 3/3 |
| 0.3 | 0.3 | 20 | 70 | 3.50 | 3/3 |
| 0.3 | 0.7 | 20 | 100 | 5.00 | 3/3 |
| 0.5 | any selected | 20 | NA | NA | 0/3 |

推荐论文结论：

> Evidence significance improves rapidly with observed steps under a one-sided binomial test. Rank-based evidence reaches conventional significance with tens of steps on ALFWorld, while stronger perturbations increase the required evidence length; at severe noise, some runs no longer attain the target threshold within the evaluated range.

风险点：

- step-level evidence 把一个 accepted embedding step 作为一个 Bernoulli trial；如果论文中讲 payload-level evidence，需要解释这个统计口径。
- 4.3 是基于 match 序列的后处理注入，不是重新跑 LLM。

## 8. 给论文 agent 的使用建议

1. 写主实验时，先用 `utility_retention.csv` 和 `behavior_jsd.csv` 支撑 perception/undetectability。
2. 写 capacity 时，明确区分 `capacity_l0_l6_proxy.csv` 与 `capacity_rlnc_exact_recovery.csv`，不要混成同一个 decode success。
3. 写 Top-k 消融时，用 `topk_ablation.csv`，重点展示 ALFWorld 上 k 增大的收益和 ToolBench 的 packet-limited 现象。
4. 写 robustness 时，读取 `ROBUSTNESS_DATA_INDEX.md`，严格区分 strict 与 pooled。
5. 4.x 可以写实证结果，优先使用 `evidence_strength/stage_d_4_1_confidence_summary.csv`、`stage_d_4_2_thresholds_summary.csv` 和 `stage_d_4_3_compensation_summary.csv`。
6. 暂时不要写 OASIS 的实证结果，除非后续补跑。
