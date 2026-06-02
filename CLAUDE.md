# AI Resume Scanner — 協作框架

> **給 Claude Code：** 每次 session 開始時讀取本文件。這是系統的完整規格、架構，以及學員的開發 SOP。

---

## 專案概述

**產品：** AI Resume Scanner — 求職者上傳 PDF 履歷，AI 分析後給出 5 個維度的結構化優化建議。

**課程目的：** 讓 PM 學員體驗「與 coding agent 有效協作、打造產品驗證」的完整流程，包括需求分析、指標定義、TDD 實作、部署、產品 Pitch。

**學員角色：** PM（產品管理者）— 負責需求定義、指標設計、驗收標準，由 Claude Code 協助實作。

---

## 技術架構

```
用戶瀏覽器 (frontend/index.html)
    │  POST /analyze (multipart: pdf_file + jd_text)
    ▼
FastAPI (backend/main.py)
    ├── pdf_parser.py  ← pdfminer.six 抽取文字
    ├── analyzer.py    ← OpenAI AsyncClient 串流分析
    ├── database.py    ← PostgreSQL 連線池 + CRUD
    └── schemas.py     ← Pydantic models
         │  SSE text/event-stream
         ▼
用戶瀏覽器（逐維度渲染分析卡片）

**History API Endpoints：**
- `GET    /api/analyses`     — 歷史紀錄列表
- `GET    /api/analyses/{id}` — 單筆分析詳情
- `DELETE /api/analyses/{id}` — 刪除紀錄
```

**Tech Stack：** Python 3.12, FastAPI >= 0.135.0, pdfminer.six, openai >= 1.0.0, python-multipart

**部署：** Docker → Railway（`railway.json` 已設定，`GET /health` 為 healthcheck endpoint）

---

## 檔案結構

```
ai_resume_scanner/
├── CLAUDE.md                        ← 本文件：協作框架 + 完整規格
├── README.md                        ← 快速啟動
├── requirements.txt                 ← 生產依賴
├── requirements-dev.txt             ← 開發 / 測試依賴（-r requirements.txt + pytest）
├── pytest.ini                       ← asyncio_mode = auto, testpaths = tests
├── Dockerfile                       ← python:3.12-slim, uvicorn on ${PORT:-8000}
├── railway.json                     ← healthcheckPath /health, timeout 300s
├── .env.local                       ← 環境變數模板（複製為 .env 後填入）
├── .gitignore / .dockerignore
│
├── docs/
│   ├── pm-concepts.md               ← 前置閱讀：User Story / AC / Metric 概念
│   ├── architecture.md              ← 詳細 API + SSE + 錯誤規格（本文件補充）
│   └── superpowers/
│       ├── specs/                   ← brainstorming skill 產出（學員自己生成）
│       └── plans/                   ← writing-plans skill 產出（學員自己生成）
│
├── prompt-templates/
│   └── pitch-generator.md          ← Product Pitch 生成 prompt（4 步驟含確認閘）
│
├── backend/
│   ├── __init__.py                  ← 空白 package marker
│   ├── pdf_parser.py                ← [STUB] PDF 驗證 + 文字抽取
│   ├── analyzer.py                  ← [STUB] OpenAI async 串流分析
│   ├── database.py                  ← PostgreSQL 連線池 + CRUD
│   ├── schemas.py                   ← Pydantic models
│   └── main.py                      ← [STUB] FastAPI app + 所有 endpoints
│
├── frontend/
│   └── index.html                   ← [學員產出] frontend-design skill 生成
│
└── tests/
    ├── __init__.py                  ← 空白
    ├── conftest.py                  ← autouse fixture：設定 OPENAI_API_KEY 測試用值
    ├── test_database.py
    ├── test_analyzer.py
    ├── test_main.py
    └── test_pdf_parser.py
```

---

## API 規格

### GET /health
**Response:** `{"status": "ok"}` (200)
**用途：** Railway healthcheck

### GET /
**Response:** `frontend/index.html` (HTMLResponse 200)

