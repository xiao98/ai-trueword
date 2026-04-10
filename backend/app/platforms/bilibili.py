"""B站Bot — 监听@提及和私信，提取视频内容，分类回复。

两种触发方式：
1. 评论区@提及：用户在视频评论区@Bot，Bot提取该视频信息并回复评论
2. 私信：用户发送视频链接/文字到Bot私信，Bot回复判定结果
"""

from __future__ import annotations

import asyncio
import logging
import re
import time

from bilibili_api import Credential
from bilibili_api.comment import CommentResourceType, send_comment
from bilibili_api.session import EventType, Session, get_at, send_msg
from bilibili_api.user import get_self_info
from bilibili_api.video import Video

from ..classifier import classify
from ..models import VERDICT_ACTIONS, VERDICT_LABELS, Verdict
from .base import BasePlatformBot, PlatformReply, PlatformRequest

logger = logging.getLogger(__name__)

# Match BV号 or full bilibili URL
BV_PATTERN = re.compile(r"(BV[a-zA-Z0-9]{10})")
URL_PATTERN = re.compile(r"https?://(?:www\.)?bilibili\.com/video/(BV[a-zA-Z0-9]{10})")
SHORT_URL_PATTERN = re.compile(r"https?://b23\.tv/\S+")

VERDICT_ICONS = {
    Verdict.BREAKTHROUGH: "🟢",
    Verdict.INCREMENTAL: "🔵",
    Verdict.MARKETING: "🟡",
    Verdict.HYPE: "🔴",
}


def format_reply(result: dict) -> str:
    """Format classification result for B站 reply."""
    verdict = result["verdict"]
    icon = VERDICT_ICONS.get(verdict, "⚪")
    confidence_pct = int(result["confidence"] * 100)
    return (
        f"【AI真言机判定】\n"
        f"{icon} {result['verdict_label']} ({confidence_pct}%)\n"
        f"{result['reason']}\n"
        f"建议：{result['action']}"
    )


async def extract_video_content(bvid: str, credential: Credential) -> dict:
    """Extract title, description, and top comments from a Bilibili video."""
    video = Video(bvid=bvid, credential=credential)
    info = await video.get_info()

    title = info.get("title", "")
    desc = info.get("desc", "")

    # Get top comments for additional context
    from bilibili_api.comment import get_comments, OrderType

    comments_text = ""
    try:
        comments_data = await get_comments(
            oid=info["aid"],
            type_=CommentResourceType.VIDEO,
            order=OrderType.LIKE,
            credential=credential,
        )
        top_comments = []
        for c in (comments_data.get("replies") or [])[:5]:
            text = c.get("content", {}).get("message", "")
            if text:
                top_comments.append(text)
        if top_comments:
            comments_text = "\n热门评论：\n" + "\n".join(f"- {c}" for c in top_comments)
    except Exception as e:
        logger.debug("Failed to get comments for %s: %s", bvid, e)

    content = desc
    if comments_text:
        content += comments_text

    # Truncate
    if len(content) > 2000:
        content = content[:2000] + "..."

    return {"title": title, "content": content, "aid": info["aid"]}


def extract_bvid(text: str) -> str | None:
    """Extract BV号 from text."""
    m = URL_PATTERN.search(text) or BV_PATTERN.search(text)
    return m.group(1) if m else None


