# AgentScope 2.0 + AG-UI Scaffold

[![CI](https://github.com/Ken-LK/agentscope-agui-scaffold/actions/workflows/ci.yml/badge.svg)](https://github.com/Ken-LK/agentscope-agui-scaffold/actions)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

[English](README.md) | 简体中文

一个基于原生 AgentScope 2.0 agent 构建 assistant-ui 应用的最小脚手架。

这是一个可运行、可二开的脚手架。后端提供标准 `POST /ag-ui` 入口，前端通过 `@ag-ui/client` 和 `@assistant-ui/react-ag-ui` 直接消费 AG-UI 事件流。

## 功能

- 原生 `POST /ag-ui` 入口，支持 SSE 流式输出。
- 使用官方 `AGUIProtocolMiddleware` 转换，不手写 AgentScope 到 AG-UI 的映射。
- 通过标准 `forwardedProps` 选择 agent profile。
- 内置 tool catalog、自定义 tool UI 和写操作确认卡片。
- 本地 JSONL 可观测记录，可选接入 SLS 用于巡检流程。

## 环境要求

- Python 3.11 或 3.12
- Node.js 22
- pnpm
- `DASHSCOPE_API_KEY`

## 快速启动

```bash
make backend-install
export DASHSCOPE_API_KEY=<your-api-key>
make frontend-install
make frontend-build
make backend-run
make frontend-dev
```

打开 <http://localhost:5173>。后端运行在 <http://localhost:8000>，可以用 `curl http://localhost:8000/healthz` 检查运行状态。

可以试着问：

```text
用计算器算一下 (12 + 8) * 5
```

## 架构

```text
assistant-ui
  -> @ag-ui/client HttpAgent
  -> POST /ag-ui
  -> RunAgentInput
  -> AgentScope Agent.reply_stream(...)
  -> AGUIProtocolMiddleware
  -> AG-UI SSE events
  -> assistant-ui render
```

| 层 | 职责 |
| --- | --- |
| `@ag-ui/client` | 发送 `RunAgentInput` 并读取 SSE 事件。 |
| `/ag-ui` | 解析请求、驱动 agent，并维护 run envelope。 |
| AgentScope | 执行原生 `Agent.reply_stream(...)` 流程。 |
| `AGUIProtocolMiddleware` | 将 AgentScope 事件转换为 AG-UI 事件。 |
| assistant-ui | 渲染消息、tool call 和确认 UI。 |

## 配置

运行时默认配置在 `backend/config/scaffold.toml`。环境变量只用于 secrets 和启动必要值。

```toml
[runtime]
default_agent = "default"

[model]
api_key_env = "DASHSCOPE_API_KEY"

[agent_profiles.default]
tools = ["calculator", "current_datetime", "knowledge_search", "list_notes"]
```

常见扩展点：

- 在 `[agent_profiles.<id>]` 中添加或调整 profiles。
- 在 `backend/app/tools/registry.py` 中注册工具。
- 在 `frontend/src/components/tools/tool-ui-registry.tsx` 中注册前端工具渲染器。

## 说明

- Reasoning UI 默认关闭，因为当前 assistant-ui 依赖组合存在 `REASONING_*` schema 兼容风险。
- 写工具默认关闭。只有准备好处理确认流程时才启用 `enable_write_tools`。
- 原生 `/ag-ui` 路径不需要 Redis。
- SLS 是可选项。未配置 SLS 时，trace 会落到本地 `.observability/traces.jsonl`。
- 这个公开脚手架不内置测试套件。发布变更前请运行 `make backend-lint` 和 `make frontend-build`。

## 维护

```bash
make backend-lint
make frontend-build
make clean-runtime
```

## 贡献

欢迎 issue 和小型 PR。请保持变更聚焦，避免加入业务专属逻辑。

- 贡献指南：[CONTRIBUTING.md](CONTRIBUTING.md)
- 安全策略：[SECURITY.md](SECURITY.md)
- 许可证：[Apache-2.0](LICENSE)
