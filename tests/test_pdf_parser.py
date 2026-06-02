import pytest
import os
from backend.pdf_parser import validate_pdf_magic, parse_resume, ai_preprocess_text


class TestValidatePdfMagic:
    def test_valid_pdf_magic(self):
        assert validate_pdf_magic(b"%PDF-1.4\n...")

    def test_empty_bytes(self):
        assert not validate_pdf_magic(b"")

    def test_not_pdf_magic(self):
        assert not validate_pdf_magic(b"GIF89a...")


class TestParseResume:
    def test_empty_file_raises(self):
        with pytest.raises(ValueError, match="empty_file"):
            parse_resume(b"")

    def test_file_too_large_raises(self):
        with pytest.raises(ValueError, match="file_too_large"):
            parse_resume(b"x" * (10 * 1024 * 1024 + 1))

    def test_not_pdf_raises(self):
        with pytest.raises(ValueError, match="not_pdf"):
            parse_resume(b"not a pdf content")

    def test_valid_pdf_returns_text(self):
        from reportlab.pdfgen import canvas
        import io
        buf = io.BytesIO()
        c = canvas.Canvas(buf)
        c.drawString(100, 750, "Hello World This is a resume with enough text to pass the 50 character minimum check for PDF parsing")
        c.save()
        pdf_content = buf.getvalue()
        text = parse_resume(pdf_content)
        assert "Hello World" in text


class TestAiPreprocessText:
    @pytest.mark.asyncio
    async def test_preprocess_short_text(self):
        from unittest.mock import AsyncMock, MagicMock, patch
        text = "測試履歷文字"
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "已修復的文字內容"
        with patch("backend.pdf_parser._client.chat.completions.create", new_callable=AsyncMock, return_value=mock_response):
            result = await ai_preprocess_text(text)
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_preprocess_empty_text(self):
        with pytest.raises(ValueError, match="empty_text"):
            await ai_preprocess_text("")
