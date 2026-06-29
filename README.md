# AgentScope 2.0 + AG-UI Scaffold

The minimal native AgentScope 2.0 + AG-UI scaffold for building assistant-ui apps.

一个可运行、可二开的脚手架。后端用 **AgentScope 2.0 原生 agent** 提供标准 **`POST /ag-ui`** 入口，前端用 `@ag-ui/client` 和 `@assistant-ui/react-ag-ui` 直接消费 AG-UI 事件流。它只保留搭建智能助手应用最常用的主干：profile 选择、工具目录、写工具确认、链路追踪和可替换的配置入口。

## 快速启动

```bash
make backend-install
export DASHSCOPE_API_KEY=<your-api-key>
make frontend-install
make frontend-build
make backend-run
make frontend-dev
```

后端默认运行在 <http://localhost:8000>，前端默认运行在 <http://localhost:5173>。健康检查：`curl http://localhost:8000/healthz`。

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
| `@ag-ui/client` | 发送标准 `RunAgentInput`，接收 SSE。 |
| `/ag-ui` | 解析请求、驱动 agent、维护 run 信封。 |
| AgentScope | 运行原生 `Agent.reply_stream(...)`。 |
| `AGUIProtocolMiddleware` | 将 AgentScope 事件转换为 AG-UI 事件。 |
| assistant-ui | 渲染消息、工具调用和确认卡片。 |

项目不手写 AgentScope 到 AG-UI 的协议映射，只保留薄入口、run 信封和 SSE 封帧。

> **路线说明：** 早期方案曾计划用 `agentscope-runtime` 的 `AGUIDefaultAdapter`。执行期实测发现该包**已废弃**且其 agentscope 桥接与 `agentscope==2.0.1` 的 message 模型不兼容，遂改为 **AgentScope 2.0 原生** 路线。

## 结构

```text
agentscope-agui-scaffold/
├── backend/app/runtime/agui_runtime.py   # POST /ag-ui 薄入口（SSE + run 信封 + 官方转换器）
├── backend/app/runtime/agent_runner.py   # 组装/驱动 agentscope Agent（扩展点）
├── backend/app/runtime/confirm_store.py  # 写工具确认的停泊/恢复（进程内）
├── backend/app/observability/            # 链路追踪能力（脊柱/中间件/信封/enricher/sinks）
├── backend/app/api/manifest.py           # GET /api/manifest（前端驱动）
├── backend/app/api/health.py             # GET /healthz（配置/降级诊断）
├── backend/app/tools/                     # 工具 catalog（计算器/时间/检索/笔记）
├── backend/scripts/                       # 巡检工具（patrol_scan / patrol_session / sls_add_field_index）
├── backend/config/scaffold.toml          # 单一配置入口（profiles / tools / model / observability）
└── frontend/                             # assistant-ui 工作台（manifest 驱动）
```

## 配置

默认值集中在 `backend/config/scaffold.toml`；`.env` 只放 key 和配置入口。

```toml
[runtime]
default_agent = "default"

[tools]
enable_write_tools = false          # 写工具默认关闭（见下）

[model]
credential_type = "openai_credential"
name = "qwen3-max"
api_key_env = "DASHSCOPE_API_KEY"
base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

[agent_profiles.default]
name = "通用助手"
system_prompt = "你是一个实用、简洁的 AgentScope 2.0 学习助手。请用中文回答。"
tools = ["calculator", "current_datetime", "knowledge_search", "list_notes"]
reasoning = false
max_iters = 20
```

- **Agent profile**：`[agent_profiles.<id>]` 定义，前端按标准 AG-UI `forwardedProps.agentId` 选择。
- **工具**：catalog 在 `app/tools/registry.py`，profile 用 `tools` 选择。
- **前端 tool UI**：按工具名注册渲染器，未知工具走 `DefaultToolResult`。

## 可观测性（链路追踪 + 巡检）

脚手架自带**完整链路追踪**：用一个 `run_id`（= AG-UI runId）把「用户问什么 → 系统每步怎么处理 → 怎么回答」串成一条可查的链路。采集挂在 AgentScope **原生稳定缝**（agent middleware hooks），不挂易变的 AG-UI 协议层，因此跨 adapter 切换不返工。

```text
app/observability/
  context.py     RunContext 脊柱（contextvar 传播，每条记录带 run_id/trace_id）
  middleware.py  采集中间件（on_reply/on_reasoning/on_acting/on_model_call）
  schema.py      TurnRecord 信封（领域无关；业务字段进开放的 attributes）
  enricher.py    TraceEnricher 协议 + NoopEnricher（默认）
  plugin.py      ObservabilityPlugin（装配中间件 + 持有 sinks/enricher）
  sinks/         TraceSink 协议 | SLS 结构化 | 本地 JSONL 兜底
```

