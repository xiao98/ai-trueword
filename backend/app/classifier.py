"""AI分类引擎 — AI真言机的核心。

对每条AI新闻做四级定性判断，附人话理由。
"""

from __future__ import annotations

import json
import logging
import os

import anthropic

from .models import VERDICT_ACTIONS, VERDICT_LABELS, Verdict

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
你是一个JSON API。对给定的AI新闻做定性判断，返回且仅返回一个JSON对象。

四个判定等级：
- breakthrough: 真正改变能力边界，有可验证的技术进步
- incremental: 已有方向上的合理进展
- marketing: 旧技术换新名字，正常迭代包装成革命
- hype: 没有实质内容，标题党/情绪/FOMO驱动

判断标准：
1. 有无可验证的技术指标（benchmark、论文、开源代码）
2. 是"能做新的事"还是"做已有的事好一点"
3. 信息源可信度（官方技术博客 vs 自媒体转述）
4. 情绪化词汇密度（"颠覆""革命""淘汰" = hype信号）
5. 6个月后还会有人提吗

返回格式（严格JSON，不要任何其他文字）：
{"verdict":"breakthrough或incremental或marketing或hype","confidence":0.85,"reason":"2-4句中文，说人话"}
"""


async def classify(title: str, content: str, url: str = "", max_retries: int = 2) -> dict:
    """Classify a piece of AI news with retry."""
    client = anthropic.AsyncAnthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        base_url=os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
    )

    user_message = f"判定这条AI新闻：{title}"
    if content:
        user_message += f"\n摘要：{content}"

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            message = await client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=512,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )

            # Find the first text block (skip thinking blocks)
            text = ""
            for block in message.content:
                if hasattr(block, "text"):
                    text = block.text.strip()
                    break

            if not text:
                raise ValueError("No text response from API")

            # Extract JSON object from response
            start = text.find("{")
            end = text.rfind("}") + 1
            if start == -1 or end <= start:
                raise ValueError(f"No JSON in response: {text[:200]}")

            result = json.loads(text[start:end])
            verdict = Verdict(result["verdict"])

            return {
                "verdict": verdict,
                "verdict_label": VERDICT_LABELS[verdict],
                "action": VERDICT_ACTIONS[verdict],
                "reason": result["reason"],
                "confidence": result["confidence"],
            }

        except Exception as e:
            last_error = e
            logger.warning("Classify attempt %d failed: %s", attempt + 1, e)

    raise last_error
