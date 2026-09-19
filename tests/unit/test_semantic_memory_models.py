import pytest
from pydantic import ValidationError

from app.domain.semantic_memory import (
    AliasCandidate,
    AliasRecord,
    AliasTrustState,
    NormalizedEntityText,
    RecoveryCandidateEvidence,
    SemanticEntity,
)


def entity(*, entity_pk: int | None = 1, provider_entity_id: str = "artist123") -> SemanticEntity:
    return SemanticEntity(
        entity_pk=entity_pk,
        entity_type="artist",
        provider="spotify",
        provider_entity_id=provider_entity_id,
        canonical_name="SASIOVERLXRD",
        normalized_name="sasioverlxrd",
    )


def alias(*, trust_state: AliasTrustState = AliasTrustState.CONFIRMED) -> AliasRecord:
    return AliasRecord(
        alias_pk=1,
        entity_pk=1,
        raw_alias="Sad overlxrd",
        normalized_alias="sad overlxrd",
        compact_alias="sadoverlxrd",
        trust_state=trust_state,
        source="trusted_clarification",
    )


def test_semantic_models_keep_local_and_provider_identity_separate():
    value = entity()

    assert value.entity_pk == 1
    assert value.provider_entity_id == "artist123"
    assert not hasattr(value, "track_uri")
    assert not hasattr(value, "command")
    assert not hasattr(value, "executable_path")


def test_alias_candidate_and_recovery_evidence_are_candidate_data_only():
    candidate = AliasCandidate(alias=alias(), entity=entity(), score=0.91, evidence_type="fuzzy")
    evidence = RecoveryCandidateEvidence(
        query=NormalizedEntityText(
            raw="Sad overlxrd",
            canonical_text="sad overlxrd",
            compact_text="sadoverlxrd",
            chinese_canonical="sad overlxrd",
        ),
        candidates=(candidate,),
    )

    assert evidence.automatic_canonicalization_allowed is False
    assert evidence.candidates[0].evidence_type == "fuzzy"


def test_normalized_entity_text_preserves_bounded_forms():
    value = NormalizedEntityText(
        raw="Sad Overlxrd",
        canonical_text="sad overlxrd",
        compact_text="sadoverlxrd",
        chinese_canonical="sad overlxrd",
    )

    assert value.raw == "Sad Overlxrd"
    assert value.compact_text == "sadoverlxrd"


@pytest.mark.parametrize("state", list(AliasTrustState))
def test_all_phase_one_trust_states_are_closed(state):
    assert AliasTrustState(state.value) is state


def test_provider_identity_rejects_uri_path_and_control_text():
    for value in ("spotify:artist:artist123", "C:\\artist", "artist/123", "artist\n123"):
        with pytest.raises(ValidationError):
            entity(provider_entity_id=value)


def test_models_reject_oversized_or_control_aliases():
    with pytest.raises(ValidationError):
        AliasRecord(
            entity_pk=1,
            raw_alias="a" * 301,
            normalized_alias="a",
            compact_alias="a",
            trust_state=AliasTrustState.OBSERVATION,
            source="test",
        )
    with pytest.raises(ValidationError):
        AliasRecord(
            entity_pk=1,
            raw_alias="bad\ninput",
            normalized_alias="bad",
            compact_alias="bad",
            trust_state=AliasTrustState.OBSERVATION,
            source="test",
        )
