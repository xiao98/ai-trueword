from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..models import Verdict


@dataclass
class ClassificationResult:
    verdict: Verdict
    confidence: float
    reason: str


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def classify(self, system_prompt: str, user_message: str) -> ClassificationResult:
        """Send classification request and return structured result."""
        ...
