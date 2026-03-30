# Deployment

## 一句话定位
规范 AgentMark 在开发和生产场景下的部署方式、环境变量和运行边界。

## 部署模式
1. Docker 开发模式
- 使用 `docker-compose.yml`。
- 特点: 挂载源码，后端支持热重载。

2. Docker 生产模式
- 使用 `docker-compose.prod.yml`。
- 特点: 使用预构建镜像，减少本地构建成本。

3. 本地裸机模式
- 后端与前端分别启动，便于调试。

## 环境变量
- `DEEPSEEK_API_KEY`: 推荐主推理密钥。
- `OPENAI_API_KEY`: 兼容备用密钥。
- `AGENTMARK_DEBUG_SAMPLER`: 调试采样日志开关。

## 目录挂载建议
- 持久化目录建议包括：`data/`、`experiments/`、`output/`。
- 避免在生产容器中覆盖核心代码路径导致镜像一致性破坏。

## 发布前检查清单
- 镜像标签与文档声明一致。
- API Key 来源安全，未硬编码。
- 守卫脚本在目标分支通过。
- 关键实验入口可执行。

## Agent 行为指引
- 你应该优先使用声明的 compose 文件，而非手写临时参数。
- 你应该在变更部署策略时同步更新 CI 与 runbook。
- 你不应该在生产文档中包含明文密钥示例。

## 相关文件链接
- [../../Dockerfile](../../Dockerfile)
- [../../docker-compose.yml](../../docker-compose.yml)
- [../../docker-compose.prod.yml](../../docker-compose.prod.yml)
- [./runbook-local-dev.md](./runbook-local-dev.md)

## TODO
- TODO: 增加容器健康检查和重启策略建议。
- TODO: 增加多环境配置模板（dev/staging/prod）。
