# Security And Reliability Baseline

## 一句话定位
给出主仓最低安全与可靠性约束，防止密钥泄露、路径误用和不可恢复故障。

## 安全基线
- API Key 必须通过环境变量或请求参数传入，禁止硬编码。
- `.env` 不纳入版本控制。
- 对外日志禁止打印完整密钥和敏感凭证。
- 第三方数据集来源必须记录在 `docs/references/`。

## 可靠性基线
- 关键启动路径需有可观察日志。
- 关键配置缺失时应返回明确错误信息。
- 关键检查脚本失败必须返回非零退出码。
- 关键缓存目录不可用时应提供自动下载或人工修复建议。

## 异常处理基线
- 错误响应必须包含可操作提示。
- 文档中的运行命令必须可复现。
- 规则冲突需标注 `NEEDS_HUMAN_REVIEW`。

## Agent 行为指引
- 你应该优先审查配置和凭证路径，再处理功能异常。
- 你应该在修复安全问题后同步更新文档。
- 你不应该在示例中泄露真实凭证。

## 相关文件链接
- [../../dashboard/server/utils/config.py](../../dashboard/server/utils/config.py)
- [../operations/observability.md](../operations/observability.md)
- [../references/external-dependencies-llms.txt](../references/external-dependencies-llms.txt)

## TODO
- TODO: 增加威胁建模和风险分级。
- TODO: 增加密钥轮换流程。
