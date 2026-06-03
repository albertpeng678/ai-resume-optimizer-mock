"""
OpenAI 分析模組。

責任：組建 prompt，呼叫 OpenAI API（stream=True），
      逐行 yield JSON 字串給 FastAPI SSE endpoint。

依賴：openai >= 1.0.0

SSE Event 格式（每個 yield 為一行 JSON）：
    維度結果：
        {"type":"dimension","name":"<name>","score":<1-5>,"conclusion":"<str>","quote":"<str>","optimized":"<str>","optimization_logic":"<str>","suggestions":["<str>",...]}
    完成：
        {"type":"done"}
    錯誤：
        {"type":"error","code":"<code>","message":"<str>"}

維度名稱與分析重點（依序輸出）：
    experience_relevance — 經歷與目標職位的方向匹配度、量化成果
    skill_fit            — 技能廣度與深度、與目標職位的關聯性
    layout_structure     — 格式、段落順序、長度合適性
    keyword_coverage     — ATS 關鍵字覆蓋率（通用建議，無需比對 JD）
    personal_brand       — 個人摘要/目標的品牌塑造力、專業亮點
"""
import json
import os
from typing import AsyncGenerator

from openai import AsyncOpenAI, RateLimitError, APIConnectionError, APIStatusError

# Module-level client — import 時建立，避免 lazy init 的競態問題
_client = AsyncOpenAI()


def get_client() -> AsyncOpenAI:
    """取得 AsyncOpenAI client 實例（module-level singleton）。"""
    return _client


SYSTEM_PROMPT = """你是一個資深台灣招募顧問。請分析這份履歷，依序輸出 5 個維度的分析結果。

每個維度嚴格遵守以下 JSON 格式，每個維度一行：
{"type":"dimension","name":"<name>","score":<1-5>,"conclusion":"<一句話結論（繁體中文）>","suggestions":["<建議1>","<建議2>","<建議3>"],"quote":"<從履歷中摘取的具體段落原文>","optimized":"<直接改寫後的建議寫法>","optimization_logic":"<解釋為什麼這樣改更好（台灣繁體中文）>"}

5 個維度依序為：
1. experience_relevance — 經歷與目標職位的方向匹配度、量化成果
2. skill_fit — 技能廣度與深度、與目標職位的關聯性
3. layout_structure — 格式、段落順序、長度合適性
4. keyword_coverage — ATS 關鍵字覆蓋率（通用建議，無需比對 JD）
5. personal_brand — 個人摘要/目標的品牌塑造力、專業亮點

輸出完 5 個維度後直接結束，不需要額外標記。"""


async def validate_is_resume(text: str) -> tuple[bool, str]:
    """快速判斷上傳文字是否為履歷。

    Args:
        text: 已解析的文字內容

    Returns:
        (is_resume: bool, reason: str)
    """
    if not text.strip():
        return (False, "文字為空")

    model = os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")

    response = await _client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "你是一個履歷判斷助理。判斷以下文字是否為履歷（resume/CV）。請以 JSON 格式回答：{\"is_resume\": true/false, \"reason\": \"簡短原因\"}",
            },
            {"role": "user", "content": text[:3000]},
        ],
        response_format={"type": "json_object"},
        max_completion_tokens=200,
        temperature=0,
    )
    raw = response.choices[0].message.content or "{}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return (False, "無法解析回應")
    return (bool(data.get("is_resume", False)), str(data.get("reason", "")))


async def stream_analysis(
    resume_text: str,
    jd_text: str = "",
) -> AsyncGenerator[str, None]:
    """
    串流分析履歷，逐維度 yield JSON 字串。

    實作要點：
        - 有 jd_text 時加入 prompt（提升 ATS 分析精準度）
        - 使用 os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")，temperature=0.3
        - stream=True 呼叫 OpenAI
        - Buffer 機制：累積 response chunks，按 '\\n' 切割
          有效 JSON 行（以 '{' 開頭）才 yield
        - 最後 yield json.dumps({"type": "done"})
        - 只捕捉 (RateLimitError, APIConnectionError, APIStatusError)
          yield error event，其他例外往上傳遞

    Args:
        resume_text: 履歷純文字（來自 parse_resume，已截斷至 12,000 字元）
        jd_text:     目標職位描述（選填，空字串表示未提供）

    Yields:
        JSON 字串（每次一行）：dimension / done / error events
    """
    model = os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")
    client = get_client()

    user_content = f"請分析以下履歷：\n\n{resume_text}"
    if jd_text:
        user_content += f"\n\n目標職位描述（JD）：\n\n{jd_text}"

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.3,
            stream=True,
        )

        buffer = ""
        async for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            content = delta.content if delta else ""
            if content:
                buffer += content
                extracted, consumed = _extract_jsons(buffer)
                for json_str in extracted:
                    yield json_str
                buffer = buffer[consumed:]

        # Handle any remaining complete JSON in the buffer after stream ends
        extracted, _ = _extract_jsons(buffer)
        for json_str in extracted:
            yield json_str

    except (RateLimitError, APIConnectionError, APIStatusError) as e:
        code, msg = _classify_error(e)
        yield json.dumps({"type": "error", "code": code, "message": msg})
        return

    yield json.dumps({"type": "done"})


def _extract_jsons(text: str) -> tuple[list[str], int]:
    """Extract complete JSON objects from text by tracking brace depth.
    
    Returns (extracted_jsons, consumed_count) where consumed_count is how many
    characters of text were successfully parsed. Remaining text should be kept
    in the buffer for the next chunk.
    
    Handles:
    - Newline-separated JSON objects (current working case)
    - JSON objects concatenated without newlines
    - Newlines within JSON string values
    - Escaped quotes within strings
    """
    result = []
    i = 0
    last_complete = 0
    while i < len(text):
        if text[i] == "{":
            depth = 0
            j = i
            while j < len(text):
                if text[j] == '"':
                    j += 1
                    while j < len(text):
                        if text[j] == "\\":
                            j += 2
                        elif text[j] == '"':
                            break
                        else:
                            j += 1
                elif text[j] == "{":
                    depth += 1
                elif text[j] == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = text[i:j+1]
                        try:
                            obj = json.loads(candidate)
                        except json.JSONDecodeError:
                            last_complete = i
                            i = j + 1
                            break
                        if obj.get("type") != "done":
                            result.append(candidate)
                        last_complete = j + 1
                        i = j + 1
                        break
                j += 1
            else:
                # No complete object from position i - keep everything from i
                return result, i
        else:
            i += 1
            last_complete = i
    return result, last_complete


def _classify_error(e: Exception) -> tuple[str, str]:
    """
    將 OpenAI 例外分類為 (error_code, message) tuple。

    分類規則：
        RateLimitError                → ("rate_limit",     "AI 服務暫時繁忙，請 30 秒後重試")
        APIConnectionError            → ("connection",     "無法連線，請確認網路後重試")
        APIStatusError (status 400)   → ("content_filter", "部分內容無法分析，請確認履歷內容後重試")
        其他                           → ("unknown",        "分析失敗，請重試")

    Args:
        e: 已捕捉的例外

    Returns:
        (error_code, user_facing_message)
    """
    if isinstance(e, RateLimitError):
        return ("rate_limit", "AI 服務暫時繁忙，請 30 秒後重試")
    if isinstance(e, APIConnectionError):
        return ("connection", "無法連線，請確認網路後重試")
    if isinstance(e, APIStatusError):
        if e.status_code == 400:
            return ("content_filter", "部分內容無法分析，請確認履歷內容後重試")
        return ("unknown", "分析失敗，請重試")
    return ("unknown", "分析失敗，請重試")
