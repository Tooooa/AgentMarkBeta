# AsymAgentMark-TK 后续实验执行计划

## 状态
- 状态：第 2 周后处理与 A3/A4 RLNC 恢复已完成
- 实验目录：`/root/autodl-tmp/AgentMarkcg/AgentMarkBeta`
- 外部设计文档：`/root/autodl-tmp/output-0510/docs/AsymAgentMark-TK 实验设计细节 3980516290a282a3b00c818c4f23654f.md`
- 轨迹根目录：`/root/autodl-tmp/output-0510`
- 输出根目录：`output/asym_agentmark_tk/`

## 当前结论
- 已接入 ALFWorld 的 `rank` 采样路由，使 A4 `AsymAgentMark-TK` 不再退回 differential。
- 已新增只读分析入口 `experiments/asym_agentmark_tk/scripts/analyze_available_trajectories.py`，用于扫描现有输出并生成覆盖率、效用保持和 JSD 口径的统一报告。
- 已新增 Stage A 运行入口 `experiments/asym_agentmark_tk/scripts/run_stage_a_matrix.py`，用于按方法、模型、数据集、轮次生成轨迹；API key 只从环境变量读取，不写入生成配置。
- 2026-05-10 已基于 `/root/autodl-tmp/output-0510` 完成第 2 周离线后处理：阶段 B、阶段 C 后处理部分、阶段 D 的 4.1。
- 全量纳入轨迹 `11820` 条；其中 A3/A4 可解码轨迹 `4728` 条。
- 后处理产物写入 `output/asym_agentmark_tk/week2_postprocess/`，包含每个子实验的 JSON/CSV 和 README。
- 2026-05-10 已对 `/root/autodl-tmp/output-0510` 的 A3 `agentmark` 与 A4 `rank` 补做真实 RLNC payload 恢复，产物写入 `/root/autodl-tmp/output-0510/rlnc_recovery_a3_a4/`，与 `capacity_proxy` 表分开。该表是单轨迹恢复口径：每条任务轨迹单独解码 packets，再调用 `DeterministicRLNC.decode()`，恢复 payload 等于 `11001101` 时记为成功。
- A3/A4 RLNC 恢复总览：`4728` 条任务轨迹，成功 `1901`；A3 `agentmark` 成功 `1314/2364`，A4 `rank` 成功 `587/2364`。

## 实验矩阵
方法：
- A0 `vanilla`
- A1 `clean`
- A2 `rg`
- A3 `agentmark_f`
- A4 `asym_tk`

模型：
- `deepseek`: `deepseek-chat`
- `gemini`: `gemini-2.0-flash`

数据集：
- ALFWorld: `id=140`, `ood=134`, `max_steps=30`, `temperature=1.0`
- ToolBench: 6 splits x 20 tasks, `max_steps=10`, `temperature=0.7`

## 执行命令
先做 dry-run 检查：

```bash
cd /root/autodl-tmp/AgentMarkcg/AgentMarkBeta
python experiments/asym_agentmark_tk/scripts/run_stage_a_matrix.py --smoke --dry-run
```

冒烟测试：

```bash
cd /root/autodl-tmp/AgentMarkcg/AgentMarkBeta
export DEEPSEEK_API_KEY=...
export GEMINI_API_KEY=...
python experiments/asym_agentmark_tk/scripts/run_stage_a_matrix.py --smoke --max-workers 4
```

正式 Stage A：

```bash
cd /root/autodl-tmp/AgentMarkcg/AgentMarkBeta
export DEEPSEEK_API_KEY=...
export GEMINI_API_KEY=...
python experiments/asym_agentmark_tk/scripts/run_stage_a_matrix.py --max-workers 50
```

统一扫描与后处理：

```bash
cd /root/autodl-tmp/AgentMarkcg/AgentMarkBeta
python experiments/asym_agentmark_tk/scripts/analyze_available_trajectories.py
```

第 2 周后处理：

```bash
cd /root/autodl-tmp/AgentMarkcg/AgentMarkBeta
python experiments/asym_agentmark_tk/scripts/run_week2_postprocess.py \
  --trajectory-root /root/autodl-tmp/output-0510
```

A3/A4 真实 RLNC 单轨迹恢复：

```bash
cd /root/autodl-tmp/AgentMarkcg/AgentMarkBeta
python experiments/asym_agentmark_tk/scripts/recover_output0510_rlnc_a3_a4.py \
  --input-root /root/autodl-tmp/output-0510 \
  --output-dir /root/autodl-tmp/output-0510/rlnc_recovery_a3_a4
```

