"""Platform adapter contracts and safe operation results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.domain.app_models import AppEntry, DiscoveryDiagnostics, LaunchSpec, ProcessSpec


class AdapterError(RuntimeError):
    """Expected adapter failure that can be shown as a short API error."""


@dataclass(frozen=True)
class OperationResult:
    success: bool
    message: str
    error_code: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    best_effort: bool = False


class DiscoveryPort(Protocol):
    def discover(self) -> tuple[list[AppEntry], DiscoveryDiagnostics]: ...


class LauncherPort(Protocol):
    def launch(self, spec: LaunchSpec) -> OperationResult: ...


class ProcessPort(Protocol):
    def close(self, process: ProcessSpec, *, force: bool = False) -> OperationResult: ...


class MediaPort(Protocol):
    def send(self, action: str) -> OperationResult: ...


class VolumePort(Protocol):
    def change(self, action: str, steps: int = 1) -> OperationResult: ...


class SystemPort(Protocol):
    def lock(self) -> OperationResult: ...

    def shutdown(self) -> OperationResult: ...

    def session_info(self) -> dict[str, Any]: ...


class WebsitePort(Protocol):
    def open(self, url: str) -> OperationResult: ...
