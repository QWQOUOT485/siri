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
class ClarificationContext:
    candidates: tuple[SpotifyTrackRef, ...]
    expires_at: float
    failed_attempts: int = 0


@dataclass(frozen=True)
class ClarificationSelection:
    track: SpotifyTrackRef | None = None
    error_code: str | None = None
    candidates: tuple[SpotifyTrackRef, ...] = ()
    clarification_token: str | None = None


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
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.ttl_seconds = max(15, min(ttl_seconds, 600))
        self.max_entries = max(1, min(max_entries, 4096))
        self.max_attempts = max(1, min(max_attempts, 3))
        self.clock = clock
        self._contexts: dict[str, ClarificationContext] = {}
        self._used_tokens: dict[str, float] = {}
        self._lock = threading.RLock()

    def create(self, candidates: tuple[SpotifyTrackRef, ...] | list[SpotifyTrackRef]) -> str:
        trusted = tuple(candidates)
        if not trusted or len(trusted) > 3:
            raise ValueError("clarification requires one to three trusted candidates")
        now = self.clock()
        expires_at = now + self.ttl_seconds
        with self._lock:
            self._purge(now)
            while len(self._contexts) >= self.max_entries:
                oldest = min(self._contexts, key=lambda token: self._contexts[token].expires_at)
                self._contexts.pop(oldest, None)
            token = secrets.token_urlsafe(32)
            self._contexts[token] = ClarificationContext(trusted, expires_at)
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

            index = self._selection_index(text, context.candidates)
            if index is None:
                failed_attempts = context.failed_attempts + 1
                if failed_attempts >= self.max_attempts:
                    self._contexts.pop(token, None)
                    self._used_tokens[token] = now + self.ttl_seconds
                    return ClarificationSelection(
                        error_code="SPOTIFY_CLARIFICATION_ATTEMPTS_EXHAUSTED"
                    )
                self._contexts[token] = replace(context, failed_attempts=failed_attempts)
                return ClarificationSelection(
                    error_code="SPOTIFY_CLARIFICATION_UNCLEAR",
                    candidates=context.candidates,
                    clarification_token=token,
                )

            self._contexts.pop(token, None)
            self._used_tokens[token] = now + self.ttl_seconds
            return ClarificationSelection(track=context.candidates[index])

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
