from __future__ import annotations

from datetime import datetime
from typing import Iterable, List

from .fetch import NewsItem


def _contains_keyword(item: NewsItem, keywords: Iterable[str]) -> bool:
    haystack = f"{item.title}\n{item.summary}\n{item.content}".lower()
    return any(keyword.lower() in haystack for keyword in keywords)


def filter_items(
    items: Iterable[NewsItem],
    *,
    window_start: datetime,
    window_end: datetime,
    keywords: List[str],
    max_items: int,
) -> List[NewsItem]:
    seen = set()
    filtered: List[NewsItem] = []
    for item in items:
        key = item.url.split("?")[0].rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        local_published = item.published_at.astimezone(window_start.tzinfo) if item.published_at else None
        date_ok = local_published is None or window_start <= local_published < window_end
        keyword_ok = not keywords or _contains_keyword(item, keywords)
        failure = item.title.startswith("[抓取失败]")
        if failure or (date_ok and keyword_ok):
            filtered.append(item)

    filtered.sort(
        key=lambda item: (
            item.title.startswith("[抓取失败]"),
            -item.source_weight,
            -(item.published_at.timestamp() if item.published_at else 0),
        ),
        reverse=False,
    )
    return filtered[:max_items]
