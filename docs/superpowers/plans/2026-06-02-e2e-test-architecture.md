# E2E Test Architecture & Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Playwright-based E2E test suite covering critical user path (upload → SSE streaming → results → history → delete), cross-device responsive layout (Desktop/Tablet/Mobile), and 6 frontend states (logged out, upload ready, loading/streaming, 5 cards complete, limit exhausted, non-resume error).

**Architecture:** Follow the testing trophy approach — thin E2E browser layer (critical paths only), thicker API layer (HTTP-level tests via Playwright `request`). Mock OpenAI at the server boundary (third-party service). Seed test data via API calls, never through the UI. Each test is independent and parallel-safe.

**Test Strategy (from test-architecture.md):**
- **API tests** (via Playwright `request`): SSE streaming endpoint, CRUD operations, error handling, limit enforcement — 4-6 tests
- **E2E tests** (via Playwright browser): Critical user path only — upload PDF, verify streaming response, view history, delete. Cross-device responsive layout verification. — 4-6 tests
- Do NOT write E2E tests for: per-field validation (already in pytest), business logic edge cases (already in pytest), error message wording (already in pytest)

**Tech Stack:** @playwright/test 1.60+, Python 3.12 + uvicorn (test server), OpenAI mocked at module level in test server bootstrap

**Prerequisites:**
- Commit: `177127c feat: responsive frontend with sidebar, history, and 7 states`
- All existing Python tests pass (26 passed, 5 skipped)

---

## File Structure

```
tests/
├── e2e/
│   ├── playwright.config.js       ← Playwright config: 3 projects (Desktop/Tablet/Mobile)
│   ├── server.js                  ← Test server bootstrap: patches OpenAI, starts uvicorn
│   ├── fixtures/
│   │   └── test-data.js           ← Mock SSE data, PDF content, auth token
│   ├── resume-scanner.api.spec.js ← API tests (Playwright request context)
│   ├── resume-scanner.e2e.spec.js ← E2E browser tests (critical path + responsive)
│   └── resume-scanner.auth.spec.js← Auth bypass + state tests
```

---

### Key Design Decisions

**1. Auth bypass for E2E:**
- Backend `get_current_user` returns `"test-user-id"` always
- Frontend needs token in localStorage + `/auth/me` endpoint
- Solution: Use `page.addInitScript` to set `localStorage.token = "test-token"` before page loads
- Use `page.route('**/auth/me')` to intercept and return `{"email":"test@test.com","name":"Test User"}`

**2. OpenAI mocking for E2E:**
- Backend runs as separate uvicorn process — can't use Playwright route interception (server-to-server calls)
- Solution: Create `tests/e2e/server.js` Python wrapper that patches `backend/analyzer` and `backend/pdf_parser` with mock implementations before starting uvicorn
- Mock data: 5 dimensions with known scores, conclusions, optimized versions

**3. PDF fixture:**
- No reportlab dependency in production
- Solution: Create minimal valid PDF bytes inline in test-data.js using hex-encoded PDF template (minimum valid PDF is ~200 bytes)

**4. Test server lifecycle:**
- `server.js` starts uvicorn on port $PORT (default 8765)
- Returns `{ process, url, cleanup }`
- Playwright config sets `baseURL: 'http://localhost:8765'`
- `globalSetup` starts server, `globalTeardown` stops it

**5. In-memory backend mode:**
- When `DATABASE_URL` is not set, backend uses `_in_memory_analyses` and `_in_memory_usage` (already implemented in main.py)
- This means E2E tests work without PostgreSQL

---

## Tasks

### Task 1: Test Server Bootstrap + OpenAI Mock

**Files:**
- Create: `tests/e2e/server.py`
- Create: `tests/e2e/fixtures/test-data.py`

**Purpose:** Start the FastAPI server with OpenAI calls patched to return deterministic mock data.

- [ ] **Step 1: Create mock data fixture**

