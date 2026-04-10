from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class AnalysisResult:
    summary: str  # 一句话结论
    tech_rating: int  # 技术人员适合度 1-5
    tech_note: str  # 技术人员说明
    pm_rating: int  # 产品经理/运营适合度 1-5
    pm_note: str
    beginner_rating: int  # 小白适合度 1-5
    beginner_note: str
    cautions: list[str]  # 需要注意的点
    highlights: list[str]  # 值得关注的点
    substance_pct: int  # 实质内容占比 0-100
    marketing_pct: int  # 营销成分占比 0-100


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def classify(self, system_prompt: str, user_message: str) -> AnalysisResult:
        """Send analysis request and return structured result."""
        ...
