from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ExtractedContent:
    title: str
    text: str
    url: str
    platform: str  # 'web', 'twitter', 'bilibili', 'youtube', etc.
    content_type: str  # 'article', 'video', 'tweet', 'thread'
    metadata: dict = field(default_factory=dict)


class BaseExtractor(ABC):

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """Check if this extractor can handle the given URL."""
        ...

    @abstractmethod
    async def extract(self, url: str) -> ExtractedContent:
        """Extract content from the URL."""
        ...


class ExtractorRouter:
    """Routes URLs to the appropriate extractor."""

    def __init__(self):
        self._extractors: list[BaseExtractor] = []

    def register(self, extractor: BaseExtractor):
        self._extractors.append(extractor)

    async def extract(self, url: str) -> ExtractedContent:
        for ext in self._extractors:
            if ext.can_handle(url):
                return await ext.extract(url)
        raise ValueError(f"No extractor can handle: {url}")

    def can_handle(self, url: str) -> bool:
        return any(ext.can_handle(url) for ext in self._extractors)
