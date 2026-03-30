# project-overview.zh

## 一句话定位
本文件用于让 Agent 在不读源码的前提下快速理解 AgentMark 的目标、能力边界和典型使用路径。

## 核心内容
### 项目目标
- AgentMark 聚焦 LLM Agent 行为水印。
- 目标是保持任务效用的同时提供可验证的版权保护。
- 该项目覆盖算法、接入层、可视化和实验评测。

### 用户价值
- 对研究者：可复现实验与对照评估流程。
- 对工程团队：低侵入接入水印能力。
- 对平台方：支持行为级溯源与风险追踪。

### 能力范围
- ToolBench 工具调用场景。
- ALFWorld 具身任务场景。
- Oasis 社交媒体仿真场景。
- RLNC 与语义改写鲁棒性评测。

### 非目标
- 不承诺替代所有文本水印方法。
- 不提供通用商业 SaaS 运营能力。
- 不保证隔离治理区代码风格与主仓一致。

### 关键组件
- `agentmark/core`：采样、编码、解码与日志解析。
- `agentmark/sdk`：集成封装接口。
- `agentmark/proxy`：OpenAI Chat Completions 兼容代理。
- `dashboard/server`：会话编排与 API。
- `dashboard/src`：可视化交互。
- `experiments/*`：实验运行与评测。

### 典型使用流程
1. 准备环境变量与依赖。
2. 启动后端与前端或代理服务。
3. 运行实验脚本采集轨迹与指标。
4. 在 dashboard 观察过程与结果。
5. 使用鲁棒性脚本评估恢复率和误报率。

### 输入与输出
- 输入：模型接口、任务配置、实验数据、payload 比特流。
- 输出：轨迹日志、动作权重、评测指标、可视化结果。

### 运行前置条件
- 需要 Python 3.9+（Oasis 子实验推荐 3.10+）。
- ToolBench 依赖检索缓存与数据目录结构。
- API 模式需可用的密钥与网络连接。

### 维护策略
- 主仓文档以 docs 为唯一规范来源。
- README 保留面对外部用户的快速入口。
- 规则变化必须同步到 `docs/design-docs/dependency-rules.md`。

## Agent 行为指引
- 先读本文件和 `docs/environments-matrix.md` 再决定修改范围。
- 新增功能前先判断属于核心库、接入层还是实验层。
- 若修改会触及分层边界，先更新 `docs/design-docs/dependency-rules.md`。
- 对外接口变化需同步更新运行文档和质量门禁。
- 无法判断时标注 `NEEDS_HUMAN_REVIEW`。

## 相关文件链接
- [../../README.md](../../README.md)
- [./environments-matrix.md](./environments-matrix.md)
- [../../ARCHITECTURE.md](../../ARCHITECTURE.md)
- [../operations/runbook-local-dev.md](../operations/runbook-local-dev.md)
