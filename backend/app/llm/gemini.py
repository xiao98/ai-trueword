from __future__ import annotations

import json
import logging

from google import genai
from google.genai import types

from .base import AnalysisResult, BaseLLMProvider

logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self._client = genai.Client(api_key=api_key)
        self._model = model

    @property
    def name(self) -> str:
        return f"gemini/{self._model}"

    async def classify(self, system_prompt: str, user_message: str) -> AnalysisResult:
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                max_output_tokens=1024,
                temperature=0.3,
            ),
        )

        r = json.loads(response.text)
        return AnalysisResult(
            summary=r["summary"],
            tech_rating=int(r["tech_rating"]),
            tech_note=r["tech_note"],
            pm_rating=int(r["pm_rating"]),
            pm_note=r["pm_note"],
            beginner_rating=int(r["beginner_rating"]),
            beginner_note=r["beginner_note"],
            cautions=r.get("cautions", []),
            highlights=r.get("highlights", []),
            substance_pct=int(r.get("substance_pct", 50)),
            marketing_pct=int(r.get("marketing_pct", 50)),
        )
