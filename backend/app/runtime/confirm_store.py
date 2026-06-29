"""Parked-run store + confirm/resume helpers (P0.5).

The native ``/ag-ui`` entry is stateless across requests, but write-tool
confirmation requires resuming a parked agent. We snapshot the parked
``agent.state`` (plus the awaiting tool calls) keyed by ``threadId`` so the next
request carrying ``forwardedProps.confirm`` can rebuild the agent and feed an
official ``UserConfirmResultEvent``.

This in-process store is scaffold-grade. Production deployments should back it
with Redis / external storage (a configuration surface, not a protocol change).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any


@dataclass
class ParkedRun:
    """A run parked on a write-tool confirmation."""

    reply_id: str
    state_dump: dict[str, Any]
    tool_calls: list[Any]  # AgentScope ToolCallBlock objects


class ParkedRunStore:
    """Thread-safe, in-process store of parked runs keyed by thread id."""

    def __init__(self) -> None:
        self._runs: dict[str, ParkedRun] = {}
        self._lock = threading.Lock()

    def put(self, thread_id: str, run: ParkedRun) -> None:
        with self._lock:
            self._runs[thread_id] = run

    def pop(self, thread_id: str) -> ParkedRun | None:
        with self._lock:
            return self._runs.pop(thread_id, None)

    def get(self, thread_id: str) -> ParkedRun | None:
        with self._lock:
            return self._runs.get(thread_id)

    def clear(self) -> None:
        with self._lock:
            self._runs.clear()


# Module-level default store shared by the /ag-ui entry.
parked_runs = ParkedRunStore()


def build_user_confirm_result(parked: ParkedRun, decisions: list[dict[str, Any]]):
    """Build an official ``UserConfirmResultEvent`` from frontend decisions.

    ``decisions`` is ``[{"toolCallId": str, "confirmed": bool}, ...]``. Tool
    calls without an explicit decision default to rejected (safe default).
    """

    from agentscope.event import ConfirmResult, UserConfirmResultEvent

    decision_by_id = {
        str(d.get("toolCallId")): bool(d.get("confirmed", False))
        for d in decisions
        if d.get("toolCallId")
    }

    confirm_results = [
        ConfirmResult(
            confirmed=decision_by_id.get(tool_call.id, False),
            tool_call=tool_call,
        )
        for tool_call in parked.tool_calls
    ]
    return UserConfirmResultEvent(
        reply_id=parked.reply_id,
        confirm_results=confirm_results,
    )
