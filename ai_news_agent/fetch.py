from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse
from typing import Iterable, List, Optional

import feedparser
import requests
from bs4 import BeautifulSoup

from .config import Settings, Source


@dataclass
class NewsItem:
    title: str
    url: str
    source: str
    source_weight: int
    published_at: Optional[datetime]
    summary: str = ""
    content: str = ""


def _parse_date(value: object) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def fetch_rss(source: Source, settings: Settings) -> List[NewsItem]:
    response = requests.get(
        source.url,
        headers={"User-Agent": settings.user_agent},
        timeout=settings.request_timeout_seconds,
    )
    response.raise_for_status()
    parsed = feedparser.parse(response.content)
    items: List[NewsItem] = []
    for entry in parsed.entries:
        link = getattr(entry, "link", "")
        title = getattr(entry, "title", "").strip()
        if not title or not link:
            continue
        published = (
            _parse_date(getattr(entry, "published", None))
            or _parse_date(getattr(entry, "updated", None))
        )
        raw_summary = getattr(entry, "summary", "") or ""
        summary = BeautifulSoup(raw_summary, "html.parser").get_text(" ", strip=True) if "<" in raw_summary else raw_summary
        items.append(
            NewsItem(
                title=title,
                url=link,
                source=source.name,
                source_weight=source.weight,
                published_at=published,
                summary=summary,
            )
        )
    return items


def fetch_github_trending(source: Source, settings: Settings) -> List[NewsItem]:
    response = requests.get(
        source.url,
        headers={"User-Agent": settings.user_agent},
        timeout=settings.request_timeout_seconds,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    items: List[NewsItem] = []
    for article in soup.select("article.Box-row")[:15]:
        title_el = article.select_one("h2 a")
        if not title_el:
            continue
        title = " ".join(title_el.get_text(" ", strip=True).split())
        href = title_el.get("href", "").strip()
        desc_el = article.select_one("p")
        desc = desc_el.get_text(" ", strip=True) if desc_el else ""
        if href.startswith("/"):
            href = f"https://github.com{href}"
        items.append(
            NewsItem(
                title=title,
                url=href,
                source=source.name,
                source_weight=source.weight,
                published_at=None,
                summary=desc,
            )
        )
    return items


def fetch_blog_index(source: Source, settings: Settings) -> List[NewsItem]:
    response = requests.get(
        source.url,
        headers={"User-Agent": settings.user_agent},
        timeout=settings.request_timeout_seconds,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    base_host = urlparse(source.url).netloc
    items: List[NewsItem] = []
    seen = set()
    for anchor in soup.find_all("a", href=True):
        href = urljoin(source.url, anchor["href"])
        parsed = urlparse(href)
        if parsed.netloc != base_host:
            continue
        if "/news/" not in parsed.path and "/blog/" not in parsed.path:
            continue
        if parsed.path.rstrip("/") in {"/news", "/blog"}:
            continue
        key = href.split("?")[0].rstrip("/")
        if key in seen:
            continue
        text = " ".join(anchor.get_text(" ", strip=True).split())
        if not text and anchor.get("aria-label"):
            text = " ".join(anchor["aria-label"].split())
        if not text or text.lower() in {"learn more", "featured", "read more"}:
            continue
        seen.add(key)
        items.append(
            NewsItem(
                title=text[:180],
                url=key,
                source=source.name,
                source_weight=source.weight,
                published_at=None,
                summary=text,
            )
        )
        if len(items) >= 20:
            break
    return items


def fetch_sources(sources: Iterable[Source], settings: Settings) -> List[NewsItem]:
    all_items: List[NewsItem] = []
    for source in sources:
        try:
            if source.type == "rss":
                all_items.extend(fetch_rss(source, settings))
            elif source.type == "html" and "github.com/trending" in source.url:
                all_items.extend(fetch_github_trending(source, settings))
            elif source.type == "html":
                all_items.extend(fetch_blog_index(source, settings))
        except Exception as exc:
            all_items.append(
                NewsItem(
                    title=f"[抓取失败] {source.name}",
                    url=source.url,
                    source=source.name,
                    source_weight=0,
                    published_at=None,
                    summary=str(exc),
                )
            )
    return all_items


def enrich_article_text(item: NewsItem, settings: Settings) -> NewsItem:
    try:
        response = requests.get(
            item.url,
            headers={"User-Agent": settings.user_agent},
            timeout=settings.request_timeout_seconds,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        main = soup.select_one("article") or soup.select_one("main") or soup.body
        text = main.get_text(" ", strip=True) if main else ""
        item.content = text[: settings.max_article_chars]
    except Exception:
        item.content = ""
    return item
