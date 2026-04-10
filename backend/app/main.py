from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .classifier import classify
from .database import get_feed, init_db, insert_classification, insert_news, is_classified
from .models import VERDICT_ACTIONS, VERDICT_LABELS, ClassifiedNews, SubmitRequest, Verdict
from .sources import fetch_all_sources


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("data", exist_ok=True)
    await init_db()
    yield


app = FastAPI(title="AI真言机", version="0.1.0", lifespan=lifespan)


# --- API ---


@app.post("/api/classify")
async def classify_url(req: SubmitRequest):
    """手动提交一条信息进行分类。"""
    if await is_classified(req.url):
        raise HTTPException(400, "该链接已分类过")

    news_id = await insert_news(req.title or req.url, req.url, "manual", req.content)

    try:
        result = await classify(req.title or req.url, req.content, req.url)
    except Exception as e:
        raise HTTPException(500, f"分类失败: {e}")

    await insert_classification(news_id, result["verdict"].value, result["reason"], result["confidence"])

    return {
        "title": req.title or req.url,
        "url": req.url,
        "verdict": result["verdict"].value,
        "verdict_label": result["verdict_label"],
        "action": result["action"],
        "reason": result["reason"],
        "confidence": result["confidence"],
    }


@app.get("/api/feed")
async def get_classified_feed(
    limit: int = Query(50, le=200),
    verdict: str | None = Query(None),
):
    """获取已分类的信息流。"""
    rows = await get_feed(limit, verdict)
    results = []
    for row in rows:
        v = Verdict(row["verdict"])
        results.append({
            "id": row["id"],
            "title": row["title"],
            "url": row["url"],
            "source": row["source"],
            "verdict": v.value,
            "verdict_label": VERDICT_LABELS[v],
            "action": VERDICT_ACTIONS[v],
            "reason": row["reason"],
            "confidence": row["confidence"],
            "classified_at": row["classified_at"],
        })
    return results


@app.post("/api/fetch-and-classify")
async def fetch_and_classify(limit: int = Query(5, le=20)):
    """从RSS源拉取最新信息并分类。"""
    items = await fetch_all_sources(limit_per_source=limit)

    results = []
    for item in items:
        if await is_classified(item.url):
            continue

        news_id = await insert_news(item.title, item.url, item.source, item.content)

        try:
            result = await classify(item.title, item.content, item.url)
        except Exception:
            continue

        await insert_classification(
            news_id, result["verdict"].value, result["reason"], result["confidence"]
        )
        results.append({
            "title": item.title,
            "url": item.url,
            "source": item.source,
            "verdict": result["verdict"].value,
            "verdict_label": result["verdict_label"],
            "action": result["action"],
            "reason": result["reason"],
            "confidence": result["confidence"],
        })

    return {"classified": len(results), "items": results}


# --- Static frontend ---

FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"


@app.get("/")
async def index():
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
