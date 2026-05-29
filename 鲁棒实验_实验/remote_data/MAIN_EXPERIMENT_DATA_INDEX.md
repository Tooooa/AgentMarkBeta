# AsymAgentMark-TK 全实验数据索引

生成时间：2026-05-30

本文件对照原始实验设计：

`/Users/local/AgentMarkBeta/论文写作经验/AsymAgentMark-TK 实验设计细节 c654630d517d83f89777016f636a6457.md`

整理当前已拉到本地的数据表、可用程度和缺口。所有表路径均相对于：

`/Users/local/AgentMarkBeta/鲁棒实验_实验/remote_data/extracted/output-0510`

鲁棒性 3.x 的详细索引见：

`/Users/local/AgentMarkBeta/鲁棒实验_实验/remote_data/ROBUSTNESS_DATA_INDEX.md`

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

但本地本次压缩包只包含以下原始轨迹目录：

| dataset | local raw methods | 文件数 |
| --- | --- | ---: |
| ALFWorld | `clean`, `agentmark`, `rank` | 4932 |
| ToolBench | `clean`, `agentmark`, `rank` | 2160 |

因此：

- 论文表格：A0 Vanilla、A2 RG 的 2.1/2.2 汇总结果可用。
- 重新分析：若要重算 Vanilla/RG 的行为序列、动作分布或 task-level 指标，需要从远端补传 `vanilla` 和 `rg` 原始目录。
- OASIS：当前没有数据。

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
| 4.1 解码置信度曲线 | 暂无现成表 | 缺失 | 可从 A3/A4 raw 或 by-task packet 数据后处理生成 |
| 4.2 最小证据阈值 | 暂无现成表 | 缺失 | 依赖 4.1 |
| 4.3 鲁棒性补偿分析 | 暂无现成表 | 缺失 | 依赖 3.1/3.2 + 4.1 |
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

缺失的本地 raw 目录：

- `alfworld/vanilla`
- `alfworld/rg`
- `toolbench/vanilla`
- `toolbench/rg`

如果后续需要对 2.1/2.2 做重新统计、p-value 检验或更细粒度可视化，应从远端补传这些目录。

## 7. 实验 4.x：证据强度

当前没有现成的 4.1/4.2/4.3 结果表。

可生成的数据基础：

- A3/A4 raw trajectories: `agentmark`, `rank`
- task-level decode/packet 表: `rlnc_recovery_a3_a4/rlnc_recovery_by_task.csv`
- 鲁棒性 by-task 表: `stage3_robustness_pooled_rerun/stage_c_3_1_rank_noise_by_task.csv`, `stage_c_3_2_erasure_channel_by_task.csv`

建议后处理产物：

| 新表名建议 | 来源 | 内容 |
| --- | --- | --- |
| `evidence_pvalue_curve.csv` | A3/A4 raw 或 packet table | `N`, `k`, `method`, `matches`, `p_value`, `log10_p` |
| `evidence_min_steps.csv` | 4.1 结果 | `alpha`, `payload_len`, `k`, `N_min` |
| `evidence_attack_compensation.csv` | 3.1/3.2 + 4.1 | `epsilon`, `erasure_rate`, `N_attack`, `N_clean`, `compensation_ratio` |

结论：4.x 目前属于“可由现有 A3/A4 数据后处理生成，但尚未生成”的状态。

## 8. 给论文 agent 的使用建议

1. 写主实验时，先用 `utility_retention.csv` 和 `behavior_jsd.csv` 支撑 perception/undetectability。
2. 写 capacity 时，明确区分 `capacity_l0_l6_proxy.csv` 与 `capacity_rlnc_exact_recovery.csv`，不要混成同一个 decode success。
3. 写 Top-k 消融时，用 `topk_ablation.csv`，重点展示 ALFWorld 上 k 增大的收益和 ToolBench 的 packet-limited 现象。
4. 写 robustness 时，读取 `ROBUSTNESS_DATA_INDEX.md`，严格区分 strict 与 pooled。
5. 暂时不要写 OASIS 和 4.x 的实证结果，除非后续补跑/补生成。

