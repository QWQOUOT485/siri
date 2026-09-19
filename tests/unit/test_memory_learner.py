from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.domain.semantic_memory import AliasTrustState, SemanticEntity
from app.infrastructure.semantic_memory_db import SemanticMemoryDatabase
from app.services.alias_memory import AliasMemory
from app.services.entity_normalizer import EntityNormalizer
from app.services.memory_learner import MemoryLearningEvent, MemoryLearner


def entity(provider_entity_id: str, name: str) -> SemanticEntity:
    normalized = EntityNormalizer().normalize(name)
    return SemanticEntity(
        entity_type="artist",
        provider="spotify",
        provider_entity_id=provider_entity_id,
        canonical_name=name,
        normalized_name=normalized.canonical_text,
    )


def learner(path: Path) -> tuple[MemoryLearner, SemanticMemoryDatabase, AliasMemory]:
    database = SemanticMemoryDatabase(path)
    memory = AliasMemory(database)
    return MemoryLearner(database, memory), database, memory


def event(
    alias: str = "Sad overlxrd",
    target: SemanticEntity | None = None,
    *,
    selected: bool = True,
    playback: bool = True,
    evidence_type: str = "trusted_clarification",
) -> MemoryLearningEvent:
    return MemoryLearningEvent(
        observed_alias=alias,
        trusted_entity=target or entity("artist123", "SASIOVERLXRD"),
        clarification_selected=selected,
        playback_succeeded=playback,
        evidence_type=evidence_type,
    )


def test_only_authoritative_clarification_and_success_promotes_alias(tmp_path: Path):
    learner_service, database, memory = learner(tmp_path / "semantic.sqlite3")

    result = learner_service.learn(event())

    assert result.confirmed is True
    assert result.trust_state is AliasTrustState.CONFIRMED
    assert memory.lookup_exact("Sad overlxrd") is not None
    assert database.load_entries()[0].alias.success_count == 1


def test_user_selected_candidate_without_successful_playback_is_not_confirmed(tmp_path: Path):
    learner_service, database, memory = learner(tmp_path / "semantic.sqlite3")

    result = learner_service.learn(event(playback=False))

    assert result.confirmed is False
    assert result.error_code == "MEMORY_PLAYBACK_NOT_CONFIRMED"
    assert database.load_entries() == ()
    assert memory.lookup_exact("Sad overlxrd") is None


def test_ai_or_fuzzy_evidence_cannot_promote_memory(tmp_path: Path):
    learner_service, database, memory = learner(tmp_path / "semantic.sqlite3")

    for evidence_type in ("ai", "fuzzy", "vector", "popularity"):
        result = learner_service.learn(event(evidence_type=evidence_type))
        assert result.confirmed is False
        assert result.error_code == "MEMORY_UNTRUSTED_EVIDENCE"

    assert database.load_entries() == ()
    assert memory.lookup_exact("Sad overlxrd") is None


def test_different_successful_trusted_mapping_becomes_conflicted(tmp_path: Path):
    learner_service, database, memory = learner(tmp_path / "semantic.sqlite3")

    first = learner_service.learn(event())
    second = learner_service.learn(
        event(target=entity("artist999", "Other Artist"))
    )

    assert first.confirmed is True
    assert second.confirmed is False
    assert second.conflicted is True
    assert memory.lookup_exact("Sad overlxrd") is None
    assert {entry.alias.trust_state for entry in database.load_entries()} == {AliasTrustState.CONFLICTED}


def test_concurrent_same_entity_confirmations_are_safe(tmp_path: Path):
    learner_service, database, _memory = learner(tmp_path / "semantic.sqlite3")
    trusted_event = event()

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: learner_service.learn(trusted_event), range(8)))

    assert all(result.confirmed for result in results)
    entries = database.load_entries()
    assert len(entries) == 1
    assert entries[0].alias.confirmation_count == 8


def test_invalid_event_text_fails_closed_without_touching_db(tmp_path: Path):
    learner_service, database, _memory = learner(tmp_path / "semantic.sqlite3")

    result = learner_service.learn(event(alias="bad\ninput"))

    assert result.confirmed is False
    assert result.error_code == "MEMORY_INVALID_ALIAS"
    assert database.load_entries() == ()
