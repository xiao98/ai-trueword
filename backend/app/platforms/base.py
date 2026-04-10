from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Awaitable


@dataclass
class PlatformRequest:
    """A request from a platform (e.g. @mention)."""

    platform: str  # 'telegram', 'twitter', 'wechat', 'bilibili'
    user_id: str  # platform user ID
    message_id: str  # original message/tweet/comment ID
    text: str  # raw text of the mention
    urls: list[str] = field(default_factory=list)  # extracted URLs
    reply_to_text: str = ""  # text of the message being replied to (if any)
    metadata: dict = field(default_factory=dict)


@dataclass
class PlatformReply:
    """Formatted reply to send back to a platform."""

    text: str
    verdict: str
    verdict_label: str
    action: str
    confidence: float
    model: str = ""


class BasePlatformBot(ABC):
    """Abstract base class for platform bots."""

    @property
    @abstractmethod
    def platform_name(self) -> str: ...

    @abstractmethod
    async def start(self): ...

    @abstractmethod
    async def stop(self): ...

    @abstractmethod
    async def send_reply(self, request: PlatformRequest, reply: PlatformReply): ...
