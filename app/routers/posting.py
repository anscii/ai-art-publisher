# Series-level posting endpoints removed. Use /api/posts/{id}/post instead.
# Posting logic now lives in app/routers/posts.py.
from fastapi import APIRouter

router = APIRouter(prefix="/api/series", tags=["posting"])
