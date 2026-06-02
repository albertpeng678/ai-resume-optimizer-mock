import asyncio
import os
import asyncpg
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

_pool: Optional[asyncpg.Pool] = None
_pool_lock: asyncio.Lock = asyncio.Lock()

async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        async with _pool_lock:
            if _pool is None:
                _pool = await asyncpg.create_pool(
                    os.environ["DATABASE_URL"],
                    min_size=2,
                    max_size=10,
                )
    return _pool

async def close_pool():
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None

async def init_db(pool: asyncpg.Pool):
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS analyses (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            dimensions JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_analyses_user_id ON analyses(user_id);
        CREATE INDEX IF NOT EXISTS idx_analyses_recents ON analyses(user_id, uploaded_at DESC);

        CREATE TABLE IF NOT EXISTS weekly_usage (
            user_id TEXT NOT NULL,
            week_start DATE NOT NULL,
            usage_count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, week_start)
        );
    """)

async def create_analysis(pool: asyncpg.Pool, user_id: str, filename: str, file_size: int, dimensions: list) -> UUID:
    import json
    row = await pool.fetchrow(
        "INSERT INTO analyses (user_id, filename, file_size, dimensions) VALUES ($1, $2, $3, $4::jsonb) RETURNING id",
        user_id, filename, file_size, json.dumps(dimensions),
    )
    return row["id"]

async def get_analyses(pool: asyncpg.Pool, user_id: str, limit: int = 20, offset: int = 0) -> list[dict]:
    rows = await pool.fetch(
        "SELECT id, filename, uploaded_at, dimensions FROM analyses WHERE user_id=$1 ORDER BY uploaded_at DESC LIMIT $2 OFFSET $3",
        user_id, limit, offset,
    )
    return [dict(r) for r in rows]

async def get_analysis(pool: asyncpg.Pool, analysis_id: str) -> Optional[dict]:
    row = await pool.fetchrow(
        "SELECT * FROM analyses WHERE id=$1::uuid",
        analysis_id,
    )
    return dict(row) if row else None

async def delete_analysis(pool: asyncpg.Pool, analysis_id: str, user_id: str) -> bool:
    result = await pool.execute(
        "DELETE FROM analyses WHERE id=$1::uuid AND user_id=$2",
        analysis_id, user_id,
    )
    return result == "DELETE 1"

async def get_weekly_usage(pool: asyncpg.Pool, user_id: str) -> int:
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    row = await pool.fetchrow(
        "SELECT usage_count FROM weekly_usage WHERE user_id=$1 AND week_start=$2",
        user_id, week_start,
    )
    return row["usage_count"] if row else 0

async def increment_weekly_usage(pool: asyncpg.Pool, user_id: str) -> int:
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    row = await pool.fetchrow(
        """INSERT INTO weekly_usage (user_id, week_start, usage_count)
           VALUES ($1, $2, 1)
           ON CONFLICT (user_id, week_start)
           DO UPDATE SET usage_count = weekly_usage.usage_count + 1
           RETURNING usage_count""",
        user_id, week_start,
    )
    return row["usage_count"]
