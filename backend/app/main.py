from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        for directory in app_settings.storage_directories:
            directory.mkdir(parents=True, exist_ok=True)
        yield

    app = FastAPI(lifespan=lifespan)
    app.state.settings = app_settings

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ready"}

    return app