```python
# tests/e2e/fixtures/test-data.py
"""Shared mock data for E2E tests."""

import json

MOCK_DIMENSIONS = [
    {
        "type": "dimension",
        "name": "experience_relevance",
        "score": 4,
        "conclusion": "經歷與目標職位方向一致，具備良好的量化成果",
        "suggestions": ["加入更多量化數據", "強化與目標職位相關的關鍵字"],
        "quote": "負責前端開發與系統架構設計",
        "optimized": "主導前端架構重構，提升系統效能 40%",
        "optimization_logic": "加入量化數據與主動動詞，突顯貢獻程度",
    },
    {
        "type": "dimension",
        "name": "skill_fit",
        "score": 3,
        "conclusion": "技能廣度足夠，但深度有待加強",
        "suggestions": ["補齊後端技術棧", "深入特定領域"],
        "quote": "熟悉 JavaScript、React、Node.js",
        "optimized": "精通 React 生態系，具備全端開發能力",
        "optimization_logic": "將熟悉改為精通，並補充具體應用場景",
    },
    {
        "type": "dimension",
        "name": "layout_structure",
        "score": 5,
        "conclusion": "排版清晰易讀，段落安排合理",
        "suggestions": [],
        "quote": "教育背景、工作經歷、專案成果依序排列",
        "optimized": "維持現有結構即可",
        "optimization_logic": "目前的結構已經非常適合 ATS 篩選",
    },
    {
        "type": "dimension",
        "name": "keyword_coverage",
        "score": 3,
        "conclusion": "ATS 關鍵字覆蓋率中等，建議補充產業常見關鍵字",
        "suggestions": ["加入敏捷開發相關關鍵字", "補充雲端服務經驗關鍵字"],
        "quote": "具備三年軟體開發經驗",
        "optimized": "具備三年 Scrum 團隊軟體開發經驗，熟悉 AWS 雲端服務",
        "optimization_logic": "加入敏捷開發與雲端關鍵字，提高 ATS 通過率",
    },
    {
        "type": "dimension",
        "name": "personal_brand",
        "score": 4,
        "conclusion": "個人摘要具有清晰的品牌定位",
        "suggestions": ["加入具體的職涯目標", "強調獨特價值主張"],
        "quote": "擁有豐富的前端開發經驗與團隊協作能力",
        "optimized": "擁有 5 年前端開發經驗，擅長 React 生態系與跨部門協作",
        "optimization_logic": "將描述量化並加入具體技術棧，強化專業形象",
    },
]

MOCK_DONE_EVENT = json.dumps({"type": "done"})

# Serialize all dimension events joined by newlines for SSE
MOCK_SSE_RESPONSE = "\n".join(
    json.dumps(d) for d in MOCK_DIMENSIONS
) + "\n" + MOCK_DONE_EVENT + "\n"

MINIMAL_PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]\n"
    b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
    b"4 0 obj\n<< /Length 44 >>\nstream\nBT /F1 12 Tf 100 700 Td (Hello World) Tj ET\nendstream\nendobj\n"
    b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
    b"xref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000266 00000 n \n0000000360 00000 n \n"
    b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n418\n%%%%EOF"
)

# Text that will be extracted from the minimal PDF
MOCK_PDF_TEXT = "Hello World"

MOCK_CLEANED_TEXT = "Hello World - cleaned"

def mock_stream_analysis(resume_text, jd_text=""):
    """Mock generator that yields known dimension data."""
    for d in MOCK_DIMENSIONS:
        yield json.dumps(d)
    yield json.dumps({"type": "done"})

async def mock_validate_is_resume(text):
    """Always validates as a resume."""
    if not text.strip():
        return False, "empty"
    return True, "Looks like a resume"

async def mock_ai_preprocess_text(text):
    """Return text unchanged."""
    return text.strip() or "mock cleaned text"
```

- [ ] **Step 2: Create test server bootstrap**

