import os
import inspect
import asyncio
import logging
import time
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from xhamster_api import Client


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("moviehub-api")


# =========================================================
# CONFIG
# =========================================================

UPSTREAM_TIMEOUT = float(
    os.environ.get("UPSTREAM_TIMEOUT", "30")
)


# =========================================================
# APP
# =========================================================

app = FastAPI(
    title="MovieHub API",
    description="MovieHub REST API",
    version="1.2.0"
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

    if isinstance(
        value,
        (str, int, float, bool)
    ):
        return value

    if isinstance(value, dict):

        return {
            str(k): clean(v)
            for k, v in value.items()
        }

    if isinstance(
        value,
        (list, tuple, set)
    ):

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
# HELPER: COLLECT RESULTS
# =========================================================

async def collect_results(value):

    value = await resolve(value)

    # Async generator / async iterable
    if hasattr(value, "__aiter__"):

        items = []

        async for item in value:
            items.append(item)

        return items

    # List / Tuple / Set
    if isinstance(
        value,
        (list, tuple, set)
    ):

        return list(value)

    # Dictionary
    if isinstance(value, dict):
        return [value]

    # None
    if value is None:
        return []

    # Single object
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
        "m3u8",
        "m3u8_base_url"
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

    # Keep existing behavior for normal API
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

        "video_url": clean(
            final_video_url
        ),

        "video": clean(
            final_video_url
        ),

        "url": clean(url),

        "preview_video": clean(
            preview_video
        ),

        "duration": clean(
            duration
        ),

        "rating": clean(
            rating
        ),

        "categories": clean(
            categories
        ),

        "tags": clean(
            tags
        )
    }


# =========================================================
# HELPER: SAFE CLIENT CALL
# =========================================================

async def safe_client_call(
    method_name: str,
    *args,
    **kwargs
):

    """
    Supports both synchronous and
    asynchronous client methods.

    Both positional and keyword arguments
    are supported.
    """

    method = getattr(
        client,
        method_name,
        None
    )

    if method is None:

        raise RuntimeError(
            f"Client method '{method_name}' "
            f"is not available"
        )

    try:

        # -----------------------------------------
        # Native async method
        # -----------------------------------------

        if inspect.iscoroutinefunction(
            method
        ):

            return await asyncio.wait_for(

                method(
                    *args,
                    **kwargs
                ),

                timeout=UPSTREAM_TIMEOUT
            )

        # -----------------------------------------
        # Sync method
        # Run inside worker thread
        # -----------------------------------------

        result = await asyncio.wait_for(

            asyncio.to_thread(
                method,
                *args,
                **kwargs
            ),

            timeout=UPSTREAM_TIMEOUT
        )

        # -----------------------------------------
        # Some libraries return awaitable
        # -----------------------------------------

        if inspect.isawaitable(
            result
        ):

            result = await asyncio.wait_for(

                result,

                timeout=UPSTREAM_TIMEOUT
            )

        return result

    except asyncio.TimeoutError:

        logger.warning(
            "Upstream timeout: %s args=%s kwargs=%s",
            method_name,
            args,
            kwargs
        )

        raise

    except Exception:

        logger.exception(
            "Upstream client error: %s",
            method_name
        )

        raise


# =========================================================
# ROOT
# =========================================================

@app.get("/")
async def root():

    return {

        "name": "MovieHub API",

        "status": "online",

        "version": "1.2.0",

        "docs": "/docs"
    }


# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
async def health():

    return {

        "status": "ok",

        "api": "MovieHub API",

        "upstream_timeout":
            UPSTREAM_TIMEOUT
    }


# =========================================================
# API INFO
# =========================================================

@app.get("/api")
async def api_info():

    return {

        "name":
            "MovieHub API",

        "version":
            "1.2.0",

        "upstream_timeout":
            UPSTREAM_TIMEOUT,

        "endpoints": {

            "search":
                "/api/search?q=test",

            "video":
                "/api/video?id=VIDEO_ID",

            "video_debug":
                "/api/video-debug?id=VIDEO_ID",

            "short":
                "/api/short?id=SHORT_ID",

            "channel":
                "/api/channel?id=CHANNEL_ID",

            "creator":
                "/api/creator?id=CREATOR_ID",

            "pornstar":
                "/api/pornstar?id=PROFILE_ID",

            "profile_videos":
                "/api/profile/videos?query=test"
        }
    }


