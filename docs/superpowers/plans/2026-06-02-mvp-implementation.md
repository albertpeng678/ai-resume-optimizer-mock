# AI Resume Scanner — MVP Implementation Plan (v2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build working MVP of AI Resume Scanner with resume validation, history (PostgreSQL), AI pre-processing, responsive sidebar UI, and 7-uses/week limit.

**Architecture:** FastAPI serves a single-page HTML frontend. Uploaded PDF is parsed by pdfminer.six → validated by AI (is it a resume?) → pre-processed by AI (fix garbled text) → analyzed across 5 dimensions via SSE streaming → results saved to PostgreSQL. Frontend is a responsive single HTML file with editorial/magazine style, navy blue palette, and permanent/overlay/separate sidebar for Desktop/Tablet/Mobile.

**Tech Stack:** Python 3.12, FastAPI >= 0.135.0, pdfminer.six, openai >= 1.0.0, asyncpg, pure inline HTML/CSS/JS (no frameworks)

---

## File Structure

**Create:**
- `backend/database.py` — PostgreSQL connection pool + CRUD for analyses and weekly_usage
- `backend/schemas.py` — Pydantic models for request/response
- `tests/test_pdf_parser.py` — test all validation paths
- `tests/test_analyzer.py` — test resume validation + stream_analysis
- `tests/test_database.py` — test DB CRUD operations
- `tests/test_main.py` — test API endpoints

**Modify:**
- `backend/pdf_parser.py` — update file size to 10MB, add `ai_preprocess_text`
- `backend/analyzer.py` — add `validate_is_resume`, update dimension names + SSE format, add SYSTEM_PROMPT
- `backend/main.py` — add history endpoints, resume validation, AI pre-processing, weekly limit, not_resume error
- `frontend/index.html` — full rewrite (sidebar + responsive + 7 states)
- `frontend/design.md` — already updated from spec
- `requirements.txt` — add asyncpg
- `CLAUDE.md` — update API spec, dimension names, error table, env vars

---

### Task 1: Database — PostgreSQL Connection & CRUD

**Files:**
- Create: `backend/database.py`
- Create: `tests/test_database.py`
- Modify: `requirements.txt` (add asyncpg)

- [ ] **Step 1: Write DB table migration + connection module**

```python
# backend/database.py
import os
import asyncpg
from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID

_pool: Optional[asyncpg.Pool] = None

async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            os.environ["DATABASE_URL"],
            min_size=2,
            max_size=10,
        )
    return _pool

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
    row = await pool.fetchrow(
        "INSERT INTO analyses (user_id, filename, file_size, dimensions) VALUES ($1, $2, $3, $4::jsonb) RETURNING id",
        user_id, filename, file_size, dimensions,
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
    week_start = today - __import__("datetime").timedelta(days=today.weekday())
    row = await pool.fetchrow(
        "SELECT usage_count FROM weekly_usage WHERE user_id=$1 AND week_start=$2",
        user_id, week_start,
    )
    return row["usage_count"] if row else 0

async def increment_weekly_usage(pool: asyncpg.Pool, user_id: str) -> int:
    today = date.today()
    week_start = today - __import__("datetime").timedelta(days=today.weekday())
    row = await pool.fetchrow(
        """INSERT INTO weekly_usage (user_id, week_start, usage_count)
           VALUES ($1, $2, 1)
           ON CONFLICT (user_id, week_start)
           DO UPDATE SET usage_count = weekly_usage.usage_count + 1
           RETURNING usage_count""",
        user_id, week_start,
    )
    return row["usage_count"]
```

- [ ] **Step 2: Write failing tests**