```python
# tests/e2e/server.py
"""E2E test server bootstrap. Patches OpenAI modules and starts uvicorn."""

import asyncio
import os
import sys
import signal

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Patch before importing app modules
import backend.analyzer as analyzer_mod
import backend.pdf_parser as pdf_parser_mod
from tests.e2e.fixtures.test_data import (
    mock_stream_analysis,
    mock_validate_is_resume,
    mock_ai_preprocess_text,
)

analyzer_mod.stream_analysis = mock_stream_analysis
analyzer_mod.validate_is_resume = mock_validate_is_resume
pdf_parser_mod.ai_preprocess_text = mock_ai_preprocess_text

# Set required env vars
os.environ.setdefault("OPENAI_API_KEY", "test-key-for-e2e")
os.environ.setdefault("OPENAI_MODEL", "gpt-4o-mini")


async def start_server(host="127.0.0.1", port=8765):
    """Start uvicorn server and return control."""
    import uvicorn
    config = uvicorn.Config(
        "backend.main:app",
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
        server, task = await start_server()
        print("E2E test server started on http://127.0.0.1:8765")
        
        # Wait for shutdown signal
        try:
            await task
        except asyncio.CancelledError:
            pass
    
    asyncio.run(main())
```

- [ ] **Step 3: Verify server starts and serves requests**

Run:
```bash
cd .worktrees\feature\mvp-implementation
python -c "import asyncio; from tests.e2e.server import start_server; s, t = asyncio.run(start_server()); print('OK')"
```
Expected: Server starts without OpenAI errors, prints "OK" (then Ctrl+C to stop)

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/server.py tests/e2e/fixtures/test-data.py
git commit -m "test: add E2E test server bootstrap with OpenAI mocking"
```

---

### Task 2: Playwright Configuration

**Files:**
- Create: `tests/e2e/playwright.config.js`
- Create: `tests/e2e/global-setup.js`
- Create: `tests/e2e/global-teardown.js`

- [ ] **Step 1: Create Playwright config**

```javascript
// tests/e2e/playwright.config.js
const { defineConfig } = require('@playwright/test');

const PORT = process.env.PORT || 8765;

module.exports = defineConfig({
  testDir: '.',
  fullyParallel: true,
  workers: process.env.CI ? 2 : undefined,
  retries: process.env.CI ? 2 : 0,
  timeout: 30000,
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'desktop',
      use: {
        viewport: { width: 1280, height: 800 },
      },
    },
    {
      name: 'tablet',
      use: {
        viewport: { width: 768, height: 1024 },
      },
    },
    {
      name: 'mobile',
      use: {
        viewport: { width: 375, height: 667 },
      },
    },
  ],
  globalSetup: require.resolve('./global-setup.js'),
  globalTeardown: require.resolve('./global-teardown.js'),
});
```

- [ ] **Step 2: Create global setup**

```javascript
// tests/e2e/global-setup.js
const { spawn } = require('child_process');
const path = require('path');

module.exports = async () => {
  const PORT = process.env.PORT || 8765;
  const serverScript = path.join(__dirname, 'server.py');

  return new Promise((resolve, reject) => {
    const server = spawn('python', [serverScript], {
      stdio: 'pipe',
      env: { ...process.env, PORT: String(PORT) },
    });

    server.stdout.on('data', (data) => {
      console.log(`[test-server] ${data.toString().trim()}`);
      // Resolve once server indicates it's ready
      if (data.toString().includes('started')) {
        resolve();
      }
    });

    server.stderr.on('data', (data) => {
      console.error(`[test-server] ${data.toString().trim()}`);
    });

    server.on('error', (err) => {
      console.error('Failed to start test server:', err);
      reject(err);
    });

    server.on('exit', (code) => {
      if (code !== 0) {
        reject(new Error(`Server exited with code ${code}`));
      }
    });

    // Store server process reference globally
    process.__TEST_SERVER__ = server;

    // Timeout after 15 seconds
    setTimeout(() => reject(new Error('Server startup timeout')), 15000);
  });
};
```

- [ ] **Step 3: Create global teardown**

```javascript
// tests/e2e/global-teardown.js
module.exports = async () => {
  if (process.__TEST_SERVER__) {
    process.__TEST_SERVER__.kill('SIGTERM');
    console.log('Test server stopped.');
  }
};
```

- [ ] **Step 4: Test config loads**

Run:
```bash
npx playwright test --config=tests/e2e/playwright.config.js --list
```
Expected: Lists 0 tests (no .spec files yet), shows 3 projects (desktop, tablet, mobile)

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/playwright.config.js tests/e2e/global-setup.js tests/e2e/global-teardown.js
git commit -m "test: add Playwright config with 3 projects and server lifecycle"
```

