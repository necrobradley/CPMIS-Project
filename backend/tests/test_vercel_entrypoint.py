from fastapi import FastAPI

from index import app


def test_vercel_entrypoint_exports_fastapi_application():
    assert isinstance(app, FastAPI)
    assert any(getattr(route, "path", None) == "/health" for route in app.routes)
