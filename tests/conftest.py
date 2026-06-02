import os
import pytest

# 必須在 module level 設定，讓 module-level 的 AsyncOpenAI() 能成功初始化
os.environ.setdefault("OPENAI_API_KEY", "test-key-for-testing")
os.environ.setdefault("OPENAI_MODEL", "gpt-4o-mini")


@pytest.fixture(autouse=True)
def set_openai_api_key(monkeypatch):
    """測試時自動注入假 API key，避免觸發真實 OpenAI 呼叫。"""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-for-testing")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
