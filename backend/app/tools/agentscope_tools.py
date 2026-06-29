"""AgentScope tool adapters for business functions."""

from __future__ import annotations

from typing import Any, Callable


def make_business_tool(
    func: Callable[..., Any],
    *,
    name: str,
    description: str,
    is_read_only: bool,
):
    from agentscope.permission import PermissionBehavior, PermissionDecision
    from agentscope.tool import FunctionTool

    class BusinessFunctionTool(FunctionTool):
        async def check_permissions(self, *_args: Any, **_kwargs: Any):
            behavior = (
                PermissionBehavior.ALLOW if self.is_read_only else PermissionBehavior.ASK
            )
            return PermissionDecision(
                behavior=behavior,
                message=(
                    "Read-only scaffold business tool."
                    if self.is_read_only
                    else "This scaffold tool changes process-local state."
                ),
            )

    return BusinessFunctionTool(
        func=func,
        name=name,
        description=description,
        is_read_only=is_read_only,
    )
