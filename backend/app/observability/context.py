"""Correlation spine: one ``RunContext`` per run, propagated via ``contextvar``.

Every capture seam (middleware / hooks / sinks) pins onto the same record so
``run_id`` + ``trace_id`` thread the whole link.

This module is pure stdlib (no agentscope / SLS imports) so it stays trivially
unit-testable and portable.
"""

from __future__ import annotations

import contextvars
import uuid
from dataclasses import dataclass

_current: contextvars.ContextVar["RunContext | None"] = contextvars.ContextVar(
    "scaffold_run_context",
    default=None,
)


@dataclass
class RunContext:
    """A run's correlation keys. ``run_id`` matches the AG-UI ``runId``;
    ``trace_id`` defaults to ``run_id`` (a reserved cross-stream join key)."""

    run_id: str = ""
    thread_id: str = ""
    user_id: str = ""
    agent_id: str = ""
    turn: int = 1
    trace_id: str = ""

    def __post_init__(self) -> None:
        if not self.run_id:
            self.run_id = uuid.uuid4().hex
        if not self.trace_id:
            self.trace_id = self.run_id


def set_run_context(ctx: RunContext) -> contextvars.Token:
    """Bind the current run context; returns a token for ``reset``."""

    return _current.set(ctx)


def get_run_context() -> RunContext | None:
    """Return the current run context (``None`` when unbound)."""

    return _current.get()


def reset_run_context(token: contextvars.Token) -> None:
    """Unbind (call at request teardown to avoid leaking into later tasks)."""

    try:
        _current.reset(token)
    except (ValueError, LookupError):
        pass
