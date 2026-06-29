"""Runtime settings for the native AgentScope 2.0 AG-UI scaffold."""

from __future__ import annotations

import os
import json
import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any


def _csv(value: str | None, default: list[str]) -> list[str]:
    if value is None or value.strip() == "":
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


def _default_cors_origins() -> list[str]:
    return ["http://localhost:5173", "http://127.0.0.1:5173"]


def _int(value: str | None, default: int) -> int:
    if value is None or value.strip() == "":
        return default
    return int(value)


def _bool(value: str | None, default: bool) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _json_object(value: str | None, default: dict[str, Any]) -> dict[str, Any]:
    if value is None or value.strip() == "":
        return default
    data = json.loads(value)
    if not isinstance(data, dict):
        raise ValueError("MODEL_PARAMETERS_JSON must be a JSON object")
    return data


def _empty_model_parameters() -> dict[str, Any]:
    return {}


def _read_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    result: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            result[key] = value
    return result


def _read_scaffold_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _section(config: dict[str, Any], name: str) -> dict[str, Any]:
    value = config.get(name)
    return value if isinstance(value, dict) else {}


def _config_str(section: dict[str, Any], key: str, default: str) -> str:
    value = section.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def _config_optional_str(
    section: dict[str, Any],
    key: str,
    default: str | None,
) -> str | None:
    value = section.get(key)
    if isinstance(value, str):
        return value.strip() or None
    return default


def _config_int(section: dict[str, Any], key: str, default: int) -> int:
    value = section.get(key)
    if value is None:
        return default
    return int(value)


def _config_optional_int(
    section: dict[str, Any],
    key: str,
    default: int | None,
) -> int | None:
    value = section.get(key)
    if value is None:
        return default
    parsed = int(value)
    return parsed or None


def _config_float(section: dict[str, Any], key: str, default: float) -> float:
    value = section.get(key)
    if value is None:
        return default
    return float(value)


def _config_bool(section: dict[str, Any], key: str, default: bool) -> bool:
    value = section.get(key)
    if value is None:
        return default
    return bool(value)


def _config_str_list(
    section: dict[str, Any],
    key: str,
    default: list[str],
) -> list[str]:
    value = section.get(key)
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return [item.strip() for item in value if item.strip()]
    return default


def _config_dict(
    section: dict[str, Any],
    key: str,
    default: dict[str, Any],
) -> dict[str, Any]:
    value = section.get(key)
    return dict(value) if isinstance(value, dict) else default


def _env_optional_str(
    env: dict[str, str],
    key: str,
    default: str | None,
) -> str | None:
    if key not in env:
        return default
    return env.get(key) or None


# All read-only scaffold tools; the default tool set for a profile that does
# not list its own tools. Write tools are opted in per profile + global flag.
_DEFAULT_PROFILE_TOOLS = (
    "calculator",
    "current_datetime",
    "knowledge_search",
    "list_notes",
)


@dataclass(frozen=True)
class AgentProfileConfig:
    """A configurable agent profile selectable via forwardedProps.agentId."""

    id: str
    name: str
    system_prompt: str = ""
    tools: tuple[str, ...] = _DEFAULT_PROFILE_TOOLS
    reasoning: bool = False
    max_iters: int = 20


def _parse_profiles(
    config: dict[str, Any],
    agent_config: dict[str, Any],
    runtime_config: dict[str, Any],
) -> tuple[tuple[AgentProfileConfig, ...], str]:
    """Parse ``[agent_profiles.*]`` (or a legacy ``[agent]``) into profiles."""

    raw = config.get("agent_profiles")
    profiles: list[AgentProfileConfig] = []
    if isinstance(raw, dict) and raw:
        for profile_id, body in raw.items():
            body = body if isinstance(body, dict) else {}
            tools = body.get("tools")
            profiles.append(
                AgentProfileConfig(
                    id=str(profile_id),
                    name=_config_str(body, "name", str(profile_id)),
                    system_prompt=_config_str(body, "system_prompt", ""),
                    tools=tuple(tools)
                    if isinstance(tools, list)
                    else _DEFAULT_PROFILE_TOOLS,
                    reasoning=_config_bool(body, "reasoning", False),
                    max_iters=_config_int(body, "max_iters", 20),
                ),
            )
    else:
        # Legacy single-agent config: synthesise a ``default`` profile.
        profiles.append(
            AgentProfileConfig(
                id="default",
                name=_config_str(agent_config, "name", "AgentScope Agent"),
                system_prompt=_config_str(agent_config, "system_prompt", ""),
                max_iters=_config_int(agent_config, "max_iters", 20),
            ),
        )

    profile_ids = {p.id for p in profiles}
    default_agent = _config_str(runtime_config, "default_agent", "")
    if default_agent not in profile_ids:
        default_agent = profiles[0].id
    return tuple(profiles), default_agent


