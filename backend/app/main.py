from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker

from backend.app.api.catalog import router as catalog_router
from backend.app.api.errors import register_error_handlers
from backend.app.config import Settings
from backend.app.infrastructure.database import create_engine_for


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or Settings()
    engine = create_engine_for(app_settings)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        for directory in app_settings.storage_directories:
            directory.mkdir(parents=True, exist_ok=True)
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(lifespan=lifespan)
    app.state.settings = app_settings
    app.state.session_factory = session_factory
    register_error_handlers(app)
    app.include_router(catalog_router)

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ready"}

    return app
