import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, TypedDict

import aiosqlite
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from core.settings import settings

Role = Literal["human", "ai", "system"]


class StoredMessage(TypedDict):
    role: Role
    content: str


class SQLiteChatMemory:
    """SQLite 版本会话记忆。

    SQLite 是一个本地文件数据库。对初学者来说，可以把它理解为：
    不需要单独启动数据库服务，但数据会真实写入一个 .sqlite3 文件。
    """

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = Path(db_path or settings.sqlite_memory_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    async def init(self) -> None:
        if self._initialized:
            return

        async with self._connect() as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    conversation_summary TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                )
                """
            )
            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_session_id_id
                ON messages(session_id, id)
                """
            )
            await db.commit()
        self._initialized = True

    async def ensure_session(self, session_id: str) -> None:
        await self.init()
        async with self._connect() as db:
            await db.execute(
                """
                INSERT INTO sessions(session_id)
                VALUES (?)
                ON CONFLICT(session_id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
                """,
                (session_id,),
            )
            await db.commit()

    async def get_messages(self, session_id: str) -> list[StoredMessage]:
        await self.ensure_session(session_id)
        async with self._connect() as db:
            rows = await db.execute_fetchall(
                """
                SELECT role, content
                FROM messages
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id,),
            )
        return [{"role": row["role"], "content": row["content"]} for row in rows]

    async def get_langchain_messages(self, session_id: str) -> list[BaseMessage]:
        stored_messages = await self.get_messages(session_id)
        messages: list[BaseMessage] = []

        for item in stored_messages:
            if item["role"] == "human":
                messages.append(HumanMessage(content=item["content"]))
            elif item["role"] == "ai":
                messages.append(AIMessage(content=item["content"]))
            else:
                messages.append(SystemMessage(content=item["content"]))

        return messages

    async def append_message(self, session_id: str, role: Role, content: str) -> None:
        await self.ensure_session(session_id)
        async with self._connect() as db:
            await db.execute(
                """
                INSERT INTO messages(session_id, role, content)
                VALUES (?, ?, ?)
                """,
                (session_id, role, content),
            )
            await db.execute(
                """
                UPDATE sessions
                SET updated_at = CURRENT_TIMESTAMP
                WHERE session_id = ?
                """,
                (session_id,),
            )
            await db.commit()

    async def get_summary(self, session_id: str) -> str:
        await self.ensure_session(session_id)
        async with self._connect() as db:
            row = await db.execute_fetchall(
                """
                SELECT conversation_summary
                FROM sessions
                WHERE session_id = ?
                """,
                (session_id,),
            )
        return str(row[0]["conversation_summary"]) if row else ""

    async def update_summary(self, session_id: str, summary: str) -> None:
        await self.ensure_session(session_id)
        async with self._connect() as db:
            await db.execute(
                """
                UPDATE sessions
                SET conversation_summary = ?, updated_at = CURRENT_TIMESTAMP
                WHERE session_id = ?
                """,
                (summary, session_id),
            )
            await db.commit()

    async def maybe_update_summary(self, session_id: str) -> str:
        """生成轻量 summary，避免长对话时上下文无限增长。

        这里先用稳定、无需额外 LLM 调用的方式做摘要：保留最近若干轮的压缩文本。
        后续如果要更智能，可以替换成专门的 summary_node。
        """

        messages = await self.get_messages(session_id)
        if len(messages) <= settings.conversation_summary_max_messages:
            summary = await self.get_summary(session_id)
            if summary:
                return summary

            summary = self._build_summary(messages)
            await self.update_summary(session_id, summary)
            return summary

        old_messages = messages[: -settings.conversation_summary_max_messages]
        summary = self._build_summary(old_messages)
        await self.update_summary(session_id, summary)
        return summary

    async def clear(self, session_id: str) -> None:
        await self.init()
        async with self._connect() as db:
            await db.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            await db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            await db.commit()

    @asynccontextmanager
    async def _connect(self) -> AsyncIterator[aiosqlite.Connection]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            yield db

    def _build_summary(self, messages: list[StoredMessage]) -> str:
        if not messages:
            return ""

        compact_items = [
            {"role": item["role"], "content": item["content"][:200]}
            for item in messages
        ]
        return json.dumps(compact_items, ensure_ascii=False)
