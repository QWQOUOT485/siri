import sqlite3
from pathlib import Path

from app.domain.semantic_memory import AliasTrustState, SemanticEntity
from app.infrastructure.semantic_memory_db import SemanticMemoryDatabase


def trusted_entity(provider_entity_id: str = "artist123") -> SemanticEntity:
    return SemanticEntity(
        entity_type="artist",
        provider="spotify",
        provider_entity_id=provider_entity_id,
        canonical_name="SASIOVERLXRD" if provider_entity_id == "artist123" else "Other Artist",
        normalized_name="sasioverlxrd" if provider_entity_id == "artist123" else "other artist",
    )


def confirm(db: SemanticMemoryDatabase, raw_alias: str, entity: SemanticEntity):
    return db.confirm_alias(
        raw_alias=raw_alias,
        normalized_alias="sad overlxrd",
        compact_alias="sadoverlxrd",
        entity=entity,
        source="trusted_clarification",
    )


def test_schema_is_created_with_foreign_keys_and_version(tmp_path: Path):
    db = SemanticMemoryDatabase(tmp_path / "semantic.sqlite3")

    assert db.available is True
    assert db.schema_version == 1
    assert db.foreign_keys_enabled is True
    assert {"entities", "aliases", "scope_context", "alias_observations"}.issubset(db.table_names())


def test_confirmed_alias_survives_close_and_restart(tmp_path: Path):
    path = tmp_path / "semantic.sqlite3"
    first = SemanticMemoryDatabase(path)
    result = confirm(first, "Sad overlxrd", trusted_entity())

    assert result.success is True
    assert result.trust_state is AliasTrustState.CONFIRMED
    first.close()

    second = SemanticMemoryDatabase(path)
    entries = second.load_entries()

    assert len(entries) == 1
    assert entries[0].alias.raw_alias == "Sad overlxrd"
    assert entries[0].entity.provider_entity_id == "artist123"


def test_same_confirmation_is_idempotent_and_counts_success(tmp_path: Path):
    db = SemanticMemoryDatabase(tmp_path / "semantic.sqlite3")

    first = confirm(db, "Sad overlxrd", trusted_entity())
    second = confirm(db, "Sad overlxrd", trusted_entity())

    assert first.success is True
    assert second.success is True
    entries = db.load_entries()
    assert entries[0].alias.confirmation_count == 2
    assert entries[0].alias.success_count == 2


def test_different_trusted_entity_confirms_a_conflict_not_last_write_wins(tmp_path: Path):
    db = SemanticMemoryDatabase(tmp_path / "semantic.sqlite3")

    confirm(db, "Sad overlxrd", trusted_entity("artist123"))
    result = confirm(db, "Sad overlxrd", trusted_entity("artist999"))

    assert result.success is False
    assert result.trust_state is AliasTrustState.CONFLICTED
    entries = db.load_entries()
    assert len(entries) == 2
    assert {entry.alias.trust_state for entry in entries} == {AliasTrustState.CONFLICTED}


def test_observations_are_disabled_by_default_and_bounded_when_enabled(tmp_path: Path):
    default_db = SemanticMemoryDatabase(tmp_path / "default.sqlite3")
    assert default_db.record_observation("sad overlxrd", None, "fuzzy", "candidate") is False
    assert default_db.observation_count() == 0

    enabled_db = SemanticMemoryDatabase(
        tmp_path / "enabled.sqlite3", observations_enabled=True, max_observations=1
    )
    assert enabled_db.record_observation("sad overlxrd", None, "fuzzy", "candidate") is True
    assert enabled_db.record_observation("other", None, "fuzzy", "candidate") is False
    assert enabled_db.observation_count() == 1


def test_corrupt_db_disables_memory_without_raising(tmp_path: Path):
    path = tmp_path / "corrupt.sqlite3"
    path.write_bytes(b"not a sqlite database")

    db = SemanticMemoryDatabase(path)

    assert db.available is False
    assert db.load_entries() == ()
    assert confirm(db, "Sad overlxrd", trusted_entity()).success is False


def test_future_schema_version_disables_memory(tmp_path: Path):
    path = tmp_path / "future.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA user_version = 99")
    connection.commit()
    connection.close()

    db = SemanticMemoryDatabase(path)

    assert db.available is False
    assert db.schema_version == 99


def test_locked_db_write_fails_closed(tmp_path: Path):
    path = tmp_path / "locked.sqlite3"
    db = SemanticMemoryDatabase(path, busy_timeout_ms=20)
    lock = sqlite3.connect(path)
    lock.execute("BEGIN EXCLUSIVE")

    try:
        result = confirm(db, "Sad overlxrd", trusted_entity())
    finally:
        lock.rollback()
        lock.close()

    assert result.success is False
    assert result.error_code in {"SEMANTIC_MEMORY_BUSY", "SEMANTIC_MEMORY_UNAVAILABLE"}