# =========================================================
# SEARCH
# =========================================================

@app.get("/api/search")
async def search(

    q: str = Query(
        ...,
        min_length=1
    ),

    page: int = Query(
        1,
        ge=1
    )
):

    try:

        logger.info(
            "SEARCH q=%s page=%s",
            q,
            page
        )

        results = await safe_client_call(

            "search_videos",

            query=q,

            pages=page
        )

        videos = await asyncio.wait_for(

            collect_results(
                results
            ),

            timeout=UPSTREAM_TIMEOUT
        )

        output = []

        for result in videos:

            try:

                output.append(
                    video_to_dict(
                        result
                    )
                )

            except Exception as e:

                logger.exception(
                    "Failed to convert search result"
                )

                output.append({

                    "error":
                        str(e)
                })

        return {

            "success":
                True,

            "query":
                q,

            "page":
                page,

            "count":
                len(output),

            "results":
                output
        }

    except asyncio.TimeoutError:

        raise HTTPException(

            status_code=504,

            detail:
                "Upstream search request timed out"
        )

    except HTTPException:

        raise

    except Exception as e:

        raise HTTPException(

            status_code=502,

            detail:
                f"Upstream search request failed: {str(e)}"
        )


# =========================================================
# VIDEO
# =========================================================

@app.get("/api/video")
async def video(

    id: str = Query(
        ...,
        min_length=1
    )
):

    try:

        logger.info(
            "VIDEO REQUEST id=%s",
            id
        )

        result = await safe_client_call(

            "get_video",

            id
        )

        result = await asyncio.wait_for(

            resolve(
                result
            ),

            timeout=UPSTREAM_TIMEOUT
        )

        if result is None:

            raise HTTPException(

                status_code=404,

                detail:
                    "Video not found"
            )

        data = video_to_dict(
            result
        )

        return {

            "success":
                True,

            "result":
                data
        }

    except asyncio.TimeoutError:

        raise HTTPException(

            status_code=504,

            detail:
                "Upstream video source timed out"
        )

    except HTTPException:

        raise

    except Exception as e:

        raise HTTPException(

            status_code=502,

            detail:
                f"Upstream video request failed: {str(e)}"
        )


# =========================================================
# VIDEO DEBUG
# =========================================================