@dataclass(frozen=True)
class Settings:
    app_name: str = "AgentScope App"
    app_version: str = "0.1.0"
    environment: str = "local"
    cors_origins: list[str] = field(default_factory=_default_cors_origins)
    suggestions: tuple[str, ...] = ()
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str | None = None
    redis_key_ttl_seconds: int | None = None
    redis_socket_timeout_seconds: float | None = None
    redis_session_prefix: str = "agentscope:session:"
    # Observability / trace capture (see app/observability + docs).
    observability_enabled: bool = True
    observability_local_dir: str = "./.observability"
    sls_enabled: bool = False
    sls_endpoint: str = ""
    sls_project: str = ""
    sls_logstore: str = "agentscope-agui"
    sls_topic: str = "agentscope-agui"
    sls_access_key_id: str = field(default="", repr=False, compare=False)
    sls_access_key_secret: str = field(default="", repr=False, compare=False)
    workspace_base_dir: str = "./.workspaces"
    workspace_ttl_seconds: float = 3600.0
    agui_default_user_id: str = "local-user"
    scaffold_config_path: str = "./config/scaffold.toml"
    agent_profiles: tuple[AgentProfileConfig, ...] = ()
    default_agent_id: str = "default"
    enable_write_tools: bool = False
    model_request_timeout_seconds: float = 60.0
    model_credential_type: str = "openai_credential"
    model_name: str = ""
    model_api_key_env: str = "DASHSCOPE_API_KEY"
    model_api_key: str | None = field(default=None, repr=False, compare=False)
    model_base_url: str | None = None
    model_parameters: dict[str, Any] = field(
        default_factory=_empty_model_parameters,
    )

    @property
    def redis_url(self) -> str:
        """Compose a ``redis://`` URL from the discrete Redis fields (used by the
        patrol session-drill tooling; override with ``--redis-url`` for a remote)."""

        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    def get_profile(self, agent_id: str | None) -> AgentProfileConfig:
        """Resolve a profile by id, falling back to the default profile."""

        profiles = self.agent_profiles or (
            AgentProfileConfig(id="default", name="AgentScope Agent"),
        )
        if agent_id:
            for profile in profiles:
                if profile.id == agent_id:
                    return profile
        for profile in profiles:
            if profile.id == self.default_agent_id:
                return profile
        return profiles[0]

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> "Settings":
        root = Path(__file__).resolve().parents[2]
        env = (
            environ
            if environ is not None
            else {**_read_dotenv(root / ".env"), **os.environ}
        )
        config_path = Path(
            env.get(
                "SCAFFOLD_CONFIG_PATH",
                str(root / "config" / "scaffold.toml"),
            ),
        )
        if not config_path.is_absolute():
            config_path = root / config_path
        config = _read_scaffold_config(config_path)
        app_config = _section(config, "app")
        redis_config = _section(config, "redis")
        workspace_config = _section(config, "workspace")
        agui_config = _section(config, "agui")
        agent_config = _section(config, "agent")
        runtime_config = _section(config, "runtime")
        tools_config = _section(config, "tools")
        model_config = _section(config, "model")
        observability_config = _section(config, "observability")
        sls_config = _section(config, "sls")
        agent_profiles, default_agent_id = _parse_profiles(
            config,
            agent_config,
            runtime_config,
        )
        model_api_key_env = env.get(
            "MODEL_API_KEY_ENV",
            _config_str(model_config, "api_key_env", cls.model_api_key_env),
        )
        return cls(
            app_name=env.get(
                "APP_NAME",
                _config_str(app_config, "name", cls.app_name),
            ),
            app_version=env.get(
                "APP_VERSION",
                _config_str(app_config, "version", cls.app_version),
            ),
            environment=env.get(
                "APP_ENV",
                _config_str(app_config, "environment", cls.environment),
            ),
            cors_origins=_csv(
                env.get("CORS_ORIGINS"),
                _config_str_list(
                    app_config,
                    "cors_origins",
                    _default_cors_origins(),
                ),
            ),
            suggestions=tuple(
                _config_str_list(app_config, "suggestions", []),
            ),
            redis_host=env.get(
                "REDIS_HOST",
                _config_str(redis_config, "host", cls.redis_host),
            ),
            redis_port=_int(
                env.get("REDIS_PORT"),
                _config_int(redis_config, "port", cls.redis_port),
            ),
            redis_db=_int(
                env.get("REDIS_DB"),
                _config_int(redis_config, "db", cls.redis_db),
            ),
            redis_password=_env_optional_str(
                env,
                "REDIS_PASSWORD",
                _config_optional_str(
                    redis_config,
                    "password",
                    cls.redis_password,
                ),
            ),
            redis_key_ttl_seconds=(
                _int(
                    env.get("REDIS_KEY_TTL_SECONDS"),
                    _config_optional_int(
                        redis_config,
                        "key_ttl_seconds",
                        cls.redis_key_ttl_seconds,
                    )
                    or 0,
                )
                or None
            ),
            redis_socket_timeout_seconds=(
                float(
                    env.get(
                        "REDIS_SOCKET_TIMEOUT_SECONDS",
                        _config_float(
                            redis_config,
                            "socket_timeout_seconds",
                            0,
                        ),
                    ),
                )
                or None
            ),
            redis_session_prefix=env.get(
                "REDIS_SESSION_PREFIX",
                _config_str(
                    redis_config,
                    "session_prefix",
                    cls.redis_session_prefix,
                ),
            ),
            observability_enabled=_bool(
                env.get("OBSERVABILITY_ENABLED"),
                _config_bool(
                    observability_config,
                    "enabled",
                    cls.observability_enabled,
                ),
            ),
            observability_local_dir=env.get(
                "OBSERVABILITY_LOCAL_DIR",
                _config_str(
                    observability_config,
                    "local_dir",
                    str(root / ".observability"),
                ),
            ),
            sls_enabled=_bool(
                env.get("SLS_ENABLED"),
                _config_bool(sls_config, "enabled", cls.sls_enabled),
            ),
            sls_endpoint=env.get(
                "SLS_ENDPOINT",
                _config_str(sls_config, "endpoint", cls.sls_endpoint),
            ),
            sls_project=env.get(
                "SLS_PROJECT",
                _config_str(sls_config, "project", cls.sls_project),
            ),
            sls_logstore=env.get(
                "SLS_LOGSTORE",
                _config_str(sls_config, "logstore", cls.sls_logstore),
            ),
            sls_topic=env.get(
                "SLS_TOPIC",
                _config_str(sls_config, "topic", cls.sls_topic),
            ),
            sls_access_key_id=env.get(
                "SLS_ACCESS_KEY_ID",
                _config_str(sls_config, "access_key_id", cls.sls_access_key_id),
            ),
            sls_access_key_secret=env.get(
                "SLS_ACCESS_KEY_SECRET",
                _config_str(
                    sls_config,
                    "access_key_secret",
                    cls.sls_access_key_secret,
                ),
            ),
            workspace_base_dir=env.get(
                "WORKSPACE_BASE_DIR",
                _config_str(
                    workspace_config,
                    "base_dir",
                    str(root / ".workspaces"),
                ),
            ),
            workspace_ttl_seconds=float(
                env.get(
                    "WORKSPACE_TTL_SECONDS",
                    _config_float(
                        workspace_config,
                        "ttl_seconds",
                        cls.workspace_ttl_seconds,
                    ),
                ),
            ),
            agui_default_user_id=env.get(
                "AGUI_DEFAULT_USER_ID",
                _config_str(
                    agui_config,
                    "default_user_id",
                    cls.agui_default_user_id,
                ),
            ),
            scaffold_config_path=str(config_path),
            agent_profiles=agent_profiles,
            default_agent_id=default_agent_id,
            enable_write_tools=_bool(
                env.get("ENABLE_WRITE_TOOLS"),
                _config_bool(
                    tools_config,
                    "enable_write_tools",
                    cls.enable_write_tools,
                ),
            ),
            model_request_timeout_seconds=float(
                env.get(
                    "MODEL_REQUEST_TIMEOUT_SECONDS",
                    _config_float(
                        model_config,
                        "request_timeout_seconds",
                        cls.model_request_timeout_seconds,
                    ),
                ),
            ),
            model_credential_type=env.get(
                "MODEL_CREDENTIAL_TYPE",
                _config_str(
                    model_config,
                    "credential_type",
                    cls.model_credential_type,
                ),
            ),
            model_name=env.get(
                "MODEL_NAME",
                _config_str(model_config, "name", cls.model_name),
            ),
            model_api_key_env=model_api_key_env,
            model_api_key=env.get(model_api_key_env) or None,
            model_base_url=_env_optional_str(
                env,
                "MODEL_BASE_URL",
                _config_optional_str(
                    model_config,
                    "base_url",
                    cls.model_base_url,
                ),
            ),
            model_parameters=_json_object(
                env.get("MODEL_PARAMETERS_JSON"),
                _config_dict(
                    model_config,
                    "parameters",
                    _empty_model_parameters(),
                ),
            ),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
