# Testing Strategy

## 一句话定位
定义主仓测试分层与优先级，明确“哪些必须测、何时测、如何测”。

## 测试分层
1. 单元测试
- 覆盖核心算法工具函数、解析函数和适配器关键路径。

2. 集成测试
- 覆盖会话流转、API 路由和关键实验入口。

3. 端到端验证
- 覆盖前后端基本联通和一次最小水印流程。

4. 守卫测试
- 文档健康检查。
- 架构依赖检查。

## 当前状态说明
- 主仓前端已有 lint 配置。
- 子依赖 `oasis/` 自带大量 pytest，但默认隔离治理。
- 主仓需要补充统一的最小回归清单。

## 最小回归清单
- 后端可启动并处理最小请求。
- 前端可加载并联通后端。
- ToolBench 缓存路径可被识别。
- 架构守卫与文档守卫通过。

## Agent 行为指引
- 你应该优先跑改动影响路径相关测试。
- 你应该在无法运行全量测试时声明覆盖范围和风险。
- 你不应该把子依赖测试结果当作主仓测试结论。

## 相关文件链接
- [../../dashboard/package.json](../../dashboard/package.json)
- [../operations/runbook-local-dev.md](../operations/runbook-local-dev.md)
- [../ci/ci-cd-policy.md](../ci/ci-cd-policy.md)

## TODO
- TODO: 增加主仓 pytest 入口与测试目录规范。
- TODO: 增加 dashboard 端到端 smoke test 脚本。
