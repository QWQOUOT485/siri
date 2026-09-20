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
from app.infrastructure.semantic_memory_db import SemanticMemoryDatabase
from app.infrastructure.spotify_auth import SpotifyAuthManager, SpotifyTokenStore
from app.services.app_service import ApplicationService, WebsiteCatalog
from app.services.command_parser import CommandParser
from app.services.command_service import CommandService
from app.services.alias_memory import AliasMemory
from app.services.entity_normalizer import EntityNormalizer
from app.services.entity_recovery import EntityRecoveryService
from app.services.local_ai_service import LocalAIService
from app.services.memory_learner import MemoryLearner
from app.services.semantic_memory_metrics import SemanticMemoryMetrics
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
    local_ai_service: LocalAIService
    semantic_memory_db: SemanticMemoryDatabase
    alias_memory: AliasMemory
    memory_learner: MemoryLearner
    entity_recovery: EntityRecoveryService
    metrics: SemanticMemoryMetrics
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
            "local_ai": self.local_ai_service.status_view(),
            "semantic_memory": {
                "enabled": self.config.semantic_memory_enabled,
                **self.alias_memory.status_view(),
            },
            "semantic_memory_metrics": self.metrics.snapshot(),
            "diagnostics_available": True,
        }


def _version() -> str:
    try:
        from app import __version__

        return __version__
    except ImportError:
        return "1.0.0"


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
    metrics = SemanticMemoryMetrics()
    entity_normalizer = EntityNormalizer(metrics=metrics)
    semantic_memory_db = SemanticMemoryDatabase(
        cfg.semantic_memory_file,
        enabled=cfg.semantic_memory_enabled,
        observations_enabled=cfg.semantic_memory_observations_enabled,
        max_aliases=cfg.semantic_memory_max_aliases,
        max_observations=cfg.semantic_memory_max_observations,
    )
    alias_memory = AliasMemory(semantic_memory_db, entity_normalizer, metrics)
    memory_learner = MemoryLearner(semantic_memory_db, alias_memory, entity_normalizer, metrics)
    entity_recovery = EntityRecoveryService(alias_memory, entity_normalizer)
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
            entity_recovery=entity_recovery,
            memory_learner=memory_learner,
            metrics=metrics,
        )
    local_ai_service = LocalAIService.from_config(cfg, logger=logger)
    command_service = CommandService(
        application_service,
        media,
        volume,
        system,
        ShutdownConfirmationService(cfg.shutdown_confirmation_seconds),
        spotify=spotify_service,
    )
    runtime = AgentRuntime(
        config=cfg,
        catalog=catalog,
        website_catalog=website_catalog,
        parser=parser,
        application_service=application_service,
        command_service=command_service,
        spotify_auth=spotify_auth,
        spotify_service=spotify_service,
        system=system,
        firewall=firewall,
        local_ai_service=local_ai_service,
        semantic_memory_db=semantic_memory_db,
        alias_memory=alias_memory,
        memory_learner=memory_learner,
        entity_recovery=entity_recovery,
        metrics=metrics,
        logger=logger,
        started_at=time.monotonic(),
        startup_refresh=startup_refresh,
    )
    session = system.session_info()
    if session.get("warning"):
        logger.warning("interactive session warning: %s", session["warning"])
    return runtime
