"""SQLite-backed session and message store."""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from generic_agent_engineered.config import RuntimeSettings
from generic_agent_engineered.runtime.messages import Message

DEFAULT_SESSION_DB_NAME = "sessions.sqlite"
FTS_QUERY_RE = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True)
class SessionRecord:
    id: str
    parent_session_id: str | None = None
    title: str = ""
    provider_id: str = ""
    model: str = ""
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StoredMessage:
    id: int
    session_id: str
    sequence: int
    message: Message
    created_at: str


@dataclass(frozen=True)
class MessageSearchResult:
    message_id: int
    session_id: str
    sequence: int
    role: str
    content: str
    rank: float


class SessionStore:
    """Persist sessions and provider-neutral runtime messages in SQLite."""

    def __init__(self, path: Path) -> None:
        self.path = path

    @classmethod
    def from_settings(cls, settings: RuntimeSettings) -> SessionStore:
        return cls(settings.state_dir / DEFAULT_SESSION_DB_NAME)

    def initialize(self) -> None:
        with closing(self.connect()):
            pass

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.executescript(_schema_sql())
        return connection

    def create_session(
        self,
        session_id: str | None = None,
        *,
        parent_session_id: str | None = None,
        title: str = "",
        provider_id: str = "",
        model: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> SessionRecord:
        with closing(self.connect()) as connection, connection:
            return _insert_session(
                connection,
                session_id=session_id or _new_session_id(),
                parent_session_id=parent_session_id,
                title=title,
                provider_id=provider_id,
                model=model,
                metadata=metadata or {},
            )

    def get_session(self, session_id: str) -> SessionRecord | None:
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT * FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        return _session_from_row(row) if row is not None else None

    def list_sessions(self) -> list[SessionRecord]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC, id ASC"
            ).fetchall()
        return [_session_from_row(row) for row in rows]

    def append_message(self, session_id: str, message: Message) -> StoredMessage:
        with closing(self.connect()) as connection, connection:
            _require_session(connection, session_id)
            return _append_message(connection, session_id, message)

    def load_stored_messages(self, session_id: str) -> list[StoredMessage]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT * FROM messages
                WHERE session_id = ?
                ORDER BY sequence ASC
                """,
                (session_id,),
            ).fetchall()
        return [_stored_message_from_row(row) for row in rows]

    def load_messages(self, session_id: str) -> list[Message]:
        return [stored.message for stored in self.load_stored_messages(session_id)]

    def search_messages(
        self,
        query: str,
        *,
        session_id: str | None = None,
        limit: int = 20,
    ) -> list[MessageSearchResult]:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        fts_query = _fts_query(query)
        where = ["messages_fts MATCH ?"]
        params: list[Any] = [fts_query]
        if session_id is not None:
            where.append("m.session_id = ?")
            params.append(session_id)
        params.append(limit)

        with closing(self.connect()) as connection:
            rows = connection.execute(
                f"""
                SELECT
                  m.id AS message_id,
                  m.session_id,
                  m.sequence,
                  m.role,
                  m.content,
                  bm25(messages_fts) AS rank
                FROM messages_fts
                JOIN messages AS m ON m.id = messages_fts.rowid
                WHERE {' AND '.join(where)}
                ORDER BY rank ASC, m.id ASC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return [_search_result_from_row(row) for row in rows]

    def branch_session(
        self,
        parent_session_id: str,
        session_id: str | None = None,
        *,
        title: str = "",
        metadata: dict[str, Any] | None = None,
        copy_messages: bool = False,
    ) -> SessionRecord:
        with closing(self.connect()) as connection, connection:
            parent = _select_session(connection, parent_session_id)
            if parent is None:
                raise KeyError(f"unknown parent session: {parent_session_id}")

            child = _insert_session(
                connection,
                session_id=session_id or _new_session_id(),
                parent_session_id=parent.id,
                title=title or parent.title,
                provider_id=parent.provider_id,
                model=parent.model,
                metadata=metadata or {},
            )
            if copy_messages:
                rows = connection.execute(
                    """
                    SELECT * FROM messages
                    WHERE session_id = ?
                    ORDER BY sequence ASC
                    """,
                    (parent_session_id,),
                ).fetchall()
                for row in rows:
                    _append_message(
                        connection,
                        child.id,
                        Message.from_dict(json.loads(row["message_json"])),
                    )
            return child


