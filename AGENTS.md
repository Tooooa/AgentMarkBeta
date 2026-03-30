# AGENTS.md

## 项目身份
AgentMark 是一个用于 LLM Agent 行为水印、验证与可视化评测的研究与工程仓库，覆盖核心算法、实验流水线和 Dashboard。

## 知识库索引
- [ARCHITECTURE.md](./ARCHITECTURE.md): 全局模块地图、关键路径与分层规则。
- [docs/index.md](./docs/index.md): 文档总入口与目录导航。
- [docs/design-docs/dependency-rules.md](./docs/design-docs/dependency-rules.md): 可机检依赖规则与禁令。
- [docs/operations/observability.md](./docs/operations/observability.md): 日志规范、监控指标与自验证流程。
- [docs/quality/QUALITY_SCORE.md](./docs/quality/QUALITY_SCORE.md): 质量评分维度与最低阈值。
- [docs/tech-debt/tech-debt-tracker.md](./docs/tech-debt/tech-debt-tracker.md): 技术债追踪与修复优先级。
- [docs/ci/ci-cd-policy.md](./docs/ci/ci-cd-policy.md): CI 门禁、PR 合并条件与失败处理。
- [docs/references/external-dependencies-llms.txt](./docs/references/external-dependencies-llms.txt): 外部依赖和环境来源。
- [scripts/guards/check_architecture.py](./scripts/guards/check_architecture.py): 架构依赖守卫脚本。
- [scripts/guards/check_docs_health.py](./scripts/guards/check_docs_health.py): 文档健康检查脚本。
- [scripts/guards/check_guard_effectiveness.py](./scripts/guards/check_guard_effectiveness.py): 故意违规回归测试脚本。

## 架构速览
- 业务主链路分为 `agentmark/` 核心库、`dashboard/server/` API 服务、`dashboard/src/` 前端展示与 `experiments/` 实验层。
- 依赖方向遵循单向约束：核心算法不依赖实验目录，前端不直接依赖 Python 模块。
- 详细规则见 [ARCHITECTURE.md](./ARCHITECTURE.md) 和 [docs/design-docs/dependency-rules.md](./docs/design-docs/dependency-rules.md)。

## Agent 行为约束
- 不得直接修改 `docs/generated/` 下的文件；若后续新增该目录，文件必须包含自动生成声明。
- 所有新建文档必须在所属目录 `index.md` 注册，否则视为不完整交付。
- 提交前必须通过文档健康检查与架构守卫检查。
- 不确定改动边界时，先阅读 `docs/` 对应文档，再查看源码实现。
- 严禁让 `agentmark/core/` 依赖 `experiments/` 或 `dashboard/`。
- 严禁让 `dashboard/src/` 直接导入 Python 代码或服务端模块。
- 子依赖隔离区默认不参与主规则失败判定：`experiments/oasis_watermark/oasis/`、`experiments/toolbench/MarkLLM/`、`dashboard/.git_backup/`。
- PR 工作流：自审 -> 对比变更 -> 运行守卫脚本 -> 满足合并条件。
- 合并前最低条件：lint 通过、测试通过（可用范围内）、架构守卫通过、文档守卫通过。
- 遇到架构意图不明确或规则冲突，必须标注 `NEEDS_HUMAN_REVIEW`。

## 快速入门
1. 阅读 [docs/index.md](./docs/index.md) 和 [ARCHITECTURE.md](./ARCHITECTURE.md) 了解边界与路径。
2. 运行 `python scripts/guards/check_docs_health.py` 与 `python scripts/guards/check_architecture.py` 做基线检查。
3. 按任务所在子域进入 `docs/design-docs/`、`docs/operations/` 或 `docs/exec-plans/active/` 获取执行上下文。
