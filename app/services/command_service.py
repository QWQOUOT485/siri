"""Execute only validated actions through local services/adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.adapters.windows.base import OperationResult
from app.domain.actions import ActionName, ValidatedAction

from .app_service import ApplicationService
from .shutdown_service import ShutdownConfirmationService


@dataclass(frozen=True)
class ServiceResult:
    success: bool
    status: str
    action: str
    message: str
    error_code: str | None = None
    candidates: list[dict[str, Any]] = field(default_factory=list)
    confirmation_required: bool = False
    confirmation_token: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    clarification_required: bool = False
    clarification_type: str | None = None
    clarification_token: str | None = None
    options: list[dict[str, Any]] = field(default_factory=list)


class CommandService:
    def __init__(self, application_service: ApplicationService, media, volume, system, shutdown: ShutdownConfirmationService, spotify=None) -> None:
        self.application_service = application_service
        self.media = media
        self.volume = volume
        self.system = system
        self.shutdown = shutdown
        self.spotify = spotify

    def execute(self, command: ValidatedAction) -> ServiceResult:
        action = command.action
        if action is ActionName.OPEN_APP:
            return self._operation(action, self.application_service.open_app(app_id=command.app_id, app_query=command.app_query))
        if action is ActionName.CLOSE_APP:
            return self._operation(action, self.application_service.close_app(app_id=command.app_id, app_query=command.app_query))
        if action is ActionName.FORCE_CLOSE_APP:
            return self._operation(action, self.application_service.close_app(app_id=command.app_id, app_query=command.app_query, force=True))
        if action is ActionName.OPEN_WEBSITE:
            return self._operation(action, self.application_service.open_website(website_id=command.website_id, website_query=command.website_query))
        if action is ActionName.REFRESH_APPS:
            return self._operation(action, self.application_service.refresh())
        if action is ActionName.LOCK:
            return self._operation(action, self.system.lock())
        if action is ActionName.REQUEST_SHUTDOWN:
            token, ttl = self.shutdown.request()
            return ServiceResult(True, "confirmation_required", action.value, "確定要關閉 Windows 電腦嗎？", confirmation_required=True, confirmation_token=token, data={"expires_in_seconds": ttl})
        if action is ActionName.CONFIRM_SHUTDOWN:
            valid, error_code = self.shutdown.consume(command.confirmation_token)
            if not valid:
                message = {"SHUTDOWN_TOKEN_EXPIRED": "關機確認已過期。", "SHUTDOWN_TOKEN_REUSED": "這個關機確認已使用過。"}.get(error_code, "關機確認無效。")
                return ServiceResult(False, "error", action.value, message, error_code=error_code)
            return self._operation(action, self.system.shutdown())
        spotify_actions = {
            ActionName.SPOTIFY_RESUME,
            ActionName.SPOTIFY_PAUSE,
            ActionName.SPOTIFY_NEXT,
            ActionName.SPOTIFY_PREVIOUS,
            ActionName.SPOTIFY_PLAY_TRACK,
        }
        if action in spotify_actions:
            if self.spotify is None:
                return ServiceResult(False, "error", action.value, "Spotify 整合尚未設定。", error_code="SPOTIFY_NOT_CONFIGURED")
            return self._operation(action, self.spotify.execute(command))
        if action in {ActionName.VOLUME_UP, ActionName.VOLUME_DOWN, ActionName.MUTE, ActionName.UNMUTE, ActionName.TOGGLE_MUTE}:
            return self._operation(action, self.volume.change(action.value, command.steps))
        return ServiceResult(False, "error", action.value, "不支援這個 action。", error_code="INVALID_ACTION")

    def execute_clarification(self, text: str, clarification_token: str) -> ServiceResult:
        """Complete one Spotify selection using a server-owned context only."""

        action = ActionName.SPOTIFY_PLAY_TRACK
        if self.spotify is None:
            return ServiceResult(False, "error", action.value, "Spotify 整合尚未設定。", error_code="SPOTIFY_NOT_CONFIGURED")
        return self._operation(action, self.spotify.execute_clarification(text, clarification_token))

    @staticmethod
    def _operation(action: ActionName, result: OperationResult) -> ServiceResult:
        data = result.data if isinstance(result.data, dict) else {}
        candidates = data.get("candidates", [])
        options = data.get("options", [])
        return ServiceResult(
            success=result.success,
            status="ok" if result.success else "error",
            action=action.value,
            message=result.message,
            error_code=result.error_code,
            candidates=candidates if isinstance(candidates, list) else [],
            clarification_required=bool(data.get("clarification_required", False)),
            clarification_type=data.get("clarification_type") if isinstance(data.get("clarification_type"), str) else None,
            clarification_token=data.get("clarification_token") if isinstance(data.get("clarification_token"), str) else None,
            options=options if isinstance(options, list) else [],
            data=data,
        )
