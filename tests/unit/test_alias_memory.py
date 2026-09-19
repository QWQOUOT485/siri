from pathlib import Path

from app.domain.semantic_memory import AliasTrustState, SemanticEntity
from app.infrastructure.semantic_memory_db import SemanticMemoryDatabase
from app.services.alias_memory import AliasMemory
from app.services.entity_normalizer import EntityNormalizer


def entity(provider_entity_id: str, name: str) -> SemanticEntity:
    return SemanticEntity(
        entity_type="artist",
        provider="spotify",
        provider_entity_id=provider_entity_id,
        canonical_name=name,
        normalized_name=EntityNormalizer().normalize(name).canonical_text,
    )


def confirm(db: SemanticMemoryDatabase, raw_alias: str, target: SemanticEntity):
    normalized = EntityNormalizer().normalize(raw_alias)
    return db.confirm_alias(
        raw_alias=raw_alias,
        normalized_alias=normalized.canonical_text,
        compact_alias=normalized.compact_text,
        entity=target,
        source="trusted_clarification",
    )


def test_memory_loads_only_confirmed_active_non_conflicted_aliases(tmp_path: Path):
    db = SemanticMemoryDatabase(tmp_path / "semantic.sqlite3")
    confirm(db, "Sad overlxrd", entity("artist123", "SASIOVERLXRD"))
    memory = AliasMemory(db)

    hit = memory.lookup_exact("sad overlxrd")

    assert hit is not None
    assert hit.entity.canonical_name == "SASIOVERLXRD"
    assert hit.alias.trust_state is AliasTrustState.CONFIRMED


def test_exact_lookup_uses_deterministic_compact_form_but_never_fuzzy_guess(tmp_path: Path):
    db = SemanticMemoryDatabase(tmp_path / "semantic.sqlite3")
    confirm(db, "Sad overlxrd", entity("artist123", "SASIOVERLXRD"))
    memory = AliasMemory(db)

    assert memory.lookup_exact("sadoverlxrd") is not None
    assert memory.lookup_exact("Sad overlord") is None


def test_conflicted_alias_is_not_in_exact_index_and_is_reported_separately(tmp_path: Path):
    db = SemanticMemoryDatabase(tmp_path / "semantic.sqlite3")
    confirm(db, "Sad overlxrd", entity("artist123", "SASIOVERLXRD"))
    confirm(db, "Sad overlxrd", entity("artist999", "Other Artist"))
    memory = AliasMemory(db)

    assert memory.lookup_exact("Sad overlxrd") is None
    conflicts = memory.lookup_conflicts("Sad overlxrd")
    assert len(conflicts.candidates) == 2
    assert conflicts.conflict is True
    assert conflicts.automatic_canonicalization_allowed is False


def test_fuzzy_lookup_is_bounded_candidate_evidence_only(tmp_path: Path):
    db = SemanticMemoryDatabase(tmp_path / "semantic.sqlite3")
    confirm(db, "Sad overlxrd", entity("artist123", "SASIOVERLXRD"))
    confirm(db, "Sassy overlord", entity("artist456", "SASSY OVERLORD"))
    memory = AliasMemory(db)

    evidence = memory.fuzzy_candidates("Sad overlxrd", limit=1)

    assert len(evidence.candidates) == 1
    assert evidence.candidates[0].evidence_type == "fuzzy"
    assert evidence.automatic_canonicalization_allowed is False


def test_reload_rebuilds_ram_index_after_database_change(tmp_path: Path):
    db = SemanticMemoryDatabase(tmp_path / "semantic.sqlite3")
    memory = AliasMemory(db)
    assert memory.lookup_exact("Sad overlxrd") is None

    confirm(db, "Sad overlxrd", entity("artist123", "SASIOVERLXRD"))
    memory.reload()

    assert memory.lookup_exact("Sad overlxrd") is not None


def test_unavailable_database_yields_empty_memory_without_crashing(tmp_path: Path):
    path = tmp_path / "corrupt.sqlite3"
    path.write_bytes(b"not sqlite")
    memory = AliasMemory(SemanticMemoryDatabase(path))

    assert memory.lookup_exact("Sad overlxrd") is None
    assert memory.fuzzy_candidates("Sad overlxrd").candidates == ()
