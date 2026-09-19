import sqlite3
from pathlib import Path

from app.domain.semantic_memory import SemanticEntity
from app.infrastructure.semantic_memory_db import SemanticMemoryDatabase
from app.services.alias_memory import AliasMemory
from app.services.entity_normalizer import EntityNormalizer
from app.services.entity_recovery import EntityRecoveryService


def artist(name: str, provider_id: str = "artist123") -> SemanticEntity:
    normalized = EntityNormalizer().normalize(name)
    return SemanticEntity(
        entity_type="artist",
        provider="spotify",
        provider_entity_id=provider_id,
        canonical_name=name,
        normalized_name=normalized.canonical_text,
    )


def setup_memory(path: Path) -> tuple[SemanticMemoryDatabase, AliasMemory, EntityRecoveryService]:
    database = SemanticMemoryDatabase(path)
    memory = AliasMemory(database)
    return database, memory, EntityRecoveryService(memory)


def confirm(database: SemanticMemoryDatabase, raw_alias: str, target: SemanticEntity):
    normalized = EntityNormalizer().normalize(raw_alias)
    return database.confirm_alias(
        raw_alias=raw_alias,
        normalized_alias=normalized.canonical_text,
        compact_alias=normalized.compact_text,
        entity=target,
        source="trusted_clarification",
    )


def test_exact_confirmed_alias_returns_canonical_name_for_existing_resolver(tmp_path: Path):
    database, memory, recovery = setup_memory(tmp_path / "semantic.sqlite3")
    confirm(database, "Sad overlxrd", artist("SASIOVERLXRD"))
    memory.reload()

    result = recovery.recover("Sad overlxrd")

    assert result.exact_hit is True
    assert result.canonical_name == "SASIOVERLXRD"
    assert result.evidence.automatic_canonicalization_allowed is True
    assert result.evidence.candidates[0].evidence_type == "exact"


def test_unresolved_text_only_returns_fuzzy_candidate_evidence(tmp_path: Path):
    database, memory, recovery = setup_memory(tmp_path / "semantic.sqlite3")
    confirm(database, "Sad overlxrd", artist("SASIOVERLXRD"))
    memory.reload()

    result = recovery.recover("Sad overlord")

    assert result.exact_hit is False
    assert result.canonical_name is None
    assert result.evidence.candidates
    assert result.evidence.candidates[0].evidence_type == "fuzzy"
    assert result.evidence.automatic_canonicalization_allowed is False


def test_conflicted_alias_never_returns_a_canonical_name(tmp_path: Path):
    database, memory, recovery = setup_memory(tmp_path / "semantic.sqlite3")
    confirm(database, "Sad overlxrd", artist("SASIOVERLXRD", "artist123"))
    confirm(database, "Sad overlxrd", artist("OTHER", "artist999"))
    memory.reload()

    result = recovery.recover("Sad overlxrd")

    assert result.canonical_name is None
    assert result.exact_hit is False
    assert result.evidence.conflict is True
    assert result.evidence.automatic_canonicalization_allowed is False


def test_provisional_alias_can_supply_evidence_but_cannot_rewrite(tmp_path: Path):
    path = tmp_path / "semantic.sqlite3"
    database, memory, recovery = setup_memory(path)
    confirm(database, "Sad overlxrd", artist("SASIOVERLXRD"))
    database._connection.execute("UPDATE aliases SET trust_state = 'provisional'")  # fixture state only
    database._connection.commit()
    memory.reload()

    result = recovery.recover("Sad overlxrd")

    assert result.canonical_name is None
    assert result.exact_hit is False
    assert result.evidence.automatic_canonicalization_allowed is False


def test_corrupt_memory_falls_back_without_recovery_authority(tmp_path: Path):
    path = tmp_path / "corrupt.sqlite3"
    path.write_bytes(b"not sqlite")
    _, memory, recovery = setup_memory(path)

    result = recovery.recover("Sad overlxrd")

    assert result.canonical_name is None
    assert result.exact_hit is False
    assert result.evidence.candidates == ()