### POST /analyze
**Request:** `multipart/form-data`
- `pdf_file`: UploadFile（PDF 檔案）
- `jd_text`: str（選填，目標職位 JD）

**Response:** `text/event-stream` (200)
每行格式：`data: <json>\n\n`

**Flow:**
1. Parse PDF
2. Validate it's a resume → if not, 400
3. Check weekly usage → if >= 7, 429
4. AI pre-process to fix garbled text
5. SSE streaming analysis
6. On done: save to DB, increment usage

**Error Responses:**
- 400: `{"detail": "<使用者可讀錯誤訊息>"}`
- 429: `{"detail": "您本週已使用 7 次，請下週再來"}`

**錯誤訊息對照表：**

| ValueError key | HTTP 400 detail |
|---------------|-----------------|
| `empty_file` | 上傳的檔案是空的 |
| `file_too_large` | 檔案超過 10MB，請壓縮後再上傳 |
| `not_pdf` | 請上傳 PDF 格式檔案 |
| `password_protected` | PDF 已加密，請移除密碼後再上傳 |
| `corrupted_pdf` | PDF 檔案損壞，請重新匯出後上傳 |
| `scanned_pdf` | 無法解析 PDF，可能為掃描版，請改用文字版 PDF（可用 Word 匯出） |
| `not_resume` | 這看起來不是一份履歷。請上傳求職用的 PDF 履歷檔案 |

### GET /api/analyses
**Response:** `[{id, filename, uploaded_at, avg_score}]` (200)

### GET /api/analyses/{id}
**Response:** `{id, filename, file_size, uploaded_at, dimensions}` (200)
**Error:** 404

### DELETE /api/analyses/{id}
**Response:** 204
**Error:** 404

### GET /metrics
**Response:** `{"total": <int>, "events": [<event>, ...]}`
每個 event 包含：`{timestamp, pdf_size, text_length, has_jd, dimensions: {name: score}, completed}`

---

## SSE Event Format

串流過程中 frontend 收到的 SSE events：

```jsonc
// 維度分析結果（5 個，依序出現）
{"type":"dimension","name":"experience_relevance","score":4,"conclusion":"經歷與目標職位方向一致","suggestions":["加入量化數據","強化關鍵字"],"quote":"負責前端開發","optimized":"主導前端架構重構","optimization_logic":"加入量化數據與主動動詞"}

// 全部完成
{"type":"done"}

// 錯誤（OpenAI 失敗時）
{"type":"error","code":"rate_limit","message":"AI 服務暫時繁忙，請 30 秒後重試"}
```

**維度名稱（依序）：**

| name | 中文標題 | 分析重點 |
|------|---------|---------|
| `experience_relevance` | 經歷相關性 | 經歷與目標職位的方向匹配度、量化成果
| `skill_fit` | 技能契合度 | 技能廣度與深度、與目標職位的關聯性
| `layout_structure` | 排版架構 | 格式、段落順序、長度合適性
| `keyword_coverage` | 關鍵字覆蓋 | ATS 關鍵字覆蓋率（通用建議，無需比對 JD）
| `personal_brand` | 個人品牌 | 個人摘要/目標的品牌塑造力、專業亮點

**Error codes：**

| code | 觸發條件 |
|------|---------|
| `rate_limit` | OpenAI RateLimitError（SDK 自動 retry 2x 後） |
| `connection` | OpenAI APIConnectionError |
| `content_filter` | OpenAI APIStatusError 400 |
| `unknown` | 其他例外 |

---

## PDF 解析規格

**驗證順序（parse_resume）：**
1. `len(content) == 0` → `ValueError("empty_file")`
2. `len(content) > 10 * 1024 * 1024` → `ValueError("file_too_large")`
3. `content[:4] != b"%PDF"` → `ValueError("not_pdf")`
4. pdfminer 解析（`LAParams(char_margin=2.0, word_margin=0.1)`）
   - `PDFPasswordIncorrect` → `ValueError("password_protected")`
   - `PDFSyntaxError` / `TypeError` → `ValueError("corrupted_pdf")`
