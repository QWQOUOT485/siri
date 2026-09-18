"""Local configuration loading.

Configuration is deliberately file-based and local.  Remote requests never
write any of these files.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from app.domain.app_models import WebsiteEntry


DEFAULT_ALLOWED_NETWORKS = (
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "127.0.0.0/8",
    "::1/128",
)


def _read_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def _load_yaml(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        import yaml  # type: ignore

        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        return default if value is None else value
    except ImportError:
        # Setup installs PyYAML.  This fallback keeps diagnostics and unit tests
        # useful if a developer imports the project before installing extras.
        return default
    except Exception:
        return default


@dataclass(frozen=True)
class AppConfig:
    root_dir: Path
    config_dir: Path
    runtime_dir: Path
    logs_dir: Path
    api_key: str
    port: int = 8000
    bind_address: str = "0.0.0.0"
    log_level: str = "INFO"
    shutdown_confirmation_seconds: int = 60
    rate_limit_per_minute: int = 120
    allowed_networks: tuple[str, ...] = DEFAULT_ALLOWED_NETWORKS
    websites: tuple[WebsiteEntry, ...] = field(default_factory=tuple)
    manual_apps: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    application_aliases: dict[str, tuple[str, ...]] = field(default_factory=dict)
    spotify_client_id: str = ""
    spotify_redirect_uri: str = "http://127.0.0.1:8000/spotify/callback"
    spotify_device_name: str = ""
    spotify_token_path: Path | None = None

    @property
    def cache_path(self) -> Path:
        return self.runtime_dir / "apps.json"

    @property
    def log_path(self) -> Path:
        return self.logs_dir / "agent.log"

    @property
    def spotify_token_file(self) -> Path:
        return self.spotify_token_path or (self.runtime_dir / "spotify_token.json")

    def ensure_directories(self) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    @property
    def api_key_configured(self) -> bool:
        return bool(self.api_key and not self.api_key.startswith("replace-with-"))


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _env_value(env: Mapping[str, str], dotenv: Mapping[str, str], key: str, default: str) -> str:
    return env.get(key, dotenv.get(key, default))


def _parse_int(value: str, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _website_entries(raw: Any) -> tuple[WebsiteEntry, ...]:
    records = raw.get("websites", []) if isinstance(raw, dict) else []
    result: list[WebsiteEntry] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        try:
            website_id = str(item["id"]).strip().lower()
            display_name = str(item["display_name"]).strip()
            aliases = tuple(str(alias).strip() for alias in item.get("aliases", []) if str(alias).strip())
            url = str(item["url"]).strip()
            if not website_id or not display_name or not url.startswith("https://"):
                continue
            result.append(
                WebsiteEntry(
                    website_id=website_id,
                    display_name=display_name,
                    aliases=aliases,
                    url=url,
                )
            )
        except Exception:
            continue
    return tuple(result)


def load_config(*, root_dir: Path | None = None, environ: Mapping[str, str] | None = None) -> AppConfig:
    root = (root_dir or project_root()).resolve()
    env = environ or os.environ
    dotenv_values = _read_dotenv(root / ".env")
    config_dir_name = _env_value(env, dotenv_values, "SIRI_AGENT_CONFIG_DIR", "config")
    runtime_dir_name = _env_value(env, dotenv_values, "SIRI_AGENT_RUNTIME_DIR", "runtime")
    config_dir = (root / config_dir_name).resolve()
    runtime_dir = (root / runtime_dir_name).resolve()
    logs_dir = (root / "logs").resolve()

    networks_raw = _load_yaml(config_dir / "allowed_networks.yaml", {})
    networks = networks_raw.get("allowed_networks", []) if isinstance(networks_raw, dict) else []
    allowed_networks = tuple(str(value).strip() for value in networks if str(value).strip()) or DEFAULT_ALLOWED_NETWORKS

    manual_raw = _load_yaml(config_dir / "manual_apps.yaml", {})
    manual_apps = manual_raw.get("manual_apps", []) if isinstance(manual_raw, dict) else []
    manual_apps = tuple(item for item in manual_apps if isinstance(item, dict))

    aliases_raw = _load_yaml(config_dir / "app_aliases.yaml", {})
    aliases_section = aliases_raw.get("application_aliases", {}) if isinstance(aliases_raw, dict) else {}
    application_aliases: dict[str, tuple[str, ...]] = {}
    if isinstance(aliases_section, dict):
        for name, aliases in aliases_section.items():
            if isinstance(aliases, (list, tuple)):
                cleaned = tuple(str(value).strip() for value in aliases if str(value).strip())
                if cleaned:
                    application_aliases[str(name).strip()] = cleaned

    token_path_value = _env_value(env, dotenv_values, "SPOTIFY_TOKEN_PATH", "runtime/spotify_token.json")
    token_path = Path(token_path_value)
    if not token_path.is_absolute():
        token_path = root / token_path

    return AppConfig(
        root_dir=root,
        config_dir=config_dir,
        runtime_dir=runtime_dir,
        logs_dir=logs_dir,
        api_key=_env_value(env, dotenv_values, "SIRI_AGENT_API_KEY", ""),
        port=_parse_int(_env_value(env, dotenv_values, "SIRI_AGENT_PORT", "8000"), 8000, 1, 65535),
        bind_address=_env_value(env, dotenv_values, "SIRI_AGENT_BIND", "0.0.0.0"),
        log_level=_env_value(env, dotenv_values, "SIRI_AGENT_LOG_LEVEL", "INFO").upper(),
        shutdown_confirmation_seconds=_parse_int(
            _env_value(env, dotenv_values, "SIRI_AGENT_SHUTDOWN_CONFIRMATION_SECONDS", "60"),
            60,
            15,
            600,
        ),
        rate_limit_per_minute=_parse_int(
            _env_value(env, dotenv_values, "SIRI_AGENT_RATE_LIMIT_PER_MINUTE", "120"),
            120,
            10,
            1000,
        ),
        allowed_networks=allowed_networks,
        websites=_website_entries(_load_yaml(config_dir / "websites.yaml", {})),
        manual_apps=manual_apps,
        application_aliases=application_aliases,
        spotify_client_id=_env_value(env, dotenv_values, "SPOTIFY_CLIENT_ID", "").strip(),
        spotify_redirect_uri=_env_value(
            env,
            dotenv_values,
            "SPOTIFY_REDIRECT_URI",
            "http://127.0.0.1:8000/spotify/callback",
        ).strip(),
        spotify_device_name=_env_value(env, dotenv_values, "SPOTIFY_DEVICE_NAME", "").strip(),
        spotify_token_path=token_path.resolve(),
    )
