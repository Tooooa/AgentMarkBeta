# Golden Rules

## 一句话定位
定义项目级不可违反的硬性约束，作为所有改动和评审的最高优先级规则。

## 核心规则
1. 不得让 `agentmark/core/` 依赖 `experiments/` 或 `dashboard/`。
2. 不得让 `dashboard/src/` 直接导入任何 Python 代码路径。
3. 所有文档新增或迁移后必须登记在对应 `index.md`。
4. 提交前必须通过文档健康检查和架构依赖检查。
5. 子依赖隔离区不参与主仓守卫失败判定：
   - `experiments/oasis_watermark/oasis/`
   - `experiments/toolbench/MarkLLM/`
   - `dashboard/.git_backup/`
6. 如遇规则冲突或架构意图不清，必须标注 `NEEDS_HUMAN_REVIEW`。
7. 禁止在 PR 中提交明文密钥、令牌或敏感配置。
8. 守卫脚本报错必须附修复，不允许直接跳过。

## Agent 行为指引
- 你应该把本文件作为冲突决策的最终裁决依据。
- 你应该在规则新增或变更时同步更新本文件和依赖规则文档。
- 你不应该以“临时方便”为理由突破黄金准则。

## 相关文件链接
- [./dependency-rules.md](./dependency-rules.md)
- [./core-beliefs.md](./core-beliefs.md)
- [../../AGENTS.md](../../AGENTS.md)

## TODO
- TODO: 增加“违规严重级别”定义和处理时限。
