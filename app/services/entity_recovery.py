"""Compose exact alias recovery with candidate-only local evidence."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.semantic_memory import NormalizedEntityText, RecoveryCandidateEvidence

from .alias_memory import AliasMemory
from .entity_normalizer import EntityNormalizer


@dataclass(frozen=True)
class EntityRecoveryResult:
    normalized: NormalizedEntityText | None
    canonical_name: str | None
    exact_hit: bool
    evidence: RecoveryCandidateEvidence


class EntityRecoveryService:
    """Interpret artist text without selecting or executing a provider ID."""

    def __init__(self, memory: AliasMemory, normalizer: EntityNormalizer | None = None) -> None:
        self.memory = memory
        self.normalizer = normalizer or memory.normalizer

    def recover(self, value: str) -> EntityRecoveryResult:
        try:
            normalized = self.normalizer.normalize(value)
        except (TypeError, ValueError):
            return EntityRecoveryResult(
                normalized=None,
                canonical_name=None,
                exact_hit=False,
                evidence=RecoveryCandidateEvidence(query=self._empty_query(), candidates=()),
            )

        exact = self.memory.lookup_exact(normalized)
        if exact is not None:
            return EntityRecoveryResult(
                normalized=normalized,
                canonical_name=exact.entity.canonical_name,
                exact_hit=True,
                evidence=RecoveryCandidateEvidence(
                    query=normalized,
                    candidates=(exact,),
                    automatic_canonicalization_allowed=True,
                ),
            )

        conflicts = self.memory.lookup_conflicts(normalized)
        if conflicts.conflict:
            return EntityRecoveryResult(
                normalized=normalized,
                canonical_name=None,
                exact_hit=False,
                evidence=conflicts,
            )

        return EntityRecoveryResult(
            normalized=normalized,
            canonical_name=None,
            exact_hit=False,
            evidence=self.memory.fuzzy_candidates(normalized),
        )

    def canonicalize(self, value: str) -> str | None:
        """Return only the exact confirmed canonical display name, if any."""

        return self.recover(value).canonical_name

    @staticmethod
    def _empty_query() -> NormalizedEntityText:
        return NormalizedEntityText(raw="?", canonical_text="?", compact_text="?", chinese_canonical="?")
