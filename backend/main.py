import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.sse import EventSourceResponse

from backend.pdf_parser import parse_resume, ai_preprocess_text
from backend.analyzer import stream_analysis, validate_is_resume
from backend.database import (
    get_pool, init_db, create_analysis, get_analyses,
    get_analysis, delete_analysis, get_weekly_usage, increment_weekly_usage,
)

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
_in_memory_analyses: dict[str, list] = {}
_in_memory_usage: dict[str, int] = {}

async def get_current_user(request: Request) -> str:
    return "test-user-id"

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY 未設定")
    try:
        pool = await get_pool()
        await init_db(pool)
    except Exception:
        pass
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/auth/login")
async def auth_login():
    return RedirectResponse(url="/auth/callback?token=mock-token")

@app.get("/auth/callback")
async def auth_callback(token: str = ""):
    if not token:
        raise HTTPException(400, "Missing token")
    html = f"""<html><body><script>
localStorage.setItem('token', '{token}');
window.location.href = '/';
</script></body></html>"""
    return HTMLResponse(content=html)

@app.get("/auth/me")
async def auth_me(request: Request):
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return {"email": "user@example.com", "name": "User"}
    raise HTTPException(401, "Unauthorized")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/metrics")
async def metrics():
    return {"total": len(_metrics), "events": _metrics}

@app.get("/", response_class=HTMLResponse)
async def index():
    try:
        with open("frontend/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<html><body><h1>Frontend not built yet</h1></body></html>")

@app.get("/api/analyses")
async def analyses_list(user_id: str = Depends(get_current_user)):
    try:
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
    except Exception:
        items = _in_memory_analyses.get(user_id, [])
        return items

@app.get("/api/analyses/{analysis_id}")
async def analysis_detail(analysis_id: str, user_id: str = Depends(get_current_user)):
    try:
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
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(404, "分析記錄不存在")

@app.delete("/api/analyses/{analysis_id}")
async def analysis_delete(analysis_id: str, user_id: str = Depends(get_current_user)):
    try:
        pool = await get_pool()
        deleted = await delete_analysis(pool, analysis_id, user_id)
        if not deleted:
            raise HTTPException(404, "分析記錄不存在")
        return JSONResponse(status_code=204, content=None)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(404, "分析記錄不存在")

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

    try:
        pool = await get_pool()
        usage = await get_weekly_usage(pool, user_id)
        if usage >= 7:
            raise HTTPException(429, "本週已達 7 次使用上限")
    except HTTPException:
        raise
    except Exception:
        pass

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
                    yield f"data: {data}\n\n"
                    continue
                if parsed.get("type") == "dimension":
                    event["dimensions"][parsed["name"]] = parsed.get("score")
                if parsed.get("type") == "done":
                    event["completed"] = True
                    dims = [{"name": k, "score": v} for k, v in event["dimensions"].items()]
                    try:
                        pool = await get_pool()
                        await increment_weekly_usage(pool, user_id)
                        await create_analysis(
                            pool, user_id,
                            pdf_file.filename or "resume.pdf",
                            len(content),
                            dims,
                        )
                    except Exception:
                        import uuid
                        from datetime import datetime
                        avg = sum(d.get("score", 0) for d in dims) / len(dims) if dims else 0
                        entry = _in_memory_analyses.setdefault(user_id, [])
                        entry.insert(0, {
                            "id": str(uuid.uuid4()),
                            "filename": pdf_file.filename or "resume.pdf",
                            "uploaded_at": datetime.now().isoformat(),
                            "avg_score": round(avg, 1),
                        })
                yield f"data: {data}\n\n"
        finally:
            _metrics.append(event)

    return EventSourceResponse(event_generator())
