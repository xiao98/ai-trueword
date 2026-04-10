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
from bilibili_api.session import EventType, get_at, send_msg
from bilibili_api.user import get_self_info
from bilibili_api.video import Video

from ..classifier import classify
from .base import BasePlatformBot, PlatformReply, PlatformRequest

logger = logging.getLogger(__name__)

# Match BV号 or full bilibili URL
BV_PATTERN = re.compile(r"(BV[a-zA-Z0-9]{10})")
URL_PATTERN = re.compile(r"https?://(?:www\.)?bilibili\.com/video/(BV[a-zA-Z0-9]{10})")
SHORT_URL_PATTERN = re.compile(r"https?://b23\.tv/\S+")

def _stars(n: int) -> str:
    return "★" * n + "☆" * (5 - n)


def format_reply(result: dict, max_len: int = 950) -> str:
    """Format analysis result for B站 reply. Kept under 1000 chars."""
    lines = [f"【AI真言机分析】"]
    lines.append(f"📌 {result['summary']}")

    lines.append(f"🎯 技术人员{_stars(result['tech_rating'])} 产品运营{_stars(result['pm_rating'])} 入门者{_stars(result['beginner_rating'])}")

    # Pick the most relevant audience note (highest rated)
    ratings = [
        (result['tech_rating'], f"技术视角：{result['tech_note']}"),
        (result['pm_rating'], f"产品视角：{result['pm_note']}"),
        (result['beginner_rating'], f"入门视角：{result['beginner_note']}"),
    ]
    ratings.sort(key=lambda x: x[0], reverse=True)
    lines.append(ratings[0][1])

    if result.get("cautions"):
        lines.append("⚠️ " + result["cautions"][0])

    if result.get("highlights"):
        lines.append("✅ " + result["highlights"][0])

    lines.append(f"📊 实质{result['substance_pct']}%/营销{result['marketing_pct']}%")

    text = "\n".join(lines)
    if len(text) > max_len:
        text = text[:max_len - 3] + "..."
    return text


async def extract_video_content(bvid: str, credential: Credential) -> dict:
    """Extract title, description, and top comments from a Bilibili video."""
    video = Video(bvid=bvid, credential=credential)
    info = await video.get_info()

    title = info.get("title", "")
    desc = info.get("desc", "")

    # Get subtitles (CC or AI-generated)
    import httpx as _httpx

    subtitles_text = ""
    try:
        first_cid = info["pages"][0]["cid"] if info.get("pages") else None
        if first_cid:
            player_info = await video.get_player_info(cid=first_cid)
            subtitle_list = (
                player_info.get("subtitle", {}).get("subtitles") or []
            )
            # Prefer Chinese subtitles
            subtitle_url = ""
            for sub in subtitle_list:
                lan = sub.get("lan", "")
                if "zh" in lan or "cn" in lan:
                    subtitle_url = sub.get("subtitle_url", "")
                    break
            if not subtitle_url and subtitle_list:
                subtitle_url = subtitle_list[0].get("subtitle_url", "")

            if subtitle_url:
                if subtitle_url.startswith("//"):
                    subtitle_url = "https:" + subtitle_url
                async with _httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(subtitle_url)
                    sub_data = resp.json()
                    lines = [item.get("content", "") for item in sub_data.get("body", [])]
                    subtitles_text = " ".join(lines)
                    logger.info("获取字幕成功: %s, %d字", bvid, len(subtitles_text))
    except Exception as e:
        logger.debug("Failed to get subtitles for %s: %s", bvid, e)

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

    # Compose content: subtitles > description, plus comments
    content = ""
    if subtitles_text:
        content = "视频字幕内容：\n" + subtitles_text
    elif desc:
        content = desc
    if comments_text:
        content += comments_text

    # Truncate to fit LLM context
    if len(content) > 4000:
        content = content[:4000] + "..."

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
        """Poll for new DMs using get_sessions + fetch_session_msgs."""
        from bilibili_api.session import get_sessions, fetch_session_msgs

        logger.info("B站私信轮询启动 (间隔10s)")
        seen_seqnos: set[int] = set()
        first_run = True

        while self._running:
            try:
                sessions = await get_sessions(self.credential, session_type=1)
                session_list = sessions.get("session_list") or []

                for sess in session_list:
                    talker_id = sess.get("talker_id", 0)
                    if talker_id == self._my_uid:
                        continue

                    last_seqno = sess.get("max_seqno", 0)
                    if last_seqno in seen_seqnos:
                        continue

                    # Fetch latest messages from this conversation
                    msgs = await fetch_session_msgs(
                        talker_id=talker_id,
                        credential=self.credential,
                        session_type=1,
                    )
                    for msg in (msgs.get("messages") or []):
                        seqno = msg.get("msg_seqno", 0)
                        if seqno in seen_seqnos:
                            continue
                        seen_seqnos.add(seqno)

                        if first_run:
                            continue  # Skip existing messages on startup

                        sender = msg.get("sender_uid", 0)
                        if sender == self._my_uid:
                            continue

                        msg_type = msg.get("msg_type", 0)
                        content = ""

                        if msg_type == 1:  # Text
                            try:
                                import json
                                body = json.loads(msg.get("content", "{}"))
                                content = body.get("content", "")
                            except (json.JSONDecodeError, TypeError):
                                content = str(msg.get("content", ""))
                        elif msg_type == 7:  # Shared video
                            try:
                                import json
                                body = json.loads(msg.get("content", "{}"))
                                bvid = body.get("bvid", "")
                                title = body.get("title", "")
                                if bvid:
                                    content = f"https://www.bilibili.com/video/{bvid}"
                                elif title:
                                    content = title
                            except (json.JSONDecodeError, TypeError):
                                pass

                        if content:
                            await self._handle_dm_raw(sender, content)

                    seen_seqnos.add(last_seqno)

                first_run = False

            except Exception as e:
                logger.warning("B站私信轮询异常: %s", e)

            await asyncio.sleep(10)

    async def _handle_dm_raw(self, sender_uid: int, content: str):
        """Handle a raw DM message."""
        logger.info("B站私信: UID=%s, 内容=%s", sender_uid, content[:100])

        bvid = extract_bvid(content)

        try:
            if bvid:
                video = await extract_video_content(bvid, self.credential)
                result = await classify(
                    title=video["title"],
                    content=video["content"],
                )
            else:
                result = await classify(title=content, content="")

            reply_text = format_reply(result)

            await send_msg(
                credential=self.credential,
                receiver_id=sender_uid,
                msg_type=EventType.TEXT,
                content=reply_text,
            )
            logger.info("B站私信回复: UID=%s", sender_uid)
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

    async def stop(self):
        self._running = False

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
