"""The single automatic trust-promotion authority for Phase 1."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.semantic_memory import AliasTrustState, SemanticEntity
from app.infrastructure.semantic_memory_db import SemanticMemoryDatabase

from .alias_memory import AliasMemory
from .entity_normalizer import EntityNormalizer


@dataclass(frozen=True)
class MemoryLearningEvent:
    """Server-created evidence emitted after clarification and playback.

    The API layer never accepts this object.  SpotifyService creates it only
    from its server-owned clarification context and a successful player result.
    """

    observed_alias: str
    trusted_entity: SemanticEntity
    clarification_selected: bool
    playback_succeeded: bool
    evidence_type: str = "trusted_clarification"


@dataclass(frozen=True)
class MemoryLearningResult:
    confirmed: bool = False
    conflicted: bool = False
    trust_state: AliasTrustState | None = None
    error_code: str | None = None


class MemoryLearner:
    """Promote memory only from the complete trusted clarification event."""

    _AUTHORITATIVE_EVIDENCE = "trusted_clarification"

    def __init__(
        self,
        database: SemanticMemoryDatabase,
        memory: AliasMemory,
        normalizer: EntityNormalizer | None = None,
    ) -> None:
        self.database = database
        self.memory = memory
        self.normalizer = normalizer or EntityNormalizer()

    def learn(self, event: MemoryLearningEvent) -> MemoryLearningResult:
        if not isinstance(event, MemoryLearningEvent):
            return MemoryLearningResult(error_code="MEMORY_INVALID_EVENT")
        if event.evidence_type != self._AUTHORITATIVE_EVIDENCE:
            return MemoryLearningResult(error_code="MEMORY_UNTRUSTED_EVIDENCE")
        if not event.clarification_selected:
            return MemoryLearningResult(error_code="MEMORY_CLARIFICATION_NOT_SELECTED")
        if not event.playback_succeeded:
            return MemoryLearningResult(error_code="MEMORY_PLAYBACK_NOT_CONFIRMED")
        if event.trusted_entity.provider != "spotify" or event.trusted_entity.entity_type != "artist":
            return MemoryLearningResult(error_code="MEMORY_UNTRUSTED_ENTITY")
        try:
            normalized = self.normalizer.normalize(event.observed_alias)
        except (TypeError, ValueError):
            return MemoryLearningResult(error_code="MEMORY_INVALID_ALIAS")

        result = self.database.confirm_alias(
            raw_alias=normalized.raw,
            normalized_alias=normalized.canonical_text,
            compact_alias=normalized.compact_text,
            entity=event.trusted_entity,
            source=self._AUTHORITATIVE_EVIDENCE,
        )
        if result.success:
            self._rebuild_after_commit()
            return MemoryLearningResult(confirmed=True, trust_state=AliasTrustState.CONFIRMED)
        if result.conflict:
            self._rebuild_after_commit()
            return MemoryLearningResult(
                conflicted=True,
                trust_state=AliasTrustState.CONFLICTED,
                error_code=result.error_code or "SEMANTIC_MEMORY_CONFLICT",
            )
        return MemoryLearningResult(
            trust_state=result.trust_state,
            error_code=result.error_code or "SEMANTIC_MEMORY_UNAVAILABLE",
        )

    def _rebuild_after_commit(self) -> None:
        try:
            self.memory.reload()
        except Exception:
            # SQLite is still the source of truth.  A second reload is the
            # safe recovery if a transient RAM/index update failed.
            try:
                self.memory.reload()
            except Exception:
                pass