@app.get("/api/video-debug")
async def video_debug(

    id: str = Query(
        ...,
        min_length=1
    )
):

    """
    Diagnostic endpoint.

    This does NOT use video_to_dict()
    for the main inspection.

    It shows what get_video() actually
    returns and which fields are available.
    """

    started = time.monotonic()

    logger.info(
        "DEBUG VIDEO START id=%s",
        id
    )

    try:

        # -----------------------------------------
        # Check client method
        # -----------------------------------------

        method = getattr(
            client,
            "get_video",
            None
        )

        if method is None:

            return {

                "success":
                    False,

                "stage":
                    "client_method",

                "id":
                    id,

                "error":
                    "Client method get_video() not found"
            }

        logger.info(
            "DEBUG get_video method found"
        )

        # -----------------------------------------
        # Call get_video()
        # -----------------------------------------

        if inspect.iscoroutinefunction(
            method
        ):

            result = await asyncio.wait_for(

                method(id),

                timeout=UPSTREAM_TIMEOUT
            )

        else:

            result = await asyncio.wait_for(

                asyncio.to_thread(
                    method,
                    id
                ),

                timeout=UPSTREAM_TIMEOUT
            )

        # -----------------------------------------
        # Resolve awaitable
        # -----------------------------------------

        if inspect.isawaitable(
            result
        ):

            result = await asyncio.wait_for(

                result,

                timeout=UPSTREAM_TIMEOUT
            )

        elapsed = round(

            time.monotonic()
            - started,

            3
        )

        # -----------------------------------------
        # Nothing returned
        # -----------------------------------------

        if result is None:

            return {

                "success":
                    False,

                "stage":
                    "upstream_result",

                "id":
                    id,

                "elapsed_seconds":
                    elapsed,

                "message":
                    "get_video() returned None"
            }

        # -----------------------------------------
        # Extract actual item
        # -----------------------------------------

        inspected = extract_item(
            result
        )

        # -----------------------------------------
        # Result type
        # -----------------------------------------

        result_type = type(
            inspected
        ).__name__

        # -----------------------------------------
        # Get all public attributes
        # -----------------------------------------

        attributes = {}

        try:

            if isinstance(
                inspected,
                dict
            ):

                for key, value in inspected.items():

                    attributes[
                        str(key)
                    ] = clean(value)

            else:

                for name in dir(
                    inspected
                ):

                    if name.startswith("_"):
                        continue

                    try:

                        value = getattr(
                            inspected,
                            name
                        )

                        if callable(
                            value
                        ):
                            continue

                        attributes[
                            name
                        ] = clean(value)

                    except Exception:

                        continue

        except Exception as e:

            attributes = {

                "inspection_error":
                    str(e)
            }

        # -----------------------------------------
        # Read important fields
        # -----------------------------------------

        def read_field(name):

            try:

                if isinstance(
                    inspected,
                    dict
                ):

                    return inspected.get(
                        name
                    )

                return getattr(
                    inspected,
                    name,
                    None
                )

            except Exception:

                return None

        field_names = [

            "id",

            "video_id",

            "title",

            "url",

            "video",

            "video_url",

            "stream_url",

            "stream",

            "play_url",

            "download_url",

            "m3u8",

            "m3u8_base_url",

            "preview_video",

            "duration",

            "thumbnail",

            "description"
        ]

        stream_fields = {}

        for name in field_names:

            value = read_field(
                name
            )

            if value is not None:

                stream_fields[
                    name
                ] = clean(value)

        # -----------------------------------------
        # Determine likely stream fields
        # -----------------------------------------

        possible_streams = {}

        for name in [

            "video",

            "video_url",

            "stream_url",

            "stream",

            "play_url",

            "download_url",

            "m3u8",

            "m3u8_base_url",

            "url",

            "preview_video"

        ]:

            value = read_field(
                name
            )

            if value:

                possible_streams[
                    name
                ] = clean(value)

        # -----------------------------------------
        # Final debug response
        # -----------------------------------------

        return {

            "success":
                True,

            "stage":
                "complete",

            "id":
                id,

            "elapsed_seconds":
                elapsed,

            "result_type":
                result_type,

            "stream_fields":
                stream_fields,

            "possible_streams":
                possible_streams,

            "available_fields":
                list(
                    attributes.keys()
                ),

            "raw":
                attributes
        }

    except asyncio.TimeoutError:

        elapsed = round(

            time.monotonic()
            - started,

            3
        )

        logger.warning(

            "DEBUG VIDEO TIMEOUT "
            "id=%s after=%s",

            id,

            elapsed
        )

        return {

            "success":
                False,

            "stage":
                "upstream_timeout",

            "id":
                id,

            "elapsed_seconds":
                elapsed,

            "timeout_seconds":
                UPSTREAM_TIMEOUT,

            "message":
                "get_video() did not return before timeout"
        }

    except Exception as e:

        elapsed = round(

            time.monotonic()
            - started,

            3
        )

        logger.exception(

            "DEBUG VIDEO ERROR id=%s",

            id
        )

        return {

            "success":
                False,

            "stage":
                "exception",

            "id":
                id,

            "elapsed_seconds":
                elapsed,

            "error_type":
                type(e).__name__,

            "error":
                str(e)
        }


# =========================================================
# SHORT
# =========================================================

@app.get("/api/short")
async def short(

    id: str = Query(
        ...,
        min_length=1
    )
):

    try:

        result = await safe_client_call(

            "get_short",

            id
        )

        result = await asyncio.wait_for(

            resolve(
                result
            ),

            timeout=UPSTREAM_TIMEOUT
        )

        if result is None:

            raise HTTPException(

                status_code=404,

                detail:
                    "Short video not found"
            )

        data = video_to_dict(
            result
        )

        return {

            "success":
                True,

            "result":
                data
        }

    except asyncio.TimeoutError:

        raise HTTPException(

            status_code=504,

            detail:
                "Upstream short-video request timed out"
        )

    except HTTPException:

        raise

    except Exception as e:

        raise HTTPException(

            status_code=502,

            detail:
                f"Upstream short-video request failed: {str(e)}"
        )