## 交付物
- 2026-05-10 容量 + 感知最终交付目录：`/root/autodl-tmp/output-0510/asym_agentmark_tk/`
- 容量 1.1 L0-L6 proxy：`/root/autodl-tmp/output-0510/asym_agentmark_tk/capacity_l0_l6_proxy.csv`
- 容量 1.1 真实 RLNC payload 恢复：`/root/autodl-tmp/output-0510/asym_agentmark_tk/capacity_rlnc_exact_recovery.csv`
- 容量 1.2 Top-k 消融：`/root/autodl-tmp/output-0510/asym_agentmark_tk/topk_ablation.csv`
- 感知 2.1 效用保持：`/root/autodl-tmp/output-0510/asym_agentmark_tk/utility_retention.csv`
- 感知 2.2 行为分布 JSD：`/root/autodl-tmp/output-0510/asym_agentmark_tk/behavior_jsd.csv`
- 覆盖率和效用/JSD 总表：`output/asym_agentmark_tk/analysis/available_trajectory_summary.md`
- 机器可读汇总：`output/asym_agentmark_tk/analysis/available_trajectory_summary.json`
- 第 2 周后处理总览：`output/asym_agentmark_tk/week2_postprocess/README.md`
- 第 2 周机器可读索引：`output/asym_agentmark_tk/week2_postprocess/week2_postprocess_summary.json`
- 阶段 B 2.1 效用保持：`output/asym_agentmark_tk/week2_postprocess/stage_b_2_1_utility.csv`
- 阶段 B 2.2 行为分布 JSD：`output/asym_agentmark_tk/week2_postprocess/stage_b_2_2_jsd.csv`
- 阶段 B 1.1 容量 proxy：`output/asym_agentmark_tk/week2_postprocess/stage_b_1_1_capacity_proxy.csv`
- 阶段 B 1.2 Top-k 消融：`output/asym_agentmark_tk/week2_postprocess/stage_b_1_2_topk_ablation.csv`
- 阶段 C 3.1 排名噪声注入：`output/asym_agentmark_tk/week2_postprocess/stage_c_3_1_rank_noise.csv`
- 阶段 C 3.2 步骤擦除 + 信道降级：`output/asym_agentmark_tk/week2_postprocess/stage_c_3_2_erasure_channel.csv`
- 阶段 C 3.4 假阳性检验：`output/asym_agentmark_tk/week2_postprocess/stage_c_3_4_false_positive.csv`
- 阶段 D 4.1 置信度曲线：`output/asym_agentmark_tk/week2_postprocess/stage_d_4_1_confidence_curve.csv`
- A3/A4 真实 RLNC 恢复：`/root/autodl-tmp/output-0510/rlnc_recovery_a3_a4/rlnc_recovery_by_task.csv`
- A3/A4 RLNC 恢复 cell 汇总：`/root/autodl-tmp/output-0510/rlnc_recovery_a3_a4/rlnc_recovery_by_cell.csv`
- A3/A4 RLNC 恢复 mean/std：`/root/autodl-tmp/output-0510/rlnc_recovery_a3_a4/rlnc_recovery_mean_std.csv`
- 轨迹生成日志：`output/asym_agentmark_tk/stage_a/logs/`
- 每个任务的 ALFWorld/ToolBench 轨迹：`output/asym_agentmark_tk/stage_a/`

## 后处理映射
- 容量 + 感知最终总入口：

```bash
cd /root/autodl-tmp/AgentMarkcg/AgentMarkBeta
python experiments/asym_agentmark_tk/scripts/run_capacity_perception.py --overwrite
```

- 本轮最终交付只纳入 ALFWorld + ToolBench；OASIS 按外部设计文档的待定补充处理，不进入 `/root/autodl-tmp/output-0510/asym_agentmark_tk/`。
- 最终容量结果采用双口径分开汇报：`capacity_l0_l6_proxy.*` / `topk_ablation.*` 用 bit-level offline proxy 展示信道趋势，`capacity_rlnc_exact_recovery.*` 复用真实 A3/A4 RLNC 单轨迹恢复表展示 bit-exact payload recovery，不混用两类口径。
- 实验 2.1 效用保持：复用 `/root/autodl-tmp/output-0510/final/utility_summary_with_steps.json`，输出 JSON/CSV。
- 实验 2.2 行为分布 JSD：复用动作序列，分别计算相对 `clean` 和 `vanilla` 的 JSD。
- 实验 1.1 容量对比：对 A3/A4 的每步 `bits_embedded`、候选集合和信道等级做 bit-level offline proxy，输出 payload 长度 `8/16/32/64` 的恢复率。
- 实验 1.2 Top-k 消融：仅用 A4/rank 轨迹，输出 `k=2/4/6/8/10/20` 的恢复率与 bit match rate。
- 实验 3.1 排名噪声注入：仅用 A4/rank 轨迹，输出噪声率 `0/0.05/0.10/0.20/0.30` 的恢复率。
- 实验 3.2 步骤擦除 + 信道降级：用 A3/A4，输出擦除率 `0/0.10/0.20/0.30/0.50` 与 `L0/L3/L5` 信道组合。
- 实验 3.4 假阳性检验：Clean 轨迹按每配置 1000 个随机 payload 试验的解析期望输出，FPR = `2^-L`。
- 实验 4.1 置信度曲线：A3/A4 前 `N={5,10,20,30,50,80,100,150,200}` 个 bit match 做单侧二项检验，输出 p-value 与 log10 p-value。
- A3/A4 真实 RLNC 恢复：`recover_output0510_rlnc_a3_a4.py` 逐任务读取 trace，A3 用 `differential_based_decoder`，A4 用 `rank_based_decoder`；长度不一致的 step 记为 `len_mismatch_steps` 并不进入 packets；packet 冲突时删除冲突 index；每条任务单独调用 `DeterministicRLNC.decode()`，不做多轨迹联合恢复。

## 风险与注意
- `experiments/toolbench/configs/a1_rank_toolbench_gemini_r*.json` 是历史配置，包含硬编码 key；后续实验不要直接复用这些文件。
- `run_stage_a_matrix.py` 生成的临时配置只包含 `${DEEPSEEK_API_KEY}` / `${GEMINI_API_KEY}` 占位符，密钥由子进程环境展开。
- ToolBench A0/A1 在当前 runner 中均走无水印 baseline 轨迹；若论文需要严格区分“纯 ReAct vanilla”和“Clean 概率 pipeline”，需要进一步拆分 ToolBench vanilla runner。
- 当前 1.1/3.2 仍是 bit-level offline decoder proxy，用于信道/top-k/擦除趋势分析；真实 RLNC payload 恢复请使用 `/root/autodl-tmp/output-0510/rlnc_recovery_a3_a4/` 的单轨迹恢复表，不与 proxy 容量表混用。
