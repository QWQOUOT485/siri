"""Short-lived, server-owned Spotify candidate clarification contexts."""

from __future__ import annotations

import re
import secrets
import threading
import time
from dataclasses import dataclass, replace
from typing import Callable

from app.adapters.spotify.catalog import SpotifyTrackRef
from app.domain.chinese import normalize_chinese_text


@dataclass(frozen=True)
class ClarificationRecoveryRequest:
    """Server-created search inputs for one bounded next-candidate fetch."""

    track: str
    artist: str | None = None
    album: str | None = None
    version_hint: str | None = None
    source_text: str | None = None
    offset: int = 0

    def __post_init__(self) -> None:
        for name in ("track", "artist", "album", "source_text"):
            value = getattr(self, name)
            if value is None:
                continue
            if not isinstance(value, str) or len(value) > 300 or any(ord(char) < 32 or ord(char) == 127 for char in value):
                raise ValueError("clarification recovery text is invalid")
        if not isinstance(self.track, str) or not self.track.strip():
            raise ValueError("clarification recovery requires a track")
        if self.version_hint is not None and (
            not isinstance(self.version_hint, str) or len(self.version_hint) > 16
        ):
            raise ValueError("clarification recovery version is invalid")
        if isinstance(self.offset, bool) or not isinstance(self.offset, int) or not 0 <= self.offset <= 50:
            raise ValueError("clarification recovery offset is invalid")


@dataclass(frozen=True)
class ClarificationContext:
    candidates: tuple[SpotifyTrackRef, ...]
    expires_at: float
    failed_attempts: int = 0
    observed_alias: str | None = None
    recovery_candidates: tuple[SpotifyTrackRef, ...] = ()
    recovery_request: ClarificationRecoveryRequest | None = None
    # recovery_fetches counts provider fetches, while recovery_rounds counts
    # every successful user-visible continuation page. Keeping those counters
    # separate prevents a local page from bypassing the round cap or changing
    # the provider offset.
    recovery_fetches: int = 0
    recovery_rounds: int = 0
    recovery_pending: bool = False
    recovery_exhausted: bool = False
    shown_track_ids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ClarificationSelection:
    track: SpotifyTrackRef | None = None
    error_code: str | None = None
    candidates: tuple[SpotifyTrackRef, ...] = ()
    clarification_token: str | None = None
    observed_alias: str | None = None
    recovery_request: ClarificationRecoveryRequest | None = None
    recovery_fetch_index: int | None = None
    shown_track_ids: tuple[str, ...] = ()


