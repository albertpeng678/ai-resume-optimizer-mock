"""
PDF 解析模組。

責任：驗證上傳的 PDF 檔案，並使用 pdfminer.six 提取純文字。

依賴：pdfminer.six

完整規格請見 CLAUDE.md「PDF 解析規格」章節。
"""
import os
import tempfile
from pdfminer.high_level import extract_text
from pdfminer.layout import LAParams
from pdfminer.pdfparser import PDFSyntaxError
from pdfminer.pdfdocument import PDFPasswordIncorrect

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def validate_pdf_magic(content: bytes) -> bool:
    if len(content) < 4:
        return False
    return content[:4] == b"%PDF"


def parse_resume(content: bytes, max_chars: int = 12_000) -> str:
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
