from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from xhamster_api import Client


APP_VERSION = "1.0.0"

app = FastAPI(
    title="MovieHub xHamster API",
    description="FastAPI bridge for the xhamster_api package.",
    version=APP_VERSION,
)

# ---------------------------------------------------------
# CORS
# ---------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# Global Client
# ---------------------------------------------------------

client: Client | None = None


@app.on_event("startup")
async def startup() -> None:
    global client
    client = Client()


@app.on_event("shutdown")
async def shutdown() -> None:
    global client
    client = None


def get_client() -> Client:
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="API client is not initialized",
        )

    return client


# ---------------------------------------------------------
# Safe JSON conversion
# ---------------------------------------------------------

def clean(value: Any) -> Any:

    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, list):
        return [clean(item) for item in value]

    if isinstance(value, tuple):
        return [clean(item) for item in value]

    if isinstance(value, dict):
        return {
            str(key): clean(val)
            for key, val in value.items()
        }

    return str(value)


# ---------------------------------------------------------
# Video serializer
# ---------------------------------------------------------

def video_to_dict(video: Any) -> dict[str, Any]:

    return {
        "id": clean(
            getattr(video, "video_id", None)
        ),

        "video_id": clean(
            getattr(video, "video_id", None)
        ),

        "title": clean(
            getattr(video, "title", None)
        ),

        "url": clean(
            getattr(video, "url", None)
        ),

        "thumbnail": clean(
            getattr(video, "thumbnail", None)
        ),

        "preview_thumbnail": clean(
            getattr(video, "preview_thumbnail", None)
        ),

        "preview_video": clean(
            getattr(video, "preview_video", None)
        ),

        "video": clean(
            getattr(video, "m3u8_base_url", None)
        ),

        "m3u8": clean(
            getattr(video, "m3u8_base_url", None)
        ),

        "description": clean(
            getattr(video, "description", None)
        ),

        "duration": clean(
            getattr(video, "duration", None)
        ),

        "views": clean(
            getattr(video, "views", None)
        ),

        "comments": clean(
            getattr(video, "comments_count", None)
        ),

        "rating": clean(
            getattr(video, "rating_percentage", None)
        ),

        "likes": clean(
            getattr(video, "likes", None)
        ),

        "dislikes": clean(
            getattr(video, "dislikes", None)
        ),

        "uploader": clean(
            getattr(video, "uploader_name", None)
        ),

        "tags": clean(
            getattr(video, "tags", None)
        ),

        "genre": clean(
            getattr(video, "tags", None)
        ),

        "categories": clean(
            getattr(video, "categories", None)
        ),

        "pornstars": clean(
            getattr(video, "pornstars", None)
        ),

        "created_at": clean(
            getattr(video, "created_timestamp", None)
        ),

        "date_ago": clean(
            getattr(video, "date_ago", None)
        ),

        "is_vr": clean(
            getattr(video, "is_vr", None)
        ),

        "is_hd": clean(
            getattr(video, "is_hd", None)
        ),

        "max_resolution": clean(
            getattr(video, "max_resolution", None)
        ),

        "orientation": clean(
            getattr(video, "orientation", None)
        ),
    }


# ---------------------------------------------------------
# Short serializer
# ---------------------------------------------------------

def short_to_dict(short: Any) -> dict[str, Any]:

    return {
        "id": clean(
            getattr(short, "video_id", None)
        ),

        "video_id": clean(
            getattr(short, "video_id", None)
        ),

        "title": clean(
            getattr(short, "title", None)
        ),

        "url": clean(
            getattr(short, "url", None)
        ),

        "thumbnail": clean(
            getattr(short, "thumbnail", None)
        ),

        "preview_video": clean(
            getattr(short, "preview_video", None)
        ),

        "video": clean(
            getattr(short, "m3u8_base_url", None)
        ),

        "m3u8": clean(
            getattr(short, "m3u8_base_url", None)
        ),

        "duration": clean(
            getattr(short, "duration", None)
        ),

        "views": clean(
            getattr(short, "views", None)
        ),

        "likes": clean(
            getattr(short, "likes", None)
        ),

        "author": clean(
            getattr(short, "author", None)
        ),

        "author_link": clean(
            getattr(short, "author_link", None)
        ),

        "author_logo": clean(
            getattr(short, "author_logo", None)
        ),

        "tags": clean(
            getattr(short, "tags", None)
        ),
    }


# ---------------------------------------------------------
# Collect async results
# ---------------------------------------------------------

