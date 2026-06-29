"""Aliyun SLS structured sink — flat per-turn KV → SLS logstore.

The primary discovery / aggregation data source (and the patrol tools' main data
source). Lazily imports the ``aliyun-log-python-sdk`` so the dependency is optional:
when disabled or missing config, every call is a no-op. Write failures only log;
they never raise into the request path. Fields are already desensitized by the
capture layer (``ObservabilityMiddleware``).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from app.observability.schema import TurnRecord

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SLSConfig:
    enabled: bool = False
    endpoint: str = ""
    access_key_id: str = ""
    access_key_secret: str = ""
    project: str = ""
    logstore: str = ""
    topic: str = ""
    source: str = "agentscope-agui-scaffold"

    @property
    def usable(self) -> bool:
        return bool(
            self.enabled
            and self.endpoint
            and self.access_key_id
            and self.project
            and self.logstore
        )


class SLSStructuredSink:
    """Emit a ``TurnRecord`` as a flat KV log line to SLS."""

    def __init__(self, config: SLSConfig) -> None:
        self._config = config
        self._client: Any = None
        self._init_done = False

    def _get_client(self) -> Any:
        if self._init_done:
            return self._client
        self._init_done = True
        if not self._config.usable:
            logger.info("SLS sink disabled (missing config)")
            self._client = None
            return None
        try:
            from aliyun.log import LogClient  # noqa: PLC0415

            self._client = LogClient(
                self._config.endpoint,
                self._config.access_key_id,
                self._config.access_key_secret,
            )
        except Exception:  # noqa: BLE001
            logger.exception("SLS client init failed; sink disabled")
            self._client = None
        return self._client

    def emit(self, record: TurnRecord) -> None:
        self.put(record.to_flat_contents())

    def put(self, contents: list[tuple[str, str]]) -> None:
        """Write one flat KV log line (also used for upload/feedback events)."""

        client = self._get_client()
        if client is None:
            return
        try:
            from aliyun.log import LogItem, PutLogsRequest  # noqa: PLC0415

            item = LogItem(timestamp=int(time.time()), contents=contents)
            request = PutLogsRequest(
                project=self._config.project,
                logstore=self._config.logstore,
                topic=self._config.topic,
                source=self._config.source,
                logitems=[item],
            )
            client.put_logs(request)
        except Exception:  # noqa: BLE001
            logger.warning("SLS put_logs failed", exc_info=True)
