from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus, urljoin, urlparse
from typing import Iterable, List, Optional

import feedparser
import requests
from requests import HTTPError
from bs4 import BeautifulSoup

from .config import Settings, Source


@dataclass
class NewsItem:
    title: str
    url: str
    source: str
    source_type: str
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
                source_type=source.type,
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
                source_type=source.type,
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
                source_type=source.type,
                source_weight=source.weight,
                published_at=None,
                summary=text,
            )
        )
        if len(items) >= 20:
            break
    return items


def fetch_google_news_rss(source: Source, settings: Settings) -> List[NewsItem]:
    query = source.query or "AI agent"
    url = source.url.format(query=quote_plus(query))
    return fetch_rss(Source(source.name, url, "rss", source.weight), settings)[: source.limit]


def fetch_gdelt(source: Source, settings: Settings) -> List[NewsItem]:
    query = source.query or "AI agent"
    params = {
        "query": query,
        "mode": "artlist",
        "format": "json",
        "maxrecords": str(source.limit),
        "sort": "datedesc",
    }
    response = requests.get(
        source.url,
        params=params,
        headers={"User-Agent": settings.user_agent},
        timeout=settings.request_timeout_seconds,
    )
    response.raise_for_status()
    articles = response.json().get("articles", [])
    items: List[NewsItem] = []
    for article in articles[: source.limit]:
        title = (article.get("title") or "").strip()
        url = (article.get("url") or "").strip()
        if not title or not url:
            continue
        published = _parse_date(article.get("seendate"))
        summary_parts = [
            article.get("sourcecountry", ""),
            article.get("domain", ""),
            article.get("language", ""),
        ]
        summary = " | ".join(part for part in summary_parts if part)
        items.append(
            NewsItem(
                title=title,
                url=url,
                source=source.name,
                source_type=source.type,
                source_weight=source.weight,
                published_at=published,
                summary=summary,
            )
        )
    return items


def fetch_hackernews(source: Source, settings: Settings) -> List[NewsItem]:
    query = source.query or "AI agent"
    params = {
        "query": query,
        "tags": "story",
        "hitsPerPage": str(source.limit),
    }
    response = requests.get(
        source.url,
        params=params,
        headers={"User-Agent": settings.user_agent},
        timeout=settings.request_timeout_seconds,
    )
    response.raise_for_status()
    hits = response.json().get("hits", [])
    items: List[NewsItem] = []
    for hit in hits[: source.limit]:
        title = (hit.get("title") or "").strip()
        url = (hit.get("url") or "").strip() or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
        if not title or not url:
            continue
        published = _parse_date(hit.get("created_at"))
        points = hit.get("points")
        comments = hit.get("num_comments")
        summary = f"points={points}, comments={comments}"
        items.append(
            NewsItem(
                title=title,
                url=url,
                source=source.name,
                source_type=source.type,
                source_weight=source.weight,
                published_at=published,
                summary=summary,
            )
        )
    return items


def fetch_github_search(source: Source, settings: Settings) -> List[NewsItem]:
    query = source.query or "agent language:python"
    params = {
        "q": query,
        "sort": "updated",
        "order": "desc",
        "per_page": str(source.limit),
    }
    response = requests.get(
        source.url,
        params=params,
        headers={
            "User-Agent": settings.user_agent,
            "Accept": "application/vnd.github+json",
        },
        timeout=settings.request_timeout_seconds,
    )
    response.raise_for_status()
    repos = response.json().get("items", [])
    items: List[NewsItem] = []
    for repo in repos[: source.limit]:
        full_name = repo.get("full_name") or ""
        html_url = repo.get("html_url") or ""
        if not full_name or not html_url:
            continue
        published = _parse_date(repo.get("updated_at"))
        stars = repo.get("stargazers_count", 0)
        language = repo.get("language") or ""
        description = repo.get("description") or ""
        summary = f"{description} stars={stars} language={language}".strip()
        items.append(
            NewsItem(
                title=full_name,
                url=html_url,
                source=source.name,
                source_type=source.type,
                source_weight=source.weight,
                published_at=published,
                summary=summary,
            )
        )
    return items


def fetch_sources(sources: Iterable[Source], settings: Settings) -> List[NewsItem]:
    all_items: List[NewsItem] = []
    for source in sources:
        try:
            if source.type == "rss":
                all_items.extend(fetch_rss(source, settings))
            elif source.type == "google_news_rss":
                all_items.extend(fetch_google_news_rss(source, settings))
            elif source.type == "gdelt":
                all_items.extend(fetch_gdelt(source, settings))
            elif source.type == "hackernews":
                all_items.extend(fetch_hackernews(source, settings))
            elif source.type == "github_search":
                all_items.extend(fetch_github_search(source, settings))
            elif source.type == "html" and "github.com/trending" in source.url:
                all_items.extend(fetch_github_trending(source, settings))
            elif source.type == "html":
                all_items.extend(fetch_blog_index(source, settings))
        except HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code == 429:
                continue
            all_items.append(
                NewsItem(
                    title=f"[抓取失败] {source.name}",
                    url=source.url,
                    source=source.name,
                    source_type=source.type,
                    source_weight=0,
                    published_at=None,
                    summary=str(exc),
                )
            )
        except Exception as exc:
            all_items.append(
                NewsItem(
                    title=f"[抓取失败] {source.name}",
                    url=source.url,
                    source=source.name,
                    source_type=source.type,
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
