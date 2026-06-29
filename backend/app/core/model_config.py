"""Build an AgentScope 2.0 chat model from scaffold settings.

The scaffold drives an ``agentscope.agent.Agent`` directly (native path), so we
construct a concrete ``ChatModelBase`` from configuration + an injected API key
instead of going through the Agent Service credential REST resources.
"""

from __future__ import annotations

import os
from typing import Mapping

from app.core.settings import Settings


# Map the configured ``credential_type`` to the AgentScope 2.0 credential class.
# Both OpenAI and DashScope (OpenAI-compatible) are common scaffold targets.
_CREDENTIAL_TYPES = {
    "openai_credential": "OpenAICredential",
    "dashscope_credential": "DashScopeCredential",
    "anthropic_credential": "AnthropicCredential",
    "deepseek_credential": "DeepSeekCredential",
    "moonshot_credential": "MoonshotCredential",
    "gemini_credential": "GeminiCredential",
    "xai_credential": "XAICredential",
    "ollama_credential": "OllamaCredential",
}


def resolve_model_api_key(
    settings: Settings,
    environ: Mapping[str, str] | None = None,
) -> str:
    env = environ if environ is not None else os.environ
    api_key = env.get(settings.model_api_key_env) or settings.model_api_key
    if not api_key:
        raise RuntimeError(
            f"Missing model API key. Set {settings.model_api_key_env} before "
            "starting the AgentScope agent runtime.",
        )
    return api_key


def build_credential(settings: Settings, api_key: str):
    """Create an AgentScope 2.0 credential object from settings."""

    import agentscope.credential as credentials

    class_name = _CREDENTIAL_TYPES.get(settings.model_credential_type)
    if class_name is None:
        raise RuntimeError(
            f"Unsupported model credential type "
            f"{settings.model_credential_type!r}. "
            f"Supported: {', '.join(sorted(_CREDENTIAL_TYPES))}.",
        )
    credential_cls = getattr(credentials, class_name)

    data: dict[str, object] = {"id": "scaffold-credential", "api_key": api_key}
    if settings.model_base_url:
        data["base_url"] = settings.model_base_url
    return credential_cls(**data)


def build_chat_model(
    settings: Settings,
    environ: Mapping[str, str] | None = None,
):
    """Build a concrete ``ChatModelBase`` ready to drive an ``Agent``."""

    api_key = resolve_model_api_key(settings, environ)
    credential = build_credential(settings, api_key)
    model_cls = credential.get_chat_model_class()
    parameters = (
        model_cls.Parameters(**settings.model_parameters)
        if settings.model_parameters
        else None
    )
    return model_cls(
        credential=credential,
        model=settings.model_name,
        parameters=parameters,
        stream=True,
    )
