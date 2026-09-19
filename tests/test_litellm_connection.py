from __future__ import annotations

import os
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv

from ai_news_agent.litellm_client import chat_completions_url


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _masked(value: str) -> str:
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


@pytest.mark.integration
def test_litellm_chat_completion_connection() -> None:
    load_dotenv(PROJECT_ROOT / ".env", override=True)

    base_url = os.environ.get("LITELLM_BASE_URL", "").rstrip("/")
    api_key = os.environ.get("LITELLM_API_KEY", "")
    model = os.environ.get("LITELLM_MODEL", "")

    assert base_url, "LITELLM_BASE_URL is missing"
    assert api_key, "LITELLM_API_KEY is missing"
    assert model, "LITELLM_MODEL is missing"

    print(f"LiteLLM base_url={base_url}")
    print(f"LiteLLM model={model}")
    print(f"LiteLLM api_key={_masked(api_key)}")

    url = chat_completions_url(base_url)
    print(f"LiteLLM url={url}")

    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "user", "content": "请只回复两个字：成功"},
            ],
            "temperature": 0,
            "max_tokens": 128,
        },
        timeout=60,
    )

    print(f"LiteLLM status={response.status_code}")
    if response.status_code >= 400:
        print(response.text[:2000])

    response.raise_for_status()
    data = response.json()
    content = data["choices"][0]["message"]["content"]
    print(f"LiteLLM content={content!r}")
    assert content.strip(), data
