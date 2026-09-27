import os
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from xhamster_api import Client


app = FastAPI(
    title="MovieHub API",
    description="MovieHub API wrapper",
    version="1.0.0"
)

# =========================
# CORS
# =========================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# Client
# =========================

client = Client()


# =========================
# Helpers
# =========================

def clean(value: Any):
    """
    Convert package objects into JSON-safe data.
    """

    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, list):
        return [clean(x) for x in value]

    if isinstance(value, tuple):
        return [clean(x) for x in value]

    if isinstance(value, dict):
        return {
            str(k): clean(v)
            for k, v in value.items()
        }

    if hasattr(value, "__dict__"):
        data = {}

        for key, val in vars(value).items():
            if not key.startswith("_"):
                data[key] = clean(val)

        return data

    return str(value)


def video_to_dict(video):
    """
    Normalize video object for MovieHub.
    """

    data = clean(video)

    if not isinstance(data, dict):
        return {
            "value": data
        }

    return {
        "id": data.get("id"),
        "title": data.get("title"),
        "thumbnail": (
            data.get("thumbnail")
            or data.get("thumb")
            or data.get("image")
        ),
        "video": (
            data.get("m3u8")
            or data.get("video")
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


# =========================
# Home
# =========================

@app.get("/")
def home():
    return {
        "name": "MovieHub API",
        "status": "online",
        "version": "1.0.0",
        "docs": "/docs"
    }


# =========================
# Health
# =========================

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "api": "MovieHub API"
    }


# =========================
# Search
# =========================

@app.get("/api/search")
def search(
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

        items = []

        for video in results:
            items.append(video_to_dict(video))

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


# =========================
# Video
# =========================

@app.get("/api/video")
def video(
    id: str = Query(...)
):
    try:

        result = client.get_video(id)

        return {
            "success": True,
            "result": video_to_dict(result)
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =========================
# Short
# =========================

@app.get("/api/short")
def short(
    id: str = Query(...)
):
    try:

        result = client.get_short(id)

        return {
            "success": True,
            "result": clean(result)
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =========================
# Channel
# =========================

@app.get("/api/channel")
def channel(
    id: str = Query(...)
):
    try:

        result = client.get_channel(id)

        return {
            "success": True,
            "result": clean(result)
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =========================
# Creator
# =========================

@app.get("/api/creator")
def creator(
    id: str = Query(...)
):
    try:

        result = client.get_creator(id)

        return {
            "success": True,
            "result": clean(result)
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =========================
# Pornstar
# =========================

@app.get("/api/pornstar")
def pornstar(
    id: str = Query(...)
):
    try:

        result = client.get_pornstar(id)

        return {
            "success": True,
            "result": clean(result)
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =========================
# Profile Videos
# =========================

@app.get("/api/profile/videos")
def profile_videos(
    profile: str = Query(...),
    pages: int = 1
):
    try:

        results = client.search_videos(
            query=profile,
            pages=pages
        )

        items = [
            video_to_dict(video)
            for video in results
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


# =========================
# Render Start
# =========================

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
