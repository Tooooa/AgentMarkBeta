# OBSERVABILITY

## 一句话定位
该文件是仓库根文档入口的可观测性快捷索引，便于按固定路径查找观测规范。

## 说明
- 规范正文位于 [operations/observability.md](./operations/observability.md)。
- 本文件保留用于稳定兼容路径 `docs/OBSERVABILITY.md`。

## 核心要点
- 日志应包含请求链路、会话标识和水印相关关键字段。
- 指标应覆盖延迟、错误率、解码准确率与误报率。
- 每次重大改动后应执行可观测自验证流程。

## Agent 行为指引
- 你应该优先阅读并遵循 `operations/observability.md` 的完整规范。
- 你不应该在变更日志格式后不更新观测文档。

## 相关文件链接
- [./operations/observability.md](./operations/observability.md)
- [./operations/runbook-local-dev.md](./operations/runbook-local-dev.md)
- [../AGENTS.md](../AGENTS.md)

## TODO
- TODO: 增加日志 schema 快照示例。
