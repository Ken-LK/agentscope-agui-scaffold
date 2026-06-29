"""Frontend manifest: app, agent profiles, suggestions, tools, capabilities.

Lets the workbench drive itself from backend configuration instead of hardcoding
app name, agent list, suggestions, tool catalog, and protocol capabilities.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.core.settings import Settings, get_settings
from app.tools.registry import build_scaffold_tool_specs


def build_manifest(settings: Settings) -> dict[str, Any]:
    default_profile = settings.get_profile(settings.default_agent_id)

    tool_catalog = [
        {
            "name": spec.name,
            "description": spec.description,
            "readOnly": spec.is_read_only,
            "enabled": spec.is_read_only or settings.enable_write_tools,
        }
        for spec in build_scaffold_tool_specs()
    ]

    agent_profiles = [
        {
            "id": profile.id,
            "name": profile.name,
            "reasoning": profile.reasoning,
            "tools": list(profile.tools),
        }
        for profile in (settings.agent_profiles or (default_profile,))
    ]

    return {
        "app": {
            "name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
        },
        "defaultAgentId": settings.default_agent_id,
        "agentProfiles": agent_profiles,
        "suggestions": list(settings.suggestions),
        "toolCatalog": tool_catalog,
        "protocolCapabilities": {
            # reasoning stays off until the frontend REASONING_* path is verified.
            "reasoning": default_profile.reasoning,
            "writeTools": settings.enable_write_tools,
            "confirm": True,
        },
    }


def create_manifest_router(settings: Settings | None = None) -> APIRouter:
    router = APIRouter(tags=["manifest"])

    @router.get("/api/manifest")
    async def manifest() -> dict[str, Any]:
        return build_manifest(settings or get_settings())

    return router
