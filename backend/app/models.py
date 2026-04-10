from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class Verdict(str, Enum):
    BREAKTHROUGH = "breakthrough"      # 实质性突破
    INCREMENTAL = "incremental"        # 渐进改良
    MARKETING = "marketing"            # 营销包装
    HYPE = "hype"                      # 纯粹炒作


VERDICT_LABELS = {
    Verdict.BREAKTHROUGH: "实质性突破",
    Verdict.INCREMENTAL: "渐进改良",
    Verdict.MARKETING: "营销包装",
    Verdict.HYPE: "纯粹炒作",
}

VERDICT_ACTIONS = {
    Verdict.BREAKTHROUGH: "你需要了解",
    Verdict.INCREMENTAL: "知道就行",
    Verdict.MARKETING: "跳过",
    Verdict.HYPE: "反向指标",
}


class NewsItem(BaseModel):
    id: int | None = None
    title: str
    url: str
    source: str = ""
    content: str = ""
    submitted_at: datetime | None = None


class ClassifiedNews(BaseModel):
    id: int | None = None
    news_id: int
    title: str
    url: str
    source: str
    verdict: Verdict
    verdict_label: str
    action: str
    reason: str           # 一段说人话的理由
    confidence: float     # 判断置信度 0-1
    classified_at: datetime | None = None


class SubmitRequest(BaseModel):
    url: str
    title: str = ""
    content: str = ""
