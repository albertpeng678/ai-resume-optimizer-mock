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

MOCK_PDF_TEXT = "Hello World"

def mock_parse_resume(content: bytes, max_chars: int = 12_000) -> str:
    """Mock PDF parser that returns known text from any PDF."""
    if len(content) == 0:
        raise ValueError("empty_file")
    return MOCK_PDF_TEXT[:max_chars]

async def mock_stream_analysis(resume_text, jd_text=""):
    """Mock async generator that yields known dimension data."""
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
