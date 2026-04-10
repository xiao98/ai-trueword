"""AI分类引擎 — AI真言机的核心。

对每条AI新闻做四级定性判断，附人话理由。
"""

from __future__ import annotations

import json
import os

import anthropic

from .models import VERDICT_ACTIONS, VERDICT_LABELS, ClassifiedNews, Verdict

SYSTEM_PROMPT = """\
你是"AI真言机"的判断引擎。你的任务是对一条AI相关的新闻/信息做出定性判断。

## 你的四个判定等级

1. **breakthrough**（实质性突破）— 真正改变了某个领域的能力边界，有可验证的技术进步
2. **incremental**（渐进改良）— 在已有方向上的合理进展，值得知道但不需要行动
3. **marketing**（营销包装）— 旧技术换新名字，或者把正常迭代包装成革命性突破
4. **hype**（纯粹炒作）— 没有实质内容，纯靠标题党/情绪/FOMO驱动传播

## 判断标准

- **有没有可验证的技术指标？** benchmark、论文、开源代码、第三方复现 → 加分
- **是"能做到新的事"还是"做已有的事更好一点"？** 前者是breakthrough，后者最多incremental
- **信息源是谁？** 官方技术博客 vs 自媒体转述 → 自媒体往往放大
- **用了多少情绪化词汇？** "颠覆""革命""淘汰""恐怖" → hype信号
- **6个月后还会有人提这件事吗？** 这是终极检验

## 输出格式

严格返回JSON：
{
  "verdict": "breakthrough|incremental|marketing|hype",
  "confidence": 0.0-1.0,
  "reason": "一段话，说人话，解释为什么这么判。控制在2-4句话。要具体，不要泛泛而谈。"
}

只返回JSON，不要其他内容。
"""


async def classify(title: str, content: str, url: str = "") -> dict:
    """Classify a piece of AI news."""
    client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    user_message = f"标题：{title}\n"
    if url:
        user_message += f"链接：{url}\n"
    if content:
        user_message += f"内容：{content}\n"

    message = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    text = message.content[0].text.strip()
    # Handle potential markdown code block wrapping
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    result = json.loads(text)

    verdict = Verdict(result["verdict"])
    return {
        "verdict": verdict,
        "verdict_label": VERDICT_LABELS[verdict],
        "action": VERDICT_ACTIONS[verdict],
        "reason": result["reason"],
        "confidence": result["confidence"],
    }
