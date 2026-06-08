"""
JARVIS Core — Audit Log

SQLite-backed logging for all conversations, actions, permissions, and errors.
Async writes to avoid blocking the main event loop.
"""

import aiosqlite
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


class AuditLog:
    """Persistent audit logger using SQLite."""

    def __init__(self, db_path: str = "data/jarvis.sqlite"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db: Optional[aiosqlite.Connection] = None

    async def initialize(self):
        """Create tables if they don't exist."""
        self._db = await aiosqlite.connect(str(self.db_path))
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                action_name TEXT NOT NULL,
                details TEXT,
                status TEXT NOT NULL DEFAULT 'started',
                result TEXT,
                timestamp TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                request_id TEXT NOT NULL,
                action TEXT NOT NULL,
                level TEXT NOT NULL,
                description TEXT,
                approved INTEGER,
                timestamp TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                error_type TEXT NOT NULL,
                message TEXT NOT NULL,
                traceback TEXT,
                timestamp TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_conv_session ON conversations(session_id);
            CREATE INDEX IF NOT EXISTS idx_actions_session ON actions(session_id);
            CREATE INDEX IF NOT EXISTS idx_perm_session ON permissions(session_id);
            CREATE INDEX IF NOT EXISTS idx_errors_session ON errors(session_id);
        """)
        await self._db.commit()

    async def log_conversation(self, session_id: str, role: str, content: str):
        """Log a conversation message (user or assistant)."""
        if not self._db:
            return
        await self._db.execute(
            "INSERT INTO conversations (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, role, content, datetime.now().isoformat()),
        )
        await self._db.commit()

    async def log_action(
        self,
        session_id: str,
        action_type: str,
        action_name: str,
        details: dict | None = None,
        status: str = "started",
        result: str | None = None,
    ) -> int:
        """Log a tool/agent action. Returns the row ID."""
        if not self._db:
            return -1
        cursor = await self._db.execute(
            "INSERT INTO actions (session_id, action_type, action_name, details, status, result, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                session_id,
                action_type,
                action_name,
                json.dumps(details) if details else None,
                status,
                result,
                datetime.now().isoformat(),
            ),
        )
        await self._db.commit()
        return cursor.lastrowid or -1

    async def update_action(self, action_id: int, status: str, result: str | None = None, details: dict | None = None):
        """Update an action's status, result, and optional details."""
        if not self._db or action_id < 0:
            return
        if details:
            await self._db.execute(
                "UPDATE actions SET status = ?, result = ?, details = ? WHERE id = ?",
                (status, result, json.dumps(details), action_id),
            )
        else:
            await self._db.execute(
                "UPDATE actions SET status = ?, result = ? WHERE id = ?",
                (status, result, action_id),
            )
        await self._db.commit()

    async def log_permission(
        self,
        session_id: str,
        request_id: str,
        action: str,
        level: str,
        description: str,
        approved: bool | None = None,
    ):
        """Log a permission request and its resolution."""
        if not self._db:
            return
        await self._db.execute(
            "INSERT INTO permissions (session_id, request_id, action, level, description, approved, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                session_id,
                request_id,
                action,
                level,
                description,
                1 if approved else (0 if approved is not None else None),
                datetime.now().isoformat(),
            ),
        )
        await self._db.commit()

    async def log_error(
        self,
        session_id: str,
        error_type: str,
        message: str,
        traceback: str | None = None,
    ):
        """Log an error."""
        if not self._db:
            return
        await self._db.execute(
            "INSERT INTO errors (session_id, error_type, message, traceback, timestamp) VALUES (?, ?, ?, ?, ?)",
            (session_id, error_type, message, traceback, datetime.now().isoformat()),
        )
        await self._db.commit()

    async def get_logs(self, limit: int = 100, session_id: str | None = None) -> list[dict]:
        """Retrieve recent logs across all tables."""
        if not self._db:
            return []

        logs: list[dict] = []
        where = "WHERE session_id = ?" if session_id else ""
        params = (session_id,) if session_id else ()

        # Fetch recent conversations
        async with self._db.execute(
            f"SELECT * FROM conversations {where} ORDER BY id DESC LIMIT ?",
            (*params, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            cols = [d[0] for d in cursor.description]
            for row in rows:
                entry = dict(zip(cols, row))
                entry["table"] = "conversations"
                logs.append(entry)

        # Fetch recent actions
        async with self._db.execute(
            f"SELECT * FROM actions {where} ORDER BY id DESC LIMIT ?",
            (*params, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            cols = [d[0] for d in cursor.description]
            for row in rows:
                entry = dict(zip(cols, row))
                entry["table"] = "actions"
                logs.append(entry)

        # Fetch recent permissions
        async with self._db.execute(
            f"SELECT * FROM permissions {where} ORDER BY id DESC LIMIT ?",
            (*params, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            cols = [d[0] for d in cursor.description]
            for row in rows:
                entry = dict(zip(cols, row))
                entry["table"] = "permissions"
                logs.append(entry)

        # Fetch recent errors
        async with self._db.execute(
            f"SELECT * FROM errors {where} ORDER BY id DESC LIMIT ?",
            (*params, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            cols = [d[0] for d in cursor.description]
            for row in rows:
                entry = dict(zip(cols, row))
                entry["table"] = "errors"
                logs.append(entry)

        # Sort by timestamp descending
        logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return logs[:limit]

    async def close(self):
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None


# Singleton instance
audit_log = AuditLog()
