"""``ObservabilityPlugin`` — assembler for the capture seams (Decision 2).

Holds the configured enricher + sinks and mints a per-request
``ObservabilityMiddleware`` bound to them. This is the single object the runtime
wires in: ``factory`` builds it from settings (and an optional project enricher),
stores it on ``app.state``, and ``agui_runtime`` calls ``new_middleware`` per run.

The scaffold defaults to ``NoopEnricher`` + (SLS structured ∥ local JSONL) sinks.
A derived project passes its own enricher; everything else is reused as-is.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from app.observability.enricher import NoopEnricher, TraceEnricher
from app.observability.middleware import ObservabilityMiddleware
from app.observability.sinks import LocalJsonlSink, SLSStructuredSink
from app.observability.sinks.sls_structured import SLSConfig

if TYPE_CHECKING:
    from app.core.settings import Settings


class ObservabilityPlugin:
    """Assembles middleware + holds sinks/enricher."""

    def __init__(
        self,
        *,
        enricher: TraceEnricher | None = None,
        sinks: Sequence[Any] | None = None,
        enabled: bool = True,
    ) -> None:
        self.enricher: TraceEnricher = enricher or NoopEnricher()
        self.sinks: list[Any] = list(sinks or [])
        self.enabled = enabled

    def new_middleware(
        self,
        *,
        run_id: str = "",
        thread_id: str = "",
        user_id: str = "",
        turn: int = 1,
        agent_id: str = "",
    ) -> ObservabilityMiddleware | None:
        """Mint a fresh middleware for one run, or ``None`` when disabled."""

        if not self.enabled:
            return None
        return ObservabilityMiddleware(
            run_id=run_id,
            thread_id=thread_id,
            user_id=user_id,
            turn=turn,
            agent_id=agent_id,
            enricher=self.enricher,
            sinks=self.sinks,
        )


def build_plugin(
    settings: "Settings",
    *,
    enricher: TraceEnricher | None = None,
) -> ObservabilityPlugin:
    """Build the plugin from settings.

    A derived project passes its own ``enricher`` (e.g. a ``KnowledgeSearchEnricher``)
    to lift domain fields into ``TurnRecord.attributes``; the scaffold uses
    ``NoopEnricher``.
    """

    sinks: list[Any] = []
    sinks.append(
        SLSStructuredSink(
            SLSConfig(
                enabled=settings.sls_enabled,
                endpoint=settings.sls_endpoint,
                access_key_id=settings.sls_access_key_id,
                access_key_secret=settings.sls_access_key_secret,
                project=settings.sls_project,
                logstore=settings.sls_logstore,
                topic=settings.sls_topic,
                source=settings.app_name,
            )
        )
    )
    sinks.append(LocalJsonlSink(settings.observability_local_dir))
    return ObservabilityPlugin(
        enricher=enricher,
        sinks=sinks,
        enabled=settings.observability_enabled,
    )
