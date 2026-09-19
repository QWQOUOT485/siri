"""RAM indexes for exact alias recovery and candidate-only fuzzy evidence."""

from __future__ import annotations

import threading
import time
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

from app.domain.semantic_memory import (
    AliasCandidate,
    AliasTrustState,
    NormalizedEntityText,
    RecoveryCandidateEvidence,
)
from app.infrastructure.semantic_memory_db import SemanticMemoryDatabase, SemanticMemoryEntry

from .entity_normalizer import EntityNormalizer

if TYPE_CHECKING:
    from .semantic_memory_metrics import SemanticMemoryMetrics

try:  # RapidFuzz is installed in the runtime requirements; keep startup safe if absent.
    from rapidfuzz import fuzz as _rapidfuzz
except ImportError:  # pragma: no cover - exercised only in incomplete dev installs
    _rapidfuzz = None


class AliasMemory:
    """Load trusted memory into RAM without owning trust-promotion authority."""

    def __init__(
        self,
        database: SemanticMemoryDatabase,
        normalizer: EntityNormalizer | None = None,
        metrics: "SemanticMemoryMetrics | None" = None,
    ) -> None:
        self.database = database
        self.normalizer = normalizer or EntityNormalizer()
        self.metrics = metrics
        self._lock = threading.RLock()
        self._exact_index: dict[str, AliasCandidate] = {}
        self._conflict_index: dict[str, tuple[AliasCandidate, ...]] = {}
        self._candidate_entries: tuple[SemanticMemoryEntry, ...] = ()
        self.reload()

    @property
    def available(self) -> bool:
        return bool(self.database.available)

    def status_view(self) -> dict[str, int | bool]:
        with self._lock:
            return {
                "available": self.available,
                "confirmed_aliases": len(self._exact_index),
            }

    def reload(self) -> None:
        entries = self.database.load_entries() if self.database.available else ()
        exact: dict[str, list[AliasCandidate]] = {}
        conflicts: dict[str, list[AliasCandidate]] = {}
        candidate_entries: list[SemanticMemoryEntry] = []

        for entry in entries:
            alias = entry.alias
            if not entry.entity.active or not alias.is_active:
                continue
            candidate_entries.append(entry)
            keys = {alias.normalized_alias, alias.compact_alias}
            if alias.trust_state is AliasTrustState.CONFLICTED:
                for key in keys:
                    conflicts.setdefault(key, []).append(
                        AliasCandidate(alias=alias, entity=entry.entity, score=1.0, evidence_type="conflict")
                    )
                continue
            if alias.trust_state is AliasTrustState.CONFIRMED:
                for key in keys:
                    exact.setdefault(key, []).append(
                        AliasCandidate(alias=alias, entity=entry.entity, score=1.0, evidence_type="exact")
                    )

        with self._lock:
            self._candidate_entries = tuple(candidate_entries)
            self._exact_index = {
                key: values[0]
                for key, values in exact.items()
                if len({value.entity.entity_pk for value in values}) == 1
            }
            for key, values in exact.items():
                if len({value.entity.entity_pk for value in values}) > 1:
                    conflicts.setdefault(key, []).extend(
                        AliasCandidate(
                            alias=value.alias,
                            entity=value.entity,
                            score=1.0,
                            evidence_type="conflict",
                        )
                        for value in values
                    )
            self._conflict_index = {
                key: tuple(values[:3]) for key, values in conflicts.items() if values
            }

    def lookup_exact(self, value: str | NormalizedEntityText) -> AliasCandidate | None:
        started = time.perf_counter()
        try:
            normalized = self._normalize(value)
            if normalized is None:
                return None
            with self._lock:
                result = self._exact_index.get(normalized.canonical_text) or self._exact_index.get(
                    normalized.compact_text
                )
            if result is not None and self.metrics is not None:
                self.metrics.increment("semantic_memory_exact_hit")
            return result
        finally:
            if self.metrics is not None:
                self.metrics.observe_ms("alias_lookup_ms", (time.perf_counter() - started) * 1000)

    def lookup_conflicts(self, value: str | NormalizedEntityText) -> RecoveryCandidateEvidence:
        normalized = self._normalize(value)
        if normalized is None:
            return RecoveryCandidateEvidence(query=self._empty_query(value), conflict=False)
        with self._lock:
            values = self._conflict_index.get(normalized.canonical_text) or self._conflict_index.get(
                normalized.compact_text, ()
            )
        if values and self.metrics is not None:
            self.metrics.increment("semantic_memory_conflict")
        return RecoveryCandidateEvidence(query=normalized, candidates=tuple(values[:3]), conflict=bool(values))

    def fuzzy_candidates(
        self,
        value: str | NormalizedEntityText,
        *,
        limit: int = 3,
    ) -> RecoveryCandidateEvidence:
        started = time.perf_counter()
        try:
            normalized = self._normalize(value)
            if normalized is None:
                return RecoveryCandidateEvidence(query=self._empty_query(value), candidates=())
            limit = max(1, min(int(limit), 3))
            with self._lock:
                entries = tuple(self._candidate_entries)
            scored: list[tuple[float, SemanticMemoryEntry]] = []
            for entry in entries:
                if entry.alias.trust_state in {AliasTrustState.CONFLICTED, AliasTrustState.DISABLED}:
                    continue
                score = max(
                    self._ratio(normalized.canonical_text, entry.alias.normalized_alias),
                    self._ratio(normalized.compact_text, entry.alias.compact_alias),
                )
                scored.append((score, entry))
            scored.sort(key=lambda item: (item[0], item[1].alias.alias_pk or 0), reverse=True)
            candidates = tuple(
                AliasCandidate(
                    alias=entry.alias,
                    entity=entry.entity,
                    score=score,
                    evidence_type="fuzzy",
                )
                for score, entry in scored[:limit]
            )
            if candidates and self.metrics is not None:
                self.metrics.increment("semantic_memory_fuzzy_candidate")
            return RecoveryCandidateEvidence(
                query=normalized,
                candidates=candidates,
                conflict=False,
                automatic_canonicalization_allowed=False,
            )
        finally:
            if self.metrics is not None:
                self.metrics.observe_ms("fuzzy_ms", (time.perf_counter() - started) * 1000)

    def _normalize(self, value: str | NormalizedEntityText) -> NormalizedEntityText | None:
        if isinstance(value, NormalizedEntityText):
            return value
        try:
            return self.normalizer.normalize(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _ratio(left: str, right: str) -> float:
        if not left or not right:
            return 0.0
        if _rapidfuzz is not None:
            return float(_rapidfuzz.ratio(left, right)) / 100.0
        return SequenceMatcher(None, left, right).ratio()

    @staticmethod
    def _empty_query(value: str | NormalizedEntityText) -> NormalizedEntityText:
        raw = value if isinstance(value, str) and value else "?"
        return NormalizedEntityText(raw=raw[:1], canonical_text="?", compact_text="?", chinese_canonical="?")