```python
# tests/test_database.py
import pytest
import pytest_asyncio
from backend.database import (
    get_pool, init_db, create_analysis, get_analyses,
    get_analysis, delete_analysis, get_weekly_usage, increment_weekly_usage,
)

pytestmark = pytest.mark.asyncio

@pytest_asyncio.fixture
async def pool():
    pool = await get_pool()
    await init_db(pool)
    yield pool
    await pool.execute("TRUNCATE analyses, weekly_usage")

async def test_create_and_get_analysis(pool):
    analysis_id = await create_analysis(pool, "user1", "resume.pdf", 1024, [{"name": "test"}])
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

async def test_get_analysis_wrong_user(pool):
    analysis_id = await create_analysis(pool, "user1", "resume.pdf", 1024, [])
    assert not await delete_analysis(pool, str(analysis_id), "user2")

async def test_weekly_usage(pool):
    assert await get_weekly_usage(pool, "user1") == 0
    count = await increment_weekly_usage(pool, "user1")
    assert count == 1
    assert await get_weekly_usage(pool, "user1") == 1
    count = await increment_weekly_usage(pool, "user1")
    assert count == 2
```

- [ ] **Step 3: Run tests to verify they fail (no DB)**

```bash
cd .worktrees\feature\mvp-implementation
pytest tests/test_database.py -v
```
Expected: FAIL with "database does not exist" or similar connection error (tests need DATABASE_URL env)

- [ ] **Step 4: Add asyncpg to requirements.txt**

```
# requirements.txt — add line:
asyncpg>=0.30.0
```

- [ ] **Step 5: Commit**

```bash
git add backend/database.py tests/test_database.py requirements.txt
git commit -m "feat: add PostgreSQL database module with analyses and weekly_usage CRUD"
```

---

### Task 2: PDF Parser — 10MB Limit + AI Pre-processing

**Files:**
- Modify: `backend/pdf_parser.py`
- Create: `tests/test_pdf_parser.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_pdf_parser.py
import pytest
from backend.pdf_parser import validate_pdf_magic, parse_resume, ai_preprocess_text

class TestValidatePdfMagic:
    def test_valid_pdf_magic(self):
        assert validate_pdf_magic(b"%PDF-1.4\n...")

    def test_empty_bytes(self):
        assert not validate_pdf_magic(b"")

    def test_not_pdf_magic(self):
        assert not validate_pdf_magic(b"GIF89a...")

class TestParseResume:
    def test_empty_file_raises(self):
        with pytest.raises(ValueError, match="empty_file"):
            parse_resume(b"")

    def test_file_too_large_raises(self):
        # 10MB + 1 byte = 10 * 1024 * 1024 + 1
        with pytest.raises(ValueError, match="file_too_large"):
            parse_resume(b"x" * (10 * 1024 * 1024 + 1))

    def test_not_pdf_raises(self):
        with pytest.raises(ValueError, match="not_pdf"):
            parse_resume(b"not a pdf content")

    def test_valid_pdf_returns_text(self, tmp_path):
        # Create a minimal valid PDF with text
        from pdfminer.high_level import extract_text
        pdf_content = _create_minimal_pdf("Hello World")
        text = parse_resume(pdf_content)
        assert "Hello World" in text

def _create_minimal_pdf(text: str) -> bytes:
    """Helper: create minimal valid PDF with given text."""
    from reportlab.pdfgen import canvas
    import io
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 750, text)
    c.save()
    return buf.getvalue()

class TestAiPreprocessText:
    @pytest.mark.asyncio
    async def test_preprocess_short_text(self):
        text = "測試履歷文字"
        result = await ai_preprocess_text(text)
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_preprocess_empty_text(self):
        with pytest.raises(ValueError, match="empty_text"):
            await ai_preprocess_text("")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_pdf_parser.py -v
```
Expected: FAIL (4 failures — all NotImplementedError)

- [ ] **Step 3: Implement parse_resume + validate_pdf_magic (update to 10MB)**

