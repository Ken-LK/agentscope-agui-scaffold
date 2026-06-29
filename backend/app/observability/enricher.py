"""Reuse seam: ``TraceEnricher`` — keep domain semantics behind an interface.

The framework/middleware does only generic capture; domain fields are filled by
a project-registered enricher and land in ``TurnRecord.attributes``.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class TraceEnricher(Protocol):
    """Domain enrichment protocol. Two hooks for two capture seams."""

    def on_tool_result(self, tool: str, payload: Any) -> dict:
        """Structured payload parsed from a native TOOL_RESULT → business fields.

        Return contract (all optional), merged into ``TurnRecord.attributes``; a
        few keys are also interpreted by the middleware:
          - ``status``: str   semantic tool status "ok" | "degraded" | "error"
            (refines the recorded ``ToolCall.status`` — empty hit → degraded).
          - anything else (e.g. ``evidence_refs``, ``note``) is stored verbatim.
        """
        ...

    def on_final_output(self, output: Any) -> dict:
        """Final structured output → business fields (intent / route / …),
        merged into ``TurnRecord.attributes``."""
        ...


class NoopEnricher:
    """Scaffold default: understands no domain semantics."""

    def on_tool_result(self, tool: str, payload: Any) -> dict:  # noqa: ARG002
        return {}

    def on_final_output(self, output: Any) -> dict:  # noqa: ARG002
        return {}
