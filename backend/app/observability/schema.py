"""The scaffold's fixed trace envelope: ``TurnRecord`` (Decision 3).

The scaffold *owns* exactly this envelope. All domain semantics go into the open
``attributes`` dict, filled by a project-registered ``TraceEnricher``. The scaffold
never knows what "evidence" / "recommendation" / "insurance" mean — that is what
makes the envelope reusable across derived projects.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ReasoningStep(BaseModel):
    """One ReAct reasoning step — the per-step granularity of "how the system
    processed it".

    Tool attribution is intentionally *not* recorded here: ``on_acting`` appends a
    tool_call only after ``on_reasoning`` has finished, so a step cannot reliably
    tell whether it produced a tool call. Steps record index/ms; tools live in
    ``TurnRecord.tool_calls``.
    """

    index: int
    ms: float = 0


class ToolCall(BaseModel):
    """One tool invocation. ``status`` is the refined semantic status
    ("ok" | "error" | "skipped" | "degraded") — degraded/empty results reported by
    the tool itself win over "no exception was raised, therefore ok"."""

    name: str
    args_summary: str = ""
    status: str = "ok"


class ModelCall(BaseModel):
    """One model call. Token/cost fields are best-effort (model dependent)."""

    model_name: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0
    ms: float = 0


class TurnRecord(BaseModel):
    """One turn of the complete link, keyed by ``run_id``.

    "Complete link" = a single ``run_id`` strings together the question, each
    reasoning step, each tool + its evidence, each model call, and the final answer.
    The spine comes before the fields.
    """

    event: str = "agent_run"  # SLS event type, for filtering (agent_run / upload / feedback)
    # ── scaffold envelope (stable) ──
    run_id: str
    thread_id: str = ""
    user_id: str = ""
    agent_id: str = ""
    agent_version: str = ""
    prompt_key: str = ""
    prompt_version: str = ""
    prompt_md5: str = ""
    turn: int = 1
    input_text: str = ""
    input_chars: int = 0
    output_text: str = ""
    output_length: int = 0
    reasoning_steps: list[ReasoningStep] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    model_calls: list[ModelCall] = Field(default_factory=list)
    model_ms: float = 0
    first_token_ms: float = 0
    total_ms: float = 0
    trace_id: str = ""  # defaults to run_id
    error_code: str = ""
    error_message: str = ""
    ts: float = 0
    # ── business attributes (open; the scaffold does not understand these) ──
    attributes: dict[str, Any] = Field(default_factory=dict)

    def to_flat_contents(self) -> list[tuple[str, str]]:
        """Flatten to SLS-friendly KV pairs.

        Envelope fields become top-level columns; ``attributes`` are *promoted* to
        top-level columns too (so a structured sink stays a flat KV schema and the
        patrol tools can read envelope columns without parsing a JSON blob). Nested
        models/lists are stringified as Python reprs (``ast.literal_eval``-parsable),
        matching what the patrol scanner expects.
        """

        data = self.model_dump(exclude_none=True)
        attributes = data.pop("attributes", {}) or {}
        contents: list[tuple[str, str]] = []
        for key, value in data.items():
            contents.append((key, _stringify(value)))
        for key, value in attributes.items():
            # Do not let a business attribute shadow an envelope column.
            if key in data:
                key = f"attr_{key}"
            contents.append((str(key), _stringify(value)))
        return contents


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    return str(value)
