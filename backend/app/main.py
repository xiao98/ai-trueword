from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .classifier import classify, init_router
from .config import load_config
from .database import get_feed, init_db, insert_classification, insert_news, is_classified
from .extractors import ExtractorRouter
from .extractors.webpage import WebPageExtractor
from .models import SubmitRequest
from .sources import fetch_all_sources


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("data", exist_ok=True)
    await init_db()

    # Initialize LLM router from config
    config = load_config()
    init_router(config)

    # Initialize extractor router
    extractor_router = ExtractorRouter()
    extractor_router.register(WebPageExtractor())
    app.state.extractor_router = extractor_router

    yield


app = FastAPI(title="AI真言机", version="0.2.0", lifespan=lifespan)


# --- API ---


@app.post("/api/classify")
async def classify_url(req: SubmitRequest):
    """手动提交一条信息进行分类。支持自动提取URL内容。"""
    title = req.title or req.url
    content = req.content

    # Auto-extract content from URL if no content provided
    if req.url and not content:
        try:
            extractor: ExtractorRouter = app.state.extractor_router
            if extractor.can_handle(req.url):
                extracted = await extractor.extract(req.url)
                title = extracted.title or title
                content = extracted.text
        except Exception:
            pass

    url = req.url or f"manual://{hash(title)}"

    if req.url and await is_classified(req.url):
        raise HTTPException(400, "该链接已分类过")

    news_id = await insert_news(title, url, "manual", content)

    try:
        result = await classify(title, content, url)
    except Exception as e:
        raise HTTPException(500, f"分类失败: {e}")

    import json as _json
    await insert_classification(
        news_id, "analysis", _json.dumps(result, ensure_ascii=False), result["substance_pct"] / 100
    )

    return {"title": title, "url": url, **result}


@app.get("/api/feed")
async def get_classified_feed(
    limit: int = Query(50, le=200),
    verdict: str | None = Query(None),
):
    """获取已分类的信息流。"""
    import json as _json
    rows = await get_feed(limit, verdict)
    results = []
    for row in rows:
        entry = {
            "id": row["id"],
            "title": row["title"],
            "url": row["url"],
            "source": row["source"],
            "classified_at": row["classified_at"],
        }
        # Try to parse new analysis format from reason field
        try:
            analysis = _json.loads(row["reason"])
            entry.update(analysis)
        except (ValueError, TypeError):
            entry["summary"] = row["reason"]
        results.append(entry)
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

        import json as _json
        await insert_classification(
            news_id, "analysis", _json.dumps(result, ensure_ascii=False), result["substance_pct"] / 100
        )
        results.append({
            "title": item.title,
            "url": item.url,
            "source": item.source,
            **result,
        })

    return {"classified": len(results), "items": results}


@app.get("/api/models")
async def list_models():
    """列出可用的LLM模型。"""
    from .classifier import get_router
    router = get_router()
    return {"default": router.default_name, "available": router.available}


# --- Static frontend ---

FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"


@app.get("/")
async def index():
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
