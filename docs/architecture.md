# AI Resume Scanner — Architecture Reference

> 本文件供 Claude Code 在實作時參考。是 `CLAUDE.md` 的技術補充。

---

## Data Flow

```
1. 用戶選擇 PDF（drag-drop 或 click）
2. POST /analyze (multipart)
3. FastAPI: parse_resume(bytes) → text
4. FastAPI: stream_analysis(text, jd) → AsyncGenerator
5. SSE stream → 前端逐維度渲染
6. type=done → 顯示「重新分析」按鈕
7. _metrics.append(event) → GET /metrics 可查
```

---

## Frontend 行為規格

### 狀態機

```
[閒置]
  → 上傳 PDF → [檔案已選取]
    → 點擊分析 → [前端驗證失敗] → 回到[閒置]
                → [上傳中] → [後端驗證失敗（400）] inline error 保留檔案
                           → [串流中] 5 張 skeleton → 逐一 fade-in
                             → [完成] 顯示「重新分析」
                             → [串流錯誤] Toast + 已完成卡片保留
```

### Skeleton Cards
分析開始**瞬間**顯示 5 張 skeleton（不等 SSE 回應），SSE event 到達後以 fade-in 替換。

### SSE 消費（fetch + ReadableStream）
```js
const res = await fetch('/analyze', { method: 'POST', body: formData });
const reader = res.body.getReader();
// 按 '\n' 切割，取 'data: ' 前綴後 JSON.parse
```

### Toast 通知
- 位置：右上角 fixed
- 自動消失：5 秒
- 類型：error（red border）/ info

### 錯誤顯示原則（NNGroup）
- 繁體中文、不責怪用戶
- inline error：顯示在上傳區旁，保留已選檔案
- Toast：OpenAI 失敗類錯誤，含重試按鈕

---

## Backend 模組職責

### `backend/pdf_parser.py`
- 唯一入口：`parse_resume(content: bytes) -> str`
- 輔助：`validate_pdf_magic(content: bytes) -> bool`
- 無 side effects，純函式

### `backend/analyzer.py`
- 唯一入口：`stream_analysis(resume_text, jd_text) -> AsyncGenerator[str, None]`
- 輔助：`_classify_error(e) -> tuple[str, str]`
- `get_client() -> AsyncOpenAI`（module-level singleton）

### `backend/main.py`
- FastAPI app 實例：`app`
- Lifespan 驗證 `OPENAI_API_KEY`
- `_metrics: list[dict]` module-level 儲存（MVP，非 thread-safe，多 worker 時用 Redis）

---

## Testing 規格

### test_pdf_parser.py（最少 9 個測試）
- `validate_pdf_magic`：true / false / empty（3）
- `parse_resume` error paths：empty / too_large / not_pdf（3）
- `parse_resume` mocked paths：success / truncate_12000 / scanned（3）
- 建議補充：password_protected / corrupted_pdf（2）

### test_analyzer.py（最少 5 個測試）
- `_classify_error`：rate_limit / connection / unknown（3）
- `stream_analysis`：yields dimension + done / yields error on rate_limit（2）
- mock `get_client()`，不呼叫真實 API

### test_main.py（最少 7 個測試）
- `/health` returns 200（1）
- `/analyze` 400 error paths：empty / not_pdf / too_large（3）
- `/analyze` success：200 + text/event-stream content-type（1）
- `/metrics` returns total + events（1）
- `GET /` returns HTML（1）
- 使用 `httpx.AsyncClient(transport=ASGITransport(app=app))`
- mock `parse_resume` 和 `stream_analysis`

### conftest.py
```python
@pytest.fixture(autouse=True)
def set_openai_api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-for-testing")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
```

---

## 北極星指標（供學員定義自己的版本參考）

> 每週完成完整分析的去重用戶數
> 定義：成功上傳 PDF、收到所有 5 個維度結果的 unique session（週計）

子指標：
- 上傳成功率（漏斗）
- 分析完成率（漏斗）
- 5 維度平均分（品質）
- 用戶回訪率（參與）

---

## Robustness Checklist

實作時確認：
- [ ] PDF parse 失敗路徑全部對應正確 ValueError key
- [ ] `finally` 確保 temp file 清理
- [ ] OpenAI stream 的 `except` 只捕捉已知例外（不 broad `except Exception`）
- [ ] `request.is_disconnected()` 在 event_generator 迴圈中偵測斷線
- [ ] Lifespan 驗證 `OPENAI_API_KEY`，缺少時 fail fast
- [ ] `/health` 不需 auth，確保 Railway healthcheck 能打到