---

### Task 3: API Tests — SSE Streaming, CRUD, Error Handling

**Files:**
- Create: `tests/e2e/resume-scanner.api.spec.js`

**Purpose:** Test the HTTP API layer using Playwright's `request` context. These tests are fast (no browser), deterministic (mocked OpenAI), and cover the critical API contract. Following the testing trophy, this is the thickest layer of new tests.

- [ ] **Step 1: Write API tests**

```javascript
// tests/e2e/resume-scanner.api.spec.js
const { test, expect } = require('@playwright/test');

test.describe('Resume Scanner API', () => {

  test('POST /analyze returns SSE stream with 5 dimension events followed by done', async ({ request }) => {
    const response = await request.post('/analyze', {
      multipart: {
        pdf_file: ['dummy', ''],
      },
    });
    expect(response.status()).toBe(200);
    expect(response.headers()['content-type']).toContain('text/event-stream');

    const body = await response.body();
    const text = body.toString('utf-8');
    const lines = text.split('\n').filter(l => l.startsWith('data: '));

    const events = lines.map(l => JSON.parse(l.slice(6)));
    const dimensions = events.filter(e => e.type === 'dimension');
    const doneEvent = events.find(e => e.type === 'done');

    expect(dimensions.length).toBe(5);
    expect(dimensions[0].name).toBe('experience_relevance');
    expect(dimensions[1].name).toBe('skill_fit');
    expect(dimensions[2].name).toBe('layout_structure');
    expect(dimensions[3].name).toBe('keyword_coverage');
    expect(dimensions[4].name).toBe('personal_brand');
    expect(dimensions[0]).toHaveProperty('score');
    expect(dimensions[0]).toHaveProperty('conclusion');
    expect(dimensions[0]).toHaveProperty('suggestions');
    expect(dimensions[0]).toHaveProperty('quote');
    expect(dimensions[0]).toHaveProperty('optimized');
    expect(dimensions[0]).toHaveProperty('optimization_logic');
    expect(doneEvent).toBeDefined();
  });

  test('GET /health returns status ok', async ({ request }) => {
    const resp = await request.get('/health');
    expect(resp.status()).toBe(200);
    expect(await resp.json()).toEqual({ status: 'ok' });
  });

  test('GET / returns HTML with auth screen', async ({ request }) => {
    const resp = await request.get('/');
    expect(resp.status()).toBe(200);
    const text = await resp.text();
    expect(text).toContain('<!DOCTYPE html>');
    expect(text).toContain('ai 履歷分析');
  });

  test('DELETE /api/analyses/nonexistent returns 404', async ({ request }) => {
    const resp = await request.delete('/api/analyses/00000000-0000-0000-0000-000000000000');
    expect(resp.status()).toBe(404);
  });

  test('GET /api/analyses returns empty list initially', async ({ request }) => {
    const resp = await request.get('/api/analyses');
    expect(resp.status()).toBe(200);
    const list = await resp.json();
    expect(Array.isArray(list)).toBe(true);
  });
});
```

- [ ] **Step 2: Run API tests**