class SpotifyClarificationStore:
    """Bounded in-memory TTL store for trusted candidate references.

    A context tolerates a small number of unclear Siri follow-ups, then is
    invalidated.  All reads and state transitions happen under one lock so a
    token cannot be selected twice or exceed its failed-attempt bound under
    concurrent requests.
    """

    def __init__(
        self,
        *,
        ttl_seconds: int = 60,
        max_entries: int = 256,
        max_attempts: int = 3,
        max_recovery_rounds: int = 2,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.ttl_seconds = max(15, min(ttl_seconds, 600))
        self.max_entries = max(1, min(max_entries, 4096))
        self.max_attempts = max(1, min(max_attempts, 3))
        self.max_recovery_rounds = max(1, min(max_recovery_rounds, 3))
        self.clock = clock
        self._contexts: dict[str, ClarificationContext] = {}
        self._used_tokens: dict[str, float] = {}
        self._lock = threading.RLock()

    def create(
        self,
        candidates: tuple[SpotifyTrackRef, ...] | list[SpotifyTrackRef],
        *,
        observed_alias: str | None = None,
        recovery_candidates: tuple[SpotifyTrackRef, ...] | list[SpotifyTrackRef] = (),
        recovery_request: ClarificationRecoveryRequest | None = None,
        recovery_fetches: int = 0,
        recovery_rounds: int | None = None,
        provider_fetches: int | None = None,
    ) -> str:
        trusted = self._dedupe(candidates)
        if not trusted or len(trusted) > 3:
            raise ValueError("clarification requires one to three trusted candidates")
        if recovery_request is not None and not isinstance(recovery_request, ClarificationRecoveryRequest):
            raise ValueError("clarification recovery request is invalid")
        if isinstance(recovery_fetches, bool) or not isinstance(recovery_fetches, int):
            raise ValueError("clarification recovery fetch count is invalid")
        if recovery_rounds is None:
            recovery_rounds = recovery_fetches
        if provider_fetches is None:
            provider_fetches = recovery_fetches
        for name, value in (
            ("clarification recovery round count", recovery_rounds),
            ("clarification provider fetch count", provider_fetches),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{name} is invalid")
        recovery_rounds = max(0, min(recovery_rounds, self.max_recovery_rounds))
        provider_fetches = max(0, min(provider_fetches, self.max_recovery_rounds))
        shown_track_ids = frozenset(track.track_id for track in trusted)
        recovery_pool = tuple(
            track
            for track in self._dedupe(recovery_candidates)
            if track.track_id not in shown_track_ids
        )[: max(0, 20 - len(shown_track_ids))]
        now = self.clock()
        expires_at = now + self.ttl_seconds
        with self._lock:
            self._purge(now)
            while len(self._contexts) >= self.max_entries:
                oldest = min(self._contexts, key=lambda token: self._contexts[token].expires_at)
                self._contexts.pop(oldest, None)
            token = secrets.token_urlsafe(32)
            self._contexts[token] = ClarificationContext(
                trusted,
                expires_at,
                observed_alias=observed_alias,
                recovery_candidates=recovery_pool,
                recovery_request=recovery_request,
                recovery_fetches=provider_fetches,
                recovery_rounds=recovery_rounds,
                shown_track_ids=shown_track_ids,
            )
            return token

    def select(self, token: str, text: str) -> ClarificationSelection:
        now = self.clock()
        with self._lock:
            # Check the requested context before the general purge.  Otherwise
            # an expired token would be indistinguishable from a random/invalid
            # token, which makes the Siri retry path needlessly unclear.
            context = self._contexts.get(token)
            if context is not None and now >= context.expires_at:
                self._contexts.pop(token, None)
                self._purge(now)
                return ClarificationSelection(error_code="SPOTIFY_CLARIFICATION_EXPIRED")

            self._purge(now)
            if token in self._used_tokens:
                return ClarificationSelection(error_code="SPOTIFY_CLARIFICATION_USED")
            context = self._contexts.get(token)
            if context is None:
                return ClarificationSelection(error_code="SPOTIFY_CLARIFICATION_INVALID")

            recovery_requested = self._is_recovery_request(text)
            if recovery_requested:
                return self._request_recovery_page(token, context)
            if context.recovery_pending:
                return ClarificationSelection(
                    error_code="SPOTIFY_CLARIFICATION_RECOVERY_IN_PROGRESS",
                    candidates=context.candidates,
                    clarification_token=token,
                    observed_alias=context.observed_alias,
                )

            index = self._selection_index(text, context.candidates)
            if index is None:
                failed_attempts = context.failed_attempts + 1
                if failed_attempts >= self.max_attempts:
                    self._contexts.pop(token, None)
                    self._used_tokens[token] = now + self.ttl_seconds
                    return ClarificationSelection(
                        error_code="SPOTIFY_CLARIFICATION_ATTEMPTS_EXHAUSTED",
                        observed_alias=context.observed_alias,
                    )
                self._contexts[token] = replace(context, failed_attempts=failed_attempts)
                return ClarificationSelection(
                    error_code="SPOTIFY_CLARIFICATION_UNCLEAR",
                    candidates=context.candidates,
                    clarification_token=token,
                    observed_alias=context.observed_alias,
                )

            self._contexts.pop(token, None)
            self._used_tokens[token] = now + self.ttl_seconds
            return ClarificationSelection(
                track=context.candidates[index],
                observed_alias=context.observed_alias,
            )

    def complete_recovery(
        self,
        token: str,
        recovery_fetch_index: int,
        candidates: tuple[SpotifyTrackRef, ...] | list[SpotifyTrackRef],
    ) -> ClarificationSelection:
        """Commit one server-fetched page into the existing context."""

        now = self.clock()
        with self._lock:
            self._purge(now)
            context = self._contexts.get(token)
            if context is None:
                if token in self._used_tokens:
                    return ClarificationSelection(error_code="SPOTIFY_CLARIFICATION_USED")
                return ClarificationSelection(error_code="SPOTIFY_CLARIFICATION_INVALID")
            if (
                not context.recovery_pending
                or context.recovery_fetches + 1 != recovery_fetch_index
            ):
                return ClarificationSelection(
                    error_code="SPOTIFY_CLARIFICATION_RECOVERY_INVALID",
                    candidates=context.candidates,
                    clarification_token=token,
                    observed_alias=context.observed_alias,
                )

            available = max(0, 20 - len(context.shown_track_ids))
            trusted = tuple(
                track
                for track in self._dedupe(candidates)
                if track.track_id not in context.shown_track_ids
            )[:available]
            page = trusted[:3]
            remaining = trusted[3:]
            if not page:
                self._contexts[token] = replace(
                    context,
                    recovery_fetches=recovery_fetch_index,
                    recovery_candidates=(),
                    recovery_pending=False,
                    recovery_exhausted=True,
                )
                return ClarificationSelection(
                    error_code="SPOTIFY_CLARIFICATION_RECOVERY_EXHAUSTED",
                    candidates=context.candidates,
                    clarification_token=token,
                    observed_alias=context.observed_alias,
                )

            shown = frozenset((*context.shown_track_ids, *(track.track_id for track in page)))
            next_token = self._rotate_context(
                token,
                context,
                candidates=page,
                recovery_candidates=remaining,
                recovery_fetches=recovery_fetch_index,
                recovery_rounds=context.recovery_rounds + 1,
                shown_track_ids=shown,
                now=now,
            )
            return ClarificationSelection(
                error_code="SPOTIFY_CLARIFICATION_NEXT_PAGE",
                candidates=page,
                clarification_token=next_token,
                observed_alias=context.observed_alias,
            )

    def cancel_recovery(self, token: str, recovery_fetch_index: int) -> None:
        """Release an in-flight recovery marker after a provider/auth failure."""

        now = self.clock()
        with self._lock:
            self._purge(now)
            context = self._contexts.get(token)
            if (
                context is None
                or not context.recovery_pending
                or context.recovery_fetches + 1 != recovery_fetch_index
            ):
                return
            self._contexts[token] = replace(
                context,
                recovery_pending=False,
            )

    def _request_recovery_page(self, token: str, context: ClarificationContext) -> ClarificationSelection:
        if context.recovery_pending:
            return ClarificationSelection(
                error_code="SPOTIFY_CLARIFICATION_RECOVERY_IN_PROGRESS",
                candidates=context.candidates,
                clarification_token=token,
                observed_alias=context.observed_alias,
            )

        if context.recovery_exhausted or context.recovery_rounds >= self.max_recovery_rounds:
            return ClarificationSelection(
                error_code="SPOTIFY_CLARIFICATION_RECOVERY_EXHAUSTED",
                candidates=context.candidates,
                clarification_token=token,
                observed_alias=context.observed_alias,
            )

        page = self._next_page(context)
        if page:
            shown = frozenset((*context.shown_track_ids, *(track.track_id for track in page)))
            remaining = tuple(
                track for track in context.recovery_candidates if track.track_id not in shown
            )
            next_token = self._rotate_context(
                token,
                context,
                candidates=page,
                recovery_candidates=remaining,
                recovery_fetches=context.recovery_fetches,
                recovery_rounds=context.recovery_rounds + 1,
                shown_track_ids=shown,
                now=self.clock(),
            )
            return ClarificationSelection(
                error_code="SPOTIFY_CLARIFICATION_NEXT_PAGE",
                candidates=page,
                clarification_token=next_token,
                observed_alias=context.observed_alias,
            )

        if context.recovery_request is None or context.recovery_fetches >= self.max_recovery_rounds:
            return ClarificationSelection(
                error_code="SPOTIFY_CLARIFICATION_RECOVERY_EXHAUSTED",
                candidates=context.candidates,
                clarification_token=token,
                observed_alias=context.observed_alias,
            )

        fetch_index = context.recovery_fetches + 1
        self._contexts[token] = replace(context, recovery_pending=True)
        return ClarificationSelection(
            error_code="SPOTIFY_CLARIFICATION_RECOVERY_REQUESTED",
            clarification_token=token,
            observed_alias=context.observed_alias,
            recovery_request=context.recovery_request,
            recovery_fetch_index=fetch_index,
            shown_track_ids=tuple(context.shown_track_ids),
        )

    def _rotate_context(
        self,
        old_token: str,
        context: ClarificationContext,
        *,
        candidates: tuple[SpotifyTrackRef, ...],
        recovery_candidates: tuple[SpotifyTrackRef, ...],
        recovery_fetches: int,
        recovery_rounds: int,
        shown_track_ids: frozenset[str],
        now: float,
    ) -> str:
        """Atomically retire one continuation token and issue its successor."""

        if recovery_rounds > self.max_recovery_rounds:
            raise ValueError("clarification recovery round limit exceeded")
        self._contexts.pop(old_token, None)
        self._used_tokens[old_token] = now + self.ttl_seconds
        self._purge(now)
        while len(self._contexts) >= self.max_entries:
            oldest = min(self._contexts, key=lambda token: self._contexts[token].expires_at)
            self._contexts.pop(oldest, None)
        new_token = secrets.token_urlsafe(32)
        while new_token in self._contexts or new_token in self._used_tokens:
            new_token = secrets.token_urlsafe(32)
        self._contexts[new_token] = ClarificationContext(
            candidates=tuple(candidates),
            expires_at=now + self.ttl_seconds,
            observed_alias=context.observed_alias,
            recovery_candidates=tuple(recovery_candidates),
            recovery_request=context.recovery_request,
            recovery_fetches=recovery_fetches,
            recovery_rounds=recovery_rounds,
            shown_track_ids=shown_track_ids,
        )
        return new_token

    @staticmethod
    def _next_page(context: ClarificationContext) -> tuple[SpotifyTrackRef, ...]:
        available = max(0, 20 - len(context.shown_track_ids))
        if available <= 0:
            return ()
        seen = set(context.shown_track_ids)
        return tuple(track for track in context.recovery_candidates if track.track_id not in seen)[: min(3, available)]

    @staticmethod
    def _dedupe(candidates: tuple[SpotifyTrackRef, ...] | list[SpotifyTrackRef]) -> tuple[SpotifyTrackRef, ...]:
        result: list[SpotifyTrackRef] = []
        seen: set[str] = set()
        for candidate in candidates:
            if not isinstance(candidate, SpotifyTrackRef) or candidate.track_id in seen:
                continue
            seen.add(candidate.track_id)
            result.append(candidate)
        return tuple(result)

    def _purge(self, now: float) -> None:
        expired = [token for token, context in self._contexts.items() if now >= context.expires_at]
        for token in expired:
            self._contexts.pop(token, None)
        used_expired = [token for token, expires_at in self._used_tokens.items() if now >= expires_at]
        for token in used_expired:
            self._used_tokens.pop(token, None)

    @classmethod
    def _selection_index(cls, text: str, candidates: tuple[SpotifyTrackRef, ...]) -> int | None:
        normalized = normalize_chinese_text(text or "")
        compact = re.sub(r"[\s,，。.!！?？:：]", "", normalized)
        recovery_forms = {
            "都不是",
            "不是这些",
            "换一批",
            "再一批",
            "noneofthese",
            "notthese",
            "anotherbatch",
            "nextbatch",
            "differentones",
        }
        if any(form in compact and compact != form for form in recovery_forms if len(form) >= 3):
            return None
        ordinal = {
            0: {"一", "1", "第一首", "第1首", "第一個", "第1個", "first", "thefirst"},
            1: {"二", "2", "第二首", "第2首", "第二個", "第2個", "second", "thesecond"},
            2: {"三", "3", "第三首", "第3首", "第三個", "第3個", "third", "thethird"},
        }
        for index, forms in ordinal.items():
            normalized_forms = {
                re.sub(r"[\s,，。.!！?？:：]", "", normalize_chinese_text(form))
                for form in forms
            }
            if compact in normalized_forms or any(compact.endswith(form) for form in normalized_forms if len(form) > 1):
                return index if index < len(candidates) else None

        query = normalized.strip()
        if not query:
            return None
        matches: list[int] = []
        for index, candidate in enumerate(candidates):
            labels = [normalize_chinese_text(name) for name in candidate.artist_names]
            if candidate.album_name:
                labels.append(normalize_chinese_text(candidate.album_name))
            if any(label and len(label) >= 2 and label in query for label in labels):
                matches.append(index)
        return matches[0] if len(matches) == 1 else None

    @staticmethod
    def _is_recovery_request(text: str) -> bool:
        normalized = normalize_chinese_text(text or "")
        compact = re.sub(r"[\s,，。.!！?？:：]", "", normalized)
        forms = {
            "都不是",
            "不是这些",
            "换一批",
            "再一批",
            "noneofthese",
            "notthese",
            "anotherbatch",
            "nextbatch",
            "differentones",
        }
        return compact in forms
