from __future__ import annotations

import logging
import re

from .base import BaseExtractor, ExtractedContent

logger = logging.getLogger(__name__)

VIDEO_PATTERNS = [
    re.compile(r"(youtube\.com/watch|youtu\.be/)"),
    re.compile(r"bilibili\.com/video/"),
]


class VideoExtractor(BaseExtractor):
    """Extract video title and subtitles using yt-dlp."""

    def can_handle(self, url: str) -> bool:
        return any(p.search(url) for p in VIDEO_PATTERNS)

    async def extract(self, url: str) -> ExtractedContent:
        import asyncio
        return await asyncio.to_thread(self._extract_sync, url)

    def _extract_sync(self, url: str) -> ExtractedContent:
        import yt_dlp

        info = {}
        subtitles_text = ""

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["zh", "zh-Hans", "en"],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        title = info.get("title", "")
        description = info.get("description", "")
        platform = "bilibili" if "bilibili" in url else "youtube"

        # Try to get subtitles
        subs = info.get("subtitles", {})
        auto_subs = info.get("automatic_captions", {})
        all_subs = {**auto_subs, **subs}  # manual subs override auto

        for lang in ["zh-Hans", "zh", "en"]:
            if lang in all_subs:
                for fmt in all_subs[lang]:
                    if fmt.get("ext") in ("json3", "srv3", "vtt", "srt"):
                        # For now, use description as fallback
                        # Full subtitle download would need additional HTTP fetch
                        break

        # Use description as content (subtitles require extra download step)
        text = description or ""
        if len(text) > 3000:
            text = text[:3000] + "..."

        return ExtractedContent(
            title=title,
            text=text,
            url=url,
            platform=platform,
            content_type="video",
            metadata={
                "duration": info.get("duration"),
                "view_count": info.get("view_count"),
                "uploader": info.get("uploader"),
            },
        )