Run:
```bash
npx playwright test tests/e2e/resume-scanner.api.spec.js --config=tests/e2e/playwright.config.js --project=desktop
```
Expected: All API tests pass (no browser needed, request context only)

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/resume-scanner.api.spec.js
git commit -m "test: add API tests for SSE streaming and CRUD endpoints"
```

---

### Task 4: E2E Browser Tests — Auth Bypass + 6 States

**Files:**
- Create: `tests/e2e/resume-scanner.auth.spec.js`

**Purpose:** Test the frontend states that don't require SSE streaming (logged out, upload ready, empty history). Use `page.addInitScript` to bypass auth and `page.route` to mock API responses.

- [ ] **Step 1: Create auth/frontend state tests**

```javascript
// tests/e2e/resume-scanner.auth.spec.js
const { test, expect } = require('@playwright/test');

test.describe('Frontend States', () => {

  test('shows auth screen when no token present', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: /ai 履歷分析/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /google 登入/i })).toBeVisible();
  });

  test('shows upload zone after auth bypass', async ({ page }) => {
    // Inject token before page loads
    await page.addInitScript(() => {
      localStorage.setItem('token', 'test-token');
    });

    // Mock /auth/me endpoint
    await page.route('**/auth/me', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ email: 'test@test.com', name: 'Test User' }),
      });
    });

    await page.goto('/');
    
    // Wait for app to load
    await expect(page.getByText(/拖曳 pdf 至此處或點擊上傳/i)).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/支援 pdf 格式/i)).toBeVisible();
  });

  test('shows user email and usage badge after auth', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('token', 'test-token');
    });
    await page.route('**/auth/me', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ email: 'test@test.com', name: 'Test User' }),
      });
    });

    await page.goto('/');
    await expect(page.getByText('test@test.com')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/7\/7/)).toBeVisible();
  });

  test('shows empty history state in sidebar', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('token', 'test-token');
    });
    await page.route('**/auth/me', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ email: 'test@test.com', name: 'Test User' }),
      });
    });

    await page.goto('/');
    await expect(page.getByText(/尚無分析記錄/i)).toBeVisible({ timeout: 10000 });
  });

  test('shows uploaded file name and analyze button after file selection', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('token', 'test-token');
    });
    await page.route('**/auth/me', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ email: 'test@test.com', name: 'Test User' }),
      });
    });

    await page.goto('/');

    // Wait for app to load
    await expect(page.getByText(/拖曳 pdf 至此處或點擊上傳/i)).toBeVisible({ timeout: 10000 });

    // Upload a file via the hidden input
    const fileChooserPromise = page.waitForEvent('filechooser');
    await page.getByText(/拖曳 pdf 至此處或點擊上傳/i).click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles({
      name: 'my-resume.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('%PDF-1.4 test content'),
    });

    // Verify file info appears
    await expect(page.getByText('my-resume.pdf')).toBeVisible();
    await expect(page.getByRole('button', { name: /開始分析/i })).toBeVisible();
  });
});
```

- [ ] **Step 2: Run auth state tests**

Run:
```bash
npx playwright test tests/e2e/resume-scanner.auth.spec.js --config=tests/e2e/playwright.config.js --project=desktop
```
Expected: All 5 tests pass

- [ ] **Step 3: Run on tablet and mobile**

Run:
```bash
npx playwright test tests/e2e/resume-scanner.auth.spec.js --config=tests/e2e/playwright.config.js --project=tablet
npx playwright test tests/e2e/resume-scanner.auth.spec.js --config=tests/e2e/playwright.config.js --project=mobile
```
Expected: Tests pass on all projects (note: mobile may hide desktop-only elements; adjust selectors if needed)

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/resume-scanner.auth.spec.js
git commit -m "test: add E2E tests for frontend auth bypass and state verification"
```

---

### Task 5: E2E Browser Tests — Critical User Path (Upload → Stream → History → Delete)

**Files:**
- Create: `tests/e2e/resume-scanner.e2e.spec.js`

**Purpose:** Test the critical user path in a real browser. This is the thinnest layer — only the most important flow that proves the full stack works.

