"""Application configuration - root APIRouter.

Defines all FastAPI application endpoints.

Resources:
    1. https://fastapi.tiangolo.com/tutorial/bigger-applications

"""

from fastapi import APIRouter

from app.controllers.v1 import auth, llm, users, video, random_video

root_api_router = APIRouter()
# Auth (optional; gated by MPT_AUTH_ENABLED)
root_api_router.include_router(auth.router)
root_api_router.include_router(users.router)
# v1
root_api_router.include_router(video.router)
root_api_router.include_router(random_video.router)
root_api_router.include_router(llm.router)
