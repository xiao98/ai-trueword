"""启动B站Bot。

Usage:
    # 设置环境变量后运行
    python -m scripts.run_bilibili

需要的环境变量：
    BILI_SESSDATA      - B站cookie中的SESSDATA
    BILI_BILI_JCT      - B站cookie中的bili_jct
    BILI_BUVID3        - B站cookie中的BUVID3
    BILI_DEDEUSERID    - B站cookie中的DedeUserID
    BILI_BUVID4        - (可选) B站cookie中的BUVID4
    BILI_AC_TIME_VALUE - (可选) B站cookie中的ac_time_value

    以及LLM相关的环境变量（至少一个）：
    GEMINI_API_KEY / OPENAI_API_KEY / DEEPSEEK_API_KEY
"""

import asyncio
import logging
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.classifier import init_router
from backend.app.config import load_config
from backend.app.platforms.bilibili import BilibiliBot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def get_required_env(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        logger.error("缺少环境变量: %s", name)
        sys.exit(1)
    return val


async def main():
    # Init LLM
    config = load_config()
    init_router(config)

    # Init Bilibili bot
    bot = BilibiliBot(
        sessdata=get_required_env("BILI_SESSDATA"),
        bili_jct=get_required_env("BILI_BILI_JCT"),
        buvid3=get_required_env("BILI_BUVID3"),
        dedeuserid=get_required_env("BILI_DEDEUSERID"),
        buvid4=os.environ.get("BILI_BUVID4", ""),
        ac_time_value=os.environ.get("BILI_AC_TIME_VALUE", ""),
        at_poll_interval=int(os.environ.get("BILI_POLL_INTERVAL", "30")),
    )

    logger.info("正在启动B站Bot...")

    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("B站Bot停止中...")
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
