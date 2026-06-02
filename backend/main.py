import json
import os
import secrets
import urllib.parse
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
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
_sessions: dict[str, dict] = {}

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

async def get_current_user(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth.removeprefix("Bearer ")
        session = _sessions.get(token)
        if session:
            return session["email"]
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
async def auth_login(request: Request):
    if not GOOGLE_CLIENT_ID:
        html = """<html><body style="display:flex;align-items:center;justify-content:center;height:100vh;font-family:sans-serif;background:#f8fafc">
<div style="text-align:center"><h2>Google OAuth 未設定</h2><p>請在 Railway Variables 設定 GOOGLE_CLIENT_ID 與 GOOGLE_CLIENT_SECRET</p>
<button onclick="localStorage.setItem('token','dev-token');window.location.href='/'"
  style="padding:12px 32px;font-size:16px;background:#2563eb;color:#fff;border:none;border-radius:8px;cursor:pointer;margin-top:16px">
開發模式（跳過登入）</button></div></body></html>"""
        return HTMLResponse(content=html)
    # Railway terminates SSL at proxy, so request.base_url is http://
    # Force HTTPS for Google OAuth redirect URI
    base = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
    if base:
        redirect_uri = f"https://{base}/auth/callback"
    else:
        redirect_uri = str(request.base_url).replace("http://", "https://") + "auth/callback"
    params = urllib.parse.urlencode({
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
    })
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}")

@app.get("/auth/callback")
async def auth_callback(request: Request, code: str = "", error: str = ""):
    if error:
        return HTMLResponse(f"<html><body>OAuth 錯誤：{error}</body></html>")
    if not code:
        raise HTTPException(400, "缺少授權碼")
    base = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
    if base:
        redirect_uri = f"https://{base}/auth/callback"
    else:
        redirect_uri = str(request.base_url).replace("http://", "https://") + "auth/callback"
    async with httpx.AsyncClient() as client:
        token_resp = await client.post("https://oauth2.googleapis.com/token", data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        })
        if token_resp.status_code != 200:
            raise HTTPException(400, "Token 交換失敗")
        tokens = token_resp.json()
        user_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        if user_resp.status_code != 200:
            raise HTTPException(400, "無法取得使用者資訊")
        user_info = user_resp.json()
    email = user_info.get("email", "unknown@example.com")
    name = user_info.get("name", email)
    session_token = secrets.token_urlsafe(32)
    _sessions[session_token] = {"email": email, "name": name}
    return RedirectResponse(url=f"/?token={session_token}")

@app.get("/auth/me")
async def auth_me(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Unauthorized")
    token = auth.removeprefix("Bearer ")
    session = _sessions.get(token)
    if not session:
        raise HTTPException(401, "Invalid token")
    return {"email": session["email"], "name": session.get("name", session["email"])}

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

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    return JSONResponse(
        status_code=500,
        content={"detail": f"伺服器錯誤：{type(exc).__name__}: {exc}", "trace": traceback.format_exc()},
    )

@app.post("/analyze")
async def analyze(
    request: Request,
    pdf_file: UploadFile = File(...),
    jd_text: str = Form(""),
    user_id: str = Depends(get_current_user),
):
    try:
        content = await pdf_file.read()
    except Exception as e:
        raise HTTPException(400, f"無法讀取檔案：{e}")

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

    try:
        cleaned_text = await ai_preprocess_text(resume_text)
    except Exception as e:
        raise HTTPException(400, f"文字預處理失敗：{e}")

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
