"""E2E test server bootstrap. Patches OpenAI modules and starts uvicorn."""

import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Set required env vars BEFORE importing app modules (module-level AsyncOpenAI() needs this)
os.environ.setdefault("OPENAI_API_KEY", "test-key-for-e2e")
os.environ.setdefault("OPENAI_MODEL", "gpt-4o-mini")

# Patch before importing app modules
import backend.analyzer as analyzer_mod
import backend.pdf_parser as pdf_parser_mod
from tests.e2e.fixtures.test_data import (
    mock_stream_analysis,
    mock_validate_is_resume,
    mock_ai_preprocess_text,
    mock_parse_resume,
)

analyzer_mod.stream_analysis = mock_stream_analysis
analyzer_mod.validate_is_resume = mock_validate_is_resume
pdf_parser_mod.ai_preprocess_text = mock_ai_preprocess_text
pdf_parser_mod.parse_resume = mock_parse_resume


# Add test-only reset endpoint for test isolation
import backend.main as main_mod
from fastapi import Response
from backend.database import get_pool

@main_mod.app.post("/__reset")
async def reset_test_state():
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM analyses")
            await conn.execute("DELETE FROM weekly_usage")
    except Exception:
        pass
    return Response(status_code=204)


async def start_server(host="127.0.0.1", port=8765):
    """Start uvicorn server and return control."""
    import uvicorn
    config = uvicorn.Config(
        main_mod.app,
        host=host,
        port=port,
        log_level="info",
    )
    server = uvicorn.Server(config)

    # Run server in background task
    task = asyncio.create_task(server.serve())

    # Wait for server to start
    await asyncio.sleep(2)

    return server, task


if __name__ == "__main__":
    async def main():
        port = int(os.environ.get("PORT", 8765))
        server, task = await start_server(port=port)
        print(f"E2E test server started on http://127.0.0.1:{port}", flush=True)
        try:
            await task
        except asyncio.CancelledError:
            pass
    asyncio.run(main())
