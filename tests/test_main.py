import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app

pytestmark = pytest.mark.asyncio

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

async def test_metrics(client):
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "events" in data

async def test_analyze_empty_file(client):
    resp = await client.post("/analyze", files={"pdf_file": ("empty.pdf", b"", "application/pdf")})
    assert resp.status_code == 400
    assert "空的" in resp.json()["detail"]

async def test_analyze_too_large(client):
    resp = await client.post("/analyze", files={"pdf_file": ("test.pdf", b"x" * (10 * 1024 * 1024 + 1), "application/pdf")})
    assert resp.status_code == 400
    assert "超過" in resp.json()["detail"]

async def test_analyze_not_pdf(client):
    resp = await client.post("/analyze", files={"pdf_file": ("test.pdf", b"not a pdf", "application/pdf")})
    assert resp.status_code == 400
    assert "PDF 格式" in resp.json()["detail"]

async def test_index_returns_html(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]

async def test_analyses_list(client):
    resp = await client.get("/api/analyses")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

async def test_analyses_delete_not_found(client):
    resp = await client.delete("/api/analyses/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
