"""Pure application catalog models.

No Windows imports belong in this module.  Keeping these models platform-neutral
lets matching, API serialization, and security tests run anywhere.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LaunchSource(str, Enum):
    TRUSTED = "trusted"
    METADATA_ONLY = "metadata_only"
    MANUAL = "manual"


class AppType(str, Enum):
    DESKTOP = "desktop"
    PACKAGED = "packaged"
    SYSTEM = "system"
    PORTABLE = "portable"
    METADATA = "metadata"


class LaunchMethod(str, Enum):
    EXECUTABLE = "executable"
    SHELL_URI = "shell_uri"
    SHELL_EXECUTE = "shell_execute"


class ProcessSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    executable_paths: tuple[str, ...] = Field(default_factory=tuple)
    executable_names: tuple[str, ...] = Field(default_factory=tuple)
    name_only_system: bool = False
    reliable: bool = False


class AppEntry(BaseModel):
    """Internal catalog record; filesystem targets never go to the remote API."""

    model_config = ConfigDict(extra="forbid")

    app_id: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=240)
    normalized_name: str = Field(min_length=1, max_length=240)
    aliases: tuple[str, ...] = Field(default_factory=tuple)
    launch_method: LaunchMethod | None = None
    launch_target: str | None = None
    executable_path: str | None = None
    process: ProcessSpec | None = None
    source: str = Field(min_length=1, max_length=120)
    app_type: AppType
    aumid: str | None = None
    shortcut_path: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    launch_source: LaunchSource
    launch_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    metadata_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def launchable(self) -> bool:
        return self.launch_source in {LaunchSource.TRUSTED, LaunchSource.MANUAL} and bool(
            self.launch_method and self.launch_target
        )

    def public_view(self) -> dict[str, Any]:
        """Safe representation for iPhone clients; no path, AUMID, or shortcut."""

        return {
            "app_id": self.app_id,
            "display_name": self.display_name,
            "aliases": list(self.aliases),
            "type": self.app_type.value,
            "source": self.source,
            "launch_source": self.launch_source.value,
            "confidence": self.confidence,
            "launchable": self.launchable,
            "process_hint_available": bool(self.process and self.process.reliable),
        }


class LaunchSpec(BaseModel):
    """Launch contract created by the local catalog service only."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    app_id: str = Field(min_length=8, max_length=128)
    method: LaunchMethod
    target: str = Field(min_length=1, max_length=4096)
    arguments: tuple[str, ...] = Field(default_factory=tuple)
    working_directory: str | None = None
    launch_source: LaunchSource
    verified: bool = False
    executable_path: str | None = None


class WebsiteEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    website_id: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=200)
    aliases: tuple[str, ...] = Field(default_factory=tuple)
    url: str = Field(pattern=r"^https://")


class MatchCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_id: str
    display_name: str
    score: float = Field(ge=0.0, le=1.0)
    matched_by: str
    launchable: bool


class MatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    best_match: MatchCandidate | None = None
    candidates: list[MatchCandidate] = Field(default_factory=list)
    ambiguous: bool = False


class DiscoveryDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scanned_sources: list[str] = Field(default_factory=list)
    source_counts: dict[str, int] = Field(default_factory=dict)
    ignored: list[dict[str, str]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