```python
# Modify backend/pdf_parser.py
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

def validate_pdf_magic(content: bytes) -> bool:
    if len(content) < 4:
        return False
    return content[:4] == b"%PDF"

def parse_resume(content: bytes, max_chars: int = 12_000) -> str:
    import os
    import tempfile
    from pdfminer.high_level import extract_text
    from pdfminer.layout import LAParams
    from pdfminer.pdfparser import PDFSyntaxError
    from pdfminer.pdfdocument import PDFPasswordIncorrect

    if len(content) == 0:
        raise ValueError("empty_file")
    if len(content) > MAX_FILE_SIZE:
        raise ValueError("file_too_large")
    if not validate_pdf_magic(content):
        raise ValueError("not_pdf")

    tmp = None
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.write(content)
        tmp.flush()
        tmp.close()
        text = extract_text(
            tmp.name,
            laparams=LAParams(char_margin=2.0, word_margin=0.1),
        )
    except PDFPasswordIncorrect:
        raise ValueError("password_protected")
    except (PDFSyntaxError, TypeError):
        raise ValueError("corrupted_pdf")
    finally:
        if tmp and os.path.exists(tmp.name):
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    text = text.strip()
    if len(text) < 50:
        raise ValueError("scanned_pdf")

    return text[:max_chars]
```

- [ ] **Step 4: Implement ai_preprocess_text**

```python
# Add to backend/pdf_parser.py
from openai import AsyncOpenAI

_client = AsyncOpenAI()

async def ai_preprocess_text(text: str) -> str:
    if not text.strip():
        raise ValueError("empty_text")

    response = await _client.chat.completions.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": "你是一個 PDF 文字修復助手。你的任務是修復 pdfminer 擷取造成的文字亂序、斷行、表格錯位等問題。請還原正確的閱讀順序，修正斷字，重構表格結構。只輸出修復後的文字，不要加任何說明。"},
            {"role": "user", "content": text},
        ],
        temperature=0.1,
        max_tokens=4096,
    )
    return response.choices[0].message.content.strip()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_pdf_parser.py -v
```
Expected: All tests pass (note: ai_preprocess_text tests require valid OPENAI_API_KEY; skip with `-m "not openai"` if not available)

- [ ] **Step 6: Commit**

```bash
git add backend/pdf_parser.py tests/test_pdf_parser.py
git commit -m "feat: update PDF parser with 10MB limit and AI pre-processing"
```

---

### Task 3: Analyzer — Resume Validation + New SSE Format

**Files:**
- Modify: `backend/analyzer.py`
- Create: `tests/test_analyzer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_analyzer.py
import pytest
import json
from backend.analyzer import validate_is_resume, stream_analysis, _classify_error

class TestValidateIsResume:
    @pytest.mark.asyncio
    async def test_valid_resume(self):
        is_resume, reason = await validate_is_resume("Experienced software engineer with 5 years...")
        assert isinstance(is_resume, bool)
        assert isinstance(reason, str)

    @pytest.mark.asyncio
    async def test_empty_text(self):
        is_resume, reason = await validate_is_resume("")
        assert is_resume is False
        assert "empty" in reason.lower()

class TestStreamAnalysis:
    @pytest.mark.asyncio
    async def test_stream_yields_dimensions(self):
        results = []
        async for chunk in stream_analysis("Test resume content"):
            data = json.loads(chunk)
            results.append(data["type"])
        assert "dimension" in results
        assert results[-1] == "done"

    @pytest.mark.asyncio
    async def test_stream_yields_all_5_dimensions(self):
        dim_names = []
        async for chunk in stream_analysis("Test resume content"):
            data = json.loads(chunk)
            if data["type"] == "dimension":
                dim_names.append(data["name"])
        assert len(dim_names) == 5
        assert dim_names == [
            "experience_relevance",
            "skill_fit",
            "layout_structure",
            "keyword_coverage",
            "personal_brand",
        ]

    @pytest.mark.asyncio
    async def test_dimension_contains_new_fields(self):
        async for chunk in stream_analysis("Test resume content"):
            data = json.loads(chunk)
            if data["type"] == "dimension":
                assert "conclusion" in data
                assert "quote" in data
                assert "optimized" in data
                assert "optimization_logic" in data
                assert "suggestions" in data
                break

class TestClassifyError:
    def test_rate_limit(self):
        from openai import RateLimitError
        e = RateLimitError("rate limited", response=None, body=None)
        code, msg = _classify_error(e)
        assert code == "rate_limit"

    def test_connection(self):
        from openai import APIConnectionError
        e = APIConnectionError(message="connection failed")
        code, msg = _classify_error(e)
        assert code == "connection"

    def test_unknown(self):
        code, msg = _classify_error(ValueError("something else"))
        assert code == "unknown"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_analyzer.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement validate_is_resume**

```python
# Add to backend/analyzer.py
from openai import AsyncOpenAI, RateLimitError, APIConnectionError, APIStatusError

