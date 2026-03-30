# OBSERVABILITY

## 一句话定位
定义 AgentMark 的日志格式、关键指标、告警阈值和自验证流程，确保 Agent 可以独立观测与定位问题。

## 日志格式规范
- 统一输出 JSON 结构，至少包含：`timestamp`、`component`、`event`、`session_id`、`message`。
- 水印相关日志建议包含：`watermark_round`、`bit_index`、`action`、`confidence`。
- 请求链路日志建议包含：`request_id`、`route`、`latency_ms`、`status_code`。
- 错误日志必须包含：`error_type`、`error_message`、`suggested_fix`。
- 终端前缀约定：
  - `[agentmark:scoring_request]`
  - `[agentmark:tool_calls_proxy]`
  - `[watermark]`

## 关键指标
1. 请求层
- API P95 延迟（ms）
- 接口错误率（5xx 占比）
- 会话恢复成功率

2. 水印层
- 编码成功率
- 解码成功率
- 比特恢复准确率
- 误报率（FPR）

3. 实验层
- 任务完成率
- 工具调用成功率
- 轨迹完整性（日志缺失率）

## Agent 自验证流程
1. 启动服务后检查是否出现 retriever 初始化日志。
2. 发起最小请求并确认返回包含可解析轨迹字段。
3. 执行一次水印流程，确认 `[watermark]` 日志输出完整。
4. 运行守卫脚本，确认文档和架构规则均通过。
5. 对异常日志补充修复建议并回写相应文档。

## Agent 行为指引
- 你应该先看日志是否满足最小字段，再深入业务逻辑。
- 你应该把无法复现的问题映射到指标缺口而非仅给结论。
- 你不应该在无指标证据时断言系统稳定。
- 你不应该删除关键日志前缀，避免现有观测脚本失效。

## 相关文件链接
- [../../dashboard/server/app.py](../../dashboard/server/app.py)
- [../../agentmark/proxy/server.py](../../agentmark/proxy/server.py)
- [./runbook-local-dev.md](./runbook-local-dev.md)
- [../quality/QUALITY_SCORE.md](../quality/QUALITY_SCORE.md)

## TODO
- TODO: 为每个关键指标补充采集口径与时间窗口定义。
- TODO: 增加统一日志 schema 示例文件。
