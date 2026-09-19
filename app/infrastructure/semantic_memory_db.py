"""Fail-closed SQLite storage for local semantic recovery memory."""

from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from app.domain.semantic_memory import AliasRecord, AliasTrustState, SemanticEntity


SCHEMA_VERSION = 1
DEFAULT_BUSY_TIMEOUT_MS = 250


@dataclass(frozen=True)
class SemanticMemoryEntry:
    entity: SemanticEntity
    alias: AliasRecord


@dataclass(frozen=True)
class ConfirmationWriteResult:
    success: bool
    trust_state: AliasTrustState | None = None
    entry: SemanticMemoryEntry | None = None
    error_code: str | None = None
    conflict: bool = False


class SemanticMemoryDatabase:
    """A small local DB whose failure disables memory rather than commands."""

    def __init__(
        self,
        path: Path,
        *,
        observations_enabled: bool = False,
        max_aliases: int = 1000,
        max_observations: int = 1000,
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
        clock=time.time,
    ) -> None:
        self.path = Path(path)
        self.observations_enabled = bool(observations_enabled)
        self.max_aliases = max(1, min(int(max_aliases), 100_000))
        self.max_observations = max(1, min(int(max_observations), 100_000))
        self.busy_timeout_ms = max(1, min(int(busy_timeout_ms), 5_000))
        self.clock = clock
        self._connection: sqlite3.Connection | None = None
        self._lock = threading.RLock()
        self.available = False
        self.schema_version: int | None = None
        self.error_code: str | None = None
        self._initialize()

    @property
    def foreign_keys_enabled(self) -> bool:
        if self._connection is None:
            return False
        try:
            return bool(self._connection.execute("PRAGMA foreign_keys").fetchone()[0])
        except sqlite3.DatabaseError:
            return False

    def _initialize(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(
                self.path,
                timeout=self.busy_timeout_ms / 1000,
                check_same_thread=False,
            )
            connection.row_factory = sqlite3.Row
            connection.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms}")
            connection.execute("PRAGMA foreign_keys = ON")
            self._connection = connection
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            self.schema_version = version
            if version > SCHEMA_VERSION:
                self.error_code = "SEMANTIC_MEMORY_SCHEMA_UNSUPPORTED"
                self._disable(close=True)
                return
            self._migrate(connection, version)
            self._validate_schema(connection)
            self.schema_version = SCHEMA_VERSION
            self.available = True
            self.error_code = None
        except (OSError, sqlite3.DatabaseError, ValueError):
            self._disable(close=True)
            if self.error_code is None:
                self.error_code = "SEMANTIC_MEMORY_UNAVAILABLE"

    def _migrate(self, connection: sqlite3.Connection, version: int) -> None:
        if version >= SCHEMA_VERSION:
            return
        connection.execute("BEGIN")
        try:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS entities (
                    entity_pk INTEGER PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    provider_entity_id TEXT NOT NULL,
                    canonical_name TEXT NOT NULL,
                    normalized_name TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    last_seen_at INTEGER NOT NULL,
                    active INTEGER NOT NULL CHECK (active IN (0, 1)),
                    UNIQUE(provider, entity_type, provider_entity_id)
                );

                CREATE TABLE IF NOT EXISTS aliases (
                    alias_pk INTEGER PRIMARY KEY,
                    entity_pk INTEGER NOT NULL,
                    raw_alias TEXT NOT NULL,
                    normalized_alias TEXT NOT NULL,
                    compact_alias TEXT NOT NULL,
                    trust_state TEXT NOT NULL,
                    source TEXT NOT NULL,
                    scope_context TEXT NULL,
                    confirmation_count INTEGER NOT NULL DEFAULT 0,
                    success_count INTEGER NOT NULL DEFAULT 0,
                    failure_count INTEGER NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    last_used_at INTEGER NULL,
                    disabled_at INTEGER NULL,
                    FOREIGN KEY(entity_pk) REFERENCES entities(entity_pk)
                );

                -- Reserved for a future reviewed context design.  It is not
                -- consulted by Phase 1 lookup or execution.
                CREATE TABLE IF NOT EXISTS scope_context (
                    scope_context TEXT PRIMARY KEY,
                    created_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS alias_observations (
                    observation_pk INTEGER PRIMARY KEY,
                    normalized_alias TEXT NOT NULL,
                    entity_pk INTEGER NULL,
                    evidence_type TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    FOREIGN KEY(entity_pk) REFERENCES entities(entity_pk)
                );

                CREATE INDEX IF NOT EXISTS idx_aliases_normalized
                    ON aliases(normalized_alias);
                CREATE INDEX IF NOT EXISTS idx_aliases_compact
                    ON aliases(compact_alias);
                CREATE INDEX IF NOT EXISTS idx_aliases_scope_context
                    ON aliases(scope_context);
                """
            )
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    @staticmethod
    def _validate_schema(connection: sqlite3.Connection) -> None:
        expected = {
            "entities": {
                "entity_pk",
                "entity_type",
                "provider",
                "provider_entity_id",
                "canonical_name",
                "normalized_name",
                "created_at",
                "last_seen_at",
                "active",
            },
            "aliases": {
                "alias_pk",
                "entity_pk",
                "raw_alias",
                "normalized_alias",
                "compact_alias",
                "trust_state",
                "source",
                "scope_context",
                "confirmation_count",
                "success_count",
                "failure_count",
                "created_at",
                "last_used_at",
                "disabled_at",
            },
        }
        for table, columns in expected.items():
            actual = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
            if not columns.issubset(actual):
                raise sqlite3.DatabaseError(f"semantic memory schema missing columns: {table}")

    def _disable(self, *, close: bool = False) -> None:
        self.available = False
        if close and self._connection is not None:
            try:
                self._connection.close()
            except sqlite3.DatabaseError:
                pass
            self._connection = None

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                try:
                    self._connection.close()
                finally:
                    self._connection = None
                    self.available = False

    def table_names(self) -> tuple[str, ...]:
        if not self.available or self._connection is None:
            return ()
        try:
            rows = self._connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            ).fetchall()
            return tuple(str(row[0]) for row in rows)
        except sqlite3.DatabaseError:
            self._disable(close=True)
            return ()

    def load_entries(self) -> tuple[SemanticMemoryEntry, ...]:
        if not self.available or self._connection is None:
            return ()
        with self._lock:
            try:
                rows = self._connection.execute(
                    """
                    SELECT
                        e.entity_pk, e.entity_type, e.provider, e.provider_entity_id,
                        e.canonical_name, e.normalized_name, e.created_at,
                        e.last_seen_at, e.active,
                        a.alias_pk, a.entity_pk AS alias_entity_pk, a.raw_alias,
                        a.normalized_alias, a.compact_alias, a.trust_state, a.source,
                        a.scope_context, a.confirmation_count, a.success_count,
                        a.failure_count, a.created_at AS alias_created_at,
                        a.last_used_at, a.disabled_at
                    FROM aliases AS a
                    JOIN entities AS e ON e.entity_pk = a.entity_pk
                    ORDER BY a.alias_pk
                    """
                ).fetchall()
                return tuple(self._entry_from_row(row) for row in rows)
            except (sqlite3.DatabaseError, ValueError):
                self._handle_read_error()
                return ()

    def find_entries(self, normalized_alias: str) -> tuple[SemanticMemoryEntry, ...]:
        if not self.available or self._connection is None:
            return ()
        with self._lock:
            try:
                rows = self._connection.execute(
                    """
                    SELECT
                        e.entity_pk, e.entity_type, e.provider, e.provider_entity_id,
                        e.canonical_name, e.normalized_name, e.created_at,
                        e.last_seen_at, e.active,
                        a.alias_pk, a.entity_pk AS alias_entity_pk, a.raw_alias,
                        a.normalized_alias, a.compact_alias, a.trust_state, a.source,
                        a.scope_context, a.confirmation_count, a.success_count,
                        a.failure_count, a.created_at AS alias_created_at,
                        a.last_used_at, a.disabled_at
                    FROM aliases AS a
                    JOIN entities AS e ON e.entity_pk = a.entity_pk
                    WHERE a.normalized_alias = ? OR a.compact_alias = ?
                    ORDER BY a.alias_pk
                    """,
                    (normalized_alias, normalized_alias.replace(" ", "")),
                ).fetchall()
                return tuple(self._entry_from_row(row) for row in rows)
            except (sqlite3.DatabaseError, ValueError):
                self._handle_read_error()
                return ()

    def confirm_alias(
        self,
        *,
        raw_alias: str,
        normalized_alias: str,
        compact_alias: str,
        entity: SemanticEntity,
        source: str,
        now: int | None = None,
    ) -> ConfirmationWriteResult:
        """Atomically persist a trusted confirmation or a conflict."""

        if not self.available or self._connection is None:
            return ConfirmationWriteResult(False, error_code=self.error_code or "SEMANTIC_MEMORY_UNAVAILABLE")
        timestamp = int(self.clock() if now is None else now)
        with self._lock:
            connection = self._connection
            try:
                connection.execute("BEGIN IMMEDIATE")
                entity_pk = self._upsert_entity(connection, entity, timestamp)
                rows = connection.execute(
                    "SELECT * FROM aliases WHERE normalized_alias = ? ORDER BY alias_pk",
                    (normalized_alias,),
                ).fetchall()
                active_rows = [row for row in rows if row["disabled_at"] is None and row["trust_state"] != AliasTrustState.DISABLED.value]
                different_entity = any(row["entity_pk"] != entity_pk for row in active_rows)
                if different_entity:
                    connection.execute(
                        """
                        UPDATE aliases
                        SET trust_state = ?, last_used_at = ?
                        WHERE normalized_alias = ?
                          AND disabled_at IS NULL
                          AND trust_state != ?
                        """,
                        (
                            AliasTrustState.CONFLICTED.value,
                            timestamp,
                            normalized_alias,
                            AliasTrustState.DISABLED.value,
                        ),
                    )
                    row = self._find_or_insert_alias(
                        connection,
                        rows,
                        entity_pk=entity_pk,
                        raw_alias=raw_alias,
                        normalized_alias=normalized_alias,
                        compact_alias=compact_alias,
                        source=source,
                        state=AliasTrustState.CONFLICTED,
                        timestamp=timestamp,
                    )
                    connection.commit()
                    return ConfirmationWriteResult(
                        False,
                        trust_state=AliasTrustState.CONFLICTED,
                        entry=self._entry_from_row_by_pk(connection, row["alias_pk"]),
                        error_code="SEMANTIC_MEMORY_CONFLICT",
                        conflict=True,
                    )

                existing = next((row for row in rows if row["entity_pk"] == entity_pk), None)
                if existing is not None and existing["trust_state"] in {
                    AliasTrustState.CONFLICTED.value,
                    AliasTrustState.DISABLED.value,
                }:
                    connection.commit()
                    state = AliasTrustState(existing["trust_state"])
                    return ConfirmationWriteResult(
                        False,
                        trust_state=state,
                        entry=self._entry_from_row_by_pk(connection, existing["alias_pk"]),
                        error_code="SEMANTIC_MEMORY_CONFLICT" if state is AliasTrustState.CONFLICTED else "SEMANTIC_MEMORY_DISABLED",
                        conflict=state is AliasTrustState.CONFLICTED,
                    )

                if existing is None:
                    alias_count = int(connection.execute("SELECT COUNT(*) FROM aliases").fetchone()[0])
                    if alias_count >= self.max_aliases:
                        connection.rollback()
                        return ConfirmationWriteResult(False, error_code="SEMANTIC_MEMORY_ALIAS_LIMIT")
                    connection.execute(
                        """
                        INSERT INTO aliases(
                            entity_pk, raw_alias, normalized_alias, compact_alias,
                            trust_state, source, scope_context, confirmation_count,
                            success_count, failure_count, created_at, last_used_at,
                            disabled_at
                        ) VALUES (?, ?, ?, ?, ?, ?, NULL, 1, 1, 0, ?, ?, NULL)
                        """,
                        (
                            entity_pk,
                            raw_alias,
                            normalized_alias,
                            compact_alias,
                            AliasTrustState.CONFIRMED.value,
                            source,
                            timestamp,
                            timestamp,
                        ),
                    )
                    alias_pk = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
                else:
                    connection.execute(
                        """
                        UPDATE aliases
                        SET raw_alias = ?, compact_alias = ?, trust_state = ?, source = ?,
                            confirmation_count = confirmation_count + 1,
                            success_count = success_count + 1,
                            last_used_at = ?, disabled_at = NULL
                        WHERE alias_pk = ?
                        """,
                        (
                            raw_alias,
                            compact_alias,
                            AliasTrustState.CONFIRMED.value,
                            source,
                            timestamp,
                            existing["alias_pk"],
                        ),
                    )
                    alias_pk = int(existing["alias_pk"])
                connection.commit()
                entry = self._entry_from_row_by_pk(connection, alias_pk)
                return ConfirmationWriteResult(True, AliasTrustState.CONFIRMED, entry)
            except sqlite3.OperationalError as exc:
                self._rollback_quietly(connection)
                return ConfirmationWriteResult(False, error_code=self._operation_error(exc))
            except (sqlite3.DatabaseError, ValueError):
                self._rollback_quietly(connection)
                self._disable(close=True)
                return ConfirmationWriteResult(False, error_code="SEMANTIC_MEMORY_UNAVAILABLE")

    def record_observation(
        self,
        normalized_alias: str,
        entity_pk: int | None,
        evidence_type: str,
        outcome: str,
        *,
        now: int | None = None,
    ) -> bool:
        if not self.observations_enabled or not self.available or self._connection is None:
            return False
        timestamp = int(self.clock() if now is None else now)
        with self._lock:
            try:
                count = int(self._connection.execute("SELECT COUNT(*) FROM alias_observations").fetchone()[0])
                if count >= self.max_observations:
                    return False
                self._connection.execute("BEGIN IMMEDIATE")
                self._connection.execute(
                    """
                    INSERT INTO alias_observations(
                        normalized_alias, entity_pk, evidence_type, outcome, created_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (normalized_alias, entity_pk, evidence_type, outcome, timestamp),
                )
                self._connection.commit()
                return True
            except sqlite3.OperationalError:
                self._rollback_quietly(self._connection)
                return False
            except sqlite3.DatabaseError:
                self._rollback_quietly(self._connection)
                self._disable(close=True)
                return False

    def observation_count(self) -> int:
        if not self.available or self._connection is None:
            return 0
        with self._lock:
            try:
                return int(self._connection.execute("SELECT COUNT(*) FROM alias_observations").fetchone()[0])
            except sqlite3.DatabaseError:
                self._handle_read_error()
                return 0

    def _upsert_entity(self, connection: sqlite3.Connection, entity: SemanticEntity, timestamp: int) -> int:
        connection.execute(
            """
            INSERT INTO entities(
                entity_type, provider, provider_entity_id, canonical_name,
                normalized_name, created_at, last_seen_at, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(provider, entity_type, provider_entity_id) DO UPDATE SET
                canonical_name = excluded.canonical_name,
                normalized_name = excluded.normalized_name,
                last_seen_at = excluded.last_seen_at,
                active = excluded.active
            """,
            (
                entity.entity_type,
                entity.provider,
                entity.provider_entity_id,
                entity.canonical_name,
                entity.normalized_name,
                timestamp,
                timestamp,
                1 if entity.active else 0,
            ),
        )
        row = connection.execute(
            """
            SELECT entity_pk FROM entities
            WHERE provider = ? AND entity_type = ? AND provider_entity_id = ?
            """,
            (entity.provider, entity.entity_type, entity.provider_entity_id),
        ).fetchone()
        if row is None:
            raise sqlite3.DatabaseError("semantic entity insert failed")
        return int(row[0])

    def _find_or_insert_alias(
        self,
        connection: sqlite3.Connection,
        rows,
        *,
        entity_pk: int,
        raw_alias: str,
        normalized_alias: str,
        compact_alias: str,
        source: str,
        state: AliasTrustState,
        timestamp: int,
    ):
        existing = next((row for row in rows if row["entity_pk"] == entity_pk), None)
        if existing is not None:
            connection.execute(
                "UPDATE aliases SET raw_alias = ?, compact_alias = ?, trust_state = ?, last_used_at = ? WHERE alias_pk = ?",
                (raw_alias, compact_alias, state.value, timestamp, existing["alias_pk"]),
            )
            return connection.execute("SELECT * FROM aliases WHERE alias_pk = ?", (existing["alias_pk"],)).fetchone()
        alias_count = int(connection.execute("SELECT COUNT(*) FROM aliases").fetchone()[0])
        if alias_count >= self.max_aliases:
            raise sqlite3.OperationalError("semantic memory alias limit")
        connection.execute(
            """
            INSERT INTO aliases(
                entity_pk, raw_alias, normalized_alias, compact_alias, trust_state,
                source, scope_context, confirmation_count, success_count,
                failure_count, created_at, last_used_at, disabled_at
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, 0, 0, 0, ?, ?, NULL)
            """,
            (entity_pk, raw_alias, normalized_alias, compact_alias, state.value, source, timestamp, timestamp),
        )
        alias_pk = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
        return connection.execute("SELECT * FROM aliases WHERE alias_pk = ?", (alias_pk,)).fetchone()

    @staticmethod
    def _entry_from_row(row: sqlite3.Row) -> SemanticMemoryEntry:
        entity = SemanticEntity(
            entity_pk=int(row["entity_pk"]),
            entity_type=str(row["entity_type"]),
            provider=str(row["provider"]),
            provider_entity_id=str(row["provider_entity_id"]),
            canonical_name=str(row["canonical_name"]),
            normalized_name=str(row["normalized_name"]),
            created_at=int(row["created_at"]),
            last_seen_at=int(row["last_seen_at"]),
            active=bool(row["active"]),
        )
        alias = AliasRecord(
            alias_pk=int(row["alias_pk"]),
            entity_pk=int(row["alias_entity_pk"]),
            raw_alias=str(row["raw_alias"]),
            normalized_alias=str(row["normalized_alias"]),
            compact_alias=str(row["compact_alias"]),
            trust_state=AliasTrustState(str(row["trust_state"])),
            source=str(row["source"]),
            scope_context=row["scope_context"],
            confirmation_count=int(row["confirmation_count"]),
            success_count=int(row["success_count"]),
            failure_count=int(row["failure_count"]),
            created_at=int(row["alias_created_at"]),
            last_used_at=int(row["last_used_at"]) if row["last_used_at"] is not None else None,
            disabled_at=int(row["disabled_at"]) if row["disabled_at"] is not None else None,
        )
        return SemanticMemoryEntry(entity=entity, alias=alias)

    def _entry_from_row_by_pk(self, connection: sqlite3.Connection, alias_pk: int) -> SemanticMemoryEntry:
        row = connection.execute(
            """
            SELECT
                e.entity_pk, e.entity_type, e.provider, e.provider_entity_id,
                e.canonical_name, e.normalized_name, e.created_at,
                e.last_seen_at, e.active,
                a.alias_pk, a.entity_pk AS alias_entity_pk, a.raw_alias,
                a.normalized_alias, a.compact_alias, a.trust_state, a.source,
                a.scope_context, a.confirmation_count, a.success_count,
                a.failure_count, a.created_at AS alias_created_at,
                a.last_used_at, a.disabled_at
            FROM aliases AS a JOIN entities AS e ON e.entity_pk = a.entity_pk
            WHERE a.alias_pk = ?
            """,
            (alias_pk,),
        ).fetchone()
        if row is None:
            raise sqlite3.DatabaseError("semantic alias row disappeared")
        return self._entry_from_row(row)

    def _handle_read_error(self) -> None:
        self._disable(close=True)
        self.error_code = "SEMANTIC_MEMORY_UNAVAILABLE"

    @staticmethod
    def _rollback_quietly(connection: sqlite3.Connection | None) -> None:
        if connection is None:
            return
        try:
            connection.rollback()
        except sqlite3.DatabaseError:
            pass

    @staticmethod
    def _operation_error(error: sqlite3.OperationalError) -> str:
        message = str(error).casefold()
        if "locked" in message or "busy" in message:
            return "SEMANTIC_MEMORY_BUSY"
        if "limit" in message:
            return "SEMANTIC_MEMORY_ALIAS_LIMIT"
        return "SEMANTIC_MEMORY_UNAVAILABLE"