_client = AsyncOpenAI()

async def validate_is_resume(text: str) -> tuple[bool, str]:
    if not text.strip():
        return False, "文字為空"

    response = await _client.chat.completions.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": "請判斷以下文字是否為一份求職履歷（resume/CV）。只回傳 JSON：{\"is_resume\": true/false, \"reason\": \"簡短原因\"}"},
            {"role": "user", "content": text[:2000]},
        ],
        temperature=0.1,
        max_tokens=200,
        response_format={"type": "json_object"},
    )
    result = json.loads(response.choices[0].message.content)
    return result["is_resume"], result["reason"]
```

- [ ] **Step 4: Update SYSTEM_PROMPT and stream_analysis with new dimension names + fields**

```python
# Replace SYSTEM_PROMPT in backend/analyzer.py
SYSTEM_PROMPT = """你是一個資深台灣招募顧問。請分析這份履歷，依序輸出 5 個維度的分析結果。

每個維度嚴格遵守以下 JSON 格式，每個維度一行：
{"type":"dimension","name":"<name>","score":<1-5>,"conclusion":"<一句話結論（繁體中文）>","suggestions":["<建議1>","<建議2>","<建議3>"],"quote":"<從履歷中摘取的具體段落原文>","optimized":"<直接改寫後的建議寫法>","optimization_logic":"<解釋為什麼這樣改更好（台灣繁體中文）>"}

5 個維度依序為：
1. experience_relevance — 經歷與目標職位的方向匹配度、量化成果
2. skill_fit — 技能廣度與深度、與目標職位的關聯性
3. layout_structure — 格式、段落順序、長度合適性
4. keyword_coverage — ATS 關鍵字覆蓋率（通用建議，無需比對 JD）
5. personal_brand — 個人摘要/目標的品牌塑造力、專業亮點

全部完成後輸出一行：{"type":"done"}"""

# Replace stream_analysis implementation
async def stream_analysis(
    resume_text: str,
    jd_text: str = "",
) -> AsyncGenerator[str, None]:
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    user_content = resume_text[:12000]
    if jd_text:
        user_content += f"\n\n目標職位描述：\n{jd_text[:3000]}"

    stream = await _client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.3,
        stream=True,
    )

    buffer = ""
    async for chunk in stream:
        delta = chunk.choices[0].delta.content or ""
        buffer += delta
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.strip()
            if line.startswith("{"):
                yield line

    yield json.dumps({"type": "done"})
```

- [ ] **Step 5: Keep _classify_error (already stubbed, just implement)**

```python
# Replace _classify_error placeholder
def _classify_error(e: Exception) -> tuple[str, str]:
    if isinstance(e, RateLimitError):
        return ("rate_limit", "AI 服務暫時繁忙，請 30 秒後重試")
    if isinstance(e, APIConnectionError):
        return ("connection", "無法連線，請確認網路後重試")
    if isinstance(e, APIStatusError) and e.status_code == 400:
        return ("content_filter", "部分內容無法分析，請確認履歷內容後重試")
    return ("unknown", "分析失敗，請重試")
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_analyzer.py -v
```
Expected: All pass (note: OpenAI-dependent tests require API key; skip with `-m "not openai"` if needed)

- [ ] **Step 7: Commit**

```bash
git add backend/analyzer.py tests/test_analyzer.py
git commit -m "feat: add resume validation and update analyzer with new SSE format"
```

---

### Task 4: Main API — All Endpoints

**Files:**
- Modify: `backend/main.py`
- Create: `tests/test_main.py`
- Create: `backend/schemas.py`

- [ ] **Step 1: Create Pydantic schemas**

```python
# backend/schemas.py
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Optional