def _insert_session(
    connection: sqlite3.Connection,
    *,
    session_id: str,
    parent_session_id: str | None,
    title: str,
    provider_id: str,
    model: str,
    metadata: dict[str, Any],
) -> SessionRecord:
    now = _now()
    metadata_json = _json(metadata)
    try:
        connection.execute(
            """
            INSERT INTO sessions (
              id, parent_session_id, title, provider_id, model,
              created_at, updated_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                parent_session_id,
                title,
                provider_id,
                model,
                now,
                now,
                metadata_json,
            ),
        )
    except sqlite3.IntegrityError as exc:
        raise ValueError(f"could not create session {session_id}: {exc}") from exc
    return SessionRecord(
        id=session_id,
        parent_session_id=parent_session_id,
        title=title,
        provider_id=provider_id,
        model=model,
        created_at=now,
        updated_at=now,
        metadata=dict(metadata),
    )


def _append_message(
    connection: sqlite3.Connection,
    session_id: str,
    message: Message,
) -> StoredMessage:
    sequence_row = connection.execute(
        """
        SELECT COALESCE(MAX(sequence), -1) + 1 AS next_sequence
        FROM messages
        WHERE session_id = ?
        """,
        (session_id,),
    ).fetchone()
    sequence = int(sequence_row["next_sequence"])
    now = _now()
    cursor = connection.execute(
        """
        INSERT INTO messages (session_id, sequence, role, content, message_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            sequence,
            message.role,
            message.content,
            _json(message.to_dict()),
            now,
        ),
    )
    connection.execute(
        "UPDATE sessions SET updated_at = ? WHERE id = ?",
        (now, session_id),
    )
    message_id = cursor.lastrowid
    if message_id is None:
        raise RuntimeError("sqlite did not return a message id")
    return StoredMessage(
        id=int(message_id),
        session_id=session_id,
        sequence=sequence,
        message=message,
        created_at=now,
    )


def _select_session(connection: sqlite3.Connection, session_id: str) -> SessionRecord | None:
    row = connection.execute(
        "SELECT * FROM sessions WHERE id = ?",
        (session_id,),
    ).fetchone()
    return _session_from_row(row) if row is not None else None


def _require_session(connection: sqlite3.Connection, session_id: str) -> None:
    if _select_session(connection, session_id) is None:
        raise KeyError(f"unknown session: {session_id}")


def _session_from_row(row: sqlite3.Row) -> SessionRecord:
    metadata = json.loads(row["metadata_json"])
    if not isinstance(metadata, dict):
        metadata = {}
    return SessionRecord(
        id=str(row["id"]),
        parent_session_id=row["parent_session_id"],
        title=str(row["title"]),
        provider_id=str(row["provider_id"]),
        model=str(row["model"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        metadata=metadata,
    )


def _stored_message_from_row(row: sqlite3.Row) -> StoredMessage:
    return StoredMessage(
        id=int(row["id"]),
        session_id=str(row["session_id"]),
        sequence=int(row["sequence"]),
        message=Message.from_dict(json.loads(row["message_json"])),
        created_at=str(row["created_at"]),
    )


def _search_result_from_row(row: sqlite3.Row) -> MessageSearchResult:
    return MessageSearchResult(
        message_id=int(row["message_id"]),
        session_id=str(row["session_id"]),
        sequence=int(row["sequence"]),
        role=str(row["role"]),
        content=str(row["content"]),
        rank=float(row["rank"]),
    )


def _schema_sql() -> str:
    return (Path(__file__).with_name("schema.sql")).read_text(encoding="utf-8")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fts_query(query: str) -> str:
    terms = FTS_QUERY_RE.findall(query)
    if not terms:
        raise ValueError("search query must contain at least one word")
    return " ".join(f'"{term}"' for term in terms)


def _new_session_id() -> str:
    return f"session-{uuid.uuid4().hex}"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
