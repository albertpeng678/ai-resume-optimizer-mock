# AI Resume Scanner — 產品設計規格（v2）

> 產出方式：brainstorming skill
> 日期：2026-06-02
> 更新內容：新增履歷驗證、歷史記錄、AI 前處理、邊緣案例

---

## 1. 目標用戶 Persona

### Persona A：新鮮人
- 應屆畢業 ∼ 1 年經驗
- 痛點：不懂履歷格式、不知道怎麼包裝經歷、常用 Word 手刻版型
- 使用場景：第一次寫履歷，需要模板指引和結構建議

### Persona B：轉職者
- 3-5 年經驗想轉職
- 痛點：經歷太雜不知怎麼聚焦、缺乏量化成果包裝、字數過長
- 使用場景：已有原型但需要優化，聚焦重點經歷

---

## 2. User Story & Acceptance Criteria

### User Story 1：分析報告
> 作為一位年輕求職者，我希望履歷分析可以有明確框架，以便我輕易理解以優化我的履歷。

**Scenario：閱讀分析報告**
- Given 我已取得分析報告
- Then 每個維度包含下列元素：
  - 星級評分（1-5）
  - 一句結論
  - 改善建議列表
  - 原文引述（從我的履歷中摘取具體段落）
  - 優化版本（直接改寫後的建議寫法）
  - 優化邏輯（解釋為什麼這樣改更好）

### User Story 2：上傳非履歷防呆
> 作為一位使用者，我不小心上傳論文/報告而非履歷時，系統應在分析前提醒我，以免浪費使用次數與獲得無意義的結果。

**Scenario：上傳非履歷檔案**
- Given 我上傳了一份 PDF 檔案
- When AI 判定這不是一份履歷
- Then 系統顯示紅框錯誤訊息「這看起來不是一份履歷」並說明原因
- And **不扣**該週使用次數
- And 我可以點「重新選擇檔案」重試

### User Story 3：歷史記錄
> 作為一位已分析過履歷的使用者，我希望可以查看過往的分析記錄，以免需要重新上傳與再次等待 AI 分析。

**Scenario：檢視歷史記錄**
- Given 我已登入且至少完成一次分析
- When 我點擊側邊欄中的歷史記錄
- Then 主內容區顯示該次分析的完整 5 維度結果
- And 側邊欄顯示最近分析列表（日期、檔名、平均星等）

**Scenario：從歷史記錄回到上傳**
- Given 我正在瀏覽某筆歷史記錄
- When 我點擊「上傳新履歷」按鈕
- Then 主內容區切換回上傳模式

---

## 3. 產品指標

| 類型 | 指標 | 定義 |
|------|------|------|
| 北極星 | 單月履歷完成數（去重複） | 每月成功完成 AI 分析的履歷數量，同一份不重複計算 |
| 廣度 | 登入用戶數 | 每月至少登入一次的用戶數 |
| 廣度 | 上傳用戶數 | 每月至少上傳一次履歷的用戶數 |
| 深度 | 單月重複使用用戶佔比 | 當月完成 ≥2 份分析的用戶 / 當月所有活躍用戶 |

---

## 4. MVP 功能範圍

### 核心功能
- Google OAuth 登入
- PDF 上傳（上限 5MB，含格式驗證）
- AI 履歷驗證（上傳後二元分類：是履歷/不是履歷）
- AI 前處理（修復 pdfminer 擷取亂序的文字）
- 5 維度分析（以 SSE 串流即時顯示）
- 結果展示頁面（每維度含評分、結論、建議、引述、優化、邏輯）
- 歷史記錄側邊欄（PostgreSQL 持久化儲存）
- 跨裝置響應式設計（Desktop / Tablet / Mobile）

### 非功能需求
- 每週 7 次使用限制（UTC 計算，週一重置）
- 繁體中文介面
- 錯誤處理（空檔案、超過大小、非 PDF、加密、損毀、掃描版）
- 邊緣案例防護（見 §9）

### 明確排除（MVP）
- JD（職位描述）比對分析
- 付費方案 / 金流
- 下載報告
- OCR 支援（掃描版 PDF 拒絕分析）

---

## 5. 用戶流程

```
首頁 → Google 登入
  → 儀表板（側邊欄歷史列表 + 主區上傳區）
    → 選擇 PDF → client-side 大小檢查
      → PDF parsing（pdfminer）
        → AI 履歷驗證（二元分類）
          ├─ 非履歷 → 紅框錯誤，不扣次數
          └─ 是履歷 → AI 前處理（修復文字順序）
            → 5 維度 SSE 串流分析
              → 結果即時寫入 PostgreSQL
                → 側邊欄自動更新
```

---

## 6. 分析維度