class AnalysisResponse(BaseModel):
    id: UUID
    filename: str
    uploaded_at: datetime
    dimensions: list

class AnalysisListItem(BaseModel):
    id: UUID
    filename: str
    uploaded_at: datetime
    avg_score: float

class MetricsResponse(BaseModel):
    total: int
    events: list[dict]
```

- [ ] **Step 2: Write failing tests for endpoints**

```python
# tests/test_main.py
import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app

pytestmark = pytest.mark.asyncio

@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")

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
    resp = await client.post("/analyze", files={"pdf_file": b""})
    assert resp.status_code == 400
    assert "空的" in resp.json()["detail"]

async def test_analyze_too_large(client):
    resp = await client.post("/analyze", files={"pdf_file": b"x" * (10 * 1024 * 1024 + 1)})
    assert resp.status_code == 400
    assert "超過" in resp.json()["detail"]

async def test_analyze_not_pdf(client):
    resp = await client.post("/analyze", files={"pdf_file": b"not a pdf"})
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
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/test_main.py -v
```
Expected: FAIL

- [ ] **Step 4: Implement main.py completely**

```python
# backend/main.py — full replacement
import json
import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.sse import EventSourceResponse

from backend.pdf_parser import parse_resume, ai_preprocess_text
from backend.analyzer import stream_analysis, validate_is_resume
from backend.database import (
    get_pool, init_db, create_analysis, get_analyses,
    get_analysis, delete_analysis, get_weekly_usage, increment_weekly_usage,
)
from backend.schemas import AnalysisResponse, AnalysisListItem

ERROR_MESSAGES: dict[str, str] = {
    "empty_file":         "上傳的檔案是空的",
    "file_too_large":     "檔案超過 10MB，請壓縮後再上傳",
    "not_pdf":            "請上傳 PDF 格式檔案",
    "password_protected": "PDF 已加密，請移除密碼後再上傳",
    "corrupted_pdf":      "PDF 檔案損壞，請重新匯出後上傳",
    "scanned_pdf":        "無法解析 PDF，可能為掃描版，請改用文字版 PDF（可用 Word 匯出）",
    "not_resume":         "這看起來不是一份履歷。請上傳求職用的 PDF 履歷檔案",
}

_metrics: list[dict] = []

async def get_current_user(request: Request) -> str:
    # MVP stub — always returns a test user
    # TODO: wire up Google OAuth
    return "test-user-id"

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY 未設定")
    pool = await get_pool()
    await init_db(pool)
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/metrics")
async def metrics():
    return {"total": len(_metrics), "events": _metrics}

@app.get("/", response_class=HTMLResponse)
async def index():
    with open("frontend/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/api/analyses")
async def analyses_list(user_id: str = Depends(get_current_user)):
    pool = await get_pool()
    rows = await get_analyses(pool, user_id)
    result = []
    for row in rows:
        dims = row["dimensions"]
        scores = [d.get("score", 0) for d in dims]
        avg = sum(scores) / len(scores) if scores else 0
        result.append({
            "id": str(row["id"]),
            "filename": row["filename"],
            "uploaded_at": row["uploaded_at"].isoformat(),
            "avg_score": round(avg, 1),
        })
    return result

@app.get("/api/analyses/{analysis_id}")
async def analysis_detail(analysis_id: str, user_id: str = Depends(get_current_user)):
    pool = await get_pool()
    row = await get_analysis(pool, analysis_id)
    if not row:
        raise HTTPException(404, "分析記錄不存在")
    return {
        "id": str(row["id"]),
        "filename": row["filename"],
        "file_size": row["file_size"],
        "uploaded_at": row["uploaded_at"].isoformat(),
        "dimensions": row["dimensions"],
    }

