# AI Resume Scanner

AI 驅動的履歷多維度優化分析工具。上傳 PDF 履歷，立即獲得 5 個維度的結構化建議。

## 快速啟動

### 本地開發
```bash
# 1. 安裝依賴
pip install -r requirements-dev.txt

# 2. 設定環境變數
cp .env.local .env
# 編輯 .env，填入 OPENAI_API_KEY

# 3. 啟動伺服器
uvicorn backend.main:app --reload --port 8000

# 4. 打開瀏覽器
# http://localhost:8000
```

### Docker 本地
```bash
docker build -t ai-resume-scanner .
docker run -p 8000:8000 -e OPENAI_API_KEY=your_key ai-resume-scanner
```

### Railway 部署
1. 在 Railway 建立新專案，連結此 repo
2. 設定環境變數：`OPENAI_API_KEY`
3. Push → 自動部署

## 分析維度

| 維度 | 說明 |
|------|------|
| 📋 整體結構 | 格式、段落順序、長度 |
| 👤 個人品牌 | Summary 段落力道 |
| ⭐ STAR 成果 | 工作經歷結構與量化數據 |
| ✍️ 語言表達 | 動詞力道、被動句比例 |
| 🔍 ATS 關鍵字 | 關鍵字覆蓋率（可選填 JD 對比） |

## 課程學員

請先讀 `docs/pm-concepts.md`，再依照 `CLAUDE.md` 的 SOP 開始。
