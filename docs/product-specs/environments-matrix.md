# Environments Matrix

## 一句话定位
该文档对比各实验环境的目标、依赖、入口脚本和产出，帮助 Agent 选择正确执行路径。

## 核心内容
| 环境 | 目标 | 主要入口 | 关键依赖 | 典型产出 |
|---|---|---|---|---|
| ToolBench | 工具调用行为评测 | `experiments/toolbench/scripts/run_pipeline.py` | 数据集缓存、API Key、本地或远程模型 | 轨迹、评测 JSON、日志 |
| ALFWorld | 具身文本任务行为评测 | `experiments/alfworld/scripts/run_experiment.py` | ALFWorld 环境、配置 JSON | 任务成功率、轨迹日志 |
| Oasis | 社交媒体行为模拟 | `experiments/oasis_watermark/*/run_experiment.py` | 独立 Python 环境、子依赖 | 社交行为轨迹和评分 |
| RLNC | 丢包/擦除鲁棒性评测 | `experiments/rlnc_trajectory/scripts/*.py` | RLNC 配置文件 | 恢复率/FPR 指标 |
| Semantic Rewriting | 语义改写攻击鲁棒性 | `experiments/semantic_rewriting/scripts/robustness_test.py` | 任务样本与解码比特 | 鲁棒性统计结果 |

## Agent 行为指引
- 你应该在运行前确认环境依赖和输入数据路径已经就绪。
- 你应该优先使用文档中声明的官方入口脚本，不随意替换为临时脚本。
- 你不应该在不同实验之间混用配置文件。
- 你不应该把子依赖目录中的 CI 状态当成主仓 CI 状态。

## 相关文件链接
- [../../README.md](../../README.md)
- [../../README_en.md](../../README_en.md)
- [../references/datasets-llms.txt](../references/datasets-llms.txt)
- [../operations/deployment.md](../operations/deployment.md)

## TODO
- TODO: 补充每个环境的输入输出 schema 示例。
- TODO: 增加“推荐调试顺序”章节。
