"""Native AgentScope 2.0 ``POST /ag-ui`` entry.

Thin entry responsibilities:
  - parse AG-UI ``RunAgentInput``,
  - drive the native ``Agent.reply_stream`` (see ``agent_runner``),
  - convert each ``AgentEvent`` via the **official**
    ``AGUIProtocolMiddleware`` converter (one instance per request),
  - own the run envelope (RUN_STARTED / RUN_FINISHED / RUN_ERROR) so the
    request's ``threadId`` / ``runId`` are echoed,
  - SSE-frame the output (``text/event-stream``) for ``@ag-ui/client``.

No self-built ``AgentEvent -> AG-UI Event`` content mapping lives here.
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator, Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.settings import Settings, get_settings
from app.observability import (
    ObservabilityPlugin,
    RunContext,
    reset_run_context,
    set_run_context,
)
from app.runtime.agent_runner import (
    agui_messages_to_agentscope,
    build_agent,
    resolve_profile,
)
from app.runtime.confirm_store import (
    ParkedRun,
    build_user_confirm_result,
    parked_runs,
)

logger = logging.getLogger(__name__)

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


class RunAgentInput(BaseModel):
    """AG-UI run input. Accepts camelCase (wire) and snake_case."""

    thread_id: str = Field(default="", alias="threadId")
    run_id: str = Field(default="", alias="runId")
    messages: list[dict[str, Any]] = Field(default_factory=list)
    tools: list[dict[str, Any]] = Field(default_factory=list)
    context: list[dict[str, Any]] = Field(default_factory=list)
    state: Any = None
    forwarded_props: Optional[dict[str, Any]] = Field(
        default=None,
        alias="forwardedProps",
    )

    model_config = {"populate_by_name": True, "extra": "allow"}

    def agent_id(self) -> str | None:
        props = self.forwarded_props or {}
        value = props.get("agentId")
        return value if isinstance(value, str) and value else None

    def confirm(self) -> dict[str, Any] | None:
        """Return the confirm/resume directive carried in forwardedProps."""

        props = self.forwarded_props or {}
        confirm = props.get("confirm")
        if isinstance(confirm, dict) and confirm.get("decisions") is not None:
            return confirm
        return None


def _build_converter():
    """Create a fresh official converter instance (per request).

    We reuse ``AGUIProtocolMiddleware``'s official ``AgentEvent -> AG-UI``
    mapping but bypass its ASGI machinery: the ASGI path emits NDJSON (not SSE)
    and its instance-level tool-result buffer is not concurrency-safe. A fresh
    instance per request keeps the official mapping while we own SSE framing.
    """

    from agentscope.app.middleware import AGUIProtocolMiddleware

    class _Converter(AGUIProtocolMiddleware):  # type: ignore[misc]
        def __init__(self) -> None:
            self._last_model_name = "model_call"
            self._tool_result_buffers = {}

        def convert(self, event) -> dict:
            return self._convert_to_protocol(event)

    return _Converter()


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _run_started(thread_id: str, run_id: str) -> dict:
    from ag_ui.core.events import RunStartedEvent

    return RunStartedEvent(thread_id=thread_id, run_id=run_id).model_dump(
        mode="json",
        exclude_none=True,
        by_alias=True,
    )


def _run_finished(thread_id: str, run_id: str) -> dict:
    from ag_ui.core.events import RunFinishedEvent

    return RunFinishedEvent(thread_id=thread_id, run_id=run_id).model_dump(
        mode="json",
        exclude_none=True,
        by_alias=True,
    )


def _run_error(message: str, code: str = "agent_error") -> dict:
    from ag_ui.core.events import RunErrorEvent

    return RunErrorEvent(message=message, code=code).model_dump(
        mode="json",
        exclude_none=True,
        by_alias=True,
    )


async def _resolve_run_inputs(
    run_input: RunAgentInput,
    settings: Settings,
    middlewares=None,
):
    """Build (agent, inputs) for either a fresh turn or a confirm resume."""

    profile = resolve_profile(settings, run_input.agent_id())
    confirm = run_input.confirm()
    if confirm is not None:
        parked = parked_runs.pop(run_input.thread_id or "thread")
        if parked is not None:
            agent = build_agent(
                settings,
                profile,
                state=parked.state_dump,
                middlewares=middlewares,
            )
            inputs = build_user_confirm_result(
                parked,
                confirm.get("decisions") or [],
            )
            return agent, inputs

    prior, latest = agui_messages_to_agentscope(run_input.messages)
    agent = build_agent(settings, profile, middlewares=middlewares)
    if prior:
        await agent.observe(prior)
    return agent, latest


async def agui_event_stream(
    run_input: RunAgentInput,
    settings: Settings,
    plugin: ObservabilityPlugin | None = None,
) -> AsyncGenerator[str, None]:
    """Yield SSE frames of AG-UI events for one run."""

    from agentscope.event import (
        ReplyEndEvent,
        ReplyStartEvent,
        RequireUserConfirmEvent,
    )

    thread_id = run_input.thread_id or "thread"
    run_id = run_input.run_id or "run"

    # Trace spine: one RunContext per run, propagated via contextvar so every
    # capture seam pins to the same run_id (see app/observability).
    obs = None
    ctx_token = None
    if plugin is not None:
        ctx = RunContext(
            run_id=run_id,
            thread_id=thread_id,
            user_id=settings.agui_default_user_id,
        )
        ctx_token = set_run_context(ctx)
        obs = plugin.new_middleware(
            run_id=run_id,
            thread_id=thread_id,
            user_id=ctx.user_id,
        )

    yield _sse(_run_started(thread_id, run_id))

    terminated = False
    parked_confirm: tuple[str, list] | None = None
    answer_parts: list[str] = []
    try:
        middlewares = [obs] if obs is not None else None
        agent, inputs = await _resolve_run_inputs(run_input, settings, middlewares)
        converter = _build_converter()

        async for event in agent.reply_stream(inputs=inputs):
            if isinstance(event, RequireUserConfirmEvent):
                parked_confirm = (event.reply_id, list(event.tool_calls))
            # The entry owns the run envelope, so drop the agent's
            # Reply{Start,End} -> RUN_{STARTED,FINISHED} to avoid duplicate /
            # mismatched-id terminal events.
            if isinstance(event, (ReplyStartEvent, ReplyEndEvent)):
                continue
            agui_event = converter.convert(event)
            if agui_event.get("type") == "TEXT_MESSAGE_CONTENT":
                # Answer text is cleanest reassembled from the main loop and handed
                # back to the middleware (Decision 2), not scraped from an event_tap.
                answer_parts.append(str(agui_event.get("delta", "")))
            if agui_event.get("type") == "RUN_ERROR":
                terminated = True
            yield _sse(agui_event)

        if obs is not None:
            obs.set_answer("".join(answer_parts))

        # Snapshot the parked agent for resume, or clear any stale park.
        if parked_confirm is not None:
            reply_id, tool_calls = parked_confirm
            parked_runs.put(
                thread_id,
                ParkedRun(
                    reply_id=reply_id,
                    state_dump=agent.state.model_dump(mode="json"),
                    tool_calls=tool_calls,
                ),
            )
        else:
            parked_runs.pop(thread_id)
    except Exception as exc:  # noqa: BLE001 - surface as an AG-UI RUN_ERROR
        logger.exception("AG-UI run failed: %s", exc)
        if obs is not None:
            obs.note_error(exc)
        if not terminated:
            terminated = True
            yield _sse(_run_error(f"Agent run failed: {exc}"))
        return
    finally:
        # End-of-turn emit (idempotent) + unbind the spine, always.
        if obs is not None:
            obs.finalize()
        if ctx_token is not None:
            reset_run_context(ctx_token)

    if not terminated:
        yield _sse(_run_finished(thread_id, run_id))


def create_agui_router(
    settings: Settings | None = None,
    plugin: ObservabilityPlugin | None = None,
) -> APIRouter:
    router = APIRouter(tags=["ag-ui"])

    @router.post("/ag-ui")
    async def run_agui(run_input: RunAgentInput) -> StreamingResponse:
        active_settings = settings or get_settings()
        return StreamingResponse(
            agui_event_stream(run_input, active_settings, plugin),
            media_type="text/event-stream",
            headers=SSE_HEADERS,
        )

    return router
