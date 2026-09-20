from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass(frozen=True)
class Source:
    name: str
    url: str
    type: str
    weight: int = 1
    query: Optional[str] = None
    limit: int = 20


@dataclass(frozen=True)
class Settings:
    lookback_days: int
    max_items: int
    max_enriched_items: int
    max_article_chars: int
    request_timeout_seconds: int
    user_agent: str
    keywords: List[str]
    report: Dict[str, Any]


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_sources(path: Path) -> List[Source]:
    data = load_yaml(path)
    return [Source(**item) for item in data.get("sources", [])]


def load_settings(path: Path) -> Settings:
    data = load_yaml(path)
    return Settings(
        lookback_days=int(data.get("lookback_days", 1)),
        max_items=int(data.get("max_items", 40)),
        max_enriched_items=int(data.get("max_enriched_items", 12)),
        max_article_chars=int(data.get("max_article_chars", 3000)),
        request_timeout_seconds=int(data.get("request_timeout_seconds", 20)),
        user_agent=str(data.get("user_agent", "ai-news-agent/0.1")),
        keywords=list(data.get("keywords", [])),
        report=dict(data.get("report", {})),
    )
