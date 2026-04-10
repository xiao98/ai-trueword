"""Central dispatcher: platform event → extract → classify → reply."""

from __future__ import annotations

import logging

from ..classifier import classify
from ..extractors import ExtractorRouter
from ..models import VERDICT_ACTIONS, VERDICT_LABELS, Verdict
from .base import BasePlatformBot, PlatformReply, PlatformRequest

logger = logging.getLogger(__name__)


class Dispatcher:
    """Routes platform events through the classification pipeline."""

    def __init__(self, extractor_router: ExtractorRouter):
        self.extractor = extractor_router

    async def handle(self, request: PlatformRequest, bot: BasePlatformBot) -> PlatformReply:
        """Process a platform request end-to-end."""
        title = ""
        content = request.text

        # If there are URLs, try to extract content from the first one
        if request.urls:
            url = request.urls[0]
            try:
                if self.extractor.can_handle(url):
                    extracted = await self.extractor.extract(url)
                    title = extracted.title
                    content = extracted.text or content
            except Exception as e:
                logger.warning("Extraction failed for %s: %s", url, e)

        # If no title yet, use the raw text as title
        if not title:
            title = content[:100] if content else "Unknown"

        # Include reply-to context if available
        if request.reply_to_text:
            content = f"{request.reply_to_text}\n\n{content}"

        # Classify
        result = await classify(title=title, content=content)

        verdict = result["verdict"]
        reply = PlatformReply(
            text=self._format_reply(result),
            verdict=verdict.value,
            verdict_label=result["verdict_label"],
            action=result["action"],
            confidence=result["confidence"],
            model=result.get("model", ""),
        )

        # Send reply
        await bot.send_reply(request, reply)
        return reply

    def _format_reply(self, result: dict) -> str:
        """Format a classification result as a human-readable reply."""
        verdict = result["verdict"]
        icons = {
            Verdict.BREAKTHROUGH: "🟢",
            Verdict.INCREMENTAL: "🔵",
            Verdict.MARKETING: "🟡",
            Verdict.HYPE: "🔴",
        }
        icon = icons.get(verdict, "⚪")
        confidence_pct = int(result["confidence"] * 100)

        return (
            f"AI真言机判定：\n"
            f"{icon} {result['verdict_label']} ({confidence_pct}%)\n\n"
            f"{result['reason']}\n\n"
            f"建议：{result['action']}"
        )