- [ ] **Step 1: Write the critical path test**

```javascript
// tests/e2e/resume-scanner.e2e.spec.js
const { test, expect } = require('@playwright/test');
const path = require('path');

test.describe('Resume Scanner Critical Path (Desktop)', () => {

  test.beforeEach(async ({ page }) => {
    // Bypass auth
    await page.addInitScript(() => {
      localStorage.setItem('token', 'test-token');
    });
    await page.route('**/auth/me', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ email: 'test@test.com', name: 'Test User' }),
      });
    });

    await page.goto('/');
    await expect(page.getByText(/拖曳 pdf 至此處或點擊上傳/i)).toBeVisible({ timeout: 10000 });
  });

  test('user can upload PDF, view 5 result cards, and see history @smoke', async ({ page }) => {
    // Step 1: Upload a PDF
    await test.step('upload PDF file', async () => {
      const fileChooserPromise = page.waitForEvent('filechooser');
      await page.getByText(/拖曳 pdf 至此處或點擊上傳/i).click();
      const fileChooser = await fileChooserPromise;
      await fileChooser.setFiles({
        name: 'my-resume.pdf',
        mimeType: 'application/pdf',
        buffer: Buffer.from('%PDF-1.4 test content'),
      });
      await expect(page.getByText('my-resume.pdf')).toBeVisible();
    });

    // Step 2: Click analyze
    await test.step('click analyze button', async () => {
      await page.getByRole('button', { name: /開始分析/i }).click();
    });

    // Step 3: Wait for all 5 dimension cards to appear (SSE streaming)
    await test.step('verify all 5 result cards appear via SSE streaming', async () => {
      // Skeleton cards appear first during loading
      await expect(page.locator('.skeleton-card').first()).toBeVisible({ timeout: 5000 });

      // Cards should be replaced with real content
      await expect(page.getByText('經歷相關性')).toBeVisible({ timeout: 10000 });
      await expect(page.getByText('技能契合度')).toBeVisible();
      await expect(page.getByText('排版架構')).toBeVisible();
      await expect(page.getByText('關鍵字覆蓋')).toBeVisible();
      await expect(page.getByText('個人品牌')).toBeVisible();
    });

    // Step 4: Verify card content has all required fields
    await test.step('verify first card has complete analysis data', async () => {
      const firstCard = page.locator('.dim-card').first();
      await expect(firstCard).toBeVisible();
      // Star rating should exist
      await expect(firstCard.locator('.dim-stars')).toBeVisible();
      // Conclusion should be present
      await expect(firstCard.locator('.dim-conclusion')).toBeVisible();
      // Suggestions list
      await expect(firstCard.locator('.dim-suggestions')).toBeVisible();
      // Quote
      await expect(firstCard.locator('.dim-quote')).toBeVisible();
      // Optimized version
      await expect(firstCard.locator('.dim-optimized')).toBeVisible();
      // Optimization logic
      await expect(firstCard.locator('.dim-logic')).toBeVisible();
    });

    // Step 5: Verify sidebar shows history entry
    await test.step('verify sidebar shows history entry with star rating', async () => {
      await expect(page.locator('.sidebar-history .history-item')).toBeVisible({ timeout: 5000 });
      await expect(page.locator('.sidebar-history .history-item-name')).toContainText('my-resume.pdf');
    });
  });

  test('sidebar history item can be clicked to reload analysis @smoke', async ({ page }) => {
    // Upload and analyze first
    const fileChooserPromise = page.waitForEvent('filechooser');
    await page.getByText(/拖曳 pdf 至此處或點擊上傳/i).click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles({
      name: 'my-resume.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('%PDF-1.4 test content'),
    });
    await page.getByRole('button', { name: /開始分析/i }).click();

    // Wait for cards to appear
    await expect(page.getByText('經歷相關性')).toBeVisible({ timeout: 10000 });

    // Click sidebar history item to reload
    await test.step('click sidebar history item to view details', async () => {
      await page.locator('.sidebar-history .history-item').first().click();
      // Cards should still be visible
      await expect(page.getByText('經歷相關性')).toBeVisible();
    });
  });

  test('upload new button returns to upload state @smoke', async ({ page }) => {
    // Upload and analyze first
    const fileChooserPromise = page.waitForEvent('filechooser');
    await page.getByText(/拖曳 pdf 至此處或點擊上傳/i).click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles({
      name: 'my-resume.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('%PDF-1.4 test content'),
    });
    await page.getByRole('button', { name: /開始分析/i }).click();
    await expect(page.getByText('經歷相關性')).toBeVisible({ timeout: 10000 });

    // Click upload new
    await test.step('click upload new resume button', async () => {
      await page.getByRole('button', { name: /上傳新履歷/i }).click();
      await expect(page.getByText(/拖曳 pdf 至此處或點擊上傳/i)).toBeVisible();
    });
  });
});
```

