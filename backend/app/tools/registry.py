"""Tool registry exposed to AgentScope.

Each entry carries a ``write`` flag. Write tools (``is_read_only=False``) are
disabled by default in P0 because they trigger AgentScope confirmation events
that the confirm/resume link only handles from P0.5 onward. Read-only tools run
with ``PermissionBehavior.ALLOW`` and never pause the stream.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.tools.agentscope_tools import make_business_tool
from app.tools.business import (
    calculate_expression,
    current_datetime,
    list_notes,
    remember_note,
    search_scaffold_knowledge,
)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    func: Callable[..., Any]
    is_read_only: bool


def build_scaffold_tool_specs(
    user_id: str = "local-user",
    session_id: str = "main",
) -> list[ToolSpec]:
    def scaffold_search_knowledge(query: str, limit: int = 3) -> list[dict]:
        """Search the bundled AgentScope 2.0 learning notes."""

        return search_scaffold_knowledge(query=query, limit=limit)

    def scaffold_remember_note(note: str) -> dict:
        """Remember a short note in the current scaffold process."""

        return remember_note(user_id=user_id, session_id=session_id, note=note)

    def scaffold_list_notes() -> list[str]:
        """List notes remembered in the current scaffold process."""

        return list_notes(user_id=user_id, session_id=session_id)

    return [
        ToolSpec(
            name="calculator",
            description="Evaluate a safe numeric expression.",
            func=calculate_expression,
            is_read_only=True,
        ),
        ToolSpec(
            name="current_datetime",
            description="Return the current date and time for a timezone.",
            func=current_datetime,
            is_read_only=True,
        ),
        ToolSpec(
            name="knowledge_search",
            description="Search the bundled AgentScope 2.0 scaffold knowledge.",
            func=scaffold_search_knowledge,
            is_read_only=True,
        ),
        ToolSpec(
            name="list_notes",
            description="List process-local memory notes.",
            func=scaffold_list_notes,
            is_read_only=True,
        ),
        ToolSpec(
            name="remember_note",
            description="Store a short process-local memory note.",
            func=scaffold_remember_note,
            is_read_only=False,
        ),
    ]


def build_scaffold_tools(
    user_id: str = "local-user",
    session_id: str = "main",
    *,
    enable_write_tools: bool = False,
    tool_names: list[str] | None = None,
) -> list:
    """Return AgentScope ``FunctionTool`` instances for the scaffold agent.

    - ``tool_names`` selects which catalog tools to include (a profile's tool
      group). ``None`` includes the whole catalog.
    - Write tools are excluded unless ``enable_write_tools`` is True, even if
      named in ``tool_names``.
    """

    selected = set(tool_names) if tool_names is not None else None
    tools = []
    for spec in build_scaffold_tool_specs(user_id=user_id, session_id=session_id):
        if selected is not None and spec.name not in selected:
            continue
        if not spec.is_read_only and not enable_write_tools:
            continue
        tools.append(
            make_business_tool(
                spec.func,
                name=spec.name,
                description=spec.description,
                is_read_only=spec.is_read_only,
            ),
        )
    return tools