**默认即得（零改动）：** 每轮落一条 `TurnRecord` 到本地 `.observability/traces.jsonl`，含 `run_id` 脊柱、脱敏的问/答、逐步推理、工具调用（name/args/status）、模型计时、错误。`observability_enabled` 默认开。

**接业务领域字段：** 脚手架默认 `NoopEnricher`（不认识领域语义）。业务写一个 `TraceEnricher` 注册进去，领域字段（证据/意图/路由等）就进 `TurnRecord.attributes`：

```python
class MyEnricher:
    def on_tool_result(self, tool, payload) -> dict:   # 中间件在 on_acting 自动调
        ...                                            # 返回 {evidence_refs, status, ...}
    def on_final_output(self, output) -> dict:         # 需主循环调 obs.capture_final(output)
        ...

app = create_runtime_app(enricher=MyEnricher())
```

> `on_tool_result` 开箱即用（中间件自动调，还会把空命中的工具 `status` 精化成 `degraded`）；`on_final_output`（结构化输出）需业务在 `agui_runtime` 主循环里调一次 `obs.capture_final(...)`，或把该逻辑放进工具走 `on_tool_result`。

**开 SLS（巡检数据源，可选）：** 不配 SLS 时本地 JSONL 兜底，dev 够用；要做巡检/看板就在 `[sls]` 配 endpoint/project 并用 `SLS_ACCESS_KEY_ID`/`SLS_ACCESS_KEY_SECRET` 给凭据（凭据不进 toml）。

```bash
cd backend
.venv/bin/python scripts/sls_add_field_index.py --apply   # 一次性建关联键字段索引（幂等，默认 dry-run）
.venv/bin/python scripts/patrol_scan.py --since last       # 日常增量巡检（接水位线，远程异常自动下钻）
.venv/bin/python scripts/patrol_scan.py --since 11:33 --no-drill --no-watermark --no-save  # 临时排查
```

巡检报告（存 `.patrol_reports/`，gitignore）含：流量分桶（真实 vs 测试噪声）、链路完整性自检、异常 run、结论 + 评价 + 优化建议、真实会话问答（脱敏）。**只读、不打印凭据、下钻默认脱敏。**

**现状边界（诚实）：**
- **单会话逐字现场下钻是降级的**，脚手架请求间无状态、不往 Redis 写 `AgentState`，故 `patrol_session` 下钻会落到「找不到 → 回落 SLS 脱敏文本」。发现/聚合不受影响；要逐字现场，业务侧需补一层 Redis 会话持久化（键前缀走 `redis_session_prefix`，连接走 `redis_url`，接好即可用）。
- **`user_id` 当前为全局默认值**，`agui_runtime` 给所有请求用 `agui_default_user_id`。要做「谁问的」级别隔离/巡检，业务需从 `forwardedProps`/鉴权取真实 user 塞进 `RunContext`。

## 已知约束（默认关闭）

- **reasoning（思考过程）**：`@assistant-ui/react-ag-ui@0.0.34` + `@assistant-ui/react@0.14.13` 对 `REASONING_*` part 存在 zod schema 兼容风险，默认关闭。开启前须以真实 `/ag-ui` SSE + 浏览器渲染验证。
- **写工具**：`is_read_only=false` 的工具会触发 AgentScope 确认事件（→ `CUSTOM("require_user_confirm")`），运行停泊等待确认。默认 `enable_write_tools=false`；前端 `ConfirmToolCard` 提供确认卡。

## 外部依赖边界

模型供应商、以及你自行引入的 Redis / 向量库 / SLS（巡检数据源）等只通过**配置字段 + `/healthz` 诊断**接入；脚手架不在 README / Makefile / compose 里把它们作为默认启动对象。原生 `/ag-ui` 路径不需要 Redis；SLS 默认关闭，关闭时链路追踪走本地 JSONL 兜底。

## 交付清理

`.gitignore` 已排除 `.env`、`.venv/`、`.agentscope-service/`、`.workspaces/`、`dist/`、`node_modules/`、Python 缓存，以及可观测性运行态产物（`.observability/` 本地 trace、`.patrol_reports/` 巡检报告、`.patrol_watermark.json` 水位线，下钻含脱敏 PII，只留本地）。清理运行态：

```bash
make clean-runtime
```

`backend/pyproject.toml` 把 AgentScope 固定到已验证的 Git commit，避免随上游 HEAD 漂移。当前脚手架不随仓库分发测试代码；交付前用 `make backend-lint` 和 `make frontend-build` 做本地验收。

## 贡献与安全

- 贡献指南：[CONTRIBUTING.md](CONTRIBUTING.md)
- 安全问题：[SECURITY.md](SECURITY.md)
- 许可证：[Apache-2.0](LICENSE)
- GitHub：[Ken-LK/agentscope-agui-scaffold](https://github.com/Ken-LK/agentscope-agui-scaffold)