async def collect_stream(
    stream: Any,
    limit: int,
) -> tuple[list[dict[str, Any]], list[str]]:

    items: list[dict[str, Any]] = []
    errors: list[str] = []

    try:

        async for result in stream:

            if len(items) >= limit:
                break

            try:

                item = result.unwrap()

                if hasattr(item, "video_id"):

                    items.append(
                        video_to_dict(item)
                    )

                else:

                    items.append(
                        clean(item)
                    )

            except Exception as exc:

                errors.append(str(exc))

    finally:

        close_method = getattr(
            stream,
            "aclose",
            None,
        )

        if close_method:

            try:
                await close_method()
            except Exception:
                pass

    return items, errors


# ---------------------------------------------------------
# Root
# ---------------------------------------------------------

@app.get("/")
async def root():

    return {
        "success": True,
        "name": "MovieHub xHamster API",
        "version": APP_VERSION,
        "status": "online",
        "health": "/api/health",
        "docs": "/docs",
    }


# ---------------------------------------------------------
# Health
# ---------------------------------------------------------

@app.get("/api/health")
async def health():

    return {
        "success": True,
        "status": "ok",
        "client_initialized": client is not None,
    }


# ---------------------------------------------------------
# Search
# ---------------------------------------------------------

@app.get("/api/search")
async def search(
    q: str = Query(
        ...,
        min_length=1,
        description="Search query",
    ),

    pages: int = Query(
        1,
        ge=1,
        le=10,
    ),

    limit: int = Query(
        20,
        ge=1,
        le=100,
    ),

    quality: str = Query(
        "720p",
    ),

    sort: str | None = Query(
        None,
    ),

    category: str | None = Query(
        None,
    ),

    vr: bool = Query(
        False,
    ),

    full_length: bool = Query(
        False,
    ),

    min_duration: str | None = Query(
        None,
    ),

    date: str | None = Query(
        None,
    ),

    production: str | None = Query(
        None,
    ),

    fps: str | None = Query(
        None,
    ),
):

    api = get_client()

    try:

        stream = api.search_videos(
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

        results, errors = await collect_stream(
            stream,
            limit,
        )

        return {
            "success": True,
            "query": q,
            "count": len(results),
            "results": results,
            "errors": errors,
        }

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------
# Video
# ---------------------------------------------------------

@app.get("/api/video")
async def video(
    url: str = Query(
        ...,
        description="Full video URL",
    ),
):

    api = get_client()

    try:

        item = await api.get_video(
            url,
            load_html=True,
        )

        return {
            "success": True,
            "result": video_to_dict(item),
        }

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------
# Short
# ---------------------------------------------------------

@app.get("/api/short")
async def short(
    url: str = Query(
        ...,
        description="Full short URL",
    ),
):

    api = get_client()

    try:

        item = await api.get_short(
            url,
            load_html=True,
        )

        return {
            "success": True,
            "result": short_to_dict(item),
        }

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------
# Channel
# ---------------------------------------------------------

@app.get("/api/channel")
async def channel(
    url: str = Query(...),
):

    api = get_client()

    try:

        item = await api.get_channel(
            url,
            load_html=True,
        )

        return {
            "success": True,
            "result": clean(item),
        }

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------
# Creator
# ---------------------------------------------------------

@app.get("/api/creator")
async def creator(
    url: str = Query(...),
):

    api = get_client()

    try:

        item = await api.get_creator(
            url,
            load_html=True,
        )

        return {
            "success": True,
            "result": clean(item),
        }

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------
# Pornstar
# ---------------------------------------------------------

@app.get("/api/pornstar")
async def pornstar(
    url: str = Query(...),
):

    api = get_client()

    try:

        item = await api.get_pornstar(
            url,
            load_html=True,
        )

        return {
            "success": True,
            "result": clean(item),
        }

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------
# Profile videos
# ---------------------------------------------------------

@app.get("/api/profile/videos")
async def profile_videos(
    url: str = Query(...),

    pages: int = Query(
        1,
        ge=1,
        le=10,
    ),

    limit: int = Query(
        20,
        ge=1,
        le=100,
    ),
):

    api = get_client()

    try:

        if "/channels/" in url:

            profile = await api.get_channel(
                url,
                load_html=True,
            )

        elif "/pornstars/" in url:

            profile = await api.get_pornstar(
                url,
                load_html=True,
            )

        else:

            profile = await api.get_creator(
                url,
                load_html=True,
            )

        videos = profile.videos(
            pages=pages,
        )

        results, errors = await collect_stream(
            videos,
            limit,
        )

        return {
            "success": True,
            "count": len(results),
            "results": results,
            "errors": errors,
        }

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------
# Run locally
# ---------------------------------------------------------

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(
            os.getenv(
                "PORT",
                "8000",
            )
        ),
        reload=False,
)
