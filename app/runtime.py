"""Composition root for the agent."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from app.adapters.windows.discovery import WindowsApplicationDiscovery
from app.adapters.windows.firewall import WindowsFirewallInspector
from app.adapters.windows.launcher import WindowsLauncher, WindowsWebsiteOpener
from app.adapters.windows.media import WindowsMediaController
from app.adapters.windows.process import WindowsProcessController
from app.adapters.windows.system import WindowsSystemController
from app.adapters.windows.volume import WindowsVolumeController
from app.adapters.spotify.catalog import SpotifyCatalog
from app.adapters.spotify.client import SpotifyApiClient
from app.adapters.spotify.player import SpotifyPlayer
from app.catalog import ApplicationCatalog
from app.infrastructure.config import AppConfig, load_config
from app.infrastructure.logging import configure_logging
from app.infrastructure.spotify_auth import SpotifyAuthManager, SpotifyTokenStore
from app.services.app_service import ApplicationService, WebsiteCatalog
from app.services.command_parser import CommandParser
from app.services.command_service import CommandService
from app.services.shutdown_service import ShutdownConfirmationService
from app.services.spotify_clarification import SpotifyClarificationStore
from app.services.spotify_service import SpotifyService


@dataclass
class AgentRuntime:
    config: AppConfig
    catalog: ApplicationCatalog
    website_catalog: WebsiteCatalog
    parser: CommandParser
    application_service: ApplicationService
    command_service: CommandService
    spotify_auth: SpotifyAuthManager
    spotify_service: SpotifyService
    system: Any
    firewall: Any
    logger: Any
    started_at: float
    startup_refresh: bool = True

    def uptime_seconds(self) -> int:
        return max(0, int(time.monotonic() - self.started_at))

    def info(self) -> dict[str, Any]:
        session = self.system.session_info()
        return {
            "version": _version(),
            "bind_address": self.config.bind_address,
            "port": self.config.port,
            "application_count": len(self.catalog.entries()),
            "last_refresh": self.catalog.last_refresh,
            "interactive_session": session,
            "firewall": self.firewall.inspect_firewall_rule(),
            "network_profiles": self.firewall.inspect_network_profile(),
            "diagnostics_available": True,
        }


def _version() -> str:
    try:
        from app import __version__

        return __version__
    except ImportError:
        return "0.1.0"


def build_runtime(
    config: AppConfig | None = None,
    *,
    discovery=None,
    launcher=None,
    process_controller=None,
    website_opener=None,
    media=None,
    volume=None,
    system=None,
    firewall=None,
    startup_refresh: bool = True,
    spotify_service=None,
) -> AgentRuntime:
    cfg = config or load_config()
    cfg.ensure_directories()
    logger = configure_logging(cfg.log_path, cfg.log_level)
    discovery = discovery or WindowsApplicationDiscovery(manual_apps=cfg.manual_apps, application_aliases=cfg.application_aliases)
    launcher = launcher or WindowsLauncher()
    process_controller = process_controller or WindowsProcessController()
    website_opener = website_opener or WindowsWebsiteOpener()
    media = media or WindowsMediaController()
    volume = volume or WindowsVolumeController()
    system = system or WindowsSystemController()
    firewall = firewall or WindowsFirewallInspector()
    catalog = ApplicationCatalog(discovery, cfg.cache_path)
    catalog.load_cache()
    website_catalog = WebsiteCatalog(cfg.websites)
    aliases = tuple(value for entry in cfg.websites for value in (entry.display_name, *entry.aliases))
    parser = CommandParser(aliases)
    application_service = ApplicationService(catalog, launcher, process_controller, website_opener, website_catalog)
    spotify_client = SpotifyApiClient()
    spotify_auth = SpotifyAuthManager(
        client_id=cfg.spotify_client_id,
        redirect_uri=cfg.spotify_redirect_uri,
        token_store=SpotifyTokenStore(cfg.spotify_token_file),
        client=spotify_client,
    )
    if spotify_service is None:
        spotify_catalog = SpotifyCatalog(spotify_client)
        spotify_player = SpotifyPlayer(
            spotify_client,
            device_name=cfg.spotify_device_name,
            open_spotify=lambda: application_service.open_app(app_query="Spotify"),
        )
        spotify_service = SpotifyService(
            spotify_auth,
            spotify_catalog,
            spotify_player,
            clarification_store=SpotifyClarificationStore(),
        )
    command_service = CommandService(
        application_service,
        media,
        volume,
        system,
        ShutdownConfirmationService(cfg.shutdown_confirmation_seconds),
        spotify=spotify_service,
    )
    runtime = AgentRuntime(
        cfg,
        catalog,
        website_catalog,
        parser,
        application_service,
        command_service,
        spotify_auth,
        spotify_service,
        system,
        firewall,
        logger,
        time.monotonic(),
        startup_refresh,
    )
    session = system.session_info()
    if session.get("warning"):
        logger.warning("interactive session warning: %s", session["warning"])
    return runtime
