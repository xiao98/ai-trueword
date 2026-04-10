from __future__ import annotations

import json
import logging

from openai import AsyncOpenAI

from ..models import Verdict
from .base import BaseLLMProvider, ClassificationResult

logger = logging.getLogger(__name__)

# Model preference: cheaper/faster first
MODEL_PRIORITY = [
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-3-flash",
    "gemini-2.5-pro",
    "gemini-3-pro-preview",
    "gpt-4o-mini",
    "gpt-4.1-mini",
    "claude-haiku-4-5",
    "claude-sonnet-4-5",
    "claude-sonnet-4-6",
    "deepseek-chat",
    "gpt-4o",
    "gpt-4.1",
    "claude-opus-4-5",
    "claude-opus-4-6",
]


class OpenAIProvider(BaseLLMProvider):
    """Supports OpenAI GPT, DeepSeek, and any OpenAI-compatible API.

    If model is set to "auto", queries /v1/models and picks the best
    available model based on cost/speed priority.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "auto",
        base_url: str | None = None,
        provider_name: str = "openai",
    ):
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._resolved_model: str | None = None
        self._provider_name = provider_name

    @property
    def name(self) -> str:
        model = self._resolved_model or self._model
        return f"{self._provider_name}/{model}"

    async def _resolve_model(self) -> str:
        """Resolve the actual model to use."""
        if self._resolved_model:
            return self._resolved_model

        if self._model != "auto":
            self._resolved_model = self._model
            return self._model

        # Query available models
        try:
            models_resp = await self._client.models.list()
            available = {m.id for m in models_resp.data}
            logger.info("API可用模型: %s", available)

            # Pick best available by priority
            for preferred in MODEL_PRIORITY:
                # Check exact match or prefix match
                for avail in available:
                    if avail == preferred or avail.startswith(preferred):
                        self._resolved_model = avail
                        logger.info("自动选择模型: %s", avail)
                        return avail

            # Fallback: use the first available model
            if available:
                fallback = next(iter(available))
                self._resolved_model = fallback
                logger.info("未匹配优先列表，使用: %s", fallback)
                return fallback

        except Exception as e:
            logger.warning("获取模型列表失败: %s", e)

        raise ValueError("无法确定可用模型，请手动设置 OPENAI_MODEL")

    async def classify(self, system_prompt: str, user_message: str) -> ClassificationResult:
        model = await self._resolve_model()

        response = await self._client.chat.completions.create(
            model=model,
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