| 名稱 | 中文標題 | 分析重點 |
|------|---------|---------|
| `experience_relevance` | 經歷相關性 | 經歷與目標職位的方向匹配度、量化成果 |
| `skill_fit` | 技能契合度 | 技能廣度與深度、與目標職位的關聯性 |
| `layout_structure` | 排版架構 | 格式、段落順序、長度合適性 |
| `keyword_coverage` | 關鍵字覆蓋 | ATS 關鍵字覆蓋率（通用建議，無 JD 比對）|
| `personal_brand` | 個人品牌 | 個人摘要/目標的品牌塑造力、專業亮點 |

---

## 7. 跨裝置設計

### 7.1 設計系統
- **色調**：Navy Blue 單色調（`#0b1120` 主色 + `#3b82f6` 藍色點綴 + 灰階輔助）
- **字體**：Noto Sans TC（繁體中文）+ Plus Jakarta Sans（英文元素）
- **風格**：編輯/雜誌風格，大量留白（空氣感），圓角 8-16px
- **陰影**：`0 25px 50px -12px rgba(0,0,0,0.12)` 營造深度

### 7.2 Desktop（≥1024px）
- 永久側邊欄 240px（左）+ 主內容區（右）
- 側邊欄：歷史記錄列表，選中項藍色左框高亮 + 白色背景
- Nav：品牌 + tab（分析/歷史記錄）+ email + 用量 badge + 登出
- 主內容區：上傳區或 5 張完整維度卡片
- 卡片內部：結論（漸層藍底 + 藍色左框）、改善建議（dot list）、原文/優化/邏輯三塊

### 7.3 Tablet（640-1023px）
- 收合式側邊欄，漢堡選單 ☰ 點擊後 overlay 滑出
- overlay 含半透明遮罩 + 240px 側邊欄 + 陰影
- 主內容區全寬顯示
- Nav 簡化為 brand + 漢堡 + badge

### 7.4 Mobile（<640px）
- 無側邊欄，改成獨立頁面
- 歷史記錄列表頁：每筆含檔名、日期、平均星等、五維迷你標籤
- 分析詳情頁：返回箭頭、檔名 + 日期、分享/刪除按鈕、卡片內容
- 上傳頁：上傳區 + 空狀態提示
- 所有頁面 padding ≥1.15rem，底部 padding ≥2.5rem
- 大量留白確保空氣感

---

## 8. 技術架構

### 8.1 PDF 解析（pdfminer.six）
```
validate_pdf_magic(content)        → magic bytes 檢查
parse_resume(content)              → LAParams 提取文字
  │ 驗證順序：
  │ 1. 空檔案        → ValueError("empty_file")
  │ 2. >5MB          → ValueError("file_too_large")
  │ 3. 非 PDF        → ValueError("not_pdf")
  │ 4. 加密          → ValueError("password_protected")
  │ 5. 損毀          → ValueError("corrupted_pdf")
  │ 6. 文字 <50 chars→ ValueError("scanned_pdf")
  │ 7. 正常          → text[:12_000]
  │
  └→ AI 前處理（修復 pdfminer 擷取亂序/斷行問題）
       prompt <200 tokens，修正閱讀順序、還原斷字
       → 輸出 clean text 給 5 維度分析
```

### 8.2 AI 履歷驗證
- 時機：PDF parsing 後、5 維度分析前
- prompt：二元分類（是履歷/不是履歷）+ 簡短原因
- 成本：<200 tokens（遠低於完整分析）
- 不扣次數：判定非履歷時不扣該週使用次數
- 錯誤訊息：紅框顯示「這看起來不是一份履歷」+ 具體原因 + 重新選擇按鈕

### 8.3 歷史記錄（PostgreSQL）

```sql
CREATE TABLE analyses (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     TEXT NOT NULL,           -- Google OAuth sub
    filename    TEXT NOT NULL,
    file_size   INTEGER NOT NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    dimensions  JSONB NOT NULL,          -- 5 維度完整結果
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_analyses_user_id ON analyses(user_id);
CREATE INDEX idx_analyses_recents ON analyses(user_id, uploaded_at DESC);
```

**API：**
```
GET  /api/analyses          → [{id, filename, uploaded_at, dimensions}]
GET  /api/analyses/{id}     → {id, filename, ..., dimensions: [...]}
DELETE /api/analyses/{id}   → 204
```

### 8.4 上傳流程整合
```
上傳 PDF → client-size 檢查 ≤10MB
  → POST /analyze → 魔術位元驗證
    → pdfminer 解析
      → AI 履歷驗證（二元分類）
        ├─ NO  → 400 {"detail":"非履歷"}, 不扣次數
        └─ YES → AI 前處理（修復文字）
          → 5 維度 SSE 串流
            → 結果寫入 PostgreSQL
              → 側邊欄即時更新
```