# =========================================================
# CHANNEL
# =========================================================

@app.get("/api/channel")
async def channel(

    id: str = Query(
        ...,
        min_length=1
    )
):

    try:

        result = await safe_client_call(

            "get_channel",

            id
        )

        result = await asyncio.wait_for(

            resolve(
                result
            ),

            timeout=UPSTREAM_TIMEOUT
        )

        if result is None:

            raise HTTPException(

                status_code=404,

                detail:
                    "Channel not found"
            )

        return {

            "success":
                True,

            "result":
                clean(result)
        }

    except asyncio.TimeoutError:

        raise HTTPException(

            status_code=504,

            detail:
                "Upstream channel request timed out"
        )

    except HTTPException:

        raise

    except Exception as e:

        raise HTTPException(

            status_code=502,

            detail:
                f"Upstream channel request failed: {str(e)}"
        )


# =========================================================
# CREATOR
# =========================================================

@app.get("/api/creator")
async def creator(

    id: str = Query(
        ...,
        min_length=1
    )
):

    try:

        result = await safe_client_call(

            "get_creator",

            id
        )

        result = await asyncio.wait_for(

            resolve(
                result
            ),

            timeout=UPSTREAM_TIMEOUT
        )

        if result is None:

            raise HTTPException(

                status_code=404,

                detail:
                    "Creator not found"
            )

        return {

            "success":
                True,

            "result":
                clean(result)
        }

    except asyncio.TimeoutError:

        raise HTTPException(

            status_code=504,

            detail:
                "Upstream creator request timed out"
        )

    except HTTPException:

        raise

    except Exception as e:

        raise HTTPException(

            status_code=502,

            detail:
                f"Upstream creator request failed: {str(e)}"
        )


# =========================================================
# PORNSTAR / PROFILE
# =========================================================

@app.get("/api/pornstar")
async def pornstar(

    id: str = Query(
        ...,
        min_length=1
    )
):

    try:

        result = await safe_client_call(

            "get_pornstar",

            id
        )

        result = await asyncio.wait_for(

            resolve(
                result
            ),

            timeout=UPSTREAM_TIMEOUT
        )

        if result is None:

            raise HTTPException(

                status_code=404,

                detail:
                    "Profile not found"
            )

        return {

            "success":
                True,

            "result":
                clean(result)
        }

    except asyncio.TimeoutError:

        raise HTTPException(

            status_code=504,

            detail:
                "Upstream profile request timed out"
        )

    except HTTPException:

        raise

    except Exception as e:

        raise HTTPException(

            status_code=502,

            detail:
                f"Upstream profile request failed: {str(e)}"
        )


# =========================================================
# PROFILE VIDEOS
# =========================================================

@app.get("/api/profile/videos")
async def profile_videos(

    query: str = Query(
        ...,
        min_length=1
    ),

    page: int = Query(
        1,
        ge=1
    )
):

    try:

        results = await safe_client_call(

            "search_videos",

            query=query,

            pages=page
        )

        videos = await asyncio.wait_for(

            collect_results(
                results
            ),

            timeout=UPSTREAM_TIMEOUT
        )

        output = []

        for result in videos:

            try:

                output.append(
                    video_to_dict(
                        result
                    )
                )

            except Exception as e:

                logger.exception(
                    "Failed to convert profile video"
                )

                output.append({

                    "error":
                        str(e)
                })

        return {

            "success":
                True,

            "query":
                query,

            "page":
                page,

            "count":
                len(output),

            "results":
                output
        }

    except asyncio.TimeoutError:

        raise HTTPException(

            status_code=504,

            detail:
                "Upstream profile-video request timed out"
        )

    except HTTPException:

        raise

    except Exception as e:

        raise HTTPException(

            status_code=502,

            detail:
                f"Upstream profile-video request failed: {str(e)}"
        )


# =========================================================
# RUN SERVER
# =========================================================

if __name__ == "__main__":

    import uvicorn

    port = int(
        os.environ.get(
            "PORT",
            8000
        )
    )

    uvicorn.run(

        app,

        host="0.0.0.0",

        port=port
    )
