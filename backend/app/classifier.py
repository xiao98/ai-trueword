"""AI分析引擎 — AI真言机的核心。

多维度分析：适合谁看、需要注意什么、有什么价值。
"""

from __future__ import annotations

import logging

from .llm import AnalysisResult, ModelRouter

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
你是"AI真言机"的分析引擎。对给定的AI相关内容做多维度分析，返回且仅返回一个JSON对象。

## 分析维度

1. **一句话结论**：这个内容核心讲了什么，用一句话概括
2. **受众适合度**：分别评估对三类人群的价值（1-5星）
   - 技术人员（工程师、研究者）
   - 产品经理/运营（需要做AI决策的非技术人员）
   - AI小白/入门者（刚开始关注AI的人）
3. **需要注意的点**：具体指出内容中哪些说法有夸大、哪些数据缺乏来源、哪些结论需要进一步验证
4. **值得关注的点**：如果有真正有价值的信息，指出来
5. **信息质量**：实质内容占比 vs 营销成分占比（加起来100）

## 分析标准

- 有可验证的技术指标（benchmark、论文、代码）→ 实质内容高
- 有具体的使用场景和限制说明 → 对产品经理价值高
- 用通俗语言解释了技术原理 → 对小白价值高
- 大量情绪化词汇（"颠覆""革命""淘汰""恐怖"）→ 营销成分高
- 只有结论没有论证过程 → 需要注意
- 标题和实际内容不符 → 需要注意

## 返回格式（严格JSON）
{
  "summary": "一句话结论",
  "tech_rating": 3,
  "tech_note": "对技术人员的具体说明，1-2句",
  "pm_rating": 4,
  "pm_note": "对产品经理的具体说明，1-2句",
  "beginner_rating": 5,
  "beginner_note": "对小白的具体说明，1-2句",
  "cautions": ["具体注意点1", "具体注意点2"],
  "highlights": ["值得关注的点1"],
  "substance_pct": 60,
  "marketing_pct": 40
}

只返回JSON，不要任何其他文字。注意点和关注点要具体，不要泛泛而谈。
"""

# Singleton router
_router: ModelRouter | None = None


def get_router() -> ModelRouter:
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router


def init_router(config: dict | None = None):
    global _router
    _router = ModelRouter(config)


async def classify(
    title: str, content: str, url: str = "", provider: str | None = None, max_retries: int = 2
) -> dict:
    """Analyze a piece of AI content with retry."""
    router = get_router()
    llm = router.get(provider)

    user_message = f"分析这条AI内容：{title}"
    if content:
        user_message += f"\n正文：{content}"

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            result: AnalysisResult = await llm.classify(SYSTEM_PROMPT, user_message)
            return {
                "summary": result.summary,
                "tech_rating": result.tech_rating,
                "tech_note": result.tech_note,
                "pm_rating": result.pm_rating,
                "pm_note": result.pm_note,
                "beginner_rating": result.beginner_rating,
                "beginner_note": result.beginner_note,
                "cautions": result.cautions,
                "highlights": result.highlights,
                "substance_pct": result.substance_pct,
                "marketing_pct": result.marketing_pct,
                "model": llm.name,
            }
        except Exception as e:
            last_error = e
            logger.warning("Classify attempt %d/%d failed (%s): %s", attempt + 1, max_retries + 1, llm.name, e)

    raise last_error
