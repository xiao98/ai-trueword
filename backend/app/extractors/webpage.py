from __future__ import annotations

import logging

import httpx
import trafilatura

from .base import BaseExtractor, ExtractedContent

logger = logging.getLogger(__name__)


class WebPageExtractor(BaseExtractor):
    """Extract article content from any web page using trafilatura."""

    def can_handle(self, url: str) -> bool:
        return url.startswith("http://") or url.startswith("https://")

    async def extract(self, url: str) -> ExtractedContent:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            html = resp.text

        result = trafilatura.extract(
            html, include_comments=False, include_tables=False, favor_recall=True
        )
        metadata = trafilatura.extract(
            html, output_format="json", include_comments=False
        )

        title = ""
        if metadata:
            import json
            try:
                meta_dict = json.loads(metadata)
                title = meta_dict.get("title", "")
            except (json.JSONDecodeError, TypeError):
                pass

        if not title:
            # Fallback: extract <title> tag
            import re
            match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
            title = match.group(1).strip() if match else url

        text = result or ""
        # Truncate to reasonable length for LLM input
        if len(text) > 3000:
            text = text[:3000] + "..."

        return ExtractedContent(
            title=title,
            text=text,
            url=url,
            platform="web",
            content_type="article",
        )
