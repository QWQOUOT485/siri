"""Spotify intent orchestration behind the command-service seam."""

from __future__ import annotations

import re
from typing import Any

from app.adapters.spotify.client import SpotifyApiError
from app.adapters.windows.base import OperationResult
from app.domain.actions import ActionName, SPOTIFY_ACTIONS, ValidatedAction
from app.domain.chinese import normalize_chinese_text
from app.domain.semantic_memory import SemanticEntity
from app.infrastructure.spotify_auth import SpotifyAuthError

from .memory_learner import MemoryLearningEvent
from .spotify_clarification import ClarificationRecoveryRequest, ClarificationSelection, SpotifyClarificationStore


_PROVIDER_REASON = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


class SpotifyService:
    """Resolve safe Spotify actions without exposing tokens or raw API access."""

    def __init__(
        self,
        auth,
        catalog,
        player,
        clarification_store=None,
        *,
        entity_recovery=None,
        memory_learner=None,
        metrics=None,
    ) -> None:
        self.auth = auth
        self.catalog = catalog
        self.player = player
        self.clarification_store = clarification_store or SpotifyClarificationStore()
        self.entity_recovery = entity_recovery
        self.memory_learner = memory_learner
        self.metrics = metrics

    def execute(self, command: ValidatedAction, *, source_text: str | None = None) -> OperationResult:
        if command.action not in SPOTIFY_ACTIONS:
            return OperationResult(False, "不支援這個 Spotify action。", "INVALID_SPOTIFY_ACTION")
        if command.action is ActionName.SPOTIFY_PLAY_TRACK and self._version_value(command.version_hint) == "live":
            return OperationResult(
                False,
                "目前只支援正式錄音版本，不播放 Live／演唱會候選。",
                "SPOTIFY_LIVE_UNSUPPORTED",
            )
        try:
            access_token = self.auth.get_access_token()
        except SpotifyAuthError as exc:
            return OperationResult(False, str(exc), exc.error_code)

        try:
            return self._execute_with_token(command, access_token, source_text=source_text)
        except SpotifyApiError as exc:
            if exc.status_code == 401:
                try:
                    refreshed_token = self.auth.refresh_access_token()
                except SpotifyAuthError as auth_error:
                    return OperationResult(False, str(auth_error), auth_error.error_code)
                try:
                    return self._execute_with_token(command, refreshed_token, source_text=source_text)
                except SpotifyApiError as retry_error:
                    return self._api_error(retry_error)
            return self._api_error(exc)

    def execute_clarification(self, text: str, clarification_token: str) -> OperationResult:
        """Play only the trusted candidate selected from a live server context."""

        selection = self.clarification_store.select(clarification_token, text)
        if selection.recovery_request is not None:
            return self._execute_recovery_request(clarification_token, selection)
        if selection.track is None:
            if selection.error_code == "SPOTIFY_CLARIFICATION_NEXT_PAGE":
                return self._next_page_result(selection)
            data = self._selection_data(selection)
            return OperationResult(
                False,
                self._clarification_error_message(selection.error_code),
                selection.error_code or "SPOTIFY_CLARIFICATION_INVALID",
                data,
            )

        try:
            access_token = self.auth.get_access_token()
        except SpotifyAuthError as exc:
            return OperationResult(False, str(exc), exc.error_code)

        try:
            result = self._play_candidate(access_token, selection.track)
            return self._learn_after_success(result, selection.observed_alias, selection.track)
        except SpotifyApiError as exc:
            if exc.status_code == 401:
                try:
                    refreshed_token = self.auth.refresh_access_token()
                except SpotifyAuthError as auth_error:
                    return OperationResult(False, str(auth_error), auth_error.error_code)
                try:
                    result = self._play_candidate(refreshed_token, selection.track)
                    return self._learn_after_success(result, selection.observed_alias, selection.track)
                except SpotifyApiError as retry_error:
                    return self._api_error(retry_error)
            return self._api_error(exc)

    def _execute_with_token(
        self,
        command: ValidatedAction,
        access_token: str,
        *,
        source_text: str | None = None,
    ) -> OperationResult:
        if command.action is ActionName.SPOTIFY_RESUME:
            return self.player.resume(access_token)
        if command.action is ActionName.SPOTIFY_PAUSE:
            return self.player.pause(access_token)
        if command.action is ActionName.SPOTIFY_NEXT:
            return self.player.next(access_token)
        if command.action is ActionName.SPOTIFY_PREVIOUS:
            return self.player.previous(access_token)
        if command.action is ActionName.SPOTIFY_SHUFFLE_ON:
            return self.player.shuffle(access_token, enabled=True)
        if command.action is ActionName.SPOTIFY_SHUFFLE_OFF:
            return self.player.shuffle(access_token, enabled=False)
        if command.action is ActionName.SPOTIFY_REPEAT_OFF:
            return self.player.repeat(access_token, "off")
        if command.action is ActionName.SPOTIFY_REPEAT_TRACK:
            return self.player.repeat(access_token, "track")
        if command.action is ActionName.SPOTIFY_REPEAT_CONTEXT:
            return self.player.repeat(access_token, "context")
        if command.action is ActionName.SPOTIFY_CONTINUE:
            return self.player.continue_playback(access_token)

        if self._version_value(command.version_hint) == "live":
            return OperationResult(
                False,
                "目前只支援正式錄音版本，不播放 Live／演唱會候選。",
                "SPOTIFY_LIVE_UNSUPPORTED",
            )

        artist = command.artist
        if self.entity_recovery is not None and artist:
            recovered = self.entity_recovery.recover(artist)
            if recovered.exact_hit and recovered.canonical_name:
                artist = recovered.canonical_name

        resolution = self.catalog.find_track(
            command.track or "",
            artist,
            command.album,
            version_hint=command.version_hint,
            source_text=source_text,
            access_token=access_token,
        )
        if resolution.track is None:
            if resolution.ambiguous:
                candidates = tuple(resolution.candidates[:3])
                if candidates:
                    return self._create_clarification(
                        command,
                        artist,
                        source_text,
                        candidates,
                        recovery_candidates=resolution.recovery_candidates,
                        recovery_offset=self._recovery_offset(artist),
                    )

            recovered = self._recover_candidates(
                command,
                artist,
                source_text,
                access_token,
                offset=0,
            )
            if recovered:
                return self._create_clarification(
                    command,
                    artist,
                    source_text,
                    recovered[:3],
                    recovery_candidates=recovered,
                    # This title-first fetch produced the initial public
                    # clarification page. It is not a user-visible
                    # continuation, so both continuation counters remain at
                    # zero; the server-owned request offset already advances
                    # the next provider page to 10.
                    recovery_rounds=0,
                    provider_fetches=0,
                    recovery_offset=self._recovery_offset(artist, after_fetch=True),
                )
            if resolution.ambiguous:
                return OperationResult(False, f"Spotify 無法判斷歌曲 {command.track}。", "SPOTIFY_AMBIGUOUS_TRACK")
            return OperationResult(
                False,
                f"Spotify 找不到歌曲 {command.track}。",
                resolution.retry_signal or "SPOTIFY_TRACK_NOT_FOUND",
            )
        return self._play_candidate(access_token, resolution.track)

    def _create_clarification(
        self,
        command: ValidatedAction,
        artist: str | None,
        source_text: str | None,
        candidates,
        *,
        recovery_candidates=(),
        recovery_rounds: int = 0,
        provider_fetches: int = 0,
        recovery_offset: int = 0,
    ) -> OperationResult:
        trusted = tuple(candidates[:3])
        if not trusted:
            return OperationResult(
                False,
                f"Spotify 無法判斷歌曲 {command.track}。",
                "SPOTIFY_AMBIGUOUS_TRACK",
            )
        recovery_request = None
        if callable(getattr(self.catalog, "recover_candidates", None)):
            recovery_request = ClarificationRecoveryRequest(
                track=command.track or "",
                artist=artist,
                album=command.album,
                version_hint=self._version_value(command.version_hint),
                source_text=source_text,
                offset=max(0, min(int(recovery_offset), 50)),
            )
        token = self.clarification_store.create(
            trusted,
            observed_alias=command.artist,
            recovery_candidates=tuple(recovery_candidates),
            recovery_request=recovery_request,
            recovery_rounds=recovery_rounds,
            provider_fetches=provider_fetches,
        )
        if self.metrics is not None:
            self.metrics.increment("recovery_clarification")
        options = self._options(trusted)
        details = []
        if command.album:
            details.append(f"專輯：{command.album}")
        if command.version_hint and self._version_value(command.version_hint) != "live":
            details.append(f"版本：{command.version_hint.value}")
        detail_suffix = f"（{'／'.join(details)}）" if details else ""
        return OperationResult(
            False,
            self._clarification_message(command.track or "歌曲", options, detail_suffix),
            "SPOTIFY_CLARIFICATION_REQUIRED",
            self._clarification_data(token, options),
        )

    def _recover_candidates(
        self,
        command: ValidatedAction,
        artist: str | None,
        source_text: str | None,
        access_token: str,
        *,
        offset: int,
        exclude_track_ids: tuple[str, ...] = (),
    ):
        recover = getattr(self.catalog, "recover_candidates", None)
        if not callable(recover):
            return ()
        return tuple(
            recover(
                command.track or "",
                artist,
                command.album,
                version_hint=command.version_hint,
                source_text=source_text,
                access_token=access_token,
                exclude_track_ids=exclude_track_ids,
                offset=offset,
            )
        )

    @staticmethod
    def _recovery_offset(artist: str | None, *, after_fetch: bool = False) -> int:
        # A failed artist-constrained search needs a fresh title-first page;
        # a bare-title search uses the next server-owned Spotify offset.
        if artist:
            return 10 if after_fetch else 0
        return 10

    def _execute_recovery_request(
        self,
        clarification_token: str,
        selection: ClarificationSelection,
    ) -> OperationResult:
        request = selection.recovery_request
        fetch_index = selection.recovery_fetch_index
        if request is None or fetch_index is None:
            return OperationResult(
                False,
                "找不到這個歌曲選擇，請重新說出歌曲。",
                "SPOTIFY_CLARIFICATION_INVALID",
            )
        try:
            access_token = self.auth.get_access_token()
        except SpotifyAuthError as exc:
            self.clarification_store.cancel_recovery(clarification_token, fetch_index)
            return OperationResult(False, str(exc), exc.error_code)

        offset = min(50, request.offset + (fetch_index - 1) * 10)
        try:
            candidates = self._recover_candidates(
                ValidatedAction(
                    action=ActionName.SPOTIFY_PLAY_TRACK,
                    track=request.track,
                    artist=request.artist,
                    album=request.album,
                    version_hint=request.version_hint,
                ),
                request.artist,
                request.source_text,
                access_token,
                offset=offset,
                exclude_track_ids=selection.shown_track_ids,
            )
        except SpotifyApiError as exc:
            if exc.status_code == 401:
                try:
                    access_token = self.auth.refresh_access_token()
                    candidates = self._recover_candidates(
                        ValidatedAction(
                            action=ActionName.SPOTIFY_PLAY_TRACK,
                            track=request.track,
                            artist=request.artist,
                            album=request.album,
                            version_hint=request.version_hint,
                        ),
                        request.artist,
                        request.source_text,
                        access_token,
                        offset=offset,
                        exclude_track_ids=selection.shown_track_ids,
                    )
                except SpotifyAuthError as auth_error:
                    self.clarification_store.cancel_recovery(clarification_token, fetch_index)
                    return OperationResult(False, str(auth_error), auth_error.error_code)
                except SpotifyApiError as retry_error:
                    self.clarification_store.cancel_recovery(clarification_token, fetch_index)
                    return self._api_error(retry_error)
            else:
                self.clarification_store.cancel_recovery(clarification_token, fetch_index)
                return self._api_error(exc)

        page = self.clarification_store.complete_recovery(clarification_token, fetch_index, candidates)
        if page.error_code == "SPOTIFY_CLARIFICATION_NEXT_PAGE":
            return self._next_page_result(page)
        data = self._selection_data(page)
        return OperationResult(
            False,
            self._clarification_error_message(page.error_code),
            page.error_code or "SPOTIFY_CLARIFICATION_INVALID",
            data,
        )

    def _next_page_result(self, selection: ClarificationSelection) -> OperationResult:
        options = self._options(selection.candidates)
        data = self._clarification_data(selection.clarification_token or "", options)
        return OperationResult(
            False,
            self._next_page_message(options),
            "SPOTIFY_CLARIFICATION_REQUIRED",
            data,
        )

    def _selection_data(self, selection: ClarificationSelection) -> dict[str, Any]:
        if not selection.clarification_token:
            return {}
        options = self._options(selection.candidates)
        return self._clarification_data(selection.clarification_token, options)

    def _play_candidate(self, access_token: str, track) -> OperationResult:
        result = self.player.resume(access_token, track)
        if result.success:
            result.data.setdefault("track_name", track.track_name)
            result.data.setdefault("artist_names", list(track.artist_names))
            result.data.setdefault("album_name", track.album_name)
        return result

    def _learn_after_success(self, result: OperationResult, observed_alias: str | None, track) -> OperationResult:
        if not result.success or not observed_alias or self.memory_learner is None:
            return result
        entity = self._artist_entity(track)
        if entity is None:
            return result
        try:
            self.memory_learner.learn(
                MemoryLearningEvent(
                    observed_alias=observed_alias,
                    trusted_entity=entity,
                    clarification_selected=True,
                    playback_succeeded=True,
                )
            )
        except Exception:
            # Alias learning is optional; a memory failure must never turn a
            # successful trusted Spotify playback into a command failure.
            pass
        return result

    @staticmethod
    def _artist_entity(track) -> SemanticEntity | None:
        names = getattr(track, "artist_names", ())
        ids = getattr(track, "artist_ids", ())
        if not names or not ids:
            return None
        artist_name = str(names[0]).strip()
        provider_id = ids[0]
        if not artist_name or not isinstance(provider_id, str) or not provider_id:
            return None
        try:
            return SemanticEntity(
                entity_type="artist",
                provider="spotify",
                provider_entity_id=provider_id,
                canonical_name=artist_name,
                normalized_name=normalize_chinese_text(artist_name),
            )
        except Exception:
            return None

    @classmethod
    def _clarification_data(cls, token: str, options: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "clarification_required": True,
            "clarification_type": "spotify_track",
            "clarification_token": token,
            "options": options,
            "candidates": options,
        }

    @classmethod
    def _options(cls, tracks) -> list[dict[str, Any]]:
        return [
            {
                "ordinal": index,
                "label": cls._option_label(track),
                "track_name": track.track_name,
                "artist_names": list(track.artist_names),
                "album_name": track.album_name,
            }
            for index, track in enumerate(tracks, start=1)
        ]

    @staticmethod
    def _option_label(track) -> str:
        artists = "、".join(track.artist_names)
        album = f"（專輯：{track.album_name}）" if track.album_name else ""
        return f"{artists} — {track.track_name}{album}"

    @classmethod
    def _clarification_message(cls, track_name: str, options: list[dict[str, Any]], detail_suffix: str) -> str:
        option_text = "；".join(f"第{option['ordinal']}首，{option['label']}" for option in options)
        return f"找到多個可能的 {track_name}{detail_suffix}：{option_text}。請說第一首、第二首或第三首；如果都不是，請說換一批。"

    @classmethod
    def _next_page_message(cls, options: list[dict[str, Any]]) -> str:
        option_text = "；".join(f"第{option['ordinal']}首，{option['label']}" for option in options)
        return f"好，換一批候選：{option_text}。請說第一首、第二首或第三首；如果都不是，請說換一批。"

    @staticmethod
    def _clarification_error_message(error_code: str | None) -> str:
        return {
            "SPOTIFY_CLARIFICATION_EXPIRED": "歌曲選擇已過期，請重新說出歌曲。",
            "SPOTIFY_CLARIFICATION_USED": "歌曲選擇已使用過，請重新說出歌曲。",
            "SPOTIFY_CLARIFICATION_ATTEMPTS_EXHAUSTED": "歌曲選擇嘗試次數已用完，請重新說出歌曲。",
            "SPOTIFY_CLARIFICATION_UNCLEAR": "我無法判斷你選哪一首，請說第一首、第二首、第三首，或說歌手／專輯。",
            "SPOTIFY_CLARIFICATION_RECOVERY_EXHAUSTED": "沒有更多新的候選歌曲了；請選目前這一批，或重新說出更完整的歌手／專輯。",
            "SPOTIFY_CLARIFICATION_RECOVERY_IN_PROGRESS": "我正在準備下一批候選，請稍後再說換一批。",
            "SPOTIFY_CLARIFICATION_RECOVERY_INVALID": "歌曲候選恢復狀態無效，請重新說出歌曲。",
        }.get(error_code or "", "找不到這個歌曲選擇，請重新說出歌曲。")

    @staticmethod
    def _version_value(version_hint) -> str | None:
        if version_hint is None:
            return None
        return str(getattr(version_hint, "value", version_hint)).casefold()

    @staticmethod
    def _public_track(track) -> dict[str, Any]:
        return {
            "track_name": track.track_name,
            "artist_names": list(track.artist_names),
            "album_name": track.album_name,
        }

    @staticmethod
    def _api_error(error: SpotifyApiError) -> OperationResult:
        if error.status_code == 403:
            reason = (
                error.reason
                if isinstance(error.reason, str) and _PROVIDER_REASON.fullmatch(error.reason) is not None
                else None
            )
            data = {"provider_reason": reason} if reason is not None else {}
            return OperationResult(False, str(error), "SPOTIFY_FORBIDDEN", data)
        if error.status_code == 429:
            data = {"retry_after_seconds": error.retry_after_seconds} if error.retry_after_seconds is not None else {}
            return OperationResult(False, str(error), "SPOTIFY_RATE_LIMITED", data)
        if error.status_code is None:
            return OperationResult(False, str(error), "SPOTIFY_NETWORK_ERROR")
        return OperationResult(False, str(error), "SPOTIFY_API_ERROR")
