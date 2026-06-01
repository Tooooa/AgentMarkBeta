# output-0510 干净实验目录

本目录是按 AsymMark-R 实验设计整理后的最终干净数据入口。这里不再保留旧数据与补跑数据并列的混合结构；每个 task/split 只暴露一份最终被统一审计接受的合规记录。原先不合规或缺失的数据，已由 `output_supplement_0426_fix` 中的补跑合规结果替换。

## 当前阶段状态

截至 2026-05-10，实验设计中的 ALFWorld + ToolBench 主实验轨迹生成阶段已完成，并已通过完整性与合规性审计。本目录是后续效用统计、容量实验、Top-k 消融、跨模型解码、排名噪声鲁棒性和统计检验的 canonical 输入。

已完成：

- 轨迹生成：ALFWorld 与 ToolBench 均完整。
- 合规清洗：不合规旧记录已由 `output_supplement_0426_fix` 中的合规补跑记录替换。
- 效用汇总：`final/unified_summary.*` 与 `final/utility_summary_with_steps.*` 已生成。

尚不等同于全部论文实验完成：

- Capacity、Top-k 消融、跨模型解码、排名噪声鲁棒性、JSD/统计检验属于后续分析/解码阶段。

## 实验口径

- 方法：`vanilla`、`clean`、`rg`、`agentmark`、`rank`，分别对应 A0 Vanilla、A1 Clean、A2 Red-Green、A3 AgentMark-F、A4 AsymMark-R/Ours。
- 模型：`gemini-flash` = Gemini Flash 2.0，`deepseek` = DeepSeek v3.2；历史 `deepseek-chat` 结果按 v3.2 口径保留。
- ALFWorld：按实际可加载 canonical 范围，ID `0-139` 共 140 条，OOD `0-133` 共 134 条，每个 split 3 轮。
- ToolBench：6 个 split，每 split 20 条，每个方法/模型 3 轮。
- 参数：ALFWorld `temperature=1.0`、`max_steps=30`；ToolBench `temperature=0.7`、`max_steps=10`。

> 设计文档中有一处写作 `ID 134 + OOD 140`，但本次统一审计按实际环境可加载范围执行：ID=140、OOD=134。

## 目录结构

- `alfworld/<method>/<model>/run_<1-3>/<ID|OOD>/task_XXX/evaluation_report.json`：ALFWorld 最终合规报告入口。
- `toolbench/<method>/<model>/run_<1-3>/<split>/<task_id>.json`：ToolBench 最终合规轨迹入口。
- `toolbench/unified_eval_0426/`：ToolBench 统一评测摘要，不包含 API key 配置文件。
- `final/unified_summary.md`：最终统一结果表。
- `final/unified_summary.json`：最终统一结果表结构化版本。
- `final/utility_summary_with_steps.md`：按实验设计 2.1 整理的效用表，包含 SR/Solve Rate 与平均步数。
- `rlnc_recovery_a3_a4/`：A3/A4 的单轨迹 RLNC recovery 初步分析，不属于轨迹生成完整性判定依据。
- `audit/`：用于生成本目录的原始审计文件。
- `manifests/alfworld_clean_records.*`：ALFWorld 每条最终记录的来源、路径、success、steps。
- `manifests/toolbench_clean_records.*`：ToolBench 每条最终记录的来源和路径。
- `docs/`：实验设计文档副本。

## 完整性

- ALFWorld：`5 方法 x 2 模型 x 3 轮 x (140 ID + 134 OOD) = 8220` 条任务级记录。
- ToolBench：`5 方法 x 2 模型 x 3 轮 x 6 split x 20 = 3600` 条任务级轨迹。
- `audit/gap_manifest.json` 中 ALFWorld 与 ToolBench 缺口均为空。
- 2026-05-10 复核：所有 ALFWorld/ToolBench 链接目标存在，未发现 `Invalid game index`、`Traceback` 或明文 `sk-...` key。

## 快速查看

```bash
cd /root/autodl-tmp/output-0510
less final/unified_summary.md
less final/utility_summary_with_steps.md
python -m json.tool manifests/clean_build_summary.json
python -m json.tool final/unified_summary.json | less
```
