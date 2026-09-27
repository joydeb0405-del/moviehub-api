import os
import inspect
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from xhamster_api import Client


# =========================================================
# APP
# =========================================================

app = FastAPI(
    title="MovieHub API",
    description="MovieHub API wrapper",
    version="1.1.0"
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# CLIENT
# =========================================================

client = Client()


# =========================================================
# JSON CLEANER
# =========================================================

def clean(value: Any):
    """
    Convert package objects / generators / dicts / lists
    into JSON-safe Python data.
    """

    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, dict):
        return {
            str(k): clean(v)
            for k, v in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [
            clean(item)
            for item in value
        ]

    if hasattr(value, "__dict__"):
        data = {}

        for key, val in vars(value).items():
            if not key.startswith("_"):
                data[key] = clean(val)

        return data

    return str(value)


# =========================================================
# RESOLVE ASYNC COROUTINE
# =========================================================

async def resolve(value):
    """
    Resolve coroutine/awaitable values.

    Example:
        client.get_video(...)
        client.get_short(...)
    """

    if inspect.isawaitable(value):
        return await value

    return value


# =========================================================
# COLLECT ASYNC GENERATOR / ITERABLE
# =========================================================

async def collect_results(value):
    """
    Supports:

    - async generator
    - async iterable
    - coroutine returning an async generator
    - normal iterable
    - single object
    """

    # First resolve coroutine if necessary
    if inspect.isawaitable(value):
        value = await value

    # Async generator / async iterable
    if hasattr(value, "__aiter__"):
        items = []

        async for item in value:
            items.append(item)

        return items

    # Normal list / tuple / set
    if isinstance(value, (list, tuple, set)):
        return list(value)

    # Do not iterate dictionaries as results
    if isinstance(value, dict):
        return [value]

    # Single object
    return [value]


# =========================================================
# VIDEO NORMALIZER
# =========================================================

def video_to_dict(video):
    """
    Normalize video object into MovieHub format.
    """

    data = clean(video)

    if not isinstance(data, dict):
        return {
            "value": data
        }

    return {
        "id": (
            data.get("id")
            or data.get("video_id")
        ),

        "title": (
            data.get("title")
            or data.get("name")
        ),

        "thumbnail": (
            data.get("thumbnail")
            or data.get("thumb")
            or data.get("image")
            or data.get("poster")
        ),

        "video": (
            data.get("m3u8")
            or data.get("video")
            or data.get("video_url")
            or data.get("url")
        ),

        "description": data.get("description"),

        "duration": data.get("duration"),

        "rating": data.get("rating"),

        "categories": (
            data.get("categories")
            or data.get("category")
        ),

        "tags": data.get("tags"),

        "raw": data
    }


# =========================================================
# HOME
# =========================================================

@app.get("/")
async def home():

    return {
        "name": "MovieHub API",
        "status": "online",
        "version": "1.1.0",
        "docs": "/docs"
    }


# =========================================================
# HEALTH
# =========================================================

@app.get("/api/health")
async def health():

    return {
        "status": "ok",
        "api": "MovieHub API"
    }


# =========================================================
# SEARCH
# =========================================================

@app.get("/api/search")
async def search(
    q: str = Query(..., min_length=1),
    quality: int | None = None,
    sort: str | None = None,
    category: str | None = None,
    vr: bool | None = None,
    full_length: bool | None = None,
    min_duration: int | None = None,
    date: str | None = None,
    production: str | None = None,
    fps: int | None = None,
    pages: int = 1,
):

    try:

        if pages < 1:
            pages = 1

        results = client.search_videos(
            query=q,
            minimum_quality=quality,
            sort_by=sort,
            category=category,
            vr=vr,
            full_length_only=full_length,
            min_duration=min_duration,
            date=date,
            production=production,
            fps=fps,
            pages=pages,
        )

        # IMPORTANT:
        # search_videos() returns an async generator
        videos = await collect_results(results)

        items = [
            video_to_dict(video)
            for video in videos
        ]

        return {
            "success": True,
            "query": q,
            "count": len(items),
            "results": items
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =========================================================
# VIDEO
# =========================================================

@app.get("/api/video")
async def video(
    id: str = Query(...)
):

    try:

        result = client.get_video(id)

        # Handles coroutine if returned
        result = await resolve(result)

        return {
            "success": True,
            "result": video_to_dict(result)
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =========================================================
# SHORT
# =========================================================

@app.get("/api/short")
async def short(
    id: str = Query(...)
):

    try:

        result = client.get_short(id)

        # Handles coroutine / normal result
        result = await resolve(result)

        # If get_short returns an async iterable,
        # collect it safely.
        if hasattr(result, "__aiter__"):

            items = []

            async for item in result:
                items.append(clean(item))

            return {
                "success": True,
                "count": len(items),
                "result": items
            }

        return {
            "success": True,
            "result": clean(result)
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =========================================================
# CHANNEL
# =========================================================

@app.get("/api/channel")
async def channel(
    id: str = Query(...)
):

    try:

        result = client.get_channel(id)

        result = await resolve(result)

        return {
            "success": True,
            "result": clean(result)
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =========================================================
# CREATOR
# =========================================================

@app.get("/api/creator")
async def creator(
    id: str = Query(...)
):

    try:

        result = client.get_creator(id)

        result = await resolve(result)

        return {
            "success": True,
            "result": clean(result)
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =========================================================
# PORNSTAR
# =========================================================

@app.get("/api/pornstar")
async def pornstar(
    id: str = Query(...)
):

    try:

        result = client.get_pornstar(id)

        result = await resolve(result)

        return {
            "success": True,
            "result": clean(result)
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =========================================================
# PROFILE VIDEOS
# =========================================================

@app.get("/api/profile/videos")
async def profile_videos(
    profile: str = Query(...),
    pages: int = 1
):

    try:

        if pages < 1:
            pages = 1

        results = client.search_videos(
            query=profile,
            pages=pages
        )

        # search_videos() is an async generator
        videos = await collect_results(results)

        items = [
            video_to_dict(video)
            for video in videos
        ]

        return {
            "success": True,
            "profile": profile,
            "count": len(items),
            "results": items
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =========================================================
# RENDER START
# =========================================================

if __name__ == "__main__":

    import uvicorn

    port = int(
        os.environ.get("PORT", 8000)
    )

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port
    )
