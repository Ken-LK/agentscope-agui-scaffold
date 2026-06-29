"""Application factory.

Builds a plain FastAPI app that exposes the native AgentScope 2.0 ``POST
/ag-ui`` entry plus health. No Agent Service (session / credential / message
bus / workspace) machinery is wired into the main path — the thin AG-UI entry
drives an ``agentscope.agent.Agent`` directly.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.manifest import create_manifest_router
from app.core.logging import configure_logging
from app.core.settings import Settings, get_settings
from app.observability import build_plugin
from app.observability.enricher import TraceEnricher
from app.runtime.agui_runtime import create_agui_router


def create_runtime_app(
    settings: Settings | None = None,
    *,
    enricher: TraceEnricher | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging()

    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Trace observability: assemble the plugin (sinks + enricher) once and mint a
    # per-request capture middleware from it. A derived project passes its own
    # ``enricher`` to lift domain fields into ``TurnRecord.attributes``.
    observability = build_plugin(settings, enricher=enricher)

    app.state.settings = settings
    app.state.observability = observability
    app.state.degraded_reason = None

    app.include_router(health_router)
    app.include_router(create_manifest_router(settings))
    app.include_router(create_agui_router(settings, observability))
    return app
