import os
import pytest
import pytest_asyncio
from backend.database import (
    get_pool, init_db, create_analysis, get_analyses,
    get_analysis, delete_analysis, get_weekly_usage, increment_weekly_usage,
)

_has_db_url = bool(os.environ.get("DATABASE_URL"))

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not _has_db_url, reason="需要 DATABASE_URL"),
]

@pytest_asyncio.fixture
async def pool():
    pool = await get_pool()
    await init_db(pool)
    yield pool
    await pool.execute("TRUNCATE analyses, weekly_usage")

async def test_create_and_get_analysis(pool):
    await create_analysis(pool, "user1", "resume.pdf", 1024, [{"name": "test"}])
    rows = await get_analyses(pool, "user1")
    assert len(rows) == 1
    assert rows[0]["filename"] == "resume.pdf"

async def test_get_analysis_by_id(pool):
    analysis_id = await create_analysis(pool, "user1", "resume.pdf", 1024, [])
    result = await get_analysis(pool, str(analysis_id))
    assert result is not None
    assert result["filename"] == "resume.pdf"

async def test_delete_analysis(pool):
    analysis_id = await create_analysis(pool, "user1", "resume.pdf", 1024, [])
    assert await delete_analysis(pool, str(analysis_id), "user1")
    assert await get_analysis(pool, str(analysis_id)) is None

async def test_delete_analysis_wrong_user(pool):
    analysis_id = await create_analysis(pool, "user1", "resume.pdf", 1024, [])
    assert not await delete_analysis(pool, str(analysis_id), "user2")

async def test_weekly_usage(pool):
    assert await get_weekly_usage(pool, "user1") == 0
    count = await increment_weekly_usage(pool, "user1")
    assert count == 1
    assert await get_weekly_usage(pool, "user1") == 1
    count = await increment_weekly_usage(pool, "user1")
    assert count == 2