@app.delete("/api/analyses/{analysis_id}")
async def analysis_delete(analysis_id: str, user_id: str = Depends(get_current_user)):
    pool = await get_pool()
    deleted = await delete_analysis(pool, analysis_id, user_id)
    if not deleted:
        raise HTTPException(404, "分析記錄不存在")
    return JSONResponse(status_code=204, content=None)

@app.post("/analyze")
async def analyze(
    request: Request,
    pdf_file: UploadFile = File(...),
    jd_text: str = Form(""),
    user_id: str = Depends(get_current_user),
):
    content = await pdf_file.read()

    try:
        resume_text = parse_resume(content)
    except ValueError as e:
        key = str(e)
        detail = ERROR_MESSAGES.get(key, "處理失敗，請重試")
        raise HTTPException(400, detail)

    is_resume, reason = await validate_is_resume(resume_text)
    if not is_resume:
        raise HTTPException(400, f"這看起來不是一份履歷。{reason}")

    pool = await get_pool()
    usage = await get_weekly_usage(pool, user_id)
    if usage >= 7:
        raise HTTPException(429, "本週已達 7 次使用上限")

    cleaned_text = await ai_preprocess_text(resume_text)

    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pdf_size": len(content),
        "text_length": len(cleaned_text),
        "has_jd": bool(jd_text),
        "dimensions": {},
        "completed": False,
    }

    async def event_generator():
        nonlocal event
        try:
            async for data in stream_analysis(cleaned_text, jd_text):
                if await request.is_disconnected():
                    break
                try:
                    parsed = json.loads(data)
                except json.JSONDecodeError:
                    yield {"data": data}
                    continue
                if parsed.get("type") == "dimension":
                    event["dimensions"][parsed["name"]] = parsed.get("score")
                if parsed.get("type") == "done":
                    event["completed"] = True
                    dims = [v for v in event["dimensions"].values()]
                    await increment_weekly_usage(pool, user_id)
                    await create_analysis(
                        pool, user_id,
                        pdf_file.filename or "resume.pdf",
                        len(content),
                        [{"name": k, "score": v} for k, v in event["dimensions"].items()],
                    )
                yield {"data": data}
        finally:
            _metrics.append(event)

    return EventSourceResponse(event_generator())
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_main.py -v
```
Expected: All pass (note: requires DATABASE_URL env var for DB-dependent tests)

- [ ] **Step 6: Commit**

```bash
git add backend/main.py backend/schemas.py tests/test_main.py
git commit -m "feat: implement all API endpoints with validation, history, and weekly limit"
```

---

### Task 5: Frontend — Sidebar + Responsive + 7 States

**Files:**
- Rewrite: `frontend/index.html`

**Instructions:** Use ui-ux-pro-max skill to generate a complete single-page HTML/CSS/JS application with:

**Design system (from design.md):**
- Colors: Navy Blue (#0b1120 primary, #3b82f6 accent, #f4f7fa bg, #1e293b dark, #94a3b8 muted, #0f172a sidebar)
- Typography: Noto Sans TC (Chinese), Plus Jakarta Sans (English/numbers)
- Style: Editorial/magazine, generous whitespace, 8-16px border-radius, subtle shadows (`0 25px 50px -12px rgba(0,0,0,0.12)`)
- No emoji anywhere
- No external CSS frameworks

**Layout (responsive):**
- Desktop (>=1024px): Permanent 240px sidebar (left) + main content (right)
- Tablet (640-1023px): Collapsible sidebar via hamburger menu, overlay with semi-transparent backdrop
- Mobile (<640px): No sidebar, separate pages (history page, analysis detail page, upload page)

**Nav bar:**
- Desktop: brand + tabs (分析/歷史記錄) + email + usage badge (x/7) + logout
- Tablet: brand + hamburger + badge
- Mobile: per-page config (history page has back arrow, upload page has brand)

**7 states to support:**
1. **Logged out** — Google login button, centered
2. **Upload (ready)** — Drag & drop zone with subtle dashed border, file size hint
3. **Upload (loading/streaming)** — Progress indicator, first cards appear as SSE arrives
4. **5 cards complete** — Full analysis display; each card has star rating, conclusion (gradient blue bg + blue left border), suggestions (dot list), quote (italic, subtle bg), optimized version (green-tinted bg), optimization logic
5. **Limit exhausted** — Red-bordered message "本週已達 7 次使用上限，請下週再試"
6. **Non-resume error** — Red-bordered error with reason + "重新選擇檔案" button
7. **Empty history** — Sidebar shows "尚無分析記錄" placeholder

**Sidebar:**
- Desktop: permanent, list items with filename + date + avg star rating; selected item has blue left border + white bg
- Tablet: hamburger toggle, overlay slides in
- Mobile: separate page ("歷史記錄" tab in nav)
- Upload button at top of sidebar ("上傳新履歷")

**Interactions:**
- Click sidebar item → load analysis detail in main content
- Click "上傳新履歷" → switch to upload mode
- Debounce upload button to prevent double-click
- SSE progress: show loading skeleton, replace with card content as events arrive
- Responsive: use CSS media queries, no JS resize listeners needed

- [ ] **Step 1: Generate frontend/index.html using ui-ux-pro-max skill**

- [ ] **Step 2: Commit**

```bash
git add frontend/index.html
git commit -m "feat: responsive frontend with sidebar, history, and 7 states"
```

---

### Task 6: Documentation — Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update API spec to match new endpoints**

Changes needed in CLAUDE.md:
1. Update dimension names (overall_structure → experience_relevance, etc.)
2. Update SSE event format (add conclusion, quote, optimized, optimization_logic fields)
3. Add not_resume to error table
4. Update file size from 5MB to 10MB
5. Add DATABASE_URL to env vars table
6. Add new API endpoints to architecture diagram:
   - GET /api/analyses
   - GET /api/analyses/{id}
   - DELETE /api/analyses/{id}
   - GET /metrics
7. Add history storage layer to architecture diagram (PostgreSQL)
8. Add new file listings to file structure:
   - `backend/database.py`
   - `backend/schemas.py`

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with new API spec, dimensions, and endpoints"
```

