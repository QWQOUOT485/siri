from __future__ import annotations

from pathlib import Path

import pytest

from app.adapters.windows.base import OperationResult
from app.domain.app_models import AppEntry, AppType, DiscoveryDiagnostics, LaunchMethod, LaunchSource, ProcessSpec, WebsiteEntry
from app.infrastructure.config import AppConfig
from app.runtime import build_runtime


def entry(name: str, *, aliases=(), target: str | None = None, source: str = "test", launch_source=LaunchSource.TRUSTED, process_names=()) -> AppEntry:
    return AppEntry(
        app_id=f"app_{name.casefold().replace(' ', '_')}_12345678",
        display_name=name,
        normalized_name=name.casefold(),
        aliases=tuple(alias.casefold() for alias in aliases),
        launch_method=LaunchMethod.EXECUTABLE if target else None,
        launch_target=target,
        executable_path=target,
        process=ProcessSpec(executable_names=tuple(process_names), reliable=bool(process_names)) if process_names else None,
        source=source,
        app_type=AppType.DESKTOP if launch_source is not LaunchSource.METADATA_ONLY else AppType.METADATA,
        confidence=0.95 if launch_source is not LaunchSource.METADATA_ONLY else 0.4,
        launch_source=launch_source,
        launch_confidence=0.95 if launch_source is not LaunchSource.METADATA_ONLY else 0.0,
        metadata_confidence=0.9,
    )


class FakeDiscovery:
    def __init__(self, entries):
        self._entries = entries

    def discover(self):
        return list(self._entries), DiscoveryDiagnostics(scanned_sources=["fake"], source_counts={"fake": len(self._entries)})


class FakeLauncher:
    def __init__(self):
        self.specs = []

    def launch(self, spec):
        self.specs.append(spec)
        return OperationResult(True, "started")


class FakeProcess:
    def __init__(self):
        self.calls = []

    def close(self, process, *, force=False):
        self.calls.append((process, force))
        return OperationResult(True, "closed")


class FakeMedia:
    def __init__(self):
        self.actions = []

    def send(self, action):
        self.actions.append(action)
        return OperationResult(True, "media")


class FakeVolume:
    def __init__(self):
        self.actions = []
        self.exact_calls = []

    def change(self, action, steps=1):
        self.actions.append((action, steps))
        return OperationResult(True, "volume")

    def set_volume(self, volume_percent):
        self.exact_calls.append(volume_percent)
        return OperationResult(True, "exact volume", data={"level": volume_percent / 100})


class FakeSystem:
    def __init__(self):
        self.lock_calls = 0
        self.shutdown_calls = 0

    def session_info(self):
        return {"interactive": True, "session_id": 1, "user": "tester", "warning": None}

    def lock(self):
        self.lock_calls += 1
        return OperationResult(True, "locked")

    def shutdown(self):
        self.shutdown_calls += 1
        return OperationResult(True, "shutdown")


class FakeFirewall:
    def inspect_firewall_rule(self):
        return {"available": True, "exists": False}

    def inspect_network_profile(self):
        return {"available": True, "profiles": []}


@pytest.fixture
def sample_entries():
    return [
        entry("Discord", aliases=("discord",), target="C:\\Program Files\\Discord\\Discord.exe", process_names=("discord.exe",)),
        entry("Visual Studio 2026", aliases=("vs 2026",), target="C:\\Program Files\\Visual Studio\\devenv.exe", process_names=("devenv.exe",)),
        entry("Visual Studio Code", aliases=("vscode", "vs code", "code"), target="C:\\Program Files\\Microsoft VS Code\\Code.exe", process_names=("code.exe",)),
        entry("Adobe Photoshop 2026", aliases=("photoshop", "adobe photoshop"), target="C:\\Program Files\\Adobe\\Photoshop.exe", process_names=("photoshop.exe",)),
        entry("Installed Only", launch_source=LaunchSource.METADATA_ONLY),
    ]


@pytest.fixture
def fake_runtime(tmp_path: Path, sample_entries):
    config_dir = tmp_path / "config"
    runtime_dir = tmp_path / "runtime"
    logs_dir = tmp_path / "logs"
    config_dir.mkdir()
    config = AppConfig(
        root_dir=tmp_path,
        config_dir=config_dir,
        runtime_dir=runtime_dir,
        logs_dir=logs_dir,
        api_key="test-key",
        allowed_networks=("127.0.0.0/8",),
        websites=(
            WebsiteEntry(website_id="youtube_music", display_name="YouTube Music", aliases=("youtube music",), url="https://music.youtube.com/"),
        ),
    )
    launcher = FakeLauncher()
    process = FakeProcess()
    media = FakeMedia()
    volume = FakeVolume()
    system = FakeSystem()
    runtime = build_runtime(
        config,
        discovery=FakeDiscovery(sample_entries),
        launcher=launcher,
        process_controller=process,
        website_opener=FakeLauncher(),
        media=media,
        volume=volume,
        system=system,
        firewall=FakeFirewall(),
        startup_refresh=False,
    )
    runtime.catalog.refresh()
    return runtime, launcher, process, media, volume, system
