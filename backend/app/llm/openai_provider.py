from __future__ import annotations

import json
import logging

from openai import AsyncOpenAI

from ..models import Verdict
from .base import BaseLLMProvider, ClassificationResult

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """Supports OpenAI GPT, DeepSeek, and any OpenAI-compatible API."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
        provider_name: str = "openai",
    ):
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._provider_name = provider_name

    @property
    def name(self) -> str:
        return f"{self._provider_name}/{self._model}"

    async def classify(self, system_prompt: str, user_message: str) -> ClassificationResult:
        response = await self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            max_tokens=512,
            temperature=0.3,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )

        text = response.choices[0].message.content.strip()
        # Extract JSON if wrapped
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            text = text[start:end]

        result = json.loads(text)
        return ClassificationResult(
            verdict=Verdict(result["verdict"]),
            confidence=float(result["confidence"]),
            reason=result["reason"],
        )
