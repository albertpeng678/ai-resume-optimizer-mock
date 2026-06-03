import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from backend.analyzer import validate_is_resume, stream_analysis, _classify_error


MOCK_DIMENSIONS = [
    {"type": "dimension", "name": "experience_relevance", "score": 4, "conclusion": "Good", "quote": "text", "optimized": "better", "optimization_logic": "logic", "suggestions": ["s1"]},
    {"type": "dimension", "name": "skill_fit", "score": 3, "conclusion": "OK", "quote": "text", "optimized": "better", "optimization_logic": "logic", "suggestions": ["s1"]},
    {"type": "dimension", "name": "layout_structure", "score": 4, "conclusion": "Good", "quote": "text", "optimized": "better", "optimization_logic": "logic", "suggestions": ["s1"]},
    {"type": "dimension", "name": "keyword_coverage", "score": 3, "conclusion": "OK", "quote": "text", "optimized": "better", "optimization_logic": "logic", "suggestions": ["s1"]},
    {"type": "dimension", "name": "personal_brand", "score": 5, "conclusion": "Great", "quote": "text", "optimized": "better", "optimization_logic": "logic", "suggestions": ["s1"]},
]


@pytest.fixture
def mock_openai_stream():
    chunks = []
    for d in MOCK_DIMENSIONS:
        line = json.dumps(d, ensure_ascii=False)
        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta.content = line + "\n"
        chunks.append(chunk)

    mock_stream = AsyncMock()
    mock_stream.__aiter__.return_value = iter(chunks)

    patcher = patch(
        "backend.analyzer._client.chat.completions.create",
        new_callable=AsyncMock,
        return_value=mock_stream,
    )
    return patcher


class TestValidateIsResume:
    @pytest.mark.asyncio
    async def test_valid_resume(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            '{"is_resume": true, "reason": "Looks like a resume"}'
        )

        with patch(
            "backend.analyzer._client.chat.completions.create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            is_resume, reason = await validate_is_resume(
                "Experienced software engineer with 5 years of experience in Python and Node.js"
            )
            assert is_resume is True
            assert "resume" in reason

    @pytest.mark.asyncio
    async def test_empty_text(self):
        is_resume, reason = await validate_is_resume("")
        assert is_resume is False
        assert "空" in reason


class TestStreamAnalysis:
    @pytest.mark.asyncio
    async def test_stream_yields_dimensions(self, mock_openai_stream):
        with mock_openai_stream:
            results = []
            async for chunk in stream_analysis("Test resume"):
                data = json.loads(chunk)
                results.append(data["type"])
        assert "dimension" in results
        assert results[-1] == "done"

    @pytest.mark.asyncio
    async def test_stream_yields_all_5_dimensions(self, mock_openai_stream):
        with mock_openai_stream:
            dim_names = []
            async for chunk in stream_analysis("Test resume"):
                data = json.loads(chunk)
                if data["type"] == "dimension":
                    dim_names.append(data["name"])
        assert len(dim_names) == 5
        assert set(dim_names) == {
            "experience_relevance",
            "skill_fit",
            "layout_structure",
            "keyword_coverage",
            "personal_brand",
        }

    @pytest.mark.asyncio
    async def test_stream_yields_done_exactly_once_when_ai_also_emits_done(self):
        """Regression: when the AI response includes {"type":"done"} (as instructed
        by the system prompt), stream_analysis MUST yield done exactly once.
        Currently the hardcoded yield at line 152 duplicates the AI's own done line."""
        chunks = []
        for d in MOCK_DIMENSIONS:
            line = json.dumps(d, ensure_ascii=False)
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta.content = line + "\n"
            chunks.append(chunk)
        # AI also outputs {"type":"done"} as instructed by system prompt
        done_chunk = MagicMock()
        done_chunk.choices = [MagicMock()]
        done_chunk.choices[0].delta.content = json.dumps({"type": "done"}) + "\n"
        chunks.append(done_chunk)

        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = iter(chunks)

        with patch(
            "backend.analyzer._client.chat.completions.create",
            new_callable=AsyncMock,
            return_value=mock_stream,
        ):
            done_count = 0
            async for chunk in stream_analysis("Test resume"):
                data = json.loads(chunk)
                if data["type"] == "done":
                    done_count += 1

        assert done_count == 1, f"Expected 1 done event, got {done_count}. The AI's done line + hardcoded yield at line 152 produces a duplicate."

    @pytest.mark.asyncio
    async def test_stream_extracts_dims_without_newlines(self):
        """Regression: when AI outputs JSON objects concatenated without newlines
        (e.g. all dims in a single chunk), stream_analysis must still extract all 5.
        Previously this produced dimensions: [] in the saved analysis."""
        all_dims = []
        for d in MOCK_DIMENSIONS:
            all_dims.append(d)
        all_json = "".join(json.dumps(d, ensure_ascii=False) for d in all_dims) + json.dumps({"type": "done"})

        chunks = []
        chunk_size = 50
        for i in range(0, len(all_json), chunk_size):
            c = MagicMock()
            c.choices = [MagicMock()]
            c.choices[0].delta.content = all_json[i:i+chunk_size]
            chunks.append(c)

        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = iter(chunks)

        with patch(
            "backend.analyzer._client.chat.completions.create",
            new_callable=AsyncMock,
            return_value=mock_stream,
        ):
            dim_count = 0
            done_count = 0
            async for chunk in stream_analysis("Test resume"):
                data = json.loads(chunk)
                if data["type"] == "dimension":
                    dim_count += 1
                elif data["type"] == "done":
                    done_count += 1

        assert dim_count == 5, f"Expected 5 dimensions, got {dim_count}"
        assert done_count == 1, f"Expected 1 done, got {done_count}"

    @pytest.mark.asyncio
    async def test_dimension_contains_new_fields(self, mock_openai_stream):
        with mock_openai_stream:
            async for chunk in stream_analysis("Test resume"):
                data = json.loads(chunk)
                if data["type"] == "dimension":
                    assert "conclusion" in data
                    assert "quote" in data
                    assert "optimized" in data
                    assert "optimization_logic" in data
                    assert "suggestions" in data
                    break

    @pytest.mark.asyncio
    async def test_stream_error(self):
        from openai import APIStatusError
        import httpx

        req = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
        resp = httpx.Response(429, request=req)

        async def mock_side_effect(*args, **kwargs):
            raise APIStatusError("rate limited", response=resp, body=None)

        with patch(
            "backend.analyzer._client.chat.completions.create",
            new_callable=AsyncMock,
            side_effect=mock_side_effect,
        ):
            results = []
            async for chunk in stream_analysis("Test resume"):
                data = json.loads(chunk)
                results.append(data)
        assert len(results) == 1
        assert results[0]["type"] == "error"


class TestClassifyError:
    def test_rate_limit(self):
        from openai import RateLimitError
        import httpx

        req = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
        resp = httpx.Response(429, request=req)
        e = RateLimitError("rate limited", response=resp, body=None)
        code, msg = _classify_error(e)
        assert code == "rate_limit"

    def test_connection(self):
        from openai import APIConnectionError
        import httpx

        req = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
        e = APIConnectionError(message="connection failed", request=req)
        code, msg = _classify_error(e)
        assert code == "connection"

    def test_unknown(self):
        code, msg = _classify_error(ValueError("something else"))
        assert code == "unknown"
