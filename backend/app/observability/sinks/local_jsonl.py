"""Local JSONL sink — offline durable fallback (one line per record).

Single-instance local index. Multi-instance deployments need a shared store
(Redis/DB); this is the always-available durability floor.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any

from app.observability.schema import TurnRecord

logger = logging.getLogger(__name__)

_lock = threading.Lock()


class LocalJsonlSink:
    """Append finished records to ``<dir>/traces.jsonl``."""

    def __init__(self, directory: str, filename: str = "traces.jsonl") -> None:
        self._dir = directory
        self._filename = filename

    @property
    def path(self) -> str:
        return os.path.join(self._dir, self._filename)

    def emit(self, record: TurnRecord) -> None:
        try:
            payload = record.model_dump(exclude_none=True)
            self._append(payload)
        except Exception:  # noqa: BLE001 - never break the request path
            logger.warning("LocalJsonlSink emit failed", exc_info=True)

    def _append(self, payload: dict[str, Any]) -> None:
        payload.setdefault("ts", time.time())
        with _lock:
            os.makedirs(self._dir, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