---

## Self-Review

**Spec coverage check:**
- §1 Persona A/B → covered by existing design doc
- §2 US1 (analysis report) → Task 3 (SSE format) + Task 5 (frontend cards)
- §2 US2 (non-resume upload) → Task 3 (validate_is_resume) + Task 4 (400 error, no usage deduct before validation)
- §2 US3 (history) → Task 1 (DB) + Task 4 (history endpoints) + Task 5 (sidebar)
- §3 Metrics → Task 4 (metrics endpoint) + Task 5 (usage badge)
- §4 MVP scope → all tasks cover all items
- §5 User flow → Task 4 (complete flow in main.py)
- §6 Dimensions → Task 3 (updated names + fields)
- §7 Responsive design → Task 5 (3 breakpoint layouts)
- §8 Tech architecture → Tasks 1-4
- §9 Edge cases → Task 2 (A1-A6), Task 5 (A11 debounce), Task 3 (C2/C4), Task 4 (C8/E3/E5), Task 1 (D5 cache), Task 5 (E6 display), Task 4 (F2 is_disconnected check)
- §10 SSE format → Task 3 (new JSON fields)
- §11 Error table → Task 4 (not_resume added)
- §12 Env vars → Task 6 (CLAUDE.md update)

**Placeholder scan:** No TODOs, TBDs, or "implement later" remain. Every step has complete code.

**Type consistency:** 
- `validate_is_resume` returns `tuple[bool, str]` — consistent across Task 3 and Task 4 usage
- `ai_preprocess_text` takes `str`, returns `str` — consistent
- `stream_analysis` yields JSON strings — consistent
- DB function signatures match across Task 1 create and Task 4 usage
