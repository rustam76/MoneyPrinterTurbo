"""
Controller untuk random video source selection API.

Endpoint ini memungkinkan user untuk mencari dan memilih video secara random
dari multiple providers (Pexels, Pixabay, Coverr).
"""

from typing import List, Optional

from fastapi import Query
from loguru import logger

from app.controllers.v1.base import new_router
from app.models.exception import HttpException
from app.models.schema import MaterialInfo, VideoAspect, BaseResponse
from app.services.random_video_source import (
    search_and_select_random,
    search_and_select_multiple,
)

router = new_router()


class RandomVideoResponse(BaseResponse):
    """Response untuk random video selection."""

    class Config:
        json_schema_extra = {
            "example": {
                "status": 200,
                "message": "success",
                "data": {
                    "provider": "pexels",
                    "url": "https://example.com/video.mp4",
                    "duration": 10,
                    "source_info": {
                        "provider": "pexels",
                        "search_term": "nature",
                        "asset_id": "12345",
                        "creator": {"name": "John Doe"},
                    },
                },
            },
        }


class MultipleRandomVideosResponse(BaseResponse):
    """Response untuk multiple random video selections."""

    class Config:
        json_schema_extra = {
            "example": {
                "status": 200,
                "message": "success",
                "data": {
                    "total": 3,
                    "videos": [
                        {
                            "provider": "pexels",
                            "url": "https://example.com/video1.mp4",
                            "duration": 10,
                        },
                        {
                            "provider": "pixabay",
                            "url": "https://example.com/video2.mp4",
                            "duration": 8,
                        },
                        {
                            "provider": "coverr",
                            "url": "https://example.com/video3.mp4",
                            "duration": 12,
                        },
                    ],
                },
            },
        }


@router.get(
    "/api/v1/random-video/select",
    response_model=RandomVideoResponse,
    summary="Select random video",
    description="Search from multiple providers and select one random video",
    tags=["Random Video"],
)
def get_random_video(
    search_term: str = Query(
        ..., description="Search keyword for video", min_length=1, max_length=100
    ),
    min_duration: int = Query(
        5, description="Minimum video duration in seconds", ge=1, le=300
    ),
    aspect: str = Query(
        "portrait",
        description="Video aspect ratio: portrait, landscape, or square",
        regex="^(portrait|landscape|square)$",
    ),
    providers: Optional[str] = Query(
        None,
        description="Comma-separated list of providers to search (pexels,pixabay,coverr). Default: all",
    ),
):
    """
    Search and select a random video from enabled providers.

    Parameters:
    - search_term: Keyword to search for
    - min_duration: Minimum video duration in seconds
    - aspect: Video aspect ratio (portrait/landscape/square)
    - providers: Comma-separated provider list (optional)

    Returns:
    - Single random MaterialInfo with video details
    """
    try:
        # Parse aspect
        try:
            video_aspect = VideoAspect(aspect)
        except ValueError:
            raise HttpException(
                status_code=400,
                message=f"Invalid aspect ratio: {aspect}. "
                f"Must be one of: portrait, landscape, square",
            )

        # Parse providers
        enabled_providers = None
        if providers:
            enabled_providers = [p.strip() for p in providers.split(",")]
            valid_providers = {"pexels", "pixabay", "coverr"}
            invalid = set(enabled_providers) - valid_providers
            if invalid:
                raise HttpException(
                    status_code=400,
                    message=f"Invalid providers: {', '.join(invalid)}. "
                    f"Valid providers: pexels, pixabay, coverr",
                )

        logger.info(
            f"random video request: term={search_term!r}, aspect={aspect}, "
            f"min_duration={min_duration}, providers={enabled_providers or 'all'}"
        )

        # Search and select
        selected = search_and_select_random(
            search_term=search_term,
            minimum_duration=min_duration,
            video_aspect=video_aspect,
            enabled_providers=enabled_providers,
        )

        if not selected:
            raise HttpException(
                status_code=404,
                message=f"No videos found for search term: {search_term!r}",
            )

        # Convert MaterialInfo to dict for response
        video_data = {
            "provider": selected.provider,
            "url": selected.url,
            "duration": selected.duration,
        }
        if selected.source_info:
            video_data["source_info"] = selected.source_info

        return RandomVideoResponse(data=video_data)

    except HttpException:
        raise
    except Exception as e:
        logger.error(f"random video selection error: {type(e).__name__}: {e}")
        raise HttpException(
            status_code=500,
            message=f"Error selecting random video: {str(e)}",
        )


@router.get(
    "/api/v1/random-video/select-multiple",
    response_model=MultipleRandomVideosResponse,
    summary="Select multiple random videos",
    description="Search from multiple providers and select multiple random videos",
    tags=["Random Video"],
)
def get_multiple_random_videos(
    search_term: str = Query(
        ..., description="Search keyword for video", min_length=1, max_length=100
    ),
    count: int = Query(
        5, description="Number of videos to select", ge=1, le=50
    ),
    min_duration: int = Query(
        5, description="Minimum video duration in seconds", ge=1, le=300
    ),
    aspect: str = Query(
        "portrait",
        description="Video aspect ratio: portrait, landscape, or square",
        regex="^(portrait|landscape|square)$",
    ),
    providers: Optional[str] = Query(
        None,
        description="Comma-separated list of providers to search (pexels,pixabay,coverr). Default: all",
    ),
):
    """
    Search and select multiple random videos from enabled providers.

    Parameters:
    - search_term: Keyword to search for
    - count: Number of videos to select (1-50)
    - min_duration: Minimum video duration in seconds
    - aspect: Video aspect ratio (portrait/landscape/square)
    - providers: Comma-separated provider list (optional)

    Returns:
    - List of MaterialInfo with video details
    """
    try:
        # Parse aspect
        try:
            video_aspect = VideoAspect(aspect)
        except ValueError:
            raise HttpException(
                status_code=400,
                message=f"Invalid aspect ratio: {aspect}. "
                f"Must be one of: portrait, landscape, square",
            )

        # Parse providers
        enabled_providers = None
        if providers:
            enabled_providers = [p.strip() for p in providers.split(",")]
            valid_providers = {"pexels", "pixabay", "coverr"}
            invalid = set(enabled_providers) - valid_providers
            if invalid:
                raise HttpException(
                    status_code=400,
                    message=f"Invalid providers: {', '.join(invalid)}. "
                    f"Valid providers: pexels, pixabay, coverr",
                )

        logger.info(
            f"multiple random video request: term={search_term!r}, count={count}, "
            f"aspect={aspect}, min_duration={min_duration}, "
            f"providers={enabled_providers or 'all'}"
        )

        # Search and select
        selected_videos = search_and_select_multiple(
            search_term=search_term,
            count=count,
            minimum_duration=min_duration,
            video_aspect=video_aspect,
            enabled_providers=enabled_providers,
        )

        if not selected_videos:
            raise HttpException(
                status_code=404,
                message=f"No videos found for search term: {search_term!r}",
            )

        # Convert to list of dicts for response
        videos_data = []
        for video in selected_videos:
            video_dict = {
                "provider": video.provider,
                "url": video.url,
                "duration": video.duration,
            }
            if video.source_info:
                video_dict["source_info"] = video.source_info
            videos_data.append(video_dict)

        return MultipleRandomVideosResponse(
            data={
                "total": len(videos_data),
                "videos": videos_data,
            }
        )

    except HttpException:
        raise
    except Exception as e:
        logger.error(f"multiple random video selection error: {type(e).__name__}: {e}")
        raise HttpException(
            status_code=500,
            message=f"Error selecting random videos: {str(e)}",
        )