class BilibiliBot(BasePlatformBot):

    def __init__(
        self,
        sessdata: str,
        bili_jct: str,
        buvid3: str,
        dedeuserid: str,
        buvid4: str = "",
        ac_time_value: str = "",
        at_poll_interval: int = 30,
    ):
        self.credential = Credential(
            sessdata=sessdata,
            bili_jct=bili_jct,
            buvid3=buvid3,
            buvid4=buvid4,
            dedeuserid=dedeuserid,
            ac_time_value=ac_time_value,
        )
        self._at_poll_interval = at_poll_interval
        self._session: Session | None = None
        self._my_uid: int = 0
        self._running = False
        self._last_at_time: int = 0
        self._processed_at_ids: set[int] = set()

    @property
    def platform_name(self) -> str:
        return "bilibili"

    async def start(self):
        """Start both @mention polling and DM listener."""
        self._running = True

        # Get own UID
        self_info = await get_self_info(self.credential)
        self._my_uid = self_info["mid"]
        logger.info("B站Bot启动: UID=%s, 用户名=%s", self._my_uid, self_info.get("uname"))

        # Run DM listener and @mention polling concurrently
        # DM listener may fail on new accounts with no message history
        await asyncio.gather(
            self._run_dm_listener(),
            self._poll_at_mentions(),
        )

    async def _run_dm_listener(self):
        """Run DM session listener. Only one attempt — if it fails, DM is disabled."""
        try:
            self._session = Session(self.credential)

            @self._session.on(EventType.TEXT)
            async def on_text(event):
                await self._handle_dm(event)

            @self._session.on(EventType.SHARE_VIDEO)
            async def on_share(event):
                await self._handle_dm(event)

            logger.info("B站私信监听启动")
            await self._session.run(exclude_self=True)

            # run() returns immediately, keep this coroutine alive
            while self._running:
                await asyncio.sleep(60)
        except Exception as e:
            logger.warning("B站私信监听不可用（@提及仍正常工作）: %s", e)
            # Don't retry — just let @mention polling continue

    async def stop(self):
        self._running = False
        if self._session:
            self._session.close()

    async def send_reply(self, request: PlatformRequest, reply: PlatformReply):
        """Send reply based on request type."""
        if request.metadata.get("type") == "comment":
            # Reply as comment
            await send_comment(
                text=reply.text,
                oid=request.metadata["aid"],
                type_=CommentResourceType.VIDEO,
                root=int(request.message_id),
                credential=self.credential,
            )
        else:
            # Reply as DM
            await send_msg(
                credential=self.credential,
                receiver_id=int(request.user_id),
                msg_type=EventType.TEXT,
                content=reply.text,
            )

    # --- Internal handlers ---

    async def _handle_dm(self, event):
        """Handle incoming private message."""
        sender_uid = event.sender_uid

        # Skip own messages to prevent infinite loop
        if sender_uid == self._my_uid:
            return

        content = str(event.content) if event.content else ""
        if not content.strip():
            return

        # Deduplicate by msg_key
        msg_key = getattr(event, "msg_key", None)
        if msg_key and msg_key in self._processed_at_ids:
            return
        if msg_key:
            self._processed_at_ids.add(msg_key)

        logger.info("B站私信: UID=%s, 内容=%s", sender_uid, content[:100])

        # Try to find a BV号
        bvid = extract_bvid(content)

        try:
            if bvid:
                video = await extract_video_content(bvid, self.credential)
                result = await classify(
                    title=video["title"],
                    content=video["content"],
                )
                reply_text = format_reply(result)
            else:
                # Treat raw text as news to classify
                result = await classify(title=content, content="")
                reply_text = format_reply(result)

            await send_msg(
                credential=self.credential,
                receiver_id=sender_uid,
                msg_type=EventType.TEXT,
                content=reply_text,
            )
            logger.info("B站私信回复: UID=%s, verdict=%s", sender_uid, result["verdict"].value)
        except Exception as e:
            logger.error("B站私信处理失败: %s", e, exc_info=True)
            try:
                await send_msg(
                    credential=self.credential,
                    receiver_id=sender_uid,
                    msg_type=EventType.TEXT,
                    content="判定失败，请稍后再试。",
                )
            except Exception:
                pass

    async def _poll_at_mentions(self):
        """Poll for @mention notifications."""
        logger.info("B站@提及轮询启动 (间隔%ds)", self._at_poll_interval)
        # Don't filter by time — use ID-based deduplication instead
        self._last_at_id: int = 0

        # First poll: mark existing mentions as processed (don't reply to old ones)
        try:
            data = await get_at(self.credential)
            for item in data.get("items") or []:
                self._processed_at_ids.add(item.get("id", 0))
            logger.info("已跳过 %d 条历史@提及", len(self._processed_at_ids))
        except Exception as e:
            logger.error("初始@提及拉取失败: %s", e)

        while self._running:
            await asyncio.sleep(self._at_poll_interval)
            try:
                data = await get_at(self.credential)
                items = data.get("items") or []

                for item in items:
                    item_id = item.get("id", 0)
                    if item_id in self._processed_at_ids:
                        continue
                    self._processed_at_ids.add(item_id)

                    await self._handle_at_mention(item)

                # Keep set manageable
                if len(self._processed_at_ids) > 1000:
                    self._processed_at_ids = set(list(self._processed_at_ids)[-500:])

            except Exception as e:
                logger.error("B站@提及轮询异常: %s", e)

    async def _handle_at_mention(self, item: dict):
        """Handle a single @mention notification."""
        try:
            # Extract info from the at-mention item
            item_detail = item.get("item", {})
            source_content = item_detail.get("source_content", "")
            subject_id = item_detail.get("subject_id", 0)  # video aid
            source_id = item_detail.get("source_id", 0)  # comment rpid
            root_id = item_detail.get("root_id", 0)
            sender_uid = item.get("user", {}).get("mid", 0)

            logger.info("B站@提及: UID=%s, aid=%s, source_id=%s, 内容=%s",
                        sender_uid, subject_id, source_id, source_content[:100])

            # Try to get video info
            if subject_id:
                try:
                    video = Video(aid=subject_id, credential=self.credential)
                    info = await video.get_info()
                    bvid = info.get("bvid", "")
                    if bvid:
                        video_data = await extract_video_content(bvid, self.credential)
                        result = await classify(
                            title=video_data["title"],
                            content=video_data["content"],
                        )
                    else:
                        result = await classify(title=source_content, content="")
                except Exception:
                    result = await classify(title=source_content, content="")
            else:
                result = await classify(title=source_content, content="")

            reply_text = format_reply(result)

            # Reply as comment — source_id is the comment that @mentioned us
            rpid = source_id or root_id
            if subject_id and rpid:
                await send_comment(
                    text=reply_text,
                    oid=subject_id,
                    type_=CommentResourceType.VIDEO,
                    root=rpid,
                    credential=self.credential,
                )
                logger.info("B站评论回复: aid=%s, verdict=%s", subject_id, result["verdict"].value)
            elif sender_uid:
                # Fallback: reply via DM
                await send_msg(
                    credential=self.credential,
                    receiver_id=sender_uid,
                    msg_type=EventType.TEXT,
                    content=reply_text,
                )
                logger.info("B站DM回复(fallback): UID=%s", sender_uid)

        except Exception as e:
            logger.error("B站@提及处理失败: %s", e)
