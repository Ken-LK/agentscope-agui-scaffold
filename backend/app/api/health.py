"""Health endpoint.

Surfaces configuration readiness — model key, scaffold config file, agent
profiles, and the Redis configuration surface — so a degraded deploy reports a
concrete reason instead of failing opaquely on the first run.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request

from app.core.settings import Settings, get_settings

router = APIRouter(tags=["health"])


def _model_key_present(settings: Settings) -> bool:
    return bool(
        settings.model_api_key or os.environ.get(settings.model_api_key_env),
    )


def build_health(
    settings: Settings,
    degraded_reason: str | None = None,
) -> dict[str, Any]:
    model_key_present = _model_key_present(settings)
    config_exists = Path(settings.scaffold_config_path).exists()
    redis_configured = bool(settings.redis_host and settings.redis_port)

    reasons: list[str] = []
    if not model_key_present:
        reasons.append(
            f"missing model API key ({settings.model_api_key_env})",
        )
    if not settings.model_name:
        reasons.append("model name is not configured")
    if degraded_reason:
        reasons.append(degraded_reason)

    return {
        "status": "ok" if not reasons else "degraded",
        "degradedReason": "; ".join(reasons) or None,
        "checks": {
            "configFile": {
                "path": settings.scaffold_config_path,
                "exists": config_exists,
            },
            "model": {
                "name": settings.model_name or None,
                "apiKeyEnv": settings.model_api_key_env,
                "apiKeyPresent": model_key_present,
            },
            "redis": {
                # Configuration surface only: health does not ping external
                # systems by default.
                "configured": redis_configured,
                "host": settings.redis_host,
                "port": settings.redis_port,
            },
            "agents": {
                "defaultAgentId": settings.default_agent_id,
                "profiles": [p.id for p in settings.agent_profiles],
            },
        },
    }


@router.get("/healthz")
async def healthz(request: Request) -> dict[str, Any]:
    settings = getattr(request.app.state, "settings", None) or get_settings()
    degraded_reason = getattr(request.app.state, "degraded_reason", None)
    return build_health(settings, degraded_reason)
