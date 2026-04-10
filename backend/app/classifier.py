"""AI分类引擎 — AI真言机的核心。

薄编排层：接收新闻，委托给LLM provider分类，返回结果。
"""

from __future__ import annotations

import logging

from .llm import ClassificationResult, ModelRouter
from .models import VERDICT_ACTIONS, VERDICT_LABELS

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

# Singleton router, initialized on first use
_router: ModelRouter | None = None


def get_router() -> ModelRouter:
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router


def init_router(config: dict | None = None):
    """Initialize the model router with config. Call at startup."""
    global _router
    _router = ModelRouter(config)


async def classify(
    title: str, content: str, url: str = "", provider: str | None = None, max_retries: int = 2
) -> dict:
    """Classify a piece of AI news with retry."""
    router = get_router()
    llm = router.get(provider)

    user_message = f"判定这条AI新闻：{title}"
    if content:
        user_message += f"\n摘要：{content}"

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            result: ClassificationResult = await llm.classify(SYSTEM_PROMPT, user_message)
            return {
                "verdict": result.verdict,
                "verdict_label": VERDICT_LABELS[result.verdict],
                "action": VERDICT_ACTIONS[result.verdict],
                "reason": result.reason,
                "confidence": result.confidence,
                "model": llm.name,
            }
        except Exception as e:
            last_error = e
            logger.warning("Classify attempt %d/%d failed (%s): %s", attempt + 1, max_retries + 1, llm.name, e)

    raise last_error