5. `len(text.strip()) < 50` → `ValueError("scanned_pdf")`
6. 截斷至 `text[:12_000]`，回傳

**重要：** 使用 `tempfile.NamedTemporaryFile`，在 `finally` 確保清理。

---

## OpenAI 分析規格

**模型：** `os.environ.get("OPENAI_MODEL", "gpt-4o-mini")`

**Prompt 策略：**
- System prompt：設定為資深台灣招募顧問角色，要求繁體中文輸出，逐維度輸出 JSON
- User prompt：履歷文字 + 可選 JD
- Temperature: 0.3
- stream=True

**Buffer 機制：**
累積 response chunks，按 `\n` 切割，驗證 JSON 後 yield，最後加 `{"type":"done"}`。

**Client：** module-level `_client = AsyncOpenAI()`（非 lazy，無競態）

---

## 環境變數

| 變數 | 必填 | 預設 | 說明 |
|------|------|------|------|
| `OPENAI_API_KEY` | 是 | — | OpenAI API key，啟動時驗證 |
| `OPENAI_MODEL` | 否 | `gpt-4o-mini` | 使用的模型 |
| `PORT` | 否 | `8000` | Railway 自動注入 |
| `DATABASE_URL` | 否 | — | PostgreSQL 連線字串 |

---

## 學員開發 SOP

### 開始前（必做）
1. 讀 `docs/pm-concepts.md`（10 分鐘）
2. `cp .env.local .env` 並填入 `OPENAI_API_KEY`
3. `pip install -r requirements-dev.txt`

### Step 1：需求訪談（brainstorming skill）

在 Claude Code 輸入你對這個產品的想法，brainstorming skill 引導你定義：
- 目標用戶 Persona
- User Story + Acceptance Criteria
- 產品指標（北極星 + 子指標）

遇到 UI 問題時，接受 Visual Companion 提議。

產出：`docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`

**PM 自查：**
- User Story 有明確角色、功能、可衡量的價值嗎？
- AC 有 Given/When/Then 且含邊界值嗎？
- 北極星指標可量化且直接反映用戶拿到核心價值嗎？

### Step 2：隔離工作環境（using-git-worktrees skill）

### Step 3：實作計劃（writing-plans skill）

產出：`docs/superpowers/plans/YYYY-MM-DD-<feature>.md`

計劃中 Task 1 應使用 `frontend-design skill` 生成 `frontend/index.html`。

### Step 4：實作（subagent-driven-development skill）

每個 task：
- Implementer subagent 依 TDD 實作
- Spec reviewer 確認符合 spec
- Code quality reviewer 確認品質

### Step 5：E2E 驗證（Playwright MCP — 節點 2）

整合完成後，Playwright 測試：上傳 PDF → 串流分析 → 結果卡片顯示

### Step 6：部署至 Railway

```bash
git push  # Railway 自動觸發 Docker build + deploy
```

在 Railway Dashboard 設定環境變數 `OPENAI_API_KEY`。

### Step 7：生產驗證（Playwright MCP — 節點 3）

Playwright 截圖 Railway URL，確認生產環境正常。

### Step 8：Product Pitch

讀 `prompt-templates/pitch-generator.md`，複製 prompt 至 Claude Code 執行。

---

## Skill 速查表

| 情況 | Skill |
|------|-------|
| 有新 idea / 新功能 | `superpowers:brainstorming` |
| 開始實作前 | `superpowers:using-git-worktrees` + `superpowers:writing-plans` |
| 執行計劃 | `superpowers:subagent-driven-development` |
| 每個 task 實作 | `superpowers:test-driven-development` |
| 測試失敗 / bug | `superpowers:systematic-debugging` |
| Task 完成後 | `superpowers:requesting-code-review` |
| 宣告完成前 | `superpowers:verification-before-completion` |
| 所有 task 完成 | `superpowers:finishing-a-development-branch` |
| Task 1 前端設計 | `frontend-design:frontend-design` |
| E2E 驗證 | Playwright MCP（節點 2 本地 + 節點 3 生產）|
