# AgentScope 2.0 + AG-UI Scaffold

[![CI](https://github.com/Ken-LK/agentscope-agui-scaffold/actions/workflows/ci.yml/badge.svg)](https://github.com/Ken-LK/agentscope-agui-scaffold/actions)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

The minimal native AgentScope 2.0 + AG-UI scaffold for building assistant-ui apps.

一个可运行、可二开的脚手架。后端用 **AgentScope 2.0 原生 agent** 提供标准 **`POST /ag-ui`** 入口，前端用 `@ag-ui/client` 和 `@assistant-ui/react-ag-ui` 直接消费 AG-UI 事件流。

## Features

- Native `POST /ag-ui` endpoint with SSE streaming.
- Official `AGUIProtocolMiddleware` conversion, no custom AgentScope to AG-UI mapper.
- Agent profile selection through standard `forwardedProps`.
- Tool catalog, custom tool UI, and write-tool confirmation card.
- Local JSONL observability, with optional SLS sink for patrol workflows.

## Requirements

- Python 3.11 or 3.12
- Node.js 22
- pnpm
- `DASHSCOPE_API_KEY`

## Quick Start

```bash
make backend-install
export DASHSCOPE_API_KEY=<your-api-key>
make frontend-install
make frontend-build
make backend-run
make frontend-dev
```

Open <http://localhost:5173>. The backend runs on <http://localhost:8000>, and `curl http://localhost:8000/healthz` checks runtime health.

Try asking:

```text
用计算器算一下 (12 + 8) * 5
```

## Architecture

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

| Layer | Responsibility |
| --- | --- |
| `@ag-ui/client` | Sends `RunAgentInput` and reads SSE events. |
| `/ag-ui` | Parses the request, drives the agent, and owns the run envelope. |
| AgentScope | Runs the native `Agent.reply_stream(...)` flow. |
| `AGUIProtocolMiddleware` | Converts AgentScope events into AG-UI events. |
| assistant-ui | Renders messages, tool calls, and confirmation UI. |

## Configuration

Runtime defaults live in `backend/config/scaffold.toml`. Environment variables hold secrets and bootstrap values only.

```toml
[runtime]
default_agent = "default"

[model]
api_key_env = "DASHSCOPE_API_KEY"

[agent_profiles.default]
tools = ["calculator", "current_datetime", "knowledge_search", "list_notes"]
```

Common extension points:

- Add or tune profiles in `[agent_profiles.<id>]`.
- Register tools in `backend/app/tools/registry.py`.
- Register frontend tool renderers in `frontend/src/components/tools/tool-ui-registry.tsx`.

## Notes

- Reasoning UI is off by default because the current assistant-ui package set has `REASONING_*` schema compatibility risk.
- Write tools are off by default. Enable `enable_write_tools` only when you are ready to handle confirmation.
- Redis is not required for the native `/ag-ui` path.
- SLS is optional. Without SLS, traces fall back to local `.observability/traces.jsonl`.
- This public scaffold does not ship a bundled test suite. Use `make backend-lint` and `make frontend-build` before publishing changes.

## Maintenance

```bash
make backend-lint
make frontend-build
make clean-runtime
```

## Contributing

Issues and small PRs are welcome. Keep changes focused and avoid adding business-specific logic.

- Contribution guide: [CONTRIBUTING.md](CONTRIBUTING.md)
- Security policy: [SECURITY.md](SECURITY.md)
- License: [Apache-2.0](LICENSE)
