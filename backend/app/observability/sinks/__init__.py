"""Pluggable trace sinks (Decision 4).

One ``RunContext`` + one capture pass can fan out to several sinks, all sharing the
same ``run_id``. The scaffold ships an SLS structured sink (primary discovery /
aggregation data source) and a local JSONL fallback (offline durability).
"""

from __future__ import annotations

from app.observability.sinks.base import TraceSink
from app.observability.sinks.local_jsonl import LocalJsonlSink
from app.observability.sinks.sls_structured import SLSStructuredSink

__all__ = ["TraceSink", "SLSStructuredSink", "LocalJsonlSink"]
