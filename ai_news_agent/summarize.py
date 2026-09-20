from __future__ import annotations

import os
from typing import List

import requests

from .fetch import NewsItem
from .litellm_client import chat_completions_url


def build_prompt(items: List[NewsItem], report_date: str) -> str:
    source_blocks = []
    for index, item in enumerate(items, start=1):
        published = item.published_at.isoformat() if item.published_at else "unknown"
        source_blocks.append(
            "\n".join(
                [
                    f"[{index}] {item.title}",
                    f"source: {item.source}",
                    f"published: {published}",
                    f"url: {item.url}",
                    f"summary: {item.summary[:800]}",
                    f"content: {item.content[:1800]}",
                ]
            )
        )

    return f"""你是一个严谨的 AI/Agent 行业资讯分析员。请基于下面候选来源，生成 {report_date} 的中文日报。

要求：
- 优先选择 AI agent、tool use、computer use、coding agent、MCP、RAG/workflow、多智能体、重要模型/平台发布、开源项目、论文和产业动态。
- 不要编造；如果来源信息不足，请明确说信息不足。
- 每条新闻都要带来源链接。
- 明确区分事实、推测和传闻。
- 输出 Markdown。

格式：
# AI / Agent 前沿资讯日报 - {report_date}

## 今日要点
用 5-8 条项目符号，每条包含：标题、为什么重要、来源链接。

## 值得跟进的论文/项目
最多 5 条。

## 今日观察
一段 150-250 字趋势判断。

## 来源候选
不要逐条复述，只在必要时列出被采用的链接。

候选来源：
{chr(10).join(source_blocks)}
"""


def summarize_with_litellm(prompt: str) -> str:
    base_url = os.environ.get("LITELLM_BASE_URL", "http://127.0.0.1:4000").rstrip("/")
    api_key = os.environ.get("LITELLM_API_KEY")
    model = os.environ.get("LITELLM_MODEL")
    if not api_key:
        raise RuntimeError("Missing LITELLM_API_KEY. Copy .env.example to .env and fill it.")
    if not model:
        raise RuntimeError("Missing LITELLM_MODEL. Set it to a model name allowed by your LiteLLM proxy.")

    response = requests.post(
        chat_completions_url(base_url),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": "You produce concise, source-grounded Chinese AI news briefings."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        },
        timeout=120,
    )
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        body = response.text[:2000]
        raise RuntimeError(
            f"LiteLLM request failed: status={response.status_code}, body={body}"
        ) from exc
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()