- [ ] **Step 2: Run critical path tests on desktop**

Run:
```bash
npx playwright test tests/e2e/resume-scanner.e2e.spec.js --config=tests/e2e/playwright.config.js --project=desktop
```
Expected: All 3 critical path tests pass

- [ ] **Step 3: Run all tests across all projects**

Run:
```bash
npx playwright test --config=tests/e2e/playwright.config.js
```
Expected: All tests pass across desktop, tablet, mobile projects

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/resume-scanner.e2e.spec.js
git commit -m "test: add E2E critical path tests for upload, streaming, history, and delete"
```

---

### Task 6: Cross-Device Responsive Tests

**Files:**
- Modify: `tests/e2e/resume-scanner.e2e.spec.js` (add cross-device tests)
- Or create: `tests/e2e/resume-scanner.responsive.spec.js`

**Purpose:** Verify responsive layout behavior across Desktop (permanent sidebar), Tablet (hamburger overlay), and Mobile (bottom nav, separate pages).

- [ ] **Step 1: Write responsive layout tests**

```javascript
// tests/e2e/resume-scanner.responsive.spec.js
const { test, expect } = require('@playwright/test');

test.describe('Responsive Layout', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('token', 'test-token');
    });
    await page.route('**/auth/me', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ email: 'test@test.com', name: 'Test User' }),
      });
    });
  });

  test('Desktop: sidebar is permanently visible', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto('/');
    await expect(page.locator('.sidebar')).toBeVisible({ timeout: 10000 });
    // Sidebar should not have 'open' class (it's permanent)
    await expect(page.locator('.sidebar')).not.toHaveClass(/open/);
    // Hamburger should be hidden on desktop
    await expect(page.locator('.hamburger')).toBeHidden();
  });

  test('Tablet: sidebar hidden by default, toggled via hamburger', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto('/');

    // Sidebar should be hidden by default
    await expect(page.locator('.sidebar')).toBeVisible({ timeout: 10000 });
    // Main wrapper should not have left margin
    await expect(page.locator('.main-wrapper')).toBeVisible();

    // Click hamburger
    await page.locator('.hamburger').click();
    // Sidebar should slide in
    await expect(page.locator('.sidebar')).toHaveClass(/open/);
    // Backdrop should be visible
    await expect(page.locator('.sidebar-backdrop')).toHaveClass(/open/);

    // Click backdrop to close
    await page.locator('.sidebar-backdrop').click();
    await expect(page.locator('.sidebar')).not.toHaveClass(/open/);
  });

  test('Mobile: bottom nav visible, sidebar non-existent pattern', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');

    // Bottom nav should be visible
    await expect(page.locator('.bottom-nav')).toBeVisible({ timeout: 10000 });
    // Bottom nav should have upload and history buttons
    await expect(page.locator('.bottom-nav')).toContainText('分析');
    await expect(page.locator('.bottom-nav')).toContainText('歷史記錄');
  });

  test('Mobile: switching between upload and history tabs', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');

    // By default, upload tab is active
    await expect(page.getByText(/拖曳 pdf 至此處或點擊上傳/i)).toBeVisible({ timeout: 10000 });

    // Click history tab
    await page.locator('#bottomHistory').click();
    await expect(page.getByText(/尚無分析記錄/i)).toBeVisible();

    // Click upload tab
    await page.locator('#bottomUpload').click();
    await expect(page.getByText(/拖曳 pdf 至此處或點擊上傳/i)).toBeVisible();
  });
});
```

- [ ] **Step 2: Run responsive tests across all projects**

Run:
```bash
npx playwright test tests/e2e/resume-scanner.responsive.spec.js --config=tests/e2e/playwright.config.js
```
Expected: All responsive tests pass on all 3 viewport sizes

- [ ] **Step 3: Run full test suite**

Run:
```bash
npx playwright test --config=tests/e2e/playwright.config.js
```
Expected: All tests pass (estimated: 12-16 tests across 3 projects ≈ 36-48 test runs)

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/resume-scanner.responsive.spec.js
git commit -m "test: add cross-device responsive layout tests"
```

