# Dependency Rules

## 一句话定位
本文件定义可自动化校验的依赖方向与禁令，是架构守卫脚本的直接输入来源。

## 核心内容
### 规则 R1: 核心层边界
- 允许: `agentmark/core/` 依赖标准库和第三方基础包。
- 禁止: `agentmark/core/` 导入 `agentmark/environments/`、`dashboard/`、`experiments/`。

### 规则 R2: 适配层方向
- 允许: `agentmark/environments/` 导入 `agentmark/core/` 和 `agentmark/sdk/`。
- 禁止: `agentmark/environments/` 导入 `dashboard/src/` 或 `dashboard/server/`。

### 规则 R3: 代理层边界
- 允许: `agentmark/proxy/` 导入 `agentmark/sdk/` 与 `agentmark/core/`。
- 禁止: `agentmark/proxy/` 直接导入 `experiments/`。

### 规则 R4: Dashboard 后端层级
- 允许: `dashboard/server/routers/` -> `dashboard/server/services/` -> `dashboard/server/core/`。
- 禁止: `dashboard/server/routers/` 直接导入 `experiments/`。

### 规则 R5: 前后端分离
- 允许: `dashboard/src/` 通过 HTTP 调用后端。
- 禁止: `dashboard/src/` 直接导入 Python 路径。

### 规则 R6: 实验层单向依赖
- 允许: `experiments/*` 导入 `agentmark/*`。
- 禁止: `agentmark/*` 导入 `experiments/*`。

### 规则 R7: 隔离白名单
- 白名单路径: `experiments/oasis_watermark/oasis/`、`experiments/toolbench/MarkLLM/`、`dashboard/.git_backup/`。
- 处理原则: 记录存在但不纳入主仓失败判定。

## Agent 行为指引
- 你应该让新代码遵循上述规则，避免后续守卫失败。
- 你应该在新增模块时同步更新本文件和守卫脚本。
- 你不应该手动忽略守卫报错而不解释。
- 你不应该把隔离区误加入主治理区。

## 相关文件链接
- [../../ARCHITECTURE.md](../../ARCHITECTURE.md)
- [../../scripts/guards/check_architecture.py](../../scripts/guards/check_architecture.py)
- [../ci/ci-cd-policy.md](../ci/ci-cd-policy.md)

## TODO
- TODO: 增加 TypeScript import 路径规则（前端内部模块分层）。
- TODO: 增加循环依赖检测规则。
