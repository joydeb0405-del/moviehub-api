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
    description="MovieHub REST API",
    version="1.0.0"
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# CLIENT
# =========================================================

client = Client()


# =========================================================
# HELPER: GET ATTRIBUTE
# =========================================================

def get_attr(obj: Any, *names):
    if obj is None:
        return None

    for name in names:
        try:
            if isinstance(obj, dict):
                value = obj.get(name)
            else:
                value = getattr(obj, name, None)

            if value is not None:
                return value

        except Exception:
            continue

    return None


# =========================================================
# HELPER: CLEAN JSON
# =========================================================

def clean(value: Any):

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
            clean(v)
            for v in value
        ]

    try:
        if hasattr(value, "isoformat"):
            return value.isoformat()
    except Exception:
        pass

    return str(value)


# =========================================================
# HELPER: RESOLVE COROUTINE
# =========================================================

async def resolve(value):

    if inspect.isawaitable(value):
        return await value

    return value


# =========================================================
# HELPER: COLLECT ASYNC RESULTS
# =========================================================

async def collect_results(value):

    value = await resolve(value)

    # Async generator / async iterable
    if hasattr(value, "__aiter__"):

        items = []

        async for item in value:
            items.append(item)

        return items

    # List / tuple / set
    if isinstance(value, (list, tuple, set)):
        return list(value)

    # Dictionary
    if isinstance(value, dict):
        return [value]

    # Single object
    if value is None:
        return []

    return [value]


# =========================================================
# HELPER: EXTRACT ScrapeResult.item
# =========================================================

def extract_item(value):

    item = get_attr(
        value,
        "item"
    )

    if item is not None:
        return item

    return value


# =========================================================
# VIDEO CONVERTER
# =========================================================

def video_to_dict(video):

    # ScrapeResult -> Video
    video = extract_item(video)

    video_id = get_attr(
        video,
        "id",
        "video_id"
    )

    title = get_attr(
        video,
        "title",
        "name"
    )

    url = get_attr(
        video,
        "url",
        "video_url"
    )

    thumbnail = get_attr(
        video,
        "thumbnail",
        "thumb",
        "image",
        "poster"
    )

    preview_video = get_attr(
        video,
        "preview_video"
    )

    description = get_attr(
        video,
        "description"
    )

    duration = get_attr(
        video,
        "duration"
    )

    rating = get_attr(
        video,
        "rating"
    )

    categories = get_attr(
        video,
        "categories",
        "category"
    )

    tags = get_attr(
        video,
        "tags"
    )

    m3u8 = get_attr(
        video,
        "m3u8"
    )

    stream_url = get_attr(
        video,
        "video",
        "video_url",
        "stream_url",
        "stream",
        "play_url",
        "download_url"
    )

    # Priority:
    # actual stream > m3u8 > preview > source URL
    final_video_url = (
        stream_url
        or m3u8
        or preview_video
        or url
    )

    return {
        "id": clean(video_id),

        "title": clean(title),

        "description": clean(description),

        "poster": clean(thumbnail),

        "thumbnail": clean(thumbnail),

        "video_url": clean(final_video_url),

        "video": clean(final_video_url),

        "url": clean(url),

        "preview_video": clean(preview_video),

        "duration": clean(duration),

        "rating": clean(rating),

        "categories": clean(categories),

        "tags": clean(tags)
    }


# =========================================================
# ROOT
# =========================================================

@app.get("/")
async def root():

    return {
        "name": "MovieHub API",
        "status": "online",
        "version": "1.0.0",
        "docs": "/docs"
    }


# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
async def health():

    return {
        "status": "ok",
        "api": "MovieHub API"
    }


# =========================================================
# API INFO
# =========================================================

@app.get("/api")
async def api_info():

    return {
        "name": "MovieHub API",
        "version": "1.0.0",

        "endpoints": {
            "search": "/api/search?q=test",
            "video": "/api/video?id=VIDEO_ID",
            "short": "/api/short?id=SHORT_ID",
            "channel": "/api/channel?id=CHANNEL_ID",
            "creator": "/api/creator?id=CREATOR_ID",
            "pornstar": "/api/pornstar?id=PROFILE_ID",
            "profile_videos": "/api/profile/videos?query=test"
        }
    }


# =========================================================
# SEARCH
# =========================================================

@app.get("/api/search")
async def search(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1)
):

    try:

        # IMPORTANT:
        # xhamster_api uses "pages", not "page"
        results = client.search_videos(
            query=q,
            pages=page
        )

        videos = await collect_results(results)

        output = []

        for result in videos:

            try:

                output.append(
                    video_to_dict(result)
                )

            except Exception as e:

                output.append({
                    "error": str(e)
                })

        return {
            "success": True,
            "query": q,
            "page": page,
            "count": len(output),
            "results": output
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

        result = await resolve(result)

        if result is None:

            raise HTTPException(
                status_code=404,
                detail="Video not found"
            )

        data = video_to_dict(result)

        return {
            "success": True,
            "result": data
        }

    except HTTPException:
        raise

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

        result = await resolve(result)

        if result is None:

            raise HTTPException(
                status_code=404,
                detail="Short video not found"
            )

        data = video_to_dict(result)

        return {
            "success": True,
            "result": data
        }

    except HTTPException:
        raise

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

        if result is None:

            raise HTTPException(
                status_code=404,
                detail="Channel not found"
            )

        return {
            "success": True,
            "result": clean(result)
        }

    except HTTPException:
        raise

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

        if result is None:

            raise HTTPException(
                status_code=404,
                detail="Creator not found"
            )

        return {
            "success": True,
