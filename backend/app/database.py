from __future__ import annotations

import aiosqlite

DB_PATH = "data/zhenyan.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    source TEXT DEFAULT '',
    content TEXT DEFAULT '',
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS classifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    news_id INTEGER NOT NULL REFERENCES news(id),
    verdict TEXT NOT NULL,
    reason TEXT NOT NULL,
    confidence REAL NOT NULL,
    classified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def init_db():
    db = await get_db()
    await db.executescript(SCHEMA)
    await db.commit()
    await db.close()


async def insert_news(title: str, url: str, source: str, content: str) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT OR IGNORE INTO news (title, url, source, content) VALUES (?, ?, ?, ?)",
            (title, url, source, content),
        )
        await db.commit()
        if cursor.lastrowid == 0:
            row = await db.execute_fetchall("SELECT id FROM news WHERE url = ?", (url,))
            return row[0][0]
        return cursor.lastrowid
    finally:
        await db.close()


async def insert_classification(news_id: int, verdict: str, reason: str, confidence: float) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO classifications (news_id, verdict, reason, confidence) VALUES (?, ?, ?, ?)",
            (news_id, verdict, reason, confidence),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def get_feed(limit: int = 50, verdict_filter: str | None = None) -> list[dict]:
    db = await get_db()
    try:
        query = """
            SELECT c.id, c.news_id, n.title, n.url, n.source,
                   c.verdict, c.reason, c.confidence, c.classified_at
            FROM classifications c
            JOIN news n ON c.news_id = n.id
        """
        params = []
        if verdict_filter:
            query += " WHERE c.verdict = ?"
            params.append(verdict_filter)
        query += " ORDER BY c.classified_at DESC LIMIT ?"
        params.append(limit)

        rows = await db.execute_fetchall(query, params)
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def is_classified(url: str) -> bool:
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            """SELECT 1 FROM classifications c
               JOIN news n ON c.news_id = n.id
               WHERE n.url = ? LIMIT 1""",
            (url,),
        )
        return len(rows) > 0
    finally:
        await db.close()
