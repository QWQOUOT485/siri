from pathlib import Path

import pytest
from pydantic import ValidationError

from app.api.schemas import ActionRequest, CommandRequest
from app.domain.actions import ActionName
from app.domain.semantic_memory import SemanticEntity
from app.infrastructure.semantic_memory_db import SemanticMemoryDatabase
from app.services.alias_memory import AliasMemory
from app.services.entity_normalizer import EntityNormalizer
from app.services.entity_recovery import EntityRecoveryService
from app.services.memory_learner import MemoryLearningEvent, MemoryLearner


def trusted_entity() -> SemanticEntity:
    return SemanticEntity(
        entity_type="artist",
        provider="spotify",
        provider_entity_id="artist123",
        canonical_name="SASIOVERLXRD",
        normalized_name="sasioverlxrd",
    )


def test_client_cannot_submit_memory_authority_fields():
    for extra in (
        {"provider_entity_id": "artist123"},
        {"trust_state": "confirmed"},
        {"memory_db_path": "C:\\memory.sqlite3"},
    ):
        with pytest.raises(ValidationError):
            CommandRequest(text="播放 Stay", **extra)
        with pytest.raises(ValidationError):
            ActionRequest(action=ActionName.SPOTIFY_PLAY_TRACK, track="Stay", **extra)


def test_provider_identity_model_rejects_uri_path_and_client_like_values():
    for value in ("spotify:artist:artist123", "https://evil.example", "C:\\memory.sqlite3", "artist/123"):
        with pytest.raises(ValidationError):
            SemanticEntity(
                entity_type="artist",
                provider="spotify",
                provider_entity_id=value,
                canonical_name="Artist",
                normalized_name="artist",
            )


def test_high_fuzzy_score_stays_candidate_only_without_confirmation(tmp_path: Path):
    database = SemanticMemoryDatabase(tmp_path / "semantic.sqlite3")
    memory = AliasMemory(database)
    normalized = EntityNormalizer().normalize("Sad overlxrd")
    database.confirm_alias(
        raw_alias=normalized.raw,
        normalized_alias=normalized.canonical_text,
        compact_alias=normalized.compact_text,
        entity=trusted_entity(),
        source="trusted_clarification",
    )
    memory.reload()
    recovery = EntityRecoveryService(memory)

    result = recovery.recover("Sad overlord")

    assert result.canonical_name is None
    assert result.evidence.automatic_canonicalization_allowed is False


def test_memory_learner_rejects_an_event_that_is_not_the_server_authority_chain(tmp_path: Path):
    database = SemanticMemoryDatabase(tmp_path / "semantic.sqlite3")
    memory = AliasMemory(database)
    learner = MemoryLearner(database, memory)

    result = learner.learn(
        MemoryLearningEvent(
            observed_alias="Sad overlxrd",
            trusted_entity=trusted_entity(),
            clarification_selected=True,
            playback_succeeded=True,
            evidence_type="ai",
        )
    )

    assert result.confirmed is False
    assert database.load_entries() == ()