---

## 9. 邊緣案例（Must Have）

### 上傳處理
| # | 情境 | 處理方式 |
|---|------|---------|
| A1 | 超過 10MB | client-side 先擋，顯示「檔案超過 10MB 限制」，不扣次數 |
| A2 | 損壞 PDF | server 解析 header，回傳「無法解析此 PDF」，不扣次數 |
| A3 | 密碼保護 | 偵測加密 flag，回傳「此 PDF 受密碼保護」，不扣次數 |
| A4 | 空白檔案 | client + server 雙重檢查，回傳「檔案為空」，不扣次數 |
| A5 | 掃描圖檔 PDF | 解析後文字 <50 chars，回傳「無法解析 PDF，可能為掃描版」 |
| A6 | 偽裝 .pdf | 檢查 magic bytes，不符則回傳「請上傳 PDF 格式」 |
| A11 | 連續點擊上傳 | debounce 按鈕，第一次點擊後 disabled，防止重複送單 |

### SSE 串流
| # | 情境 | 處理方式 |
|---|------|---------|
| C2 | 單維度 JSON 壞掉 | try/catch 隔離該維度，顯示錯誤，不影響其他 4 個維度 |
| C4 | 單維度分析失敗 | 儲存 4 個成功維度，失敗維度顯示「分析失敗」與重試按鈕 |
| C8 | 使用者重整頁面 | 若 SSE 進行中，提示「分析正在進行，是否恢復？」|

### 歷史記錄
| # | 情境 | 處理方式 |
|---|------|---------|
| D5 | DB 查詢失敗 | 顯示「無法載入歷史記錄」+ 重試按鈕，上次成功列表 cache 於 localStorage |

### 每週限制
| # | 情境 | 處理方式 |
|---|------|---------|
| E3 | 分析失敗扣不扣次數？ | 通過履歷驗證後即扣次數（AI 資源已被消耗） |
| E5 | 同時上傳 race condition | DB `CHECK (usage_count <= 7)` 防止超額 |
| E6 | 跨週 UTC 計算 | 以 UTC 判斷，顯示時轉換使用者當地時間 |

### OAuth
| # | 情境 | 處理方式 |
|---|------|---------|
| F2 | 分析中登出 | 警告「登出將中斷當前分析」，確認後中止 SSE，已分析維度存入 DB |

---

## 10. 典型 Dimension SSE Event

```json
{
  "type": "dimension",
  "name": "experience_relevance",
  "score": 4,
  "conclusion": "經歷與目標職位方向一致，但缺乏量化成果與關鍵字覆蓋。",
  "suggestions": [
    "加入量化數據（提升幅度、團隊規模、專案時程）",
    "強化與目標職位關鍵字的對應關係",
    "將被動描述改為主動表述"
  ],
  "quote": "負責前端開發，參與多個專案，與團隊協作完成需求",
  "optimized": "主導前端架構重構，將頁面載入速度提升 40%，帶領 3 人團隊在 6 個月內交付 5 個跨部門專案",
  "optimization_logic": "加入量化數據（40%、3 人、6 個月、5 個）與主動動詞（主導、帶領），取代被動描述"
}
```

**Error codes：**

| code | 觸發條件 |
|------|---------|
| `rate_limit` | OpenAI RateLimitError（SDK 自動 retry 2x 後） |
| `connection` | OpenAI APIConnectionError |
| `content_filter` | OpenAI APIStatusError 400 |
| `unknown` | 其他例外 |

---

## 11. 錯誤訊息對照表（擴充）

| ValueError key | HTTP 400 detail |
|---------------|-----------------|
| `empty_file` | 上傳的檔案是空的 |
| `file_too_large` | 檔案超過 5MB，請壓縮後再上傳 |
| `not_pdf` | 請上傳 PDF 格式檔案 |
| `password_protected` | PDF 已加密，請移除密碼後再上傳 |
| `corrupted_pdf` | PDF 檔案損壞，請重新匯出後上傳 |
| `scanned_pdf` | 無法解析 PDF，可能為掃描版，請改用文字版 PDF（可用 Word 匯出）|
| `not_resume` | 這看起來不是一份履歷。[具體原因]，請上傳求職用的 PDF 履歷檔案 |

---

## 12. 環境變數

| 變數 | 必填 | 預設 | 說明 |
|------|------|------|------|
| `OPENAI_API_KEY` | 是 | — | OpenAI API key，啟動時驗證 |
| `OPENAI_MODEL` | 否 | `gpt-4o-mini` | 使用的模型 |
| `PORT` | 否 | `8000` | Railway 自動注入 |
| `DATABASE_URL` | 是 | — | PostgreSQL 連線字串 |
