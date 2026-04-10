from __future__ import annotations

import json
import logging

from google import genai
from google.genai import types

from ..models import Verdict
from .base import BaseLLMProvider, ClassificationResult

logger = logging.getLogger(__name__)

VERDICT_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "verdict": types.Schema(
            type=types.Type.STRING,
            enum=["breakthrough", "incremental", "marketing", "hype"],
        ),
        "confidence": types.Schema(type=types.Type.NUMBER),
        "reason": types.Schema(type=types.Type.STRING),
    },
    required=["verdict", "confidence", "reason"],
)


class GeminiProvider(BaseLLMProvider):

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self._client = genai.Client(api_key=api_key)
        self._model = model

    @property
    def name(self) -> str:
        return f"gemini/{self._model}"

    async def classify(self, system_prompt: str, user_message: str) -> ClassificationResult:
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=VERDICT_SCHEMA,
                max_output_tokens=512,
                temperature=0.3,
            ),
        )

        result = json.loads(response.text)
        return ClassificationResult(
            verdict=Verdict(result["verdict"]),
            confidence=float(result["confidence"]),
            reason=result["reason"],
        )
