# Local Development Runbook

## 一句话定位
提供可复制的一键本地启动路径和故障排查步骤，确保 Agent 可独立拉起服务并完成基本验证。

## 启动前准备
1. Python 环境
- 方式 A: `conda env create -f environment.yml`。
- 方式 B: `pip install -r requirements.txt`。

2. 前端环境
- 进入 `dashboard/` 后执行 `npm install`。

3. 环境变量
- 创建 `.env`，至少提供 `DEEPSEEK_API_KEY` 或 `OPENAI_API_KEY`。

4. 检索缓存
- `entrypoint.sh` 会检查 `experiments/toolbench/data/data/toolenv/tools`。
- 若目录为空，脚本尝试下载 `retriever_cache.zip` 并解压。

## 本地启动
### 后端
- 命令: `python dashboard/server/app.py` 或 `uvicorn dashboard.server.app:app --host 0.0.0.0 --port 8000 --reload`。

### 前端
- 命令: `cd dashboard && npm run dev`。
- 默认访问: `http://localhost:5173`。

### Docker
- 开发: `docker-compose up -d`。
- 生产模拟: `docker-compose -f docker-compose.prod.yml up -d`。

## 快速自检
1. 打开首页，确认静态资源可访问。
2. 调用后端健康接口或最小会话接口，确认无 5xx。
3. 运行文档与架构守卫脚本：
- `python scripts/guards/check_docs_health.py`
- `python scripts/guards/check_architecture.py`

## 常见问题
- 问题: `Missing API key`。
  - 处理: 检查 `.env` 和请求体 `apiKey`。
- 问题: ToolBench 检索不可用。
  - 处理: 检查缓存目录与解压结果。
- 问题: 前端无法联通后端。
  - 处理: 检查端口、CORS 和代理配置。

## Agent 行为指引
- 你应该先跑最小闭环，再执行耗时实验。
- 你应该在报错时先确认环境变量和路径依赖。
- 你不应该在本地环境未就绪时直接改业务逻辑。

## 相关文件链接
- [../../entrypoint.sh](../../entrypoint.sh)
- [../../docker-compose.yml](../../docker-compose.yml)
- [../../docker-compose.prod.yml](../../docker-compose.prod.yml)
- [../../dashboard/server/utils/config.py](../../dashboard/server/utils/config.py)

## TODO
- TODO: 增加 Windows PowerShell 等价命令。
- TODO: 增加最小 API 请求示例。
