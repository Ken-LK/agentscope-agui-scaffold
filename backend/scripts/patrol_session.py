"""Patrol companion: restore a session's verbatim scene from Redis (read-only).

SLS gives the metric-ized turn (run_id-keyed, desensitized + truncated); Redis
gives the session's verbatim scene. After SLS surfaces a suspect run, take its
thread_id + user_id and use this to read the Redis ``AgentState.context``.

Three caveats this enforces:
  1. Read-only: GET + TTL only, never writes Redis.
  2. Current state, not per-run history: a CAS overwrite keeps only the thread's
     latest turn; older turns fall back to SLS.
  3. Redis holds raw PII: desensitized by default before display (``--raw`` disables
     — handle with care, do not export). Remote Redis uses RESP2 (``protocol=2``).

Whether the scaffold actually persists ``AgentState`` to Redis is project-specific;
when nothing is found the tool degrades cleanly to "fall back to SLS". The Redis key
prefix is configurable via ``settings.redis_session_prefix``.

Reused by patrol_scan.py: load_session() / render_session_lines().

Usage (use the .venv interpreter):
    cd backend && .venv/bin/python scripts/patrol_session.py <user_id> <thread_id>
    cd backend && .venv/bin/python scripts/patrol_session.py local-user main --raw --max 2000
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from app.core.settings import get_settings
from app.observability.desensitize import desensitize


def _clean(value: str, fallback: str) -> str:
    value = (value or "").strip()
    if not value:
        return fallback
    return value.replace(":", "_")  # colon is the scope separator; escape it


def make_session_scope(user_id: str, thread_id: str) -> str:
    return f"{_clean(user_id, 'anonymous')}:{_clean(thread_id, 'default')}"


def session_key(user_id: str, thread_id: str) -> str:
    prefix = get_settings().redis_session_prefix
    return f"{prefix}{make_session_scope(user_id, thread_id)}"


def _mask(text: str, raw: bool, max_chars: int) -> str:
    text = text or ""
    if not raw:
        text = desensitize(text)
    if max_chars and len(text) > max_chars:
        text = text[:max_chars] + f"…(+{len(text) - max_chars})"
    return text


def _blocks_text(output: Any) -> str:
    """tool_result.output (content-block list) → joined text."""

    if isinstance(output, str):
        return output
    if isinstance(output, list):
        parts = []
        for b in output:
            if isinstance(b, dict):
                parts.append(b.get("text") or b.get("thinking") or json.dumps(b, ensure_ascii=False))
            else:
                parts.append(str(b))
        return "".join(parts)
    return json.dumps(output, ensure_ascii=False) if output is not None else ""


def load_session(user_id: str, thread_id: str, redis_url: str = "") -> tuple[dict | None, int, str]:
    """Read one session ``AgentState`` (GET + TTL only, never writes). Returns
    (state|None, ttl_seconds, key). ``redis_url`` falls back to settings."""

    redis_url = redis_url or get_settings().redis_url
    from redis import Redis  # noqa: PLC0415

    client = Redis.from_url(redis_url, decode_responses=True, protocol=2)
    key = session_key(user_id, thread_id)
    raw = client.get(key)
    ttl = client.ttl(key)
    if raw is None:
        return None, ttl, key
    try:
        return json.loads(raw), ttl, key
    except ValueError:
        return None, ttl, key


def render_session_lines(state: dict, raw: bool = False, max_chars: int = 1200) -> list[str]:
    """Render one ``AgentState`` into per-turn question→thinking→tool→answer lines."""

    lines: list[str] = []
    for msg in state.get("context") or []:
        role = msg.get("role", "?")
        name = msg.get("name", "")
        ts = msg.get("created_at", "")
        head = {"user": "👤 user", "assistant": "🤖 assistant", "system": "⚙️  system"}.get(role, role)
        lines.append(f"── {head} ({name}) {ts}")
        label = "❓ ask" if role == "user" else "💬 answer"
        content = msg.get("content")
        if isinstance(content, str):
            lines.append(f"   {label}: " + _mask(content, raw, max_chars))
            continue
        for b in content or []:
            t = b.get("type")
            if t == "text":
                lines.append(f"   {label}: " + _mask(b.get("text", ""), raw, max_chars))
            elif t == "thinking":
                lines.append("   🧠 thinking: " + _mask(b.get("thinking", ""), raw, max_chars))
            elif t == "tool_call":
                lines.append(f"   🔧 call {b.get('name')}: " + _mask(str(b.get("input", "")), raw, max_chars))
            elif t == "tool_result":
                st = b.get("state", "")
                body = _mask(_blocks_text(b.get("output")), raw, max_chars)
                lines.append(f"   📄 result[{b.get('name')} {st}]: " + body)
            else:
                lines.append(f"   ·  {t}")
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description="Read-only Redis session restore (who asked / how it answered)")
    ap.add_argument("user_id")
    ap.add_argument("thread_id")
    ap.add_argument("--redis-url", default="", help="defaults to settings.redis_url")
    ap.add_argument("--raw", action="store_true", help="no desensitization (careful, do not export)")
    ap.add_argument("--max", type=int, default=1200, help="max chars per block (default 1200)")
    args = ap.parse_args()

    redis_url = args.redis_url or get_settings().redis_url
    print(f"redis    = {redis_url.split('@')[-1]}")  # never print credentials
    state, ttl, key = load_session(args.user_id, args.thread_id, redis_url)
    print(f"key      = {key}")
    if state is None:
        print("\n[not found] session not in Redis (TTL expired, or user/thread mismatch).")
        print("→ fall back to SLS: full-text query input_text/output_text by run_id / thread_id (desensitized).")
        return 0

    context = state.get("context") or []
    print(f"ttl_left = {ttl}s" + ("  (-1=never expires)" if ttl == -1 else ""))
    print(f"session_id = {state.get('session_id', '')}")
    print(f"turns(messages) = {len(context)}   note: CAS overwrite — this is the thread's current (latest) state")
    for line in render_session_lines(state, args.raw, args.max):
        print(line if line.startswith("──") else "  " + line)
    if not args.raw:
        print("\n(desensitized display; raw content holds PII, read-only check, do not export)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
