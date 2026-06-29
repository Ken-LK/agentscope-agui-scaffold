"""``ObservabilityMiddleware`` — per-turn, staged trace capture on the native seams.

A legitimate AgentScope 2.0 ``MiddlewareBase`` subclass:
  - ``on_reply``      wraps the whole turn: timing + capture the question text +
                      finalize on teardown.
  - ``on_reasoning``  per ReAct step (how the system processed it).
  - ``on_model_call`` accumulate model-call time (+ best-effort model name).
  - ``on_acting``     capture tool name/args/status + parse the native TOOL_RESULT
                      and hand it to the enricher for domain fields.

This is the scaffold's *stable* capture layer: it hangs on AgentScope's native
hooks, never on the AG-UI mapper/adapter. Everything domain-specific is delegated
to a ``TraceEnricher`` and lands in ``TurnRecord.attributes``.

⚠️ Tool-result shape gotcha (else evidence is silently dropped): a plain dict tool
return is ``json.dumps``-ed by ``FunctionTool`` into a **TextBlock** (not
``metadata``); and ``call_tool`` yields ``ToolChunk`` + ``ToolResponse`` whose
``content`` are both the **cumulative full text** (not deltas). So: parse each item
*individually* and keep the last that parses — concatenating across items doubles the
JSON into an invalid string.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, AsyncGenerator, Callable, Sequence

from agentscope.middleware import MiddlewareBase

from app.observability.context import get_run_context
from app.observability.desensitize import desensitize
from app.observability.enricher import NoopEnricher, TraceEnricher
from app.observability.schema import ModelCall, ReasoningStep, ToolCall, TurnRecord

logger = logging.getLogger(__name__)

_TEXT_CAP = 4000  # truncation cap for question/answer text on the trace (post-desensitize)
_ARGS_CAP = 200


class ObservabilityMiddleware(MiddlewareBase):
    """Records one ``TurnRecord`` per turn. Build one instance per request.

    ``run_id`` / ``thread_id`` / ``user_id`` prefer the ``contextvar`` ``RunContext``
    (the spine); constructor args are the fallback.
    """

    def __init__(
        self,
        *,
        user_id: str = "",
        thread_id: str = "",
        turn: int = 1,
        run_id: str = "",
        agent_id: str = "",
        enricher: TraceEnricher | None = None,
        sinks: Sequence[Any] | None = None,
    ) -> None:
        ctx = get_run_context()
        self._user_id = (ctx.user_id if ctx else "") or user_id
        self._thread_id = (ctx.thread_id if ctx else "") or thread_id
        self._agent_id = (ctx.agent_id if ctx else "") or agent_id
        self._turn = (ctx.turn if ctx else 0) or turn
        self._run_id = (ctx.run_id if ctx else "") or run_id or uuid.uuid4().hex
        self._trace_id = (ctx.trace_id if ctx else "") or self._run_id
        self._enricher: TraceEnricher = enricher or NoopEnricher()
        self._sinks: list[Any] = list(sinks or [])
        self._t_start = 0.0
        self._model_ms = 0.0
        self._first_token_ms = 0.0
        self._total_ms = 0.0
        self._reasoning_steps: list[ReasoningStep] = []
        self._tool_calls: list[ToolCall] = []
        self._model_calls: list[ModelCall] = []
        self._attributes: dict[str, Any] = {}
        self._input_text = ""
        self._output_text = ""
        self._error_code = ""
        self._error_msg = ""
        self._emitted = False

    # ── hooks ─────────────────────────────────────────────────────────
    async def on_reply(
        self,
        agent: Any,
        input_kwargs: dict,
        next_handler: Callable[..., AsyncGenerator],
    ) -> AsyncGenerator:
        self._t_start = time.perf_counter()
        if not self._input_text:
            self._input_text = self._capture_input(input_kwargs.get("inputs"))
        try:
            async for item in next_handler(**input_kwargs):
                if self._first_token_ms == 0.0:
                    self._first_token_ms = (time.perf_counter() - self._t_start) * 1000
                yield item
        except Exception as exc:  # noqa: BLE001
            self._error_code = type(exc).__name__
            self._error_msg = desensitize(str(exc))
            raise
        finally:
            # Only record timing here; the actual emit is deferred to finalize()
            # so the main loop can hand back the answer + run any final enrichment.
            self._total_ms = (time.perf_counter() - self._t_start) * 1000

    async def on_reasoning(
        self,
        agent: Any,
        input_kwargs: dict,
        next_handler: Callable[..., AsyncGenerator],
    ) -> AsyncGenerator:
        idx = len(self._reasoning_steps) + 1
        t0 = time.perf_counter()
        try:
            async for item in next_handler(**input_kwargs):
                yield item
        finally:
            self._reasoning_steps.append(
                ReasoningStep(index=idx, ms=round((time.perf_counter() - t0) * 1000, 2))
            )

    async def on_model_call(
        self,
        agent: Any,
        input_kwargs: dict,
        next_handler: Callable[..., Any],
    ) -> Any:
        t0 = time.perf_counter()
        result = await next_handler(**input_kwargs)
        ms = (time.perf_counter() - t0) * 1000
        self._model_ms += ms
        self._model_calls.append(ModelCall(model_name=self._model_name(agent), ms=round(ms, 2)))
        return result

    async def on_acting(
        self,
        agent: Any,
        input_kwargs: dict,
        next_handler: Callable[..., AsyncGenerator],
    ) -> AsyncGenerator:
        tool_call = input_kwargs.get("tool_call")
        name = getattr(tool_call, "name", None) or (
            tool_call.get("name") if isinstance(tool_call, dict) else "tool"
        )
        raw_args = getattr(tool_call, "input", None)
        if raw_args is None and isinstance(tool_call, dict):
            raw_args = tool_call.get("input")
        args_summary = desensitize(
            json.dumps(raw_args, ensure_ascii=False, default=str)[:_ARGS_CAP]
        )
        status = "ok"
        text_buf: list[str] = []
        payload: dict | None = None
        try:
            async for item in next_handler(**input_kwargs):
                # call_tool yields ToolChunk + ToolResponse; both .content are the
                # cumulative full text (not deltas). Parse each item individually and
                # keep the last that parses; concatenating across items doubles the JSON.
                direct = self._payload_from_item(item)
                if direct is not None:
                    payload = direct
                else:
                    parsed = self._loads_dict("".join(self._texts_of_item(item)))
                    if parsed is not None:
                        payload = parsed
                    else:
                        text_buf.extend(self._texts_of_item(item))
                yield item
        except Exception:
            status = "error"
            raise
        finally:
            if payload is None and text_buf:
                payload = self._loads_dict("".join(text_buf))
            if isinstance(payload, dict):
                status = self._ingest_tool_payload(str(name), payload, status)
            self._tool_calls.append(
                ToolCall(name=str(name), args_summary=args_summary, status=status)
            )

    # ── capture helpers ───────────────────────────────────────────────
    def _ingest_tool_payload(self, name: str, payload: dict, base_status: str) -> str:
        """Hand the parsed tool payload to the enricher, merge business fields into
        ``attributes``, and return the refined status."""

        biz = self._enricher.on_tool_result(name, payload) or {}
        for key, value in biz.items():
            if key == "status":
                continue
            self._merge_attribute(key, value)
        biz_status = biz.get("status")
        if base_status == "error":
            return "error"
        return biz_status or base_status

    def _merge_attribute(self, key: str, value: Any) -> None:
        """Merge an enricher field into attributes. Lists accumulate (deduped);
        scalars take the first non-empty value."""

        if isinstance(value, list):
            existing = self._attributes.setdefault(key, [])
            if isinstance(existing, list):
                for item in value:
                    if item not in existing:
                        existing.append(item)
            return
        if value in (None, "", [], {}):
            return
        self._attributes.setdefault(key, value)

    @staticmethod
    def _model_name(agent: Any) -> str:
        model = getattr(agent, "model", None)
        for attr in ("model_name", "model", "name"):
            value = getattr(model, attr, None)
            if isinstance(value, str) and value:
                return value
        return ""

    @staticmethod
    def _payload_from_item(item: Any) -> dict | None:
        """Pull a structured dict from one tool-result item.

        Covers: (1) ``item.output`` is a dict; (2) ``item.content`` is a list of
        TextBlocks holding JSON (AgentScope serializes a dict return into a TextBlock,
        leaving metadata empty — the real root cause of empty evidence);
        (3) ``item.content`` / ``item.metadata`` is itself a dict.
        """

        out = getattr(item, "output", None)
        if isinstance(out, dict):
            return out
        meta = getattr(item, "metadata", None)
        if isinstance(meta, dict) and meta:
            return meta
        content = getattr(item, "content", None)
        if isinstance(content, dict):
            return content
        return None

    @staticmethod
    def _texts_of_item(item: Any) -> list[str]:
        """All TextBlock texts in one tool-result item (for JSON parsing)."""

        content = getattr(item, "content", None)
        if not isinstance(content, list):
            return []
        out: list[str] = []
        for block in content:
            text = getattr(block, "text", None)
            if text is None and isinstance(block, dict):
                text = block.get("text")
            if isinstance(text, str) and text:
                out.append(text)
        return out

    @staticmethod
    def _loads_dict(raw: str) -> dict | None:
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return None
        return data if isinstance(data, dict) else None

    def _capture_input(self, inputs: Any) -> str:
        return desensitize(self._msg_text(inputs))[:_TEXT_CAP]

    @classmethod
    def _msg_text(cls, value: Any) -> str:
        """Recursively pull text: Msg(content=[block]) / TextBlock(.text) / dict /
        str / list are all covered."""

        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, (list, tuple)):
            return " ".join(t for t in (cls._msg_text(v) for v in value) if t).strip()
        if isinstance(value, dict):
            if isinstance(value.get("text"), str):
                return value["text"]
            if "content" in value:
                return cls._msg_text(value["content"])
            return ""
        text = getattr(value, "text", None)
        if isinstance(text, str):
            return text
        content = getattr(value, "content", None)
        if content is not None and content is not value:
            return cls._msg_text(content)
        return ""

    # ── main-loop handoff ─────────────────────────────────────────────
    def set_answer(self, text: str) -> None:
        """Main loop hands back the final answer text (desensitized + truncated),
        completing the question→answer link."""

        self._output_text = desensitize(text or "")[:_TEXT_CAP]

    def set_attributes(self, attributes: dict[str, Any]) -> None:
        """Merge arbitrary business attributes onto the turn."""

        for key, value in (attributes or {}).items():
            self._merge_attribute(key, value)

    def capture_final(self, output: Any) -> None:
        """Run the enricher's final-output hook and merge results into attributes."""

        try:
            biz = self._enricher.on_final_output(output) or {}
            for key, value in biz.items():
                self._merge_attribute(key, value)
        except Exception:  # noqa: BLE001
            logger.debug("capture_final enricher failed", exc_info=True)

    def note_error(self, exc: BaseException) -> None:
        """Record an exception from the main link (outside the middleware)."""

        if not self._error_code:
            self._error_code = type(exc).__name__
            self._error_msg = desensitize(str(exc))

    def build_record(self) -> TurnRecord:
        return TurnRecord(
            run_id=self._run_id,
            thread_id=self._thread_id,
            user_id=self._user_id,
            agent_id=self._agent_id,
            turn=self._turn,
            input_text=self._input_text,
            input_chars=len(self._input_text),
            output_text=self._output_text,
            output_length=len(self._output_text),
            reasoning_steps=self._reasoning_steps,
            tool_calls=self._tool_calls,
            model_calls=self._model_calls,
            model_ms=round(self._model_ms, 2),
            first_token_ms=round(self._first_token_ms, 2),
            total_ms=round(self._total_ms, 2),
            trace_id=self._trace_id,
            error_code=self._error_code,
            error_message=self._error_msg,
            ts=time.time(),
            attributes=dict(self._attributes),
        )

    def finalize(self) -> None:
        """Explicit end-of-turn emit (idempotent). Call after any final enrichment
        so the record is complete."""

        if self._emitted:
            return
        self._emitted = True
        record = self.build_record()
        logger.info("turn_trace %s", record.model_dump_json(exclude_none=True))
        for sink in self._sinks:
            try:
                sink.emit(record)
            except Exception:  # noqa: BLE001 - a sink must never break the request
                logger.warning("trace sink emit failed", exc_info=True)

    @property
    def current_run_id(self) -> str:
        return self._run_id
