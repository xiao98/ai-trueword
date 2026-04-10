"""新闻源采集模块。

从RSS和API获取AI相关热门信息。
"""

from __future__ import annotations

from dataclasses import dataclass

import feedparser
import httpx

# AI相关RSS源
RSS_FEEDS = [
    {
        "name": "Hacker News (AI)",
        "url": "https://hnrss.org/newest?q=AI+OR+LLM+OR+GPT+OR+Claude+OR+OpenAI+OR+Anthropic&points=50",
    },
    {
        "name": "ArXiv CS.AI",
        "url": "https://rss.arxiv.org/rss/cs.AI",
    },
    {
        "name": "ArXiv CS.CL",
        "url": "https://rss.arxiv.org/rss/cs.CL",
    },
    {
        "name": "The Verge AI",
        "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    },
    {
        "name": "TechCrunch AI",
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
    },
]


@dataclass
class FetchedItem:
    title: str
    url: str
    source: str
    content: str


async def fetch_rss(feed_url: str, feed_name: str, limit: int = 10) -> list[FetchedItem]:
    """Fetch items from a single RSS feed."""
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(feed_url)
            resp.raise_for_status()
        except httpx.HTTPError:
            return []

    parsed = feedparser.parse(resp.text)
    items = []
    for entry in parsed.entries[:limit]:
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()
        summary = entry.get("summary", "").strip()
        if title and link:
            items.append(FetchedItem(title=title, url=link, source=feed_name, content=summary))
    return items


async def fetch_all_sources(limit_per_source: int = 10) -> list[FetchedItem]:
    """Fetch from all configured sources."""
    all_items = []
    for feed in RSS_FEEDS:
        items = await fetch_rss(feed["url"], feed["name"], limit_per_source)
        all_items.extend(items)
    return all_items
