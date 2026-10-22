"""SQLite persistence, schema migrations and the audit trail."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.domain import Listing

SCHEMA_VERSION = 1

_MIGRATIONS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS listings (
        listing_id   TEXT PRIMARY KEY,
        status       TEXT NOT NULL,
        idempotency  TEXT UNIQUE,
        payload      TEXT NOT NULL,
        created_at   TEXT NOT NULL,
        updated_at   TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS audit_events (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        listing_id  TEXT NOT NULL,
        stage       TEXT NOT NULL,
        action      TEXT NOT NULL,
        detail      TEXT NOT NULL,
        created_at  TEXT NOT NULL,
        FOREIGN KEY (listing_id) REFERENCES listings (listing_id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS audit_listing_idx ON audit_events (listing_id);
    """,
]


class ListingStore:
    """Durable store for listings and their audit trail."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA foreign_keys = ON")
        self.migrate()

    def migrate(self) -> None:
        """Apply pending migrations (version tracked in ``user_version``)."""
        current = self._conn.execute("PRAGMA user_version").fetchone()[0]
        for version in range(current, len(_MIGRATIONS)):
            self._conn.executescript(_MIGRATIONS[version])
            self._conn.execute(f"PRAGMA user_version = {version + 1}")
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def ping(self) -> bool:
        try:
            self._conn.execute("SELECT 1").fetchone()
            return True
        except sqlite3.Error:
            return False

    # -- listings ---------------------------------------------------------
    def save(self, listing: Listing, idempotency_key: str | None = None) -> None:
        now = datetime.now(UTC).isoformat()
        self._conn.execute(
            """
            INSERT INTO listings (listing_id, status, idempotency, payload, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(listing_id) DO UPDATE SET
                status = excluded.status,
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (
                listing.listing_id,
                listing.status.value,
                idempotency_key,
                listing.model_dump_json(),
                now,
                now,
            ),
        )
        self._conn.commit()

    def get(self, listing_id: str) -> Listing | None:
        row = self._conn.execute(
            "SELECT payload FROM listings WHERE listing_id = ?", (listing_id,)
        ).fetchone()
        return Listing.model_validate_json(row["payload"]) if row else None

    def find_by_idempotency(self, idempotency_key: str) -> Listing | None:
        row = self._conn.execute(
            "SELECT payload FROM listings WHERE idempotency = ?", (idempotency_key,)
        ).fetchone()
        return Listing.model_validate_json(row["payload"]) if row else None

    def list(self, limit: int = 50) -> list[Listing]:
        rows = self._conn.execute(
            "SELECT payload FROM listings ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [Listing.model_validate_json(row["payload"]) for row in rows]

    # -- audit ------------------------------------------------------------
    def append_audit(self, listing_id: str, stage: str, action: str, detail: dict[str, Any] | None = None) -> None:
        self._conn.execute(
            """
            INSERT INTO audit_events (listing_id, stage, action, detail, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                listing_id,
                stage,
                action,
                json.dumps(detail or {}, ensure_ascii=False),
                datetime.now(UTC).isoformat(),
            ),
        )
        self._conn.commit()

    def audit_trail(self, listing_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT stage, action, detail, created_at FROM audit_events "
            "WHERE listing_id = ? ORDER BY id ASC",
            (listing_id,),
        ).fetchall()
        return [
            {
                "stage": row["stage"],
                "action": row["action"],
                "detail": json.loads(row["detail"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]


__all__ = ["ListingStore", "SCHEMA_VERSION"]
