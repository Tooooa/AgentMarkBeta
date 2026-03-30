# Current Refactor Plan

## 一句话定位
本文件记录 AgentMark 第三轮执行（骨架、迁移、守卫）的当前状态与收尾事项，作为 active 计划入口的可执行版本。

## 当前状态
- 目录骨架已建立：`docs/`、`scripts/guards/`、`.github/workflows/`。
- 核心文档已创建：`AGENTS.md`、`ARCHITECTURE.md`。
- 子目录索引已创建：每个 `docs/*` 目录均有 `index.md`。
- 关键文档已填充：产品、设计、运维、质量、安全、CI、参考文档均有正文与行为指引。
- 守卫脚本已落地：架构检查、文档健康检查、仓库约束检查。

## 已完成任务
1. 3a 骨架搭建
- 创建目标目录结构。
- 生成根级 `AGENTS.md`。
- 生成根级 `ARCHITECTURE.md`。

2. 3b 文档迁移与填充
- 将原重构说明迁移到 `docs/exec-plans/active/`。
- 建立并补全文档索引。
- 提供各文档的“一句话定位 + 核心内容 + Agent 行为指引 + 相关链接”。

3. 3c 架构守卫与 CI
- 新增 `check_architecture.py`。
- 新增 `check_docs_health.py`。
- 新增 `check_repo_conventions.py`。
- 新增 `.github/workflows/architecture-and-docs-guard.yml`。

## 待办事项
- TODO: 执行第4轮验证清单并输出验证报告。
- TODO: 对守卫脚本增加“故意违规样例”自动测试。
- TODO: 明确主仓测试命令矩阵并更新 `docs/quality/testing-strategy.md`。

## Agent 行为指引
- 你应该先运行三类守卫脚本，再提交后续结构变更。
- 你应该在新增文档后立即更新对应 `index.md`。
- 你不应该在未记录决策的情况下修改分层规则。
- 你遇到跨边界争议时应标注 `NEEDS_HUMAN_REVIEW`。

## 相关文件链接
- [../../index.md](../../index.md)
- [../../../AGENTS.md](../../../AGENTS.md)
- [../../../ARCHITECTURE.md](../../../ARCHITECTURE.md)
- [../../../scripts/guards/check_architecture.py](../../../scripts/guards/check_architecture.py)
- [../../../scripts/guards/check_docs_health.py](../../../scripts/guards/check_docs_health.py)