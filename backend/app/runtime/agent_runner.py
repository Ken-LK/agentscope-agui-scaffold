"""Assemble and drive a native AgentScope 2.0 agent.

This is the scaffold extension point. It builds an ``agentscope.agent.Agent``
from settings (model + toolkit + profile) and exposes its native
``reply_stream`` ``AgentEvent`` flow. AG-UI lifecycle / SSE / event mapping live
in ``agui_runtime.py`` and the official converter, not here.
"""

from __future__ import annotations

from typing import Any

from app.core.model_config import build_chat_model
from app.core.settings import AgentProfileConfig, Settings
from app.tools.registry import build_scaffold_tools


def resolve_profile(
    settings: Settings,
    agent_id: str | None,
) -> AgentProfileConfig:
    """Resolve a configured profile by id, falling back to the default."""

    return settings.get_profile(agent_id)


def build_agent(
    settings: Settings,
    profile: AgentProfileConfig,
    *,
    model=None,
    state=None,
    middlewares=None,
):
    """Build a native AgentScope ``Agent`` for the given profile.

    ``state`` (an ``AgentState`` or its ``model_dump()`` dict) restores a parked
    run so a confirmation can be resumed across stateless HTTP requests.

    ``middlewares`` (e.g. an ``ObservabilityMiddleware``) hang on the agent's native
    middleware hooks — the stable seam for trace capture. This injection point must
    survive any future swap to ``AGUIDefaultAdapter`` (see the observability doc §7).
    """

    from agentscope.agent import Agent, ReActConfig
    from agentscope.state import AgentState
    from agentscope.tool import Toolkit

    chat_model = model if model is not None else build_chat_model(settings)
    toolkit = Toolkit(
        tools=build_scaffold_tools(
            enable_write_tools=settings.enable_write_tools,
            tool_names=list(profile.tools),
        ),
    )
    if isinstance(state, dict):
        state = AgentState(**state)
    return Agent(
        name=profile.name,
        system_prompt=profile.system_prompt,
        model=chat_model,
        toolkit=toolkit,
        react_config=ReActConfig(max_iters=profile.max_iters),
        state=state,
        middlewares=list(middlewares) if middlewares else None,
    )


def _message_text(content: Any) -> str:
    """Extract plain text from an AG-UI message ``content`` (str or parts)."""

    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and part.get("type") == "text":
                parts.append(str(part.get("text", "")))
        return "".join(parts)
    if content is None:
        return ""
    return str(content)


def agui_messages_to_agentscope(messages: list[dict[str, Any]]):
    """Split AG-UI messages into (prior context msgs, latest user msg).

    The latest user message is the new turn fed to ``reply_stream``; earlier
    messages seed the agent's memory via ``observe`` (the thin entry is
    stateless across requests).
    """

    from agentscope.message import AssistantMsg, Msg, UserMsg

    converted: list[Msg] = []
    for message in messages:
        role = message.get("role")
        text = _message_text(message.get("content"))
        if role == "user":
            converted.append(UserMsg(name="user", content=text))
        elif role == "assistant":
            converted.append(AssistantMsg(name="assistant", content=text))
        # system / tool messages are ignored in P0 (profile owns the system
        # prompt); tool history is re-derived by the agent.

    if not converted or converted[-1].role != "user":
        raise ValueError("AG-UI RunAgentInput must end with a user message.")

    return converted[:-1], converted[-1]
