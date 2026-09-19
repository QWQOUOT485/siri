"""Closed domain models for local ASR/entity recovery memory.

These models deliberately describe interpretation evidence only.  They do not
contain executable targets, Spotify URIs, shell text, paths, or commands.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


MAX_ENTITY_TEXT = 300
MAX_PROVIDER_ID = 128
MAX_SOURCE = 64
MAX_SCOPE_CONTEXT = 128


class AliasTrustState(str, Enum):
    """The only trust states persisted by Phase 1."""

    OBSERVATION = "observation"
    PROVISIONAL = "provisional"
    CONFIRMED = "confirmed"
    CONFLICTED = "conflicted"
    DISABLED = "disabled"


def _reject_control_characters(value: str | None) -> str | None:
    if value is None:
        return None
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("semantic-memory text must not contain control characters")
    return value


class _MemoryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class NormalizedEntityText(_MemoryModel):
    """Non-destructive source text and deterministic comparison forms."""

    raw: str = Field(min_length=1, max_length=MAX_ENTITY_TEXT)
    canonical_text: str = Field(min_length=1, max_length=MAX_ENTITY_TEXT)
    compact_text: str = Field(min_length=1, max_length=MAX_ENTITY_TEXT)
    chinese_canonical: str = Field(min_length=1, max_length=MAX_ENTITY_TEXT)

    _validate_raw = field_validator("raw", "canonical_text", "compact_text", "chinese_canonical")(
        _reject_control_characters
    )


class SemanticEntity(_MemoryModel):
    """A local entity row linked to a server-validated provider identity."""

    entity_pk: int | None = Field(default=None, ge=1)
    entity_type: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$")
    provider: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$")
    # This is an opaque provider ID, not a URI.  The slash/colon/path forms
    # are intentionally impossible to represent in this model.
    provider_entity_id: str = Field(
        min_length=1,
        max_length=MAX_PROVIDER_ID,
        pattern=r"^[A-Za-z0-9._~-]+$",
    )
    canonical_name: str = Field(min_length=1, max_length=MAX_ENTITY_TEXT)
    normalized_name: str = Field(min_length=1, max_length=MAX_ENTITY_TEXT)
    created_at: int = Field(default=0, ge=0)
    last_seen_at: int = Field(default=0, ge=0)
    active: bool = True

    _validate_text = field_validator("canonical_name", "normalized_name")(_reject_control_characters)


class AliasRecord(_MemoryModel):
    """A persisted alias mapping; trust state is never supplied by a client."""

    alias_pk: int | None = Field(default=None, ge=1)
    entity_pk: int = Field(ge=1)
    raw_alias: str = Field(min_length=1, max_length=MAX_ENTITY_TEXT)
    normalized_alias: str = Field(min_length=1, max_length=MAX_ENTITY_TEXT)
    compact_alias: str = Field(min_length=1, max_length=MAX_ENTITY_TEXT)
    trust_state: AliasTrustState
    source: str = Field(min_length=1, max_length=MAX_SOURCE)
    scope_context: str | None = Field(default=None, max_length=MAX_SCOPE_CONTEXT)
    confirmation_count: int = Field(default=0, ge=0)
    success_count: int = Field(default=0, ge=0)
    failure_count: int = Field(default=0, ge=0)
    created_at: int = Field(default=0, ge=0)
    last_used_at: int | None = Field(default=None, ge=0)
    disabled_at: int | None = Field(default=None, ge=0)

    _validate_text = field_validator(
        "raw_alias", "normalized_alias", "compact_alias", "source", "scope_context"
    )(_reject_control_characters)

    @property
    def is_active(self) -> bool:
        return self.disabled_at is None and self.trust_state is not AliasTrustState.DISABLED


class AliasCandidate(_MemoryModel):
    """Candidate evidence; it is never an instruction to execute a provider ID."""

    alias: AliasRecord
    entity: SemanticEntity
    score: float = Field(ge=0.0, le=1.0)
    evidence_type: Literal["exact", "fuzzy", "conflict", "provisional", "observation"]


class RecoveryCandidateEvidence(_MemoryModel):
    """Bounded evidence returned to deterministic clarification/recovery code."""

    query: NormalizedEntityText
    candidates: tuple[AliasCandidate, ...] = Field(default_factory=tuple, max_length=3)
    conflict: bool = False
    automatic_canonicalization_allowed: bool = False

