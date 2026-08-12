"""Vercel FastAPI entrypoint.

Vercel discovers an ASGI application named ``app`` from this recognized root
module. Local development continues to use ``app.main:app`` with Uvicorn.
"""

from app.main import app

__all__ = ["app"]
