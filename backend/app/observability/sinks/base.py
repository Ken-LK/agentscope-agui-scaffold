"""``TraceSink`` protocol — emit a finished ``TurnRecord`` somewhere."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.observability.schema import TurnRecord


@runtime_checkable
class TraceSink(Protocol):
    """A trace destination. ``emit`` must never raise into the request path —
    a failing sink logs and swallows so observability cannot break the agent."""

    def emit(self, record: TurnRecord) -> None: ...