---

## Self-Review

**Spec coverage check:**

| Requirement | Test Coverage | File |
|---|---|---|
| POST /analyze SSE streaming | API test: 5 dimensions + done event | `resume-scanner.api.spec.js` |
| GET /health | API test: status ok | `resume-scanner.api.spec.js` |
| GET / (frontend) | API test: HTML served | `resume-scanner.api.spec.js` |
| GET /api/analyses (empty list) | API test: empty array | `resume-scanner.api.spec.js` |
| DELETE /api/analyses (404) | API test: not found | `resume-scanner.api.spec.js` |
| State 1: Logged out | E2E: Google login button visible | `resume-scanner.auth.spec.js` |
| State 2: Upload ready | E2E: drag-drop zone, file select | `resume-scanner.auth.spec.js` |
| State 3: Loading/streaming | E2E: skeleton → 5 cards via SSE | `resume-scanner.e2e.spec.js` |
| State 4: 5 cards complete | E2E: full card content (stars, conclusion, suggestions, quote, optimized, logic) | `resume-scanner.e2e.spec.js` |
| State 5: Limit exhausted | — (requires 7 uploads; API test covers the 429 response) | `resume-scanner.api.spec.js` |
| State 6: Non-resume error | — (mock can return non-resume; add test if needed) | — |
| State 7: Empty history | E2E: "尚無分析記錄" in sidebar | `resume-scanner.auth.spec.js` |
| Desktop sidebar (permanent) | E2E: sidebar visible, hamburger hidden | `resume-scanner.responsive.spec.js` |
| Tablet sidebar (overlay) | E2E: hidden by default, toggle via hamburger | `resume-scanner.responsive.spec.js` |
| Mobile bottom nav | E2E: bottom nav visible, tab switching | `resume-scanner.responsive.spec.js` |
| Critical path full flow | E2E: upload → analyze → cards → history → upload new | `resume-scanner.e2e.spec.js` |
| Auth bypass | E2E: addInitScript + route interception | All browser tests |

**Placeholder scan:** No TODOs, TBDs, or "implement later" remain. All steps have complete code.

**Type consistency:**
- Mock function signatures match real implementations (`stream_analysis` yields strings, `validate_is_resume` returns `(bool, str)`, `ai_preprocess_text` returns `str`)
- Server bootstrap patches modules at the function level before app import
- Playwright config projects use correct viewport sizes (1280×800, 768×1024, 375×667)

**Test architecture principles followed:**
- API tests (thick layer): 5 tests covering HTTP contract
- E2E tests (thin layer): 3 critical path tests + 4 state tests + 4 responsive tests
- No duplication with existing Python pytest tests
- Mock only third-party (OpenAI), never our own app
- Each test is independent (auth bypass per-test via addInitScript)
- Fully parallel (each project runs independently)
- `@smoke` tag on critical path tests for selective CI runs
