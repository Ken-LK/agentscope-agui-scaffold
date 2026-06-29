"""ASGI entrypoint."""

from app.runtime.factory import create_runtime_app


app = create_runtime_app()
