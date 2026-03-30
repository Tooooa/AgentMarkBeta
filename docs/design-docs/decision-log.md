# Decision Log

## 一句话定位
记录重构过程中的关键架构决策，保留决策背景、备选方案和影响评估。

## 核心内容
### ADR-001: 采用 Agent-first 文档治理
- 背景: 项目知识散落在 README、代码注释和目录惯例中。
- 决策: 建立 `AGENTS.md` + `ARCHITECTURE.md` + `docs/*/index.md` 体系。
- 影响: 降低 Agent 上手成本，提高上下文稳定性。

### ADR-002: 主仓与子依赖隔离治理
- 背景: `oasis/` 与 `MarkLLM/` 含独立约束，不适合直接纳入主规则。
- 决策: 标记为隔离区，仅做索引记录。
- 影响: 避免误报，降低守卫噪音。

### ADR-003: 守卫脚本优先于口头规范
- 背景: 分层规则仅在认知层，无法稳定执行。
- 决策: 建立架构检查和文档健康检查脚本并接入 CI。
- 影响: 规则可重复执行，PR 门禁标准化。

## Agent 行为指引
- 你应该在新增关键规则前先补一条 ADR 记录。
- 你应该在 ADR 中写清楚不采纳方案及原因。
- 你不应该在无 ADR 的情况下变更主规则边界。

## 相关文件链接
- [./core-beliefs.md](./core-beliefs.md)
- [./dependency-rules.md](./dependency-rules.md)
- [../exec-plans/active/current-refactor-plan.md](../exec-plans/active/current-refactor-plan.md)

## TODO
- TODO: 为每条 ADR 增加状态字段（proposed/accepted/superseded）。
- TODO: 增加决策影响回溯模板。
