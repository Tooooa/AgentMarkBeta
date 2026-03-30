# CI CD Policy

## 一句话定位
定义主仓 PR 与主分支的最小质量门禁，确保架构、文档和基本质量可持续执行。

## 流程规则
1. 触发条件
- push 到主分支。
- pull request 到主分支。

2. 必跑检查
- 文档健康检查：`python scripts/guards/check_docs_health.py`。
- 架构依赖检查：`python scripts/guards/check_architecture.py`。
- 守卫有效性检查：`python scripts/guards/check_guard_effectiveness.py`。
- 仓库约束检查：`python scripts/guards/check_repo_conventions.py`。

3. 失败处理
- 任一检查失败即阻断合并。
- 报错必须包含修复建议。
- 例外需附 `NEEDS_HUMAN_REVIEW` 说明并由维护者批准。

## PR 合并前最低条件
- lint 通过。
- 测试通过（可用范围）。
- 架构守卫通过。
- 文档守卫通过。
- 关键文档索引已更新。

## Agent 行为指引
- 你应该在提交前本地运行守卫脚本。
- 你应该把 CI 失败信息映射到具体规则并修复。
- 你不应该绕过门禁直接要求合并。

## 相关文件链接
- [../../.github/workflows/architecture-and-docs-guard.yml](../../.github/workflows/architecture-and-docs-guard.yml)
- [../design-docs/dependency-rules.md](../design-docs/dependency-rules.md)
- [../quality/QUALITY_SCORE.md](../quality/QUALITY_SCORE.md)

## TODO
- TODO: 增加主仓测试命令矩阵。
- TODO: 增加 tag 发布流程和回滚策略。
