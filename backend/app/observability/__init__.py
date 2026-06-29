"""Scaffold observability: complete-trace capture on AgentScope native seams.

This package is the scaffold's first-class trace capability, distilled from a
derived project.

Design:
  - **Spine** (`context.RunContext`): one ``run_id`` per run, propagated via a
    ``contextvar``, so every capture seam pins to the same correlation key.
  - **Capture** (`middleware.ObservabilityMiddleware`): hangs on AgentScope's
    *native* middleware hooks (``on_reply`` / ``on_reasoning`` / ``on_acting`` /
    ``on_model_call``) — the stable seam, never on the AG-UI mapper/adapter.
  - **Envelope** (`schema.TurnRecord`): a fixed, domain-agnostic record. Domain
    semantics live in the open ``attributes`` dict, filled by a project's
    ``TraceEnricher`` (`enricher`). The scaffold never knows what "evidence" is.
  - **Sinks** (`sinks`): pluggable, fan-outable ``TraceSink`` implementations
    sharing one ``run_id`` (SLS structured + local JSONL fallback).
  - **Plugin** (`plugin.ObservabilityPlugin`): assembles the above and mints a
    per-request middleware bound to the configured enricher + sinks.
"""

from __future__ import annotations

from app.observability.context import (
    RunContext,
    get_run_context,
    reset_run_context,
    set_run_context,
)
from app.observability.enricher import NoopEnricher, TraceEnricher
from app.observability.middleware import ObservabilityMiddleware
from app.observability.plugin import ObservabilityPlugin, build_plugin
from app.observability.schema import (
    ModelCall,
    ReasoningStep,
    ToolCall,
    TurnRecord,
)

__all__ = [
    "RunContext",
    "set_run_context",
    "get_run_context",
    "reset_run_context",
    "TraceEnricher",
    "NoopEnricher",
    "ObservabilityMiddleware",
    "ObservabilityPlugin",
    "build_plugin",
    "TurnRecord",
    "ReasoningStep",
    "ToolCall",
    "ModelCall",
]
